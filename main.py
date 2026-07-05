"""
Platforma — asosiy server (FastAPI).

Bu bosqichda (B bo'lim, poydevor):
  * Telegram initData tekshiruvi (har bir so'rov imzosi)
  * Ro'yxatdan o'tish: forma -> Telegramga 6 xonali kod -> tasdiqlash -> akkaunt
  * Kirish: login + parol -> Telegramga kod -> tasdiqlash -> shu Telegramga bog'lanadi
  * Parollar shifrlangan (PBKDF2) saqlanadi — ochiq holda hech qayerda turmaydi
  * /api/me — joriy foydalanuvchi
  * /api/catalog — 20 yo'nalish
  * Bot webhook: /start -> ilovani ochish tugmasi

Environment variables:
  BOT_TOKEN, BASE_URL, DB_PATH, WEBHOOK_SECRET
  UPLOAD_DIR=/data/uploads  -> Railway Volume uchun doimiy rasm papkasi
  TEST_MODE=1  -> sinov rejimi (kod Telegramga emas, xotirada qoladi — faqat test uchun)
"""

import os
import json
import time
import hmac
import secrets
import hashlib
from urllib.parse import parse_qsl
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from database import db, init_db, DB_PATH
from catalog_data import CATALOG, LISTING_CATS

# ---------- Sozlamalar ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "platforma-webhook-secret")
TEST_MODE = os.environ.get("TEST_MODE", "") == "1"
TG_API = "https://api.telegram.org/bot" + BOT_TOKEN


def resolve_upload_dir():
    """
    Rasm/fayllar saqlanadigan papkani aniqlaydi.

    Railway'da rasm yo'qolmasligi uchun eng to'g'ri yo'l:
      1) Railway Volume'ni /data ga ulash
      2) UPLOAD_DIR=/data/uploads qilib qo'yish

    Agar UPLOAD_DIR berilmagan bo'lsa, lekin /data papka mavjud bo'lsa,
    avtomatik /data/uploads ishlatiladi. Lokal kompyuterda esa eski uploads papkasi qoladi.
    """
    env_dir = (os.environ.get("UPLOAD_DIR") or "").strip()
    if env_dir:
        return env_dir
    if os.path.isdir("/data"):
        return "/data/uploads"
    return "uploads"


UPLOAD_DIR = resolve_upload_dir()

CODE_TTL = 10 * 60  # kod amal qilish vaqti: 10 daqiqa

# ---------- Bot va Mini App uchun ruxsat berilgan Telegram IDlar ----------
# Faqat shu ID egalari botdan va platformadan foydalana oladi.
ALLOWED_TG_IDS = {1423181561, 607563067}

CLOSED_MESSAGE = (
    "Loyihamiz to\'liq ishga tushmadi. "
    "Loyihamiz to\'liq ishga tushganda barcha uchun ochiladi. "
    "Iltimos kutib turing."
)


def is_allowed_tg_id(tg_id):
    """Telegram ID ruxsat berilganlar ro'yxatidami — tekshiradi."""
    try:
        return int(tg_id) in ALLOWED_TG_IDS
    except Exception:
        return False


# Sinov rejimida oxirgi kodlar shu yerda turadi (faqat TEST_MODE=1 da)
_test_codes = {}


# ---------- Telegram initData tekshiruvi ----------
def verify_init_data(init_data):
    """Mini App so'rovi haqiqatan Telegramdan kelganini imzo orqali tekshiradi."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None
    data_check_string = "\n".join("{}={}".format(k, parsed[k]) for k in sorted(parsed))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, received_hash):
        return None
    try:
        user = json.loads(parsed.get("user", "{}"))
    except Exception:
        return None
    return user if "id" in user else None


def require_tg(init_data):
    """Telegram foydalanuvchisini majburiy tekshiradi."""
    tg = verify_init_data(init_data)
    if not tg:
        raise HTTPException(401, "Iltimos, ilovani Telegram bot orqali oching.")
    if not is_allowed_tg_id(tg.get("id")):
        raise HTTPException(403, CLOSED_MESSAGE)
    return tg


def current_user(conn, tg_id):
    """Shu Telegramga bog'langan akkauntni topadi (bo'lmasa None)."""
    return conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()


# ---------- Parol (xavfsiz saqlash) ----------
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return salt + "$" + h.hex()


def check_password(password, stored):
    try:
        salt, _ = stored.split("$", 1)
    except Exception:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


def gen_code():
    return "".join(secrets.choice("0123456789") for _ in range(6))


# ---------- Telegram bot ----------
async def tg_call(method, payload):
    if TEST_MODE:
        # Sinov rejimi: tashqariga so'rov yubormaymiz
        if method == "sendMessage" and "KOD:" in str(payload.get("text", "")):
            code = payload["text"].split("KOD:")[1].strip().split()[0]
            _test_codes[payload["chat_id"]] = code
        return {"ok": True}
    if not BOT_TOKEN:
        return None
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            r = await client.post(TG_API + "/" + method, json=payload)
            return r.json()
        except Exception as e:
            print("Telegram xatosi (" + method + "):", e)
            return None


async def send_code(tg_id, code, purpose):
    title = "Ro'yxatdan o'tish" if purpose == "register" else "Kirish"
    await tg_call("sendMessage", {
        "chat_id": tg_id,
        "text": title + " uchun tasdiqlash kodingiz — KOD: " + code +
                "\n\nKod 10 daqiqa amal qiladi. Uni hech kimga bermang.",
    })


async def setup_bot():
    if not (BOT_TOKEN and BASE_URL) or TEST_MODE:
        print("Bot sozlanmadi (BOT_TOKEN/BASE_URL yo'q yoki TEST_MODE).")
        return
    # Avval eski webhook'ni o'chiramiz (toza qayta ro'yxatdan o'tkazish uchun)
    await tg_call("deleteWebhook", {"drop_pending_updates": False})
    await tg_call("setWebhook", {
        "url": BASE_URL + "/webhook",
        "secret_token": WEBHOOK_SECRET,
        "allowed_updates": ["message", "callback_query"],
    })
    # Hamma uchun pastdagi global "Platforma" tugmasini o'chiramiz.
    # Aks holda ruxsatsiz odam ham asosiy sahifani ochib ko'rishi mumkin.
    await tg_call("setChatMenuButton", {
        "menu_button": {"type": "commands"},
    })

    # Faqat ruxsat berilgan Telegram IDlar uchun alohida Web App tugmasi qo'yamiz.
    # Telegram Bot API bu yerda user_id emas, chat_id kutadi.
    for uid in ALLOWED_TG_IDS:
        await tg_call("setChatMenuButton", {
            "chat_id": uid,
            "menu_button": {"type": "web_app", "text": "Platforma", "web_app": {"url": BASE_URL}},
        })

    print("Bot sozlandi:", BASE_URL)


# ---------- App ----------
@asynccontextmanager
async def lifespan(app):
    init_db()
    await setup_bot()
    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def whitelist_middleware(request: Request, call_next):
    """
    /api/... so'rovlarini global tekshiradi.
    Bu api.py ichidagi alohida endpointlarni ham ruxsatsiz foydalanuvchilardan yopadi.
    Static sahifa server tomonda Telegram IDni bilmaydi, shuning uchun frontend guard ham kerak.
    """
    path = request.url.path

    # Telegram webhookni bloklamaymiz: u Telegram serveridan keladi.
    if path == "/webhook":
        return await call_next(request)

    # Faqat API so'rovlarini server tomonda himoya qilamiz.
    if path.startswith("/api/"):
        init_data = request.headers.get("x-telegram-init-data", "")
        tg = verify_init_data(init_data)
        if not tg:
            return JSONResponse(
                status_code=401,
                content={"detail": "Iltimos, ilovani Telegram bot orqali oching."},
            )
        if not is_allowed_tg_id(tg.get("id")):
            return JSONResponse(status_code=403, content={"detail": CLOSED_MESSAGE})

    return await call_next(request)


# Kabinet va platforma API'lari (api.py)
from api import router as api_router
app.include_router(api_router)


@app.get("/api/_dbinfo")
async def db_info():
    """Baza diagnostikasi: nechta foydalanuvchi bor, baza qayerda, fayl o'lchami."""
    import os as _os
    info = {"DB_PATH": DB_PATH}
    try:
        info["fayl_bormi"] = _os.path.isfile(DB_PATH)
        info["fayl_olchami_bayt"] = _os.path.getsize(DB_PATH) if _os.path.isfile(DB_PATH) else 0
        info["papka_bormi"] = _os.path.isdir(_os.path.dirname(DB_PATH)) if _os.path.dirname(DB_PATH) else True
    except Exception as e:
        info["fayl_xato"] = str(e)
    try:
        conn = db()
        info["foydalanuvchilar_soni"] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        info["bizneslar_soni"] = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
        info["elonlar_soni"] = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        # oxirgi 5 foydalanuvchi login va tg_id (parolsiz)
        rows = conn.execute("SELECT login, tg_id, name FROM users ORDER BY id DESC LIMIT 5").fetchall()
        info["oxirgi_foydalanuvchilar"] = [{"login": r["login"], "tg_id": r["tg_id"], "name": r["name"]} for r in rows]
        conn.close()
    except Exception as e:
        info["baza_xato"] = str(e)
    return info


@app.get("/api/_setup")
async def manual_setup():
    """Webhook'ni qo'lda qayta o'rnatish va Telegram javoblarini ko'rsatish (diagnostika)."""
    result = {"BOT_TOKEN_bormi": bool(BOT_TOKEN), "BASE_URL": BASE_URL,
              "WEBHOOK_SECRET_uzunligi": len(WEBHOOK_SECRET or ""), "TEST_MODE": TEST_MODE}
    try:
        result["deleteWebhook"] = await tg_call("deleteWebhook", {"drop_pending_updates": False})
    except Exception as e:
        result["deleteWebhook_xato"] = str(e)
    try:
        result["setWebhook"] = await tg_call("setWebhook", {
            "url": BASE_URL + "/webhook",
            "secret_token": WEBHOOK_SECRET,
            "allowed_updates": ["message", "callback_query"],
        })
    except Exception as e:
        result["setWebhook_xato"] = str(e)
    try:
        result["menu_global"] = await tg_call("setChatMenuButton", {
            "menu_button": {"type": "commands"},
        })
        result["menu_allowed"] = []
        for uid in ALLOWED_TG_IDS:
            result["menu_allowed"].append(await tg_call("setChatMenuButton", {
                "chat_id": uid,
                "menu_button": {"type": "web_app", "text": "Platforma", "web_app": {"url": BASE_URL}},
            }))
    except Exception as e:
        result["menu_xato"] = str(e)
    try:
        info = await tg_call("getWebhookInfo", {})
        result["getWebhookInfo"] = info.get("result") if isinstance(info, dict) else info
    except Exception as e:
        result["getWebhookInfo_xato"] = str(e)
    return result


# ---------- Webhook ----------
@app.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(default="")):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(403, "forbidden")
    update = await request.json()
    msg = update.get("message")
    cq = update.get("callback_query")

    # Whitelist: ruxsat berilmagan Telegram IDlar botdan foydalana olmaydi.
    incoming_tg_id = None
    incoming_chat_id = None
    if msg:
        incoming_tg_id = (msg.get("from") or {}).get("id") or (msg.get("chat") or {}).get("id")
        incoming_chat_id = (msg.get("chat") or {}).get("id")
    elif cq:
        incoming_tg_id = (cq.get("from") or {}).get("id")
        incoming_chat_id = ((cq.get("message") or {}).get("chat") or {}).get("id") or incoming_tg_id

    if incoming_tg_id is not None and not is_allowed_tg_id(incoming_tg_id):
        if cq:
            await tg_call("answerCallbackQuery", {
                "callback_query_id": cq.get("id"),
                "text": CLOSED_MESSAGE,
                "show_alert": True,
            })
        elif incoming_chat_id:
            await tg_call("sendMessage", {
                "chat_id": incoming_chat_id,
                "text": CLOSED_MESSAGE,
            })
        return {"ok": True}

    # Tasdiqlash tugmasi bosilganda (login so'rovini tasdiqlash/rad etish)
    if cq:
        data = cq.get("data", "")
        from_id = cq["from"]["id"]
        cq_id = cq["id"]
        action, _, rid = data.partition("_")
        if action in ("approve", "reject") and rid.isdigit():
            conn = db()
            row = conn.execute("SELECT * FROM login_requests WHERE id=?", (int(rid),)).fetchone()
            if not row:
                conn.close()
                await tg_call("answerCallbackQuery", {"callback_query_id": cq_id, "text": "So'rov topilmadi yoki muddati tugagan."})
                return {"ok": True}
            # faqat akkaunt egasi tasdiqlay oladi
            user = conn.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
            if not user or user["tg_id"] != from_id:
                conn.close()
                await tg_call("answerCallbackQuery", {"callback_query_id": cq_id, "text": "Bu so'rov sizga tegishli emas."})
                return {"ok": True}
            new_status = "approved" if action == "approve" else "rejected"
            conn.execute("UPDATE login_requests SET status=? WHERE id=?", (new_status, row["id"]))
            conn.commit()
            conn.close()
            note = "✅ Tasdiqlandi. Endi yangi qurilmada kabinetga kirasiz." if action == "approve" \
                   else "❌ Rad etildi. Kirishga ruxsat berilmadi."
            await tg_call("answerCallbackQuery", {"callback_query_id": cq_id, "text": note})
            # xabar matnini yangilaymiz
            try:
                await tg_call("editMessageText", {
                    "chat_id": from_id,
                    "message_id": cq["message"]["message_id"],
                    "text": cq["message"].get("text", "") + "\n\n" + note,
                })
            except Exception:
                pass
        else:
            await tg_call("answerCallbackQuery", {"callback_query_id": cq_id})
        return {"ok": True}

    # Foto/video kelsa — e'lon uchun "pochta qutisi"ga olamiz
    if msg and (msg.get("photo") or msg.get("video")):
        tg_id = msg["chat"]["id"]
        if msg.get("photo"):
            file_id = msg["photo"][-1]["file_id"]  # eng katta o'lcham
            mtype = "photo"
        else:
            file_id = msg["video"]["file_id"]
            mtype = "video"
        conn = db()
        conn.execute(
            "INSERT INTO media_inbox(tg_id, file_id, mtype, created_at) VALUES(?,?,?,?)",
            (tg_id, file_id, mtype, int(time.time())),
        )
        # faqat oxirgi 20 tasi saqlanadi
        conn.execute(
            "DELETE FROM media_inbox WHERE tg_id=? AND id NOT IN "
            "(SELECT id FROM media_inbox WHERE tg_id=? ORDER BY id DESC LIMIT 20)",
            (tg_id, tg_id),
        )
        conn.commit()
        conn.close()
        await tg_call("sendMessage", {
            "chat_id": tg_id,
            "text": ("Rasm" if mtype == "photo" else "Video") +
                    " qabul qilindi ✅ Endi ilovadagi e'lon formasiga qaytsangiz, u yerda ko'rinadi.",
        })
        return {"ok": True}

    if msg and isinstance(msg.get("text"), str) and msg["text"].split(" ")[0] == "/start":
        await tg_call("sendMessage", {
            "chat_id": msg["chat"]["id"],
            "text": "Assalomu alaykum! Platformani ochish uchun pastdagi tugmani bosing.",
            "reply_markup": {"inline_keyboard": [[
                {"text": "Platformani ochish", "web_app": {"url": BASE_URL}}
            ]]},
        })
    return {"ok": True}


# ---------- Katalog ----------
@app.get("/api/catalog")
async def get_catalog():
    return {"yonalishlar": CATALOG, "elon_toifalari": LISTING_CATS}


# ---------- Login/parol generatori ----------
def gen_login():
    return "user" + "".join(secrets.choice("0123456789") for _ in range(6))

def gen_biz_login():
    return "biz" + "".join(secrets.choice("0123456789") for _ in range(6))

def gen_pass():
    alphabet = "abcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


# ---------- Ro'yxatdan o'tish (platforma login/parol yaratadi) ----------
@app.post("/api/auth/register")
async def register(request: Request, x_telegram_init_data: str = Header(default="")):
    tg = require_tg(x_telegram_init_data)
    body = await request.json()

    role = body.get("role")
    if role not in ("user", "business"):
        raise HTTPException(400, "Rol noto'g'ri (user yoki business).")
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Ism (yoki biznes nomi) kiritilishi shart.")
    username = (body.get("username") or "").strip().lstrip("@")

    conn = db()
    existing = current_user(conn, tg["id"])

    # Shu Telegramda allaqachon akkaunt bor — ikkinchi profilni qo'shamiz (xato emas)
    if existing:
        if role == "business":
            # biznesi bormi?
            has_biz = conn.execute("SELECT id FROM businesses WHERE user_id=?", (existing["id"],)).fetchone()
            if has_biz:
                conn.close()
                raise HTTPException(400, "Sizda allaqachon biznes kabinet bor. Kabinetingizdan «Biznes kabinetga o'tish» orqali kiring.")
            # biznes profil + alohida biznes login qo'shamiz
            for _ in range(20):
                biz_login = gen_biz_login()
                if not conn.execute("SELECT 1 FROM businesses WHERE biz_login=?", (biz_login,)).fetchone() and \
                   not conn.execute("SELECT 1 FROM users WHERE login=?", (biz_login,)).fetchone():
                    break
            biz_pass = gen_pass()
            now = int(time.time())
            conn.execute(
                "INSERT INTO businesses(user_id, name, yon, tur, phone, address, lat, lng, biz_login, biz_pass_hash, status, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (existing["id"], name, (body.get("yon") or "").strip(), (body.get("tur") or "").strip(),
                 (body.get("phone") or "").strip(), (body.get("address") or "").strip(),
                 body.get("lat"), body.get("lng"), biz_login, hash_password(biz_pass), "active", now),
            )
            conn.execute("UPDATE users SET role='business' WHERE id=?", (existing["id"],))
            conn.commit()
            conn.close()
            try:
                await tg_call("sendMessage", {
                    "chat_id": tg["id"],
                    "text": ("\U0001F3EA Biznes kabinetingiz ochildi!\n\n"
                             "Biznes login: " + biz_login + "\n"
                             "Biznes parol: " + biz_pass + "\n\n"
                             "Bu login/parol bilan biznes kabinetga alohida kirishingiz mumkin. Saqlab qo'ying."),
                })
            except Exception:
                pass
            return {"ok": True, "role": "business", "added_business": True,
                    "biz_login": biz_login, "biz_password": biz_pass,
                    "message": "Biznes kabinet ochildi!"}
        else:
            # oddiy kabinet allaqachon bor (har bir akkaunt oddiy asosga ega)
            conn.close()
            raise HTTPException(400, "Sizda oddiy kabinet allaqachon bor. Kabinetingizga kiring.")

    # Login/parolni platforma o'zi yaratadi (noyob login)
    for _ in range(20):
        login = gen_login()
        if not conn.execute("SELECT id FROM users WHERE login=?", (login,)).fetchone():
            break
    password = gen_pass()

    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO users(tg_id, username, login, pass_hash, role, name, phone, region, district, mahalla, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (tg["id"], username, login, hash_password(password), role, name,
         (body.get("phone") or "").strip(), (body.get("region") or "").strip(),
         (body.get("district") or "").strip(), (body.get("mahalla") or "").strip(), now),
    )
    user_id = cur.lastrowid
    biz_login = None; biz_pass = None
    if role == "business":
        # biznes uchun alohida login/parol
        for _ in range(20):
            biz_login = gen_biz_login()
            if not conn.execute("SELECT 1 FROM businesses WHERE biz_login=?", (biz_login,)).fetchone() and \
               not conn.execute("SELECT 1 FROM users WHERE login=?", (biz_login,)).fetchone():
                break
        biz_pass = gen_pass()
        conn.execute(
            "INSERT INTO businesses(user_id, name, yon, tur, phone, address, lat, lng, biz_login, biz_pass_hash, status, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, name, (body.get("yon") or "").strip(), (body.get("tur") or "").strip(),
             (body.get("phone") or "").strip(), (body.get("address") or "").strip(),
             body.get("lat"), body.get("lng"), biz_login, hash_password(biz_pass), "active", now),
        )
    conn.commit()
    conn.close()

    # Login va parolni foydalanuvchining Telegramiga yuboramiz
    msg = ("Platformaga xush kelibsiz! \u2705\n\n"
           "Kabinetingizga kirish ma'lumotlari:\n\n"
           "\U0001F511 Login: " + login + "\n"
           "\U0001F510 Parol: " + password + "\n\n"
           "Bu ma'lumotlarni saqlab qo'ying. Boshqa qurilmadan kirganda shu login va parol kerak bo'ladi.")
    if role == "business" and biz_login:
        msg += ("\n\n\U0001F3EA Biznes kabinet uchun alohida:\n"
                "Biznes login: " + biz_login + "\nBiznes parol: " + biz_pass)
    await tg_call("sendMessage", {"chat_id": tg["id"], "text": msg})
    # Ro'yxatdan o'tgan qurilma to'g'ridan-to'g'ri kiradi
    return {"ok": True, "role": role, "login": login, "password": password,
            "biz_login": biz_login, "biz_password": biz_pass,
            "message": "Ro'yxatdan o'tdingiz! Login va parol Telegramingizga yuborildi."}


# ---------- Kirish (login/parol -> asosiy akkauntga tasdiqlash) ----------
@app.post("/api/auth/login")
async def login(request: Request, x_telegram_init_data: str = Header(default="")):
    tg = require_tg(x_telegram_init_data)
    body = await request.json()
    login_v = (body.get("login") or "").strip().lower()
    password = body.get("password") or ""

    conn = db()
    # Avval biznes login bo'lsa (biznes kabinetga alohida kirish)
    biz = conn.execute("SELECT * FROM businesses WHERE biz_login=?", (login_v,)).fetchone()
    if biz:
        if not biz["biz_pass_hash"] or not check_password(password, biz["biz_pass_hash"]):
            conn.close()
            raise HTTPException(401, "Login yoki parol noto'g'ri.")
        owner = conn.execute("SELECT * FROM users WHERE id=?", (biz["user_id"],)).fetchone()
        # qurilmani biznes egasiga bog'laymiz (agar bo'sh yoki shu qurilma bo'lsa)
        if owner and (not owner["tg_id"] or owner["tg_id"] == tg["id"]):
            if not owner["tg_id"]:
                conn.execute("UPDATE users SET tg_id=NULL WHERE tg_id=? AND id<>?", (tg["id"], owner["id"]))
                conn.execute("UPDATE users SET tg_id=? WHERE id=?", (tg["id"], owner["id"]))
                conn.commit()
            conn.close()
            return {"ok": True, "approved": True, "role": "business", "name": biz["name"], "mode": "business"}
        # boshqa qurilma — egasiga tasdiqlash so'rovi
        if owner and owner["tg_id"]:
            device_name = (tg.get("first_name") or "") + ((" @" + tg["username"]) if tg.get("username") else "")
            now = int(time.time())
            conn.execute("DELETE FROM login_requests WHERE user_id=? AND status='pending'", (owner["id"],))
            cur = conn.execute(
                "INSERT INTO login_requests(user_id, device_tg, device_name, status, expires_at, created_at) VALUES(?,?,?,?,?,?)",
                (owner["id"], tg["id"], device_name, "pending", now + 600, now),
            )
            rid = cur.lastrowid
            conn.commit()
            conn.close()
            await tg_call("sendMessage", {
                "chat_id": owner["tg_id"],
                "text": "🔐 Biznes kabinetingizga yangi qurilmadan kirish urinilmoqda:\n" + (device_name or "Noma'lum qurilma") + "\n\nSiz kiryapsizmi?",
                "reply_markup": {"inline_keyboard": [[
                    {"text": "✅ Ha, kirish", "callback_data": "approve_" + str(rid)},
                    {"text": "❌ Yo'q", "callback_data": "reject_" + str(rid)},
                ]]},
            })
            return {"ok": True, "approved": False, "request_id": rid}
        conn.close()
        raise HTTPException(400, "Biznes egasi topilmadi.")

    user = conn.execute("SELECT * FROM users WHERE login=?", (login_v,)).fetchone()
    if not user or not check_password(password, user["pass_hash"]):
        conn.close()
        raise HTTPException(401, "Login yoki parol noto'g'ri.")

    # Agar shu qurilmaning o'zidan kirilayotgan bo'lsa (asosiy akkaunt) — to'g'ridan-to'g'ri
    if user["tg_id"] == tg["id"]:
        conn.close()
        return {"ok": True, "approved": True, "role": user["role"], "name": user["name"]}

    # Boshqa qurilma — asosiy akkauntga tasdiqlash so'rovi yuboramiz
    if not user["tg_id"]:
        # akkaunt hech qaysi telegramga bog'lanmagan — shu qurilmaga bog'laymiz
        # (avval shu qurilma boshqa akkauntga bog'langan bo'lsa, uni bo'shatamiz)
        conn.execute("UPDATE users SET tg_id=NULL WHERE tg_id=? AND id<>?", (tg["id"], user["id"]))
        conn.execute("UPDATE users SET tg_id=? WHERE id=?", (tg["id"], user["id"]))
        conn.commit(); conn.close()
        return {"ok": True, "approved": True, "role": user["role"], "name": user["name"]}

    device_name = (tg.get("first_name") or "") + ((" @" + tg["username"]) if tg.get("username") else "")
    now = int(time.time())
    conn.execute("DELETE FROM login_requests WHERE user_id=? AND status='pending'", (user["id"],))
    cur = conn.execute(
        "INSERT INTO login_requests(user_id, device_tg, device_name, status, expires_at, created_at) "
        "VALUES(?,?,?,?,?,?)",
        (user["id"], tg["id"], device_name.strip(), "pending", now + CODE_TTL, now),
    )
    req_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Asosiy akkauntga tasdiqlash tugmali xabar
    await tg_call("sendMessage", {
        "chat_id": user["tg_id"],
        "text": ("\U0001F510 Akkauntingizga boshqa qurilmadan kirishga urinilmoqda:\n\n"
                 + (device_name.strip() or "Noma'lum qurilma") +
                 "\n\nBu sizmidingizmi? Agar ha bo'lsa, tasdiqlang. Agar siz bo'lmasangiz, rad eting."),
        "reply_markup": {"inline_keyboard": [[
            {"text": "\u2705 Tasdiqlash", "callback_data": "approve_" + str(req_id)},
            {"text": "\u274C Rad etish", "callback_data": "reject_" + str(req_id)},
        ]]},
    })
    return {"request_id": req_id, "approved": False,
            "message": "Asosiy Telegram akkauntingizga tasdiqlash so'rovi yuborildi. Iltimos, o'sha yerda tasdiqlang."}


@app.get("/api/auth/login/status")
async def login_status(request_id: int, x_telegram_init_data: str = Header(default="")):
    tg = require_tg(x_telegram_init_data)
    conn = db()
    row = conn.execute(
        "SELECT * FROM login_requests WHERE id=? AND device_tg=?", (request_id, tg["id"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "So'rov topilmadi.")
    if row["status"] == "pending" and row["expires_at"] < int(time.time()):
        conn.close()
        return {"status": "expired"}
    if row["status"] == "approved":
        # qurilmani akkauntga bog'laymiz (Telegram tartibi: oxirgi kirgan qurilma asosiy bo'ladi)
        user = conn.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
        # shu qurilma boshqa akkauntga bog'langan bo'lsa, faqat o'shani bo'shatamiz (target'dan tashqari)
        conn.execute("UPDATE users SET tg_id=NULL WHERE tg_id=? AND id<>?", (tg["id"], row["user_id"]))
        conn.execute("UPDATE users SET tg_id=? WHERE id=?", (tg["id"], row["user_id"]))
        conn.execute("DELETE FROM login_requests WHERE id=?", (row["id"],))
        conn.commit()
        conn.close()
        return {"status": "approved", "role": user["role"], "name": user["name"]}
    status = row["status"]
    conn.close()
    return {"status": status}

# ---------- Joriy foydalanuvchi ----------
@app.get("/api/me")
async def me(x_telegram_init_data: str = Header(default="")):
    tg = require_tg(x_telegram_init_data)
    conn = db()
    user = current_user(conn, tg["id"])
    if not user:
        conn.close()
        return {"registered": False}
    result = {
        "registered": True,
        "id": user["id"], "role": user["role"], "name": user["name"],
        "phone": user["phone"], "region": user["region"],
        "district": user["district"], "mahalla": user["mahalla"],
        "lat": user["lat"], "lng": user["lng"],
    }
    # Biznes ma'lumotini rol nima bo'lishidan qat'i nazar qaytaramiz (agar businesses yozuvi bo'lsa)
    biz = conn.execute("SELECT * FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
    result["has_business"] = bool(biz)
    if biz:
        _bk = biz.keys()
        result["business"] = {
            "id": biz["id"], "name": biz["name"], "yon": biz["yon"], "tur": biz["tur"],
            "descr": biz["descr"], "phone": biz["phone"], "telegram": biz["telegram"],
            "work_hours": biz["work_hours"], "address": biz["address"], "status": biz["status"],
            "lat": biz["lat"], "lng": biz["lng"],
            # v1422: to'lov ma'lumotlari (ustunlar bo'lmasa ham xavfsiz)
            "pay_card": biz["pay_card"] if "pay_card" in _bk else "",
            "pay_holder": biz["pay_holder"] if "pay_holder" in _bk else "",
            "pay_qr": biz["pay_qr"] if "pay_qr" in _bk else "",
        }
    conn.close()
    return result


# ---------- Biznes ochish (mavjud akkauntga biznes profil qo'shish) ----------
@app.post("/api/business/open")
async def open_business(request: Request, x_telegram_init_data: str = Header(default="")):
    tg = require_tg(x_telegram_init_data)
    conn = db()
    user = current_user(conn, tg["id"])
    if not user:
        conn.close()
        raise HTTPException(401, "Avval ro'yxatdan o'ting.")
    # allaqachon biznes bormi?
    exists = conn.execute("SELECT id FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
    if exists:
        conn.close()
        raise HTTPException(400, "Sizda allaqachon biznes profil bor.")
    b = await request.json()
    name = (b.get("name") or "").strip()
    if not name:
        conn.close()
        raise HTTPException(400, "Biznes nomi kiritilishi shart.")
    now = int(time.time())
    # biznes uchun alohida login/parol yaratamiz
    for _ in range(20):
        biz_login = gen_biz_login()
        clash = conn.execute("SELECT 1 FROM businesses WHERE biz_login=?", (biz_login,)).fetchone()
        clash2 = conn.execute("SELECT 1 FROM users WHERE login=?", (biz_login,)).fetchone()
        if not clash and not clash2:
            break
    biz_pass = gen_pass()
    conn.execute(
        """INSERT INTO businesses(user_id, name, yon, tur, descr, phone, telegram, work_hours, address, lat, lng, biz_login, biz_pass_hash, status, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (user["id"], name, (b.get("yon") or "").strip(), (b.get("tur") or "").strip(),
         (b.get("descr") or "").strip(), (b.get("phone") or "").strip(), (b.get("telegram") or "").strip(),
         (b.get("work_hours") or "").strip(), (b.get("address") or "").strip(),
         b.get("lat"), b.get("lng"), biz_login, hash_password(biz_pass), "active", now),
    )
    # rolni biznesga ham o'tkazamiz (lekin oddiy profil ham qoladi — bir akkaunt ikkala rejim)
    conn.execute("UPDATE users SET role='business' WHERE id=?", (user["id"],))
    conn.commit()
    conn.close()

    # biznes login/parolni Telegramga yuboramiz
    try:
        await tg_call("sendMessage", {
            "chat_id": tg["id"],
            "text": ("\U0001F3EA Biznes kabinetingiz ochildi!\n\n"
                     "Biznes login: " + biz_login + "\n"
                     "Biznes parol: " + biz_pass + "\n\n"
                     "Bu login/parol bilan biznes kabinetingizga alohida kirishingiz mumkin. Saqlab qo'ying."),
        })
    except Exception:
        pass
    return {"ok": True, "biz_login": biz_login, "biz_password": biz_pass}


# ---------- Koordinatadan manzil aniqlash (server orqali — ishonchli) ----------
async def reverse_geocode(lat: float, lng: float):
    """Koordinatadan manzil aniqlaydi: address (matn) + region/district (alohida) qaytaradi."""
    if TEST_MODE:
        # Sinov rejimi uchun soxta natija (haqiqiy rejimda Nominatim ishlaydi)
        return {"address": "Yunusobod tumani, Toshkent shahri",
                "region": "Toshkent shahri", "district": "Yunusobod tumani"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"format": "json", "lat": lat, "lon": lng, "accept-language": "uz"},
                headers={"User-Agent": "PlatformaApp/1.0"},
            )
            d = r.json()
    except Exception:
        return {"address": "", "region": "", "district": ""}
    a = d.get("address", {}) if isinstance(d, dict) else {}
    parts = []
    ko = a.get("road") or a.get("neighbourhood") or ""
    tuman = a.get("city_district") or a.get("county") or a.get("suburb") or a.get("town") or a.get("village") or ""
    viloyat = a.get("state") or a.get("region") or ""
    if ko:
        parts.append(ko)
    if tuman:
        parts.append(tuman)
    if viloyat and viloyat != tuman:
        parts.append(viloyat)
    return {"address": ", ".join(parts), "region": viloyat, "district": tuman}


@app.get("/api/geocode")
async def geocode(lat: float, lng: float):
    """Koordinatadan o'qiladigan manzil qaytaradi (OpenStreetMap orqali)."""
    return await reverse_geocode(lat, lng)


_file_path_cache = {}

@app.get("/media/{file_id}")
async def media_proxy(file_id: str):
    from fastapi.responses import StreamingResponse, Response
    if TEST_MODE:
        return Response(content=b"test-media", media_type="application/octet-stream")
    path = _file_path_cache.get(file_id)
    if not path:
        r = await tg_call("getFile", {"file_id": file_id})
        if not (r and r.get("ok")):
            raise HTTPException(404, "Fayl topilmadi.")
        path = r["result"]["file_path"]
        _file_path_cache[file_id] = path
    url = "https://api.telegram.org/file/bot" + BOT_TOKEN + "/" + path
    client = httpx.AsyncClient(timeout=60)
    req_s = client.build_request("GET", url)
    resp = await client.send(req_s, stream=True)
    if resp.status_code != 200:
        await resp.aclose(); await client.aclose()
        _file_path_cache.pop(file_id, None)
        raise HTTPException(404, "Fayl topilmadi.")
    ctype = "video/mp4" if path.endswith(".mp4") else "image/jpeg"

    async def gen():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose(); await client.aclose()

    return StreamingResponse(gen(), media_type=ctype,
                             headers={"Cache-Control": "public, max-age=86400"})


# ---------- Sinov yordamchisi (faqat TEST_MODE) ----------
@app.get("/api/_test/last_code/{tg_id}")
async def test_last_code(tg_id: int):
    if not TEST_MODE:
        raise HTTPException(404, "not found")
    return {"code": _test_codes.get(tg_id)}


# ---------- Yuklangan fayllar ----------
os.makedirs(UPLOAD_DIR, exist_ok=True)
print("UPLOAD_DIR:", os.path.abspath(UPLOAD_DIR))
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ---------- Mini App (eng oxirida) ----------
app.mount("/", StaticFiles(directory="static", html=True), name="static")

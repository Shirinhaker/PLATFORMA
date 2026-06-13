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
 
from database import db, init_db
from catalog_data import CATALOG, LISTING_CATS
 
# ---------- Sozlamalar ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "platforma-webhook-secret")
TEST_MODE = os.environ.get("TEST_MODE", "") == "1"
TG_API = "https://api.telegram.org/bot" + BOT_TOKEN
 
CODE_TTL = 10 * 60  # kod amal qilish vaqti: 10 daqiqa
 
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
    await tg_call("setWebhook", {
        "url": BASE_URL + "/webhook",
        "secret_token": WEBHOOK_SECRET,
        "allowed_updates": ["message"],
    })
    await tg_call("setChatMenuButton", {
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
 
# Kabinet va platforma API'lari (api.py)
from api import router as api_router
app.include_router(api_router)
 
 
# ---------- Webhook ----------
@app.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(default="")):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(403, "forbidden")
    update = await request.json()
    msg = update.get("message")
 
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
 
 
# ---------- Ro'yxatdan o'tish ----------
@app.post("/api/auth/register")
async def register(request: Request, x_telegram_init_data: str = Header(default="")):
    tg = require_tg(x_telegram_init_data)
    body = await request.json()
 
    role = body.get("role")
    if role not in ("user", "business"):
        raise HTTPException(400, "Rol noto'g'ri (user yoki business).")
    login = (body.get("login") or "").strip().lower()
    password = body.get("password") or ""
    name = (body.get("name") or "").strip()
    if len(login) < 4:
        raise HTTPException(400, "Login kamida 4 belgi bo'lsin.")
    if len(password) < 6:
        raise HTTPException(400, "Parol kamida 6 belgi bo'lsin.")
    if not name:
        raise HTTPException(400, "Ism (yoki biznes nomi) kiritilishi shart.")
 
    conn = db()
    exists = conn.execute("SELECT id FROM users WHERE login=?", (login,)).fetchone()
    if exists:
        conn.close()
        raise HTTPException(400, "Bu login band. Boshqasini tanlang.")
 
    # Shu Telegramda allaqachon akkaunt bo'lsa
    if current_user(conn, tg["id"]):
        conn.close()
        raise HTTPException(400, "Bu Telegramga allaqachon akkaunt bog'langan. Kirish bo'limidan foydalaning.")
 
    code = gen_code()
    now = int(time.time())
    payload = json.dumps({
        "name": name,
        "phone": (body.get("phone") or "").strip(),
        "region": (body.get("region") or "").strip(),
        "district": (body.get("district") or "").strip(),
        "mahalla": (body.get("mahalla") or "").strip(),
        # biznes maydonlari
        "yon": (body.get("yon") or "").strip(),
        "tur": (body.get("tur") or "").strip(),
        "address": (body.get("address") or "").strip(),
        "lat": body.get("lat"),
        "lng": body.get("lng"),
    })
    # eski kutilayotgan arizalarini tozalaymiz
    conn.execute("DELETE FROM pending_regs WHERE tg_id=?", (tg["id"],))
    cur = conn.execute(
        "INSERT INTO pending_regs(tg_id, role, login, pass_hash, payload, code, expires_at, created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (tg["id"], role, login, hash_password(password), payload, code, now + CODE_TTL, now),
    )
    pending_id = cur.lastrowid
    conn.commit()
    conn.close()
 
    await send_code(tg["id"], code, "register")
    return {"pending_id": pending_id, "message": "Tasdiqlash kodi Telegramingizga yuborildi."}
 
 
@app.post("/api/auth/register/verify")
async def register_verify(request: Request, x_telegram_init_data: str = Header(default="")):
    tg = require_tg(x_telegram_init_data)
    body = await request.json()
    pending_id = body.get("pending_id")
    code = (body.get("code") or "").strip()
 
    conn = db()
    row = conn.execute(
        "SELECT * FROM pending_regs WHERE id=? AND tg_id=?", (pending_id, tg["id"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(400, "Ariza topilmadi. Qaytadan ro'yxatdan o'ting.")
    if row["expires_at"] < int(time.time()):
        conn.close()
        raise HTTPException(400, "Kod muddati tugagan. Qaytadan urinib ko'ring.")
    if not hmac.compare_digest(row["code"], code):
        conn.close()
        raise HTTPException(400, "Kod noto'g'ri.")
 
    p = json.loads(row["payload"])
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO users(tg_id, login, pass_hash, role, name, phone, region, district, mahalla, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (tg["id"], row["login"], row["pass_hash"], row["role"], p["name"],
         p["phone"], p["region"], p["district"], p["mahalla"], now),
    )
    user_id = cur.lastrowid
 
    if row["role"] == "business":
        conn.execute(
            "INSERT INTO businesses(user_id, name, yon, tur, phone, address, lat, lng, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (user_id, p["name"], p["yon"], p["tur"], p["phone"], p["address"], p["lat"], p["lng"], now),
        )
 
    conn.execute("DELETE FROM pending_regs WHERE id=?", (row["id"],))
    conn.commit()
    conn.close()
    return {"ok": True, "role": row["role"], "message": "Ro'yxatdan o'tish yakunlandi!"}
 
 
# ---------- Kirish ----------
@app.post("/api/auth/login")
async def login(request: Request, x_telegram_init_data: str = Header(default="")):
    tg = require_tg(x_telegram_init_data)
    body = await request.json()
    login_v = (body.get("login") or "").strip().lower()
    password = body.get("password") or ""
 
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE login=?", (login_v,)).fetchone()
    if not user or not check_password(password, user["pass_hash"]):
        conn.close()
        raise HTTPException(401, "Login yoki parol noto'g'ri.")
 
    # Kod akkauntning ASOSIY (ro'yxatdan o'tgan) Telegramiga yuboriladi — Telegram tartibi.
    target_tg = user["tg_id"]
    same_device = (target_tg == tg["id"])
    if not target_tg:
        # Akkaunt hech qaysi Telegramga bog'lanmagan (kamdan-kam holat) — joriy qurilmaga yuboramiz.
        target_tg = tg["id"]
        same_device = True
 
    code = gen_code()
    now = int(time.time())
    conn.execute("DELETE FROM auth_codes WHERE user_id=?", (user["id"],))
    cur = conn.execute(
        # device_tg — kirayotgan qurilma; tasdiqlashda shu tekshiriladi
        "INSERT INTO auth_codes(user_id, tg_id, code, expires_at, created_at) VALUES(?,?,?,?,?)",
        (user["id"], tg["id"], code, now + CODE_TTL, now),
    )
    code_id = cur.lastrowid
    conn.commit()
    conn.close()
 
    await send_code(target_tg, code, "login")
    if same_device:
        msg = "Tasdiqlash kodi Telegramingizga yuborildi."
    else:
        msg = "Tasdiqlash kodi akkauntingiz ro'yxatdan o'tgan asosiy Telegramga yuborildi. Shu kodni kiriting."
    return {"code_id": code_id, "message": msg, "same_device": same_device}
 
 
@app.post("/api/auth/login/verify")
async def login_verify(request: Request, x_telegram_init_data: str = Header(default="")):
    tg = require_tg(x_telegram_init_data)
    body = await request.json()
    code_id = body.get("code_id")
    code = (body.get("code") or "").strip()
 
    conn = db()
    row = conn.execute(
        "SELECT * FROM auth_codes WHERE id=? AND tg_id=? AND used=0", (code_id, tg["id"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(400, "Kod topilmadi. Qaytadan kiring.")
    if row["expires_at"] < int(time.time()):
        conn.close()
        raise HTTPException(400, "Kod muddati tugagan.")
    if not hmac.compare_digest(row["code"], code):
        conn.close()
        raise HTTPException(400, "Kod noto'g'ri.")
 
    # Akkauntni shu Telegramga bog'laymiz (eski bog'lanish bo'lsa, ko'chadi)
    conn.execute("UPDATE users SET tg_id=NULL WHERE tg_id=?", (tg["id"],))
    conn.execute("UPDATE users SET tg_id=? WHERE id=?", (tg["id"], row["user_id"]))
    conn.execute("UPDATE auth_codes SET used=1 WHERE id=?", (row["id"],))
    conn.commit()
    user = conn.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
    conn.close()
    return {"ok": True, "role": user["role"], "name": user["name"]}
 
 
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
    }
    if user["role"] == "business":
        biz = conn.execute("SELECT * FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
        if biz:
            result["business"] = {
                "id": biz["id"], "name": biz["name"], "yon": biz["yon"], "tur": biz["tur"],
                "address": biz["address"], "status": biz["status"],
            }
    conn.close()
    return result
 
 
# ---------- Media ko'prigi (Telegramdagi rasmni ilovaga uzatish) ----------
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
 
 
# ---------- Mini App (eng oxirida) ----------
app.mount("/", StaticFiles(directory="static", html=True), name="static")
 

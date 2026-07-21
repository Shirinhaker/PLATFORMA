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
  APP_ENV, BOT_TOKEN, BASE_URL, DB_PATH, WEBHOOK_SECRET, MOBILE_OTP_SECRET
  UPLOAD_DIR=/data/uploads  -> Railway Volume uchun doimiy rasm papkasi
  BACKUP_DIR=/data/backups -> SQLite zaxira nusxalari
  TEST_MODE=1  -> sinov transporti; OTP HTTP javobida yoki test endpointida berilmaydi
"""

import os
import json
import time
import hmac
import secrets
import hashlib
import asyncio
from urllib.parse import parse_qsl
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from database import db, init_db, DB_PATH
from catalog_data import CATALOG, LISTING_CATS
from access_config import (
    PRIVILEGED_TG_IDS,
    is_privileged_tg_id,
    project_access_allowed_tg_id,
    project_access_is_restricted,
)
from location_keys import canonical_district_key, safe_district_display
from runtime_config import env_flag, is_production, safe_runtime_summary, validate_runtime_config
from backup_database import create_database_backup
from domain_config import (
    DomainPolicyMiddleware,
    configured_allowed_hosts,
    primary_domain,
    validate_domain_config,
)
from integrations import (
    IntegrationDeliveryError,
    IntegrationNotConfigured,
    get_provider,
    integration_status,
)

# ---------- Sozlamalar ----------
APP_BUILD = "v1625"
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")


def _init_data_max_age():
    """Telegram initData imzosining amal qilish muddati (soniya). 0 = cheksiz."""
    try:
        return max(0, int(os.environ.get("INIT_DATA_MAX_AGE_SEC", "86400")))
    except (TypeError, ValueError):
        return 86400


INIT_DATA_MAX_AGE = _init_data_max_age()
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "platforma-webhook-secret")
TEST_MODE = os.environ.get("TEST_MODE", "") == "1"
PRIVILEGED_DIAGNOSTICS_ENABLED = os.environ.get(
    "PRIVILEGED_DIAGNOSTICS_ENABLED", ""
).strip().lower() in ("1", "true", "yes", "on")
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


def resolve_backup_dir():
    env_dir = (os.environ.get("BACKUP_DIR") or "").strip()
    if env_dir:
        return env_dir
    persistent_root = (os.environ.get("PERSISTENT_ROOT") or "").strip()
    if persistent_root:
        return os.path.join(persistent_root, "backups")
    if os.path.isdir("/data"):
        return "/data/backups"
    return "backups"


def _backup_retention():
    try:
        return max(1, min(365, int(os.environ.get("BACKUP_RETENTION", "14"))))
    except (TypeError, ValueError):
        return 14


BACKUP_DIR = resolve_backup_dir()
BACKUP_RETENTION = _backup_retention()
DATABASE_BACKUP_ON_START = env_flag(
    "DATABASE_BACKUP_ON_START", default=is_production()
)
PRIMARY_DOMAIN = primary_domain()
ALLOWED_HOSTS = configured_allowed_hosts()
CANONICAL_WWW_REDIRECT = env_flag("CANONICAL_WWW_REDIRECT", default=True)

CODE_TTL = 10 * 60  # kod amal qilish vaqti: 10 daqiqa
MOBILE_CODE_TTL = 5 * 60
MOBILE_SESSION_TTL = 30 * 24 * 60 * 60
MOBILE_OTP_SECRET = os.environ.get("MOBILE_OTP_SECRET", WEBHOOK_SECRET)
PRIVILEGED_ACCESS_COOKIE = "koprik_privileged_access"
PRIVILEGED_ACCESS_COOKIE_TTL = 60 * 60


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
    # Imzo to'g'ri, lekin u abadiy amal qilmasligi kerak: sizib chiqqan initData
    # muddati o'tgach ishlamaydi (replay himoyasi). Telegram har ochilishda yangisini
    # beradi, shuning uchun oddiy foydalanuvchiga sezilmaydi.
    if INIT_DATA_MAX_AGE > 0:
        try:
            auth_date = int(parsed.get("auth_date", "0"))
        except (TypeError, ValueError):
            return None
        if auth_date <= 0:
            return None
        age = time.time() - auth_date
        # -300: qurilma/server soatidagi kichik farqqa yo'l qo'yamiz.
        if age > INIT_DATA_MAX_AGE or age < -300:
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


def mobile_user_from_token(conn, token, touch=False):
    """Mobil Bearer token orqali faol foydalanuvchini topadi."""
    token = (token or "").strip()
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = int(time.time())
    try:
        row = conn.execute(
            """SELECT u.*, ms.id AS mobile_session_id
               FROM mobile_sessions ms JOIN users u ON u.id=ms.user_id
               WHERE ms.token_hash=? AND ms.revoked_at=0 AND ms.expires_at>?""",
            (token_hash, now),
        ).fetchone()
    except Exception:
        return None
    if row and touch:
        conn.execute("UPDATE mobile_sessions SET last_used_at=? WHERE id=?", (now, row["mobile_session_id"]))
        conn.commit()
    return row


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
    fixed = os.environ.get("TEST_OTP_CODE", "").strip()
    if TEST_MODE and len(fixed) == 6 and fixed.isdigit():
        return fixed
    return "".join(secrets.choice("0123456789") for _ in range(6))


def normalize_uz_phone(value):
    """O'zbekiston raqamini +998XXXXXXXXX ko'rinishiga keltiradi."""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if digits.startswith("998") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 9:
        return "+998" + digits
    return ""


def mobile_code_hash(phone, code):
    raw = phone + ":" + str(code or "") + ":" + MOBILE_OTP_SECRET
    return hashlib.sha256(raw.encode()).hexdigest()


async def deliver_mobile_code(phone, code, purpose):
    """Tanlangan SMS adapteri orqali kod yuboradi; testda tashqariga chiqmaydi."""
    if TEST_MODE:
        return
    try:
        provider = get_provider("sms")
        await provider.send_verification_code(
            phone=phone,
            code=code,
            purpose=purpose,
            expires_in=MOBILE_CODE_TTL,
        )
    except IntegrationNotConfigured:
        raise HTTPException(503, "SMS xizmati hali ulanmagan.")
    except IntegrationDeliveryError:
        raise HTTPException(502, "SMS xizmati kodni yubora olmadi. Keyinroq urinib ko‘ring.")


def find_user_by_phone(conn, phone):
    """Bazadagi turli yozilishdagi telefonlarni yagona formatda solishtiradi."""
    matches = []
    for row in conn.execute("SELECT * FROM users WHERE COALESCE(phone,'')<>''").fetchall():
        if normalize_uz_phone(row["phone"]) == phone:
            matches.append(row)
    if len(matches) > 1:
        raise HTTPException(409, "Bu telefon bir nechta akkauntga biriktirilgan. Yordam xizmatiga murojaat qiling.")
    return matches[0] if matches else None


# ---------- Telegram bot ----------
async def tg_call(method, payload):
    if TEST_MODE:
        # Sinov rejimi: tashqariga so'rov ham, OTPni o'qiladigan joyga yozish ham yo'q.
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
    # Platforma endi hamma uchun ochiq: global Web App menyusi.
    await tg_call("setChatMenuButton", {
        "menu_button": {"type": "web_app", "text": "Platforma", "web_app": {"url": BASE_URL}},
    })

    print("Bot sozlandi:", BASE_URL)


# ---------- App ----------
@asynccontextmanager
async def lifespan(app):
    init_db()
    if DATABASE_BACKUP_ON_START:
        created_backup = create_database_backup(
            DB_PATH, BACKUP_DIR, retention=BACKUP_RETENTION
        )
        print("DATABASE_BACKUP:", os.path.basename(created_backup))
    from api import warm_search_cache
    warm_search_cache()
    await setup_bot()
    push_task = None
    if os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON") or os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH"):
        from push_worker import push_worker_loop
        push_task = asyncio.create_task(push_worker_loop())
    try:
        yield
    finally:
        if push_task:
            push_task.cancel()
            try:
                await push_task
            except asyncio.CancelledError:
                pass


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=ALLOWED_HOSTS,
    www_redirect=False,
)
app.add_middleware(
    DomainPolicyMiddleware,
    domain=PRIMARY_DOMAIN,
    production=is_production(),
    redirect_www=CANONICAL_WWW_REDIRECT,
)


def _project_temporarily_closed_response():
    return JSONResponse(
        status_code=403,
        content={
            "detail": "Loyiha vaqtincha yopiq. Qayta ochilganda xabar beriladi.",
            "code": "project_temporarily_closed",
        },
    )


def _ambiguous_authentication_response():
    return JSONResponse(
        status_code=400,
        content={
            "detail": "Bir so'rovda faqat bitta kirish usulidan foydalaning.",
            "code": "ambiguous_authentication",
        },
    )


def _privileged_access_cookie_value(tg_id, now=None):
    expires_at = int(time.time() if now is None else now) + PRIVILEGED_ACCESS_COOKIE_TTL
    payload = str(int(tg_id)) + ":" + str(expires_at)
    signature = hmac.new(
        WEBHOOK_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return payload + ":" + signature


def _privileged_access_cookie_tg_id(value, now=None):
    try:
        tg_text, expires_text, signature = str(value or "").split(":", 2)
        tg_id = int(tg_text)
        expires_at = int(expires_text)
    except (TypeError, ValueError):
        return None
    if expires_at <= int(time.time() if now is None else now):
        return None
    payload = tg_text + ":" + expires_text
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    return tg_id if project_access_allowed_tg_id(tg_id) else None


def _set_privileged_access_cookie(response, request, tg_id):
    response.set_cookie(
        PRIVILEGED_ACCESS_COOKIE,
        _privileged_access_cookie_value(tg_id),
        max_age=PRIVILEGED_ACCESS_COOKIE_TTL,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    return response


def _inject_mobile_init_data(request, mobile_token):
    headers = [
        (key, value)
        for key, value in request.scope.get("headers", [])
        if key.lower() != b"x-telegram-init-data"
    ]
    headers.append((b"x-telegram-init-data", ("mobile:" + mobile_token).encode()))
    request.scope["headers"] = headers


@app.middleware("http")
async def build_and_cache_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Platforma-Build"] = APP_BUILD
    path = request.url.path
    if path in ("/", "/index.html", "/healthz", "/readyz") or path.startswith("/api/ai") or path.startswith("/api/advertisements"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif response.status_code < 400 and (path in ("/app.css", "/app.js", "/regions.js", "/qrcode.min.js") or path.startswith("/demo_ads/")):
        response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
    elif response.status_code >= 400:
        response.headers["Cache-Control"] = "no-store"
    if project_access_is_restricted() and path.startswith(
        ("/media/", "/profile-media/", "/uploads/")
    ):
        response.headers["Cache-Control"] = "private, no-store"
    return response


@app.middleware("http")
async def whitelist_middleware(request: Request, call_next):
    """
    /api/... so'rovlarini global tekshiradi.
    Bu api.py ichidagi alohida endpointlarni ham ruxsatsiz foydalanuvchilardan yopadi.
    Telegram imzosi yoki mobil sessiyani tekshiradi.
    """
    path = request.url.path

    # Telegram webhookni bloklamaymiz: u Telegram serveridan keladi.
    if path == "/webhook":
        return await call_next(request)

    if project_access_is_restricted() and path.startswith(
        ("/media/", "/profile-media/", "/uploads/")
    ):
        cookie_tg_id = _privileged_access_cookie_tg_id(
            request.cookies.get(PRIVILEGED_ACCESS_COOKIE)
        )
        if cookie_tg_id is None:
            return _project_temporarily_closed_response()
        return await call_next(request)

    if path.startswith("/api/"):
        init_data = request.headers.get("x-telegram-init-data", "").strip()
        staff_token = request.headers.get("x-staff-token", "").strip()
        auth = (request.headers.get("authorization") or "").strip()
        has_bearer = auth.lower().startswith("bearer ")
        has_staff = bool(staff_token or init_data.startswith("staff:"))
        has_telegram = bool(init_data and not init_data.startswith(("staff:", "mobile:")))
        if (has_bearer and (has_staff or has_telegram)) or (
            staff_token and init_data and not init_data.startswith("staff:")
        ):
            return _ambiguous_authentication_response()

        # Vaqtinchalik yopiq rejim barcha API yo'llaridan oldin tekshiriladi.
        # Faqat access_config.py dagi Telegram IDlar va ularga bog'langan mobil
        # sessiyalar o'tadi. Staff tokeni bu global blokni chetlab o'tmaydi.
        if project_access_is_restricted():
            if has_bearer:
                mobile_token = auth[7:].strip()
                conn = db()
                mobile_user = mobile_user_from_token(conn, mobile_token)
                conn.close()
                if not mobile_user or not project_access_allowed_tg_id(mobile_user["tg_id"]):
                    return _project_temporarily_closed_response()
                _inject_mobile_init_data(request, mobile_token)
                response = await call_next(request)
                return _set_privileged_access_cookie(
                    response, request, mobile_user["tg_id"]
                )

            tg = verify_init_data(init_data)
            if not tg or not project_access_allowed_tg_id(tg.get("id")):
                return _project_temporarily_closed_response()
            response = await call_next(request)
            return _set_privileged_access_cookie(response, request, tg["id"])

        is_public_district_offers = path == "/api/home/district-offers"
        # XODIM (staff) kirishi Telegram whitelistdan ozod:
        #  1) /api/staff-auth* (login / me / logout)
        #  2) staff token bilan kelgan har qanday so'rov (endpoint tokenni o'zi tekshiradi)
        if path.startswith("/api/staff-auth") or path in (
            "/api/password-auth/login",
            "/api/mobile-auth/request-code", "/api/mobile-auth/verify-code",
            "/api/mobile-auth/register/request-code", "/api/mobile-auth/register/verify-code",
        ):
            return await call_next(request)
        if has_staff:
            return await call_next(request)
        # Mobil ilova Telegram initData o'rniga Bearer token yuboradi.
        if has_bearer:
            mobile_token = auth[7:].strip()
            conn = db()
            mobile_user = mobile_user_from_token(conn, mobile_token)
            conn.close()
            if not mobile_user:
                return JSONResponse(status_code=401, content={"detail": "Mobil sessiya tugagan yoki noto'g'ri."})
            # Mavjud endpointlar o'zgarmasligi uchun ichki mobil sessiya belgisi uzatiladi.
            _inject_mobile_init_data(request, mobile_token)
            return await call_next(request)
        tg = verify_init_data(init_data)
        if not tg:
            if is_public_district_offers:
                return await call_next(request)
            return JSONResponse(
                status_code=401,
                content={"detail": "Iltimos, ilovani Telegram bot orqali oching."},
            )
    return await call_next(request)


# Kabinet va platforma API'lari (api.py)
from api import router as api_router, public_router as public_api_router
app.include_router(api_router)
app.include_router(public_api_router)

# AI yordamchi (biznes kabinet uchun) — alohida modul
from ai_agent import router as ai_router
app.include_router(ai_router)


@app.get("/api/build")
async def app_build():
    return {"ok": True, "build": APP_BUILD, "stories": True, "story_archive": True, "story_images": True, "story_videos_60s": True, "story_video_upload_fix": True, "railpack_ffmpeg": True, "ai": True, "business_follow_map": True, "home_ads": True, "ad_image_positioning": True, "specialist_portfolio": True, "profile_avatar": True, "business_profile_upgrade": True, "user_avatar_zoom": True, "search_actor_separation": True, "listing_device_media": True, "mobile_auth_foundation": True, "mobile_phone_verification": True, "phone_registration_ui": True, "telegram_registration_ui": True, "dual_registration": True, "password_only_login": True, "single_profile_credentials": True, "separate_profile_registration": True, "business_review_management": True, "problem_orders": True, "strict_payment_flow": True, "preparing_ready_flow": True, "delivery_handoff_flow": True, "in_app_notifications": True, "push_notification_foundation": True, "firebase_push_sender": True, "action_notifications_only": True, "notification_actor_separation": True, "realtime_action_notifications": True, "ready_notification": True, "notification_all_screens": True, "order_number_time": True, "customer_order_number": True, "separate_receipt_items": True, "notification_hide_on_open": True, "public_access": False, "privileged_business_sections": True, "business_subscriptions_demo": True, "district_offers": True, "stories_subscription_independent": True, "pro_follow_map": True, "temporary_privileged_access_only": True, "security_hardening_v1616": True, "demo_district_offers_20": True, "district_offers_slow_carousel": True, "responsive_web_home_v1618": True, "separate_listings_screen": True, "home_advertisement_middle": True, "desktop_layout_polish_v1620": True, "production_foundation_v1621": True, "domain_integration_ready_v1622": True, "frontend_assets_v1623": True, "listing_media_preview_v1624": True, "static_assets_deploy_fix_v1625": True}


@app.get("/healthz", include_in_schema=False)
async def healthcheck():
    """Deploy platformasi uchun shaxsiy ma’lumotsiz liveness javobi."""
    return {"ok": True, "build": APP_BUILD}


@app.get("/readyz", include_in_schema=False)
async def readiness_check():
    """Baza va media papkasi ishlashga tayyorligini tekshiradi."""
    database_ready = False
    try:
        conn = db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        database_ready = True
    except Exception:
        database_ready = False
    uploads_ready = os.path.isdir(UPLOAD_DIR) and os.access(UPLOAD_DIR, os.W_OK)
    payload = {
        "ok": database_ready and uploads_ready,
        "build": APP_BUILD,
        "database": database_ready,
        "uploads": uploads_ready,
    }
    if not payload["ok"]:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get("/api/map-config")
def map_config():
    """Frontend xarita provayderi: OpenStreetMap."""
    return {
        "provider": "openstreetmap",
        "public_token": "",
    }


def _require_privileged_diagnostics(init_data):
    if not PRIVILEGED_DIAGNOSTICS_ENABLED:
        raise HTTPException(404, "Topilmadi.")
    if (init_data or "").startswith("mobile:"):
        conn = db()
        user = mobile_user_from_token(conn, init_data[7:].strip())
        conn.close()
        tg_id = user["tg_id"] if user else None
    else:
        tg = verify_init_data(init_data)
        tg_id = tg.get("id") if tg else None
    if not is_privileged_tg_id(tg_id):
        raise HTTPException(403, "Ruxsat yo'q.")


@app.get("/api/_dbinfo")
async def db_info(x_telegram_init_data: str = Header(default="")):
    """Faqat maxsus egalar uchun shaxsiy ma'lumotsiz diagnostika."""
    _require_privileged_diagnostics(x_telegram_init_data)
    conn = db()
    try:
        return {
            "ok": True,
            "build": APP_BUILD,
            "runtime": safe_runtime_summary(
                db_path=DB_PATH,
                upload_dir=UPLOAD_DIR,
                backup_enabled=DATABASE_BACKUP_ON_START,
            ),
            "integrations": integration_status(),
            "foydalanuvchilar_soni": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "bizneslar_soni": conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0],
            "elonlar_soni": conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0],
        }
    finally:
        conn.close()


@app.get("/api/_setup")
async def manual_setup_requires_post():
    return JSONResponse(status_code=405, content={"detail": "POST talab qilinadi."})


@app.post("/api/_setup")
async def manual_setup(x_telegram_init_data: str = Header(default="")):
    """Maxsus egalar uchun webhookni aniq POST bilan qayta o'rnatish."""
    _require_privileged_diagnostics(x_telegram_init_data)
    result = {"ok": True, "build": APP_BUILD}
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
            "menu_button": {"type": "web_app", "text": "Platforma", "web_app": {"url": BASE_URL}},
        })
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
@app.post("/api/mobile-auth/register/request-code")
async def mobile_register_request_code(request: Request):
    """Yangi akkaunt uchun telefon tasdiqlash kodini tayyorlaydi."""
    body = await request.json()
    phone = normalize_uz_phone(body.get("phone"))
    name = str(body.get("name") or "").strip()[:120]
    role = "business" if body.get("role") == "business" else "user"
    yon = str(body.get("yon") or "").strip()[:120]
    address = str(body.get("address") or "").strip()[:300]
    if not phone:
        raise HTTPException(400, "Telefon raqamini +998XXXXXXXXX ko'rinishida kiriting.")
    if len(name) < 2:
        raise HTTPException(400, "Ism-familiya yoki biznes nomini kiriting.")
    conn = db()
    if conn.execute("SELECT 1 FROM users WHERE phone=? AND role=?", (phone, role)).fetchone():
        conn.close()
        raise HTTPException(409, "Bu telefon raqami bilan shu turdagi profil mavjud. Kirish bo'limidan foydalaning.")
    now = int(time.time())
    recent = conn.execute(
        "SELECT created_at FROM mobile_pending_registrations WHERE phone=? ORDER BY id DESC LIMIT 1",
        (phone,),
    ).fetchone()
    if recent and now - int(recent["created_at"] or 0) < 60:
        wait = 60 - (now - int(recent["created_at"] or 0))
        conn.close()
        raise HTTPException(429, "Yangi kod olish uchun " + str(wait) + " soniya kuting.")
    code = gen_code()
    conn.close()
    await deliver_mobile_code(phone, code, "register")
    conn = db()
    cur = conn.execute(
        """INSERT INTO mobile_pending_registrations
           (phone,name,role,yon,address,code_hash,attempts,max_attempts,created_at,expires_at,verified_at)
           VALUES(?,?,?,?,?,?,0,5,?,?,0)""",
        (phone, name, role, yon, address, mobile_code_hash(phone, code), now, now + MOBILE_CODE_TTL),
    )
    request_id = cur.lastrowid
    conn.commit(); conn.close()
    return {"ok": True, "request_id": request_id, "expires_in": MOBILE_CODE_TTL,
            "resend_after": 60}


@app.post("/api/mobile-auth/register/verify-code")
async def mobile_register_verify_code(request: Request):
    """Telefon kodini tekshiradi, akkaunt yaratadi va mobil token beradi."""
    body = await request.json()
    try:
        request_id = int(body.get("request_id") or 0)
    except Exception:
        request_id = 0
    phone = normalize_uz_phone(body.get("phone"))
    code = "".join(ch for ch in str(body.get("code") or "") if ch.isdigit())
    if not request_id or not phone or len(code) != 6:
        raise HTTPException(400, "Telefon, request_id va 6 xonali kodni to'g'ri kiriting.")
    conn = db(); now = int(time.time())
    row = conn.execute(
        "SELECT * FROM mobile_pending_registrations WHERE id=? AND phone=?",
        (request_id, phone),
    ).fetchone()
    if not row or int(row["verified_at"] or 0):
        conn.close(); raise HTTPException(400, "Ro'yxatdan o'tish so'rovi topilmadi yoki ishlatilgan.")
    if int(row["expires_at"] or 0) <= now:
        conn.close(); raise HTTPException(400, "Tasdiqlash kodi muddati tugagan.")
    if int(row["attempts"] or 0) >= int(row["max_attempts"] or 5):
        conn.close(); raise HTTPException(429, "Kod kiritish urinishlari tugagan. Yangi kod oling.")
    if not hmac.compare_digest(row["code_hash"], mobile_code_hash(phone, code)):
        conn.execute("UPDATE mobile_pending_registrations SET attempts=attempts+1 WHERE id=?", (request_id,))
        conn.commit()
        left = max(0, int(row["max_attempts"] or 5) - int(row["attempts"] or 0) - 1)
        conn.close(); raise HTTPException(400, "Kod noto'g'ri. Qolgan urinish: " + str(left) + ".")
    if conn.execute("SELECT 1 FROM users WHERE phone=? AND role=?", (phone, row["role"])).fetchone():
        conn.close(); raise HTTPException(409, "Bu telefon bilan shu turdagi profil allaqachon yaratilgan.")
    is_business = row["role"] == "business"
    if is_business:
        login = gen_owner_key()
        password = None
        for _ in range(30):
            biz_login = gen_biz_login()
            if not conn.execute("SELECT 1 FROM businesses WHERE biz_login=?", (biz_login,)).fetchone() and not conn.execute("SELECT 1 FROM users WHERE login=?", (biz_login,)).fetchone():
                break
        biz_password = gen_pass()
    else:
        for _ in range(30):
            login = gen_login()
            if not conn.execute("SELECT 1 FROM users WHERE login=?", (login,)).fetchone():
                break
        password = gen_pass()
        biz_login = None
        biz_password = None
    cur = conn.execute(
        """INSERT INTO users(tg_id,username,login,pass_hash,role,name,phone,created_at)
           VALUES(NULL,'',?,?,?,?,?,?)""",
        (login, hash_password(password) if password else "", row["role"], row["name"], phone, now),
    )
    user_id = cur.lastrowid
    if is_business:
        conn.execute(
            """INSERT INTO businesses(user_id,name,yon,address,phone,biz_login,biz_pass_hash,status,created_at)
               VALUES(?,?,?,?,?,?,?,'active',?)""",
            (user_id, row["name"], row["yon"], row["address"], phone, biz_login, hash_password(biz_password), now),
        )
    token = secrets.token_urlsafe(48)
    expires_at = now + MOBILE_SESSION_TTL
    conn.execute("UPDATE mobile_pending_registrations SET verified_at=? WHERE id=?", (now, request_id))
    conn.execute(
        """INSERT INTO mobile_sessions
           (user_id,token_hash,device_name,created_at,expires_at,last_used_at,revoked_at)
           VALUES(?,?,?,?,?,?,0)""",
        (user_id, hashlib.sha256(token.encode()).hexdigest(),
         str(body.get("device_name") or "Mobil qurilma")[:120], now, expires_at, now),
    )
    conn.commit(); conn.close()
    return {"ok": True, "access_token": token, "token_type": "Bearer",
            "expires_in": MOBILE_SESSION_TTL, "expires_at": expires_at,
            "login": biz_login if is_business else login,
            "password": biz_password if is_business else password,
            "biz_login": biz_login, "biz_password": biz_password, "role": row["role"],
            "user": {"id": user_id, "name": row["name"], "role": row["role"]}}


@app.post("/api/mobile-auth/request-code")
async def mobile_request_code(request: Request):
    """Mavjud akkaunt telefoniga 6 xonali kirish kodi tayyorlaydi."""
    body = await request.json()
    phone = normalize_uz_phone(body.get("phone"))
    if not phone:
        raise HTTPException(400, "Telefon raqamini +998XXXXXXXXX ko'rinishida kiriting.")
    conn = db()
    user = find_user_by_phone(conn, phone)
    if not user:
        conn.close()
        raise HTTPException(404, "Bu telefon raqamiga biriktirilgan akkaunt topilmadi.")
    now = int(time.time())
    recent = conn.execute(
        "SELECT created_at FROM mobile_verification_codes WHERE phone=? AND purpose='login' ORDER BY id DESC LIMIT 1",
        (phone,),
    ).fetchone()
    if recent and now - int(recent["created_at"] or 0) < 60:
        wait = 60 - (now - int(recent["created_at"] or 0))
        conn.close()
        raise HTTPException(429, "Yangi kod olish uchun " + str(wait) + " soniya kuting.")
    code = gen_code()
    conn.close()
    await deliver_mobile_code(phone, code, "login")
    conn = db()
    cur = conn.execute(
        """INSERT INTO mobile_verification_codes
           (user_id,phone,code_hash,purpose,attempts,max_attempts,created_at,expires_at,verified_at)
           VALUES(?,?,?,'login',0,5,?,?,0)""",
        (user["id"], phone, mobile_code_hash(phone, code), now, now + MOBILE_CODE_TTL),
    )
    request_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"ok": True, "request_id": request_id, "expires_in": MOBILE_CODE_TTL,
            "resend_after": 60}


@app.post("/api/mobile-auth/verify-code")
async def mobile_verify_code(request: Request):
    """Bir martalik kodni tekshiradi va 30 kunlik mobil token beradi."""
    body = await request.json()
    try:
        request_id = int(body.get("request_id") or 0)
    except Exception:
        request_id = 0
    phone = normalize_uz_phone(body.get("phone"))
    code = "".join(ch for ch in str(body.get("code") or "") if ch.isdigit())
    if not request_id or not phone or len(code) != 6:
        raise HTTPException(400, "Telefon, request_id va 6 xonali kodni to'g'ri kiriting.")
    conn = db()
    row = conn.execute(
        "SELECT * FROM mobile_verification_codes WHERE id=? AND phone=? AND purpose='login'",
        (request_id, phone),
    ).fetchone()
    now = int(time.time())
    if not row or int(row["verified_at"] or 0):
        conn.close()
        raise HTTPException(400, "Tasdiqlash so'rovi topilmadi yoki ishlatilgan.")
    if int(row["expires_at"] or 0) <= now:
        conn.close()
        raise HTTPException(400, "Tasdiqlash kodi muddati tugagan.")
    if int(row["attempts"] or 0) >= int(row["max_attempts"] or 5):
        conn.close()
        raise HTTPException(429, "Kod kiritish urinishlari tugagan. Yangi kod oling.")
    if not hmac.compare_digest(row["code_hash"], mobile_code_hash(phone, code)):
        conn.execute("UPDATE mobile_verification_codes SET attempts=attempts+1 WHERE id=?", (request_id,))
        conn.commit()
        left = max(0, int(row["max_attempts"] or 5) - int(row["attempts"] or 0) - 1)
        conn.close()
        raise HTTPException(400, "Kod noto'g'ri. Qolgan urinish: " + str(left) + ".")

    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    device_name = str(body.get("device_name") or "Mobil qurilma").strip()[:120]
    expires_at = now + MOBILE_SESSION_TTL
    conn.execute("UPDATE mobile_verification_codes SET verified_at=? WHERE id=?", (now, request_id))
    conn.execute(
        """INSERT INTO mobile_sessions
           (user_id,token_hash,device_name,created_at,expires_at,last_used_at,revoked_at)
           VALUES(?,?,?,?,?,?,0)""",
        (row["user_id"], token_hash, device_name, now, expires_at, now),
    )
    user = conn.execute("SELECT id,name,role FROM users WHERE id=?", (row["user_id"],)).fetchone()
    conn.commit()
    conn.close()
    return {"ok": True, "access_token": token, "token_type": "Bearer",
            "expires_in": MOBILE_SESSION_TTL, "expires_at": expires_at,
            "user": {"id": user["id"], "name": user["name"], "role": user["role"]}}


@app.post("/api/mobile-auth/logout")
async def mobile_logout(request: Request):
    auth = (request.headers.get("authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Mobil token topilmadi.")
    token_hash = hashlib.sha256(auth[7:].strip().encode()).hexdigest()
    conn = db()
    cur = conn.execute(
        "UPDATE mobile_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at=0",
        (int(time.time()), token_hash),
    )
    conn.commit()
    conn.close()
    if not cur.rowcount:
        raise HTTPException(401, "Mobil sessiya topilmadi.")
    return {"ok": True}


@app.post("/api/password-auth/login")
async def password_auth_login(request: Request):
    """Oddiy yoki biznes login-paroli orqali 30 kunlik xavfsiz sessiya beradi."""
    body = await request.json()
    login = str(body.get("login") or "").strip().lower()
    password = str(body.get("password") or "")
    if len(login) < 3 or len(password) < 4:
        raise HTTPException(400, "Login va parolni kiriting.")
    conn = db(); user = None; login_role = "user"
    user_row = conn.execute("SELECT * FROM users WHERE lower(login)=?", (login,)).fetchone()
    if user_row and check_password(password, user_row["pass_hash"] or ""):
        user = user_row
    else:
        biz = conn.execute("SELECT * FROM businesses WHERE lower(biz_login)=? AND status='active'", (login,)).fetchone()
        if biz and check_password(password, biz["biz_pass_hash"] or ""):
            user = conn.execute("SELECT * FROM users WHERE id=?", (biz["user_id"],)).fetchone()
            login_role = "business"
    if not user:
        # Login mavjud yoki yo'qligini oshkor qilmaymiz.
        conn.close(); raise HTTPException(401, "Login yoki parol noto'g'ri.")
    now = int(time.time()); token = secrets.token_urlsafe(48); expires_at = now + MOBILE_SESSION_TTL
    conn.execute(
        """INSERT INTO mobile_sessions(user_id,token_hash,device_name,created_at,expires_at,last_used_at,revoked_at)
           VALUES(?,?,?,?,?,?,0)""",
        (user["id"], hashlib.sha256(token.encode()).hexdigest(),
         str(body.get("device_name") or "Qurilma")[:120], now, expires_at, now),
    )
    conn.commit(); conn.close()
    return {"ok": True, "access_token": token, "token_type": "Bearer",
            "expires_in": MOBILE_SESSION_TTL, "expires_at": expires_at,
            "login_role": login_role,
            "user": {"id": user["id"], "name": user["name"], "role": login_role}}


@app.get("/api/catalog")
async def get_catalog():
    return {"yonalishlar": CATALOG, "elon_toifalari": LISTING_CATS}


# ---------- Login/parol generatori ----------
def gen_login():
    return "user" + "".join(secrets.choice("0123456789") for _ in range(6))

def gen_biz_login():
    return "biz" + "".join(secrets.choice("0123456789") for _ in range(6))

def gen_owner_key():
    """Biznes egasining faqat ichki bog'lanish kaliti; kirish uchun ishlamaydi."""
    return "owner_" + secrets.token_hex(12)

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
    username = (body.get("username") or tg.get("username") or "").strip().lstrip("@")
    raw_phone = (body.get("phone") or "").strip()
    phone = normalize_uz_phone(raw_phone) if raw_phone else ""
    if raw_phone and not phone:
        raise HTTPException(400, "Telefon raqamini +998XXXXXXXXX ko'rinishida kiriting.")

    conn = db()
    existing = current_user(conn, tg["id"])

    # Oddiy va biznes profillar bitta users yozuviga qo'shilmaydi.
    if existing:
        conn.close()
        same = (existing["role"] or "user") == role
        if same:
            raise HTTPException(400, "Bu Telegram akkauntida tanlangan profil allaqachon mavjud. Login-parol orqali kiring.")
        raise HTTPException(409, "Oddiy va biznes profil alohida bo'lishi kerak. Ikkinchi profilni telefon orqali alohida ro'yxatdan o'tkazing.")

    # Telefon orqali avval ochilgan akkauntni Telegram orqali takroran yaratmaymiz.
    if phone:
        phone_owner = conn.execute("SELECT 1 FROM users WHERE phone=? AND role=?", (phone, role)).fetchone()
        if phone_owner:
            conn.close()
            raise HTTPException(409, "Bu telefon raqami bilan shu turdagi profil mavjud. Login-parol orqali kiring.")

    # Oddiy profilga login beriladi; biznes egasining users yozuvi faqat ichki bog'lanishdir.
    if role == "business":
        login = gen_owner_key()
        password = None
    else:
        for _ in range(20):
            login = gen_login()
            if not conn.execute("SELECT id FROM users WHERE login=?", (login,)).fetchone():
                break
        password = gen_pass()

    now = int(time.time())
    district = safe_district_display(body.get("district"))
    cur = conn.execute(
        "INSERT INTO users(tg_id, username, login, pass_hash, role, name, phone, region, district, district_key, mahalla, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (tg["id"], username, login, hash_password(password) if password else "", role, name,
         phone, (body.get("region") or "").strip(),
         district, canonical_district_key(district), (body.get("mahalla") or "").strip(), now),
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

    # Tanlangan profilga tegishli yagona login-parolni ko'rsatamiz.
    shown_login = biz_login if role == "business" else login
    shown_password = biz_pass if role == "business" else password
    cabinet_name = "Biznes kabinetingiz" if role == "business" else "Kabinetingiz"
    msg = ("Platformaga xush kelibsiz! \u2705\n\n" + cabinet_name + " uchun kirish ma'lumotlari:\n\n"
           "\U0001F511 Login: " + shown_login + "\n"
           "\U0001F510 Parol: " + shown_password + "\n\n"
           "Bu ma'lumotlarni saqlab qo'ying. Boshqa qurilmadan kirganda shu login va parol kerak bo'ladi.")
    await tg_call("sendMessage", {"chat_id": tg["id"], "text": msg})
    # Ro'yxatdan o'tgan qurilma to'g'ridan-to'g'ri kiradi
    return {"ok": True, "role": role, "login": shown_login, "password": shown_password,
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
    conn = db()
    if (x_telegram_init_data or "").startswith("mobile:"):
        user = mobile_user_from_token(conn, x_telegram_init_data[7:], touch=True)
    else:
        tg = require_tg(x_telegram_init_data)
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
        "is_privileged": is_privileged_tg_id(user["tg_id"]),
    }
    # Biznes ma'lumotini rol nima bo'lishidan qat'i nazar qaytaramiz (agar businesses yozuvi bo'lsa)
    biz = conn.execute("SELECT * FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
    result["has_business"] = bool(biz)
    if biz:
        _bk = biz.keys()
        result["business"] = {
            "id": biz["id"], "name": biz["name"], "yon": biz["yon"], "tur": biz["tur"],
            "descr": biz["descr"], "phone": biz["phone"], "telegram": biz["telegram"],
            "logo_file": biz["logo_file"] if "logo_file" in _bk else "",
            "logo_x": biz["logo_x"] if "logo_x" in _bk else 50,
            "logo_y": biz["logo_y"] if "logo_y" in _bk else 50,
            "logo_zoom": biz["logo_zoom"] if "logo_zoom" in _bk else 1,
            "work_hours": biz["work_hours"], "address": biz["address"], "status": biz["status"],
            "lat": biz["lat"], "lng": biz["lng"],
            # v1422: to'lov ma'lumotlari (ustunlar bo'lmasa ham xavfsiz)
            "pay_card": biz["pay_card"] if "pay_card" in _bk else "",
            "pay_holder": biz["pay_holder"] if "pay_holder" in _bk else "",
            "pay_qr": biz["pay_qr"] if "pay_qr" in _bk else "",
            "username": biz["username"] if "username" in _bk else "",
            "director": biz["director"] if "director" in _bk else "",
            "inn": biz["inn"] if "inn" in _bk else "",
            "biz_login": biz["biz_login"] if "biz_login" in _bk else "",
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


@app.get("/profile-media/{owner_kind}/{owner_id}")
async def profile_media(owner_kind: str, owner_id: int):
    """Avatar/logotipni doimiy SQLite manbasidan beradi; xarita <img> so'rovi uchun ochiq."""
    from fastapi.responses import Response
    if owner_kind not in ("user", "business"):
        raise HTTPException(404, "Rasm topilmadi.")
    conn = db()
    row = conn.execute(
        "SELECT mime_type,content,updated_at FROM profile_images WHERE owner_kind=? AND owner_id=?",
        (owner_kind, owner_id),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Rasm topilmadi.")
    return Response(content=row["content"], media_type=row["mime_type"], headers={"Cache-Control": "public, max-age=31536000, immutable"})


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


# ---------- Yuklangan fayllar ----------
validate_runtime_config(
    db_path=DB_PATH,
    upload_dir=UPLOAD_DIR,
    backup_dir=BACKUP_DIR,
)
validate_domain_config()
os.makedirs(UPLOAD_DIR, exist_ok=True)
print("UPLOAD_DIR:", os.path.abspath(UPLOAD_DIR))
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ---------- Mini App (eng oxirida) ----------
app.mount("/", StaticFiles(directory="static", html=True), name="static")

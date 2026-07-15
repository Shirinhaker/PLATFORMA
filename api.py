"""
Platforma — kabinet va umumiy API'lar.

Bo'limlar:
  PROFIL        - shaxsiy ma'lumotlarni tahrirlash
  MUTAXASISLIK  - "Mutaxasisligim va xizmatlarim" (davlat ishchisi rejimi bilan)
  BIZNES        - biznes profili va mahsulot/xizmatlar
  E'LONLAR      - joylash (rasm/video Telegram file_id bilan), tahrirlash, ko'rinish turi
  OBUNA         - follow/followers (odamga ham, biznesga ham)
  SAQLANGANLAR  - e'lon va bizneslarni saqlash
  BUYURTMALAR   - buyurtma/navbatlar (user/business aktyorlar bo'yicha)
  QARZ DAFTARI  - biznes kabineti bo'limi
  QIDIRUV       - mahsulot + e'lon + mutaxasis + biznes (hammasi birga)
  SAHIFALAR     - biznes sahifasi va mutaxasis (odam) sahifasi
"""

import json
import time
import re
import os
import math
import calendar
import secrets
import hashlib

from fastapi import APIRouter, Request, Header, HTTPException

from database import db

router = APIRouter(prefix="/api")


# ---------- Yordamchilar ----------
def _tg(init_data):
    from main import require_tg
    return require_tg(init_data)


def _staff_session(conn, init_data):
    """init_data 'staff:<token>' bo'lsa — faol xodim sessiyasini qaytaradi, aks holda None."""
    if not (init_data or "").startswith("staff:"):
        return None
    token = init_data[6:].strip()
    if not token:
        return None
    try:
        sess = conn.execute("SELECT * FROM staff_sessions WHERE token=?", (token,)).fetchone()
    except Exception:
        return None
    if not sess:
        return None
    st = conn.execute("SELECT * FROM staff WHERE id=?", (sess["staff_id"],)).fetchone()
    if not st or not (_row_val(st, "can_login", 0) or 0) or (st["status"] or "") != "active":
        return None
    return st


def _staff_ctx(conn, init_data):
    """Xodim bo'lsa (staff_row, biz, owner_user) qaytaradi; bo'lmasa None."""
    st = _staff_session(conn, init_data)
    if not st:
        return None
    biz = conn.execute("SELECT * FROM businesses WHERE id=?", (st["business_id"],)).fetchone()
    if not biz:
        raise HTTPException(404, "Do'kon topilmadi.")
    owner = conn.execute("SELECT * FROM users WHERE id=?", (biz["user_id"],)).fetchone()
    return st, biz, owner


def require_user(conn, init_data):
    """Ro'yxatdan o'tgan foydalanuvchini (yoki xodim bo'lsa — do'kon egasini) talab qiladi."""
    ctx = _staff_ctx(conn, init_data)
    if ctx:
        return ctx[2]  # do'kon egasi (owner)
    if (init_data or "").startswith("mobile:"):
        token = init_data[7:].strip()
        if not token:
            raise HTTPException(401, "Mobil sessiya tokeni topilmadi.")
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = int(time.time())
        sess = conn.execute(
            "SELECT * FROM mobile_sessions WHERE token_hash=? AND revoked_at=0 AND expires_at>?",
            (token_hash, now),
        ).fetchone()
        if not sess:
            raise HTTPException(401, "Mobil sessiya tugagan yoki bekor qilingan.")
        user = conn.execute("SELECT * FROM users WHERE id=?", (sess["user_id"],)).fetchone()
        if not user:
            raise HTTPException(401, "Foydalanuvchi topilmadi.")
        conn.execute("UPDATE mobile_sessions SET last_used_at=? WHERE id=?", (now, sess["id"]))
        conn.commit()
        return user
    tg = _tg(init_data)
    user = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg["id"],)).fetchone()
    if not user:
        raise HTTPException(401, "Avval ro'yxatdan o'ting yoki tizimga kiring.")
    return user


def require_business(conn, init_data):
    """Biznes akkaunt yoki xodim sessiyasi. (owner_user, biz) qaytaradi."""
    ctx = _staff_ctx(conn, init_data)
    if ctx:
        return ctx[2], ctx[1]  # (owner, biz)
    user = require_user(conn, init_data)
    if user["role"] != "business":
        raise HTTPException(403, "Bu bo'lim faqat biznes akkauntlar uchun.")
    biz = conn.execute("SELECT * FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
    if not biz:
        raise HTTPException(404, "Biznes profili topilmadi.")
    return user, biz


def _staff_perms_of(conn, init_data):
    """Xodim bo'lsa — ruxsatlar ro'yxati; do'kon egasi/oddiy foydalanuvchi bo'lsa None (to'liq huquq)."""
    st = _staff_session(conn, init_data)
    if not st:
        return None
    return _perms_parse(_row_val(st, "perms", "") or "")


def deny_staff(conn, init_data, section="Bu bo'lim"):
    """Sezgir bo'limlar: xodimlarga umuman yopiq (faqat do'kon egasi)."""
    if _staff_session(conn, init_data):
        raise HTTPException(403, section + " faqat do'kon egasi uchun.")


def need_perm(conn, init_data, perm):
    """Xodim bo'lsa — shu ruxsat borligini tekshiradi; egasi bo'lsa — o'tadi."""
    perms = _staff_perms_of(conn, init_data)
    if perms is None:
        return  # egasi — to'liq huquq
    if perm not in perms:
        raise HTTPException(403, "Bu bo'limga ruxsatingiz yo'q.")


def follower_count(conn, kind, target_id):
    """Oddiy foydalanuvchi va biznes kabinet obunalarining jami."""
    user_count = conn.execute(
        "SELECT COUNT(*) c FROM follows WHERE target_kind=? AND target_id=?", (kind, target_id)
    ).fetchone()["c"]
    business_count = conn.execute(
        "SELECT COUNT(*) c FROM business_follows WHERE target_kind=? AND target_id=?", (kind, target_id)
    ).fetchone()["c"]
    return int(user_count or 0) + int(business_count or 0)


def following_count(conn, user_id):
    return conn.execute(
        "SELECT COUNT(*) c FROM follows WHERE follower_id=?", (user_id,)
    ).fetchone()["c"]


def business_following_count(conn, business_id):
    if not business_id:
        return 0
    return conn.execute(
        "SELECT COUNT(*) c FROM business_follows WHERE business_id=?", (business_id,)
    ).fetchone()["c"]


def is_following(conn, user_id, kind, target_id, actor_type="user", business_id=None):
    if (actor_type or "user").strip().lower() == "business":
        if not business_id:
            return False
        return bool(conn.execute(
            "SELECT 1 FROM business_follows WHERE business_id=? AND target_kind=? AND target_id=?",
            (business_id, kind, target_id),
        ).fetchone())
    if not user_id:
        return False
    return bool(conn.execute(
        "SELECT 1 FROM follows WHERE follower_id=? AND target_kind=? AND target_id=?",
        (user_id, kind, target_id),
    ).fetchone())


def optional_user(conn, init_data):
    """Kirgan bo'lsa user, bo'lmasa None (mehmon rejimi)."""
    if (init_data or "").startswith("mobile:"):
        try:
            return require_user(conn, init_data)
        except HTTPException:
            return None
    try:
        tg = _tg(init_data)
    except HTTPException:
        return None
    return conn.execute("SELECT * FROM users WHERE tg_id=?", (tg["id"],)).fetchone()


def resolve_actor(conn, user, actor_type="user"):
    """
    Hozirgi amal qaysi kabinet nomidan qilinyapti: oddiy user yoki biznes.
    Frontend yuborgan actor_type tekshiriladi; business bo'lsa, biznes shu userniki bo'lishi shart.
    """
    at = (actor_type or "user").strip().lower()
    if at not in ("user", "business"):
        raise HTTPException(400, "Kabinet turi noto'g'ri.")
    if at == "user":
        return {"type": "user", "user_id": user["id"], "business_id": None, "business": None}

    biz = conn.execute("SELECT * FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
    if not biz:
        raise HTTPException(403, "Biznes kabinet topilmadi.")
    try:
        _ensure_pay_columns(conn)
        conn.commit()
        biz = conn.execute("SELECT * FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
    except Exception:
        pass
    return {"type": "business", "user_id": user["id"], "business_id": biz["id"], "business": biz}


def actor_from_body(conn, user, body):
    return resolve_actor(conn, user, (body or {}).get("actor_type") or "user")


def listing_to_dict(conn, r, with_media=True):
    d = {
        "id": r["id"], "cat": r["cat"], "title": r["title"], "price": r["price"],
        "descr": r["descr"], "address": r["address"], "lat": r["lat"], "lng": r["lng"],
        "visibility": r["visibility"], "status": r["status"], "created_at": r["created_at"],
        "user_id": r["user_id"], "business_id": r["business_id"],
    }
    if with_media:
        media = conn.execute(
            "SELECT tg_file_id, mtype FROM listing_media WHERE listing_id=? ORDER BY pos", (r["id"],)
        ).fetchall()
        d["media"] = [{"file_id": m["tg_file_id"], "type": m["mtype"]} for m in media]
    owner = conn.execute("SELECT name FROM users WHERE id=?", (r["user_id"],)).fetchone()
    d["owner_name"] = owner["name"] if owner else ""
    return d


# ====================================================================
# PROFIL
# ====================================================================
def _ensure_user_username(conn):
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "location_exact" not in cols:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN location_exact INTEGER DEFAULT 0")
        except Exception:
            pass
    if "pub_username" not in cols:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN pub_username TEXT DEFAULT ''")
        except Exception:
            pass
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_pub_username "
                     "ON users(lower(pub_username)) WHERE COALESCE(pub_username,'')<>''")
    except Exception:
        pass


@router.put("/profile")
async def update_profile(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Profil")
    _ensure_user_username(conn)
    user = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
    b = await request.json()
    # Yuborilmagan maydonlar eskisicha qoladi (bo'sh yozilmaydi)
    def keep(key, old):
        return b[key].strip() if (key in b and isinstance(b[key], str)) else old
    new_name = keep("name", user["name"])
    new_phone = keep("phone", user["phone"])
    new_region = keep("region", user["region"])
    new_district = keep("district", user["district"])
    new_mahalla = keep("mahalla", user["mahalla"])
    # lat/lng: yuborilgan bo'lsa yangilanadi, yuborilmasa eskisi qoladi.
    # Bu oddiy foydalanuvchining bosh xaritadagi "Mening manzilim" markerini tiklash uchun kerak.
    new_lat = b["lat"] if ("lat" in b and b["lat"] is not None) else user["lat"]
    new_lng = b["lng"] if ("lng" in b and b["lng"] is not None) else user["lng"]
    old_exact = int(_row_val(user, "location_exact", 0) or 0)
    new_exact = 1 if str(b.get("location_exact", old_exact)).lower() in ("1", "true") else 0
    # pub_username (ixtiyoriy, band emasligi tekshiriladi)
    new_pubu = _row_val(user, "pub_username", "") or ""
    if "pub_username" in b:
        cand = _norm_username(b.get("pub_username"))
        err = _username_error(cand)
        if err:
            conn.close()
            raise HTTPException(400, err)
        if cand:
            taken = conn.execute("SELECT id FROM users WHERE lower(pub_username)=? AND id<>?", (cand, user["id"])).fetchone()
            if taken:
                conn.close()
                raise HTTPException(400, "Bu username band. Boshqasini tanlang.")
        new_pubu = cand
    conn.execute(
        "UPDATE users SET name=?, phone=?, region=?, district=?, mahalla=?, lat=?, lng=?, location_exact=?, pub_username=? WHERE id=?",
        (new_name or user["name"], new_phone, new_region, new_district, new_mahalla, new_lat, new_lng, new_exact, new_pubu, user["id"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/profile")
async def get_profile(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    _ensure_user_username(conn)
    user = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
    result = {
        "id": user["id"], "role": user["role"], "name": user["name"], "phone": user["phone"],
        "region": user["region"], "district": user["district"], "mahalla": user["mahalla"],
        "lat": user["lat"], "lng": user["lng"], "location_exact": bool(_row_val(user, "location_exact", 0)),
        "avatar_file": _row_val(user, "avatar_file", "") or "",
        "avatar_x": float(_row_val(user, "avatar_x", 50) or 50),
        "avatar_y": float(_row_val(user, "avatar_y", 50) or 50),
        "avatar_zoom": float(_row_val(user, "avatar_zoom", 1) or 1),
        "pub_username": _row_val(user, "pub_username", "") or "",
        "followers": follower_count(conn, "user", user["id"]),
        "following": following_count(conn, user["id"]),
    }
    if user["role"] == "business":
        biz = conn.execute("SELECT * FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
        if biz:
            result["business_followers"] = follower_count(conn, "business", biz["id"])
            result["business_following"] = business_following_count(conn, biz["id"])
            result["business_id"] = biz["id"]
    conn.close()
    return result


@router.post("/profile/avatar")
async def upload_profile_avatar(request: Request, x_telegram_init_data: str = Header(default="")):
    """Oddiy foydalanuvchi profil rasmini yuklaydi va users.avatar_file ga saqlaydi."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Profil rasmi")

    ctype = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    allowed = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    if ctype not in allowed:
        conn.close()
        raise HTTPException(400, "Profil rasmi JPG, PNG, WEBP yoki GIF formatida bo'lsin.")

    raw = await request.body()
    if not raw:
        conn.close()
        raise HTTPException(400, "Rasm fayli topilmadi.")
    if len(raw) > 8 * 1024 * 1024:
        conn.close()
        raise HTTPException(400, "Profil rasmi hajmi 8 MB dan oshmasin.")

    from main import UPLOAD_DIR
    folder = os.path.join(UPLOAD_DIR, "avatars")
    os.makedirs(folder, exist_ok=True)
    safe_name = (
        "avatar_" + str(user["id"]) + "_" + str(int(time.time())) + "_" +
        secrets.token_hex(8) + allowed[ctype]
    )
    full_path = os.path.join(folder, safe_name)
    with open(full_path, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())

    avatar_url = "/profile-media/user/" + str(user["id"]) + "?v=" + str(int(time.time()))
    old_avatar = _row_val(user, "avatar_file", "") or ""
    conn.execute(
        "INSERT INTO profile_images(owner_kind,owner_id,mime_type,content,updated_at) VALUES('user',?,?,?,?) "
        "ON CONFLICT(owner_kind,owner_id) DO UPDATE SET mime_type=excluded.mime_type,content=excluded.content,updated_at=excluded.updated_at",
        (user["id"], ctype, raw, int(time.time())),
    )
    conn.execute("UPDATE users SET avatar_file=?, avatar_x=50, avatar_y=50, avatar_zoom=1 WHERE id=?", (avatar_url, user["id"]))
    conn.commit()
    conn.close()

    # Faqat o'zimizning eski avatar faylimizni ehtiyotkorlik bilan tozalaymiz.
    if old_avatar.startswith("/uploads/avatars/") and old_avatar != avatar_url:
        old_name = os.path.basename(old_avatar)
        old_path = os.path.join(folder, old_name)
        try:
            if os.path.isfile(old_path):
                os.remove(old_path)
        except Exception:
            pass

    return {"ok": True, "avatar_file": avatar_url}


@router.put("/profile/avatar-position")
async def update_profile_avatar_position(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Profil rasmi")
    b = await request.json()
    try:
        x = max(0.0, min(100.0, float(b.get("x", 50))))
        y = max(0.0, min(100.0, float(b.get("y", 50))))
        zoom = max(1.0, min(3.0, float(b.get("zoom", 1))))
    except Exception:
        conn.close()
        raise HTTPException(400, "Rasm joylashuvi noto'g'ri.")
    conn.execute("UPDATE users SET avatar_x=?, avatar_y=?, avatar_zoom=? WHERE id=?", (x, y, zoom, user["id"]))
    conn.commit(); conn.close()
    return {"ok": True, "avatar_x": x, "avatar_y": y, "avatar_zoom": zoom}


@router.post("/business/logo")
async def upload_business_logo(request: Request, x_telegram_init_data: str = Header(default="")):
    """Biznes profil rasmini yuklaydi va businesses.logo_file ga saqlaydi."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Biznes rasmi")

    ctype = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    allowed = {
        "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
        "image/webp": ".webp", "image/gif": ".gif",
    }
    if ctype not in allowed:
        conn.close()
        raise HTTPException(400, "Biznes rasmi JPG, PNG, WEBP yoki GIF formatida bo'lsin.")
    raw = await request.body()
    if not raw:
        conn.close()
        raise HTTPException(400, "Rasm fayli topilmadi.")
    if len(raw) > 8 * 1024 * 1024:
        conn.close()
        raise HTTPException(400, "Biznes rasmi hajmi 8 MB dan oshmasin.")

    from main import UPLOAD_DIR
    folder = os.path.join(UPLOAD_DIR, "business_logos")
    os.makedirs(folder, exist_ok=True)
    safe_name = "business_" + str(biz["id"]) + "_" + str(int(time.time())) + "_" + secrets.token_hex(8) + allowed[ctype]
    full_path = os.path.join(folder, safe_name)
    with open(full_path, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())

    logo_url = "/profile-media/business/" + str(biz["id"]) + "?v=" + str(int(time.time()))
    old_logo = _row_val(biz, "logo_file", "") or ""
    conn.execute(
        "INSERT INTO profile_images(owner_kind,owner_id,mime_type,content,updated_at) VALUES('business',?,?,?,?) "
        "ON CONFLICT(owner_kind,owner_id) DO UPDATE SET mime_type=excluded.mime_type,content=excluded.content,updated_at=excluded.updated_at",
        (biz["id"], ctype, raw, int(time.time())),
    )
    conn.execute("UPDATE businesses SET logo_file=?, logo_x=50, logo_y=50, logo_zoom=1 WHERE id=?", (logo_url, biz["id"]))
    conn.commit()
    conn.close()

    if old_logo.startswith("/uploads/business_logos/") and old_logo != logo_url:
        try:
            old_path = os.path.join(folder, os.path.basename(old_logo))
            if os.path.isfile(old_path):
                os.remove(old_path)
        except Exception:
            pass
    return {"ok": True, "logo_file": logo_url}


@router.put("/business/logo-position")
async def update_business_logo_position(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Biznes rasmi")
    b = await request.json()
    try:
        x = max(0.0, min(100.0, float(b.get("x", 50))))
        y = max(0.0, min(100.0, float(b.get("y", 50))))
        zoom = max(1.0, min(3.0, float(b.get("zoom", 1))))
    except Exception:
        conn.close()
        raise HTTPException(400, "Rasm joylashuvi noto'g'ri.")
    conn.execute("UPDATE businesses SET logo_x=?, logo_y=?, logo_zoom=? WHERE id=?", (x, y, zoom, biz["id"]))
    conn.commit(); conn.close()
    return {"ok": True, "logo_x": x, "logo_y": y, "logo_zoom": zoom}


# ====================================================================
# MUTAXASSISLIGIM — profil, hujjatlar, xizmat/mahsulot va portfolio
# ====================================================================
def _ensure_specialist_content_tables(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS specialist_credentials("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
        "file_url TEXT NOT NULL, pos INTEGER DEFAULT 0, created_at INTEGER NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sp_credentials_user ON specialist_credentials(user_id, pos, id)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS specialist_offers("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
        "kind TEXT NOT NULL DEFAULT 'service', name TEXT NOT NULL, price TEXT DEFAULT '', "
        "note TEXT DEFAULT '', photo_file TEXT DEFAULT '', created_at INTEGER NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sp_offers_user ON specialist_offers(user_id, created_at, id)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS specialist_portfolio("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
        "media_type TEXT NOT NULL DEFAULT 'photo', file_url TEXT NOT NULL, created_at INTEGER NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sp_portfolio_user ON specialist_portfolio(user_id, created_at, id)")


def _specialist_content(conn, user_id):
    _ensure_specialist_content_tables(conn)
    credentials = conn.execute(
        "SELECT id, file_url, pos, created_at FROM specialist_credentials WHERE user_id=? ORDER BY pos, id",
        (user_id,),
    ).fetchall()
    offers = conn.execute(
        "SELECT id, kind, name, price, note, photo_file, created_at FROM specialist_offers "
        "WHERE user_id=? ORDER BY created_at, id",
        (user_id,),
    ).fetchall()
    portfolio = conn.execute(
        "SELECT id, media_type, file_url, created_at FROM specialist_portfolio "
        "WHERE user_id=? ORDER BY created_at, id",
        (user_id,),
    ).fetchall()
    return {
        "credentials": [dict(r) for r in credentials],
        "offers": [dict(r) for r in offers],
        "portfolio": [dict(r) for r in portfolio],
    }


def _specialist_upload_kind(ctype, allow_video=False):
    images = {
        "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
        "image/webp": ".webp", "image/gif": ".gif",
    }
    videos = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
    if ctype in images:
        return "photo", images[ctype]
    if allow_video and ctype in videos:
        return "video", videos[ctype]
    return None, None


async def _save_specialist_raw(request: Request, user_id: int, prefix: str, allow_video=False, max_mb=8):
    ctype = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    mtype, ext = _specialist_upload_kind(ctype, allow_video=allow_video)
    if not ext:
        msg = "Faqat JPG, PNG yoki WEBP rasm yuboring."
        if allow_video:
            msg = "Faqat JPG, PNG, WEBP rasm yoki MP4/WEBM video yuboring."
        raise HTTPException(400, msg)
    raw = await request.body()
    if not raw:
        raise HTTPException(400, "Fayl topilmadi.")
    if len(raw) > max_mb * 1024 * 1024:
        raise HTTPException(400, "Fayl hajmi %s MB dan oshmasin." % max_mb)
    from main import UPLOAD_DIR
    folder = os.path.join(UPLOAD_DIR, "specialists")
    os.makedirs(folder, exist_ok=True)
    safe_name = "%s_%s_%s_%s%s" % (prefix, user_id, int(time.time()), secrets.token_hex(6), ext)
    path = os.path.join(folder, safe_name)
    with open(path, "wb") as f:
        f.write(raw)
    return mtype, "/uploads/specialists/" + safe_name


@router.get("/specialist")
async def get_specialist(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    _ensure_specialist_content_tables(conn)
    sp = conn.execute("SELECT * FROM specialists WHERE user_id=?", (user["id"],)).fetchone()
    content = _specialist_content(conn, user["id"])
    # Kabinetdagi fikrlar soni yuqoridagi tugmada ko'rsatiladi.
    try:
        _ensure_reviews(conn)
        review_count = conn.execute(
            "SELECT COUNT(*) c FROM reviews WHERE target_kind='specialist' AND target_id=?", (user["id"],)
        ).fetchone()["c"]
    except Exception:
        review_count = 0
    conn.close()
    if not sp:
        return {"exists": False, "visible": False, "lat": None, "lng": None,
                "review_count": review_count, **content}
    return {
        "exists": True, "kasb": sp["kasb"] or "", "descr": sp["descr"] or "",
        "visible": bool(sp["visible"]), "lat": sp["lat"], "lng": sp["lng"],
        "review_count": review_count, **content,
    }


@router.put("/specialist")
async def update_specialist(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    b = await request.json()
    kasb = (b.get("kasb") or "").strip()[:180]
    descr = (b.get("descr") or "").strip()[:3000]
    visible = 1 if b.get("visible") else 0
    if visible and not kasb:
        conn.close()
        raise HTTPException(400, "Ko'rinish uchun kasb/yo'nalish kiritilishi shart.")
    now = int(time.time())
    # Eski ustunlar bazada saqlanadi, lekin yangi kabinetda ishlatilmaydi.
    conn.execute(
        """INSERT INTO specialists(user_id, kasb, descr, narx, hudud, is_gov, org, dept, lavozim,
                                   work_hours, after_hours, visible, available, lat, lng, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET
             kasb=excluded.kasb, descr=excluded.descr, narx='', hudud='', is_gov=0,
             org='', dept='', lavozim='', work_hours='', after_hours='',
             visible=excluded.visible, available=1, lat=excluded.lat, lng=excluded.lng""",
        (user["id"], kasb, descr, "", "", 0, "", "", "", "", "", visible, 1,
         b.get("lat"), b.get("lng"), now),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/specialist/credentials/upload")
async def specialist_credential_upload(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    _ensure_specialist_content_tables(conn)
    cnt = conn.execute("SELECT COUNT(*) c FROM specialist_credentials WHERE user_id=?", (user["id"],)).fetchone()["c"]
    if cnt >= 12:
        conn.close()
        raise HTTPException(400, "Tasdiqlovchi hujjatlar 12 tadan oshmasin.")
    _, url = await _save_specialist_raw(request, user["id"], "credential", allow_video=False, max_mb=8)
    cur = conn.execute(
        "INSERT INTO specialist_credentials(user_id, file_url, pos, created_at) VALUES(?,?,?,?)",
        (user["id"], url, cnt, int(time.time())),
    )
    conn.commit(); rid = cur.lastrowid; conn.close()
    return {"ok": True, "id": rid, "file_url": url}


@router.delete("/specialist/credentials/{media_id}")
async def specialist_credential_delete(media_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db(); user = require_user(conn, x_telegram_init_data)
    conn.execute("DELETE FROM specialist_credentials WHERE id=? AND user_id=?", (media_id, user["id"]))
    conn.commit(); conn.close()
    return {"ok": True}


@router.post("/specialist/offers/image")
async def specialist_offer_image(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db(); user = require_user(conn, x_telegram_init_data); conn.close()
    _, url = await _save_specialist_raw(request, user["id"], "offer", allow_video=False, max_mb=8)
    return {"ok": True, "photo_file": url}


@router.post("/specialist/offers")
async def specialist_offer_add(body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db(); user = require_user(conn, x_telegram_init_data); _ensure_specialist_content_tables(conn)
    name = (body.get("name") or "").strip()[:160]
    if not name:
        conn.close(); raise HTTPException(400, "Mahsulot/xizmat nomini kiriting.")
    kind = "product" if (body.get("kind") or "") == "product" else "service"
    cnt = conn.execute("SELECT COUNT(*) c FROM specialist_offers WHERE user_id=?", (user["id"],)).fetchone()["c"]
    if cnt >= 60:
        conn.close(); raise HTTPException(400, "Mahsulot va xizmatlar 60 tadan oshmasin.")
    cur = conn.execute(
        "INSERT INTO specialist_offers(user_id, kind, name, price, note, photo_file, created_at) VALUES(?,?,?,?,?,?,?)",
        (user["id"], kind, name, (body.get("price") or "").strip()[:120],
         (body.get("note") or "").strip()[:1000], (body.get("photo_file") or "").strip()[:500], int(time.time())),
    )
    conn.commit(); rid = cur.lastrowid; conn.close()
    return {"ok": True, "id": rid}


@router.put("/specialist/offers/{offer_id}")
async def specialist_offer_edit(offer_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db(); user = require_user(conn, x_telegram_init_data); _ensure_specialist_content_tables(conn)
    name = (body.get("name") or "").strip()[:160]
    if not name:
        conn.close(); raise HTTPException(400, "Mahsulot/xizmat nomini kiriting.")
    kind = "product" if (body.get("kind") or "") == "product" else "service"
    cur = conn.execute(
        "UPDATE specialist_offers SET kind=?, name=?, price=?, note=?, photo_file=? WHERE id=? AND user_id=?",
        (kind, name, (body.get("price") or "").strip()[:120], (body.get("note") or "").strip()[:1000],
         (body.get("photo_file") or "").strip()[:500], offer_id, user["id"]),
    )
    if not cur.rowcount:
        conn.close(); raise HTTPException(404, "Mahsulot/xizmat topilmadi.")
    conn.commit(); conn.close(); return {"ok": True}


@router.delete("/specialist/offers/{offer_id}")
async def specialist_offer_delete(offer_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db(); user = require_user(conn, x_telegram_init_data)
    conn.execute("DELETE FROM specialist_offers WHERE id=? AND user_id=?", (offer_id, user["id"]))
    conn.commit(); conn.close(); return {"ok": True}


@router.post("/specialist/portfolio/upload")
async def specialist_portfolio_upload(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db(); user = require_user(conn, x_telegram_init_data); _ensure_specialist_content_tables(conn)
    cnt = conn.execute("SELECT COUNT(*) c FROM specialist_portfolio WHERE user_id=?", (user["id"],)).fetchone()["c"]
    if cnt >= 40:
        conn.close(); raise HTTPException(400, "Bajarilgan ishlar media fayllari 40 tadan oshmasin.")
    mtype, url = await _save_specialist_raw(request, user["id"], "portfolio", allow_video=True, max_mb=30)
    cur = conn.execute(
        "INSERT INTO specialist_portfolio(user_id, media_type, file_url, created_at) VALUES(?,?,?,?)",
        (user["id"], mtype, url, int(time.time())),
    )
    conn.commit(); rid = cur.lastrowid; conn.close()
    return {"ok": True, "id": rid, "media_type": mtype, "file_url": url}


@router.delete("/specialist/portfolio/{media_id}")
async def specialist_portfolio_delete(media_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db(); user = require_user(conn, x_telegram_init_data)
    conn.execute("DELETE FROM specialist_portfolio WHERE id=? AND user_id=?", (media_id, user["id"]))
    conn.commit(); conn.close(); return {"ok": True}


# ====================================================================
# TAXI HAYDOVCHISI (v1383)
# ====================================================================

@router.get("/driver")
async def get_driver(x_telegram_init_data: str = Header(default="")):
    """Joriy foydalanuvchining haydovchi profili. Ro'yxatdan o'tmagan bo'lsa, formani
    oldindan to'ldirish uchun akkaunt ismi va telefoni qaytariladi."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    d = conn.execute("SELECT * FROM drivers WHERE user_id=?", (user["id"],)).fetchone()
    name = user["name"]
    phone = user["phone"]
    if not d:
        conn.close()
        return {"exists": False, "name": name, "phone": phone}

    # Joriy zakaz bor paytda haydovchi har doim avtomatik BAND bo'ladi.
    active = conn.execute(
        "SELECT id FROM rides WHERE driver_id=? AND status IN ('accepted','arrived','ongoing','arrived_store','pickup_requested','in_delivery','arrived_customer','delivered_waiting_customer') LIMIT 1",
        (d["id"],),
    ).fetchone()
    if active and d["available"]:
        conn.execute("UPDATE drivers SET available=0 WHERE id=?", (d["id"],))
        conn.commit()
        d = conn.execute("SELECT * FROM drivers WHERE id=?", (d["id"],)).fetchone()

    rating = round(d["rating_sum"] / d["rating_cnt"], 1) if d["rating_cnt"] else 0
    result = {
        "exists": True, "name": name,
        "phone": d["phone"], "car_model": d["car_model"], "car_color": d["car_color"],
        "car_plate": d["car_plate"], "service": d["service"], "available": bool(d["available"]),
        "busy": bool(active),
        "rating": rating, "rating_cnt": d["rating_cnt"], "balance": d["balance"],
        "commission": COMMISSION_PER_ORDER, "is_admin": (user["tg_id"] in ADMIN_TG_IDS),
    }
    conn.close()
    return result


@router.post("/driver")
async def save_driver(request: Request, x_telegram_init_data: str = Header(default="")):
    """Haydovchi ro'yxatdan o'tadi yoki ma'lumotini tahrirlaydi (upsert).
    Taxi yoki Ikkalasi bo'lsa, mashina ma'lumoti majburiy."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    b = await request.json()
    service = (b.get("service") or "taxi").strip().lower()
    if service not in ("taxi", "dostavka", "both"):
        service = "taxi"
    phone = (b.get("phone") or "").strip()
    car_model = (b.get("car_model") or "").strip()
    car_color = (b.get("car_color") or "").strip()
    car_plate = (b.get("car_plate") or "").strip()
    if not phone:
        conn.close()
        raise HTTPException(400, "Telefon raqamini kiriting.")
    # Taxi yoki Ikkalasi — yo'lovchi tashish uchun mashina ma'lumoti majburiy
    if service in ("taxi", "both") and not (car_model and car_color and car_plate):
        conn.close()
        raise HTTPException(400, "Taxi uchun mashina rusumi, raqami va rangini to'ldiring.")
    now = int(time.time())
    conn.execute(
        """INSERT INTO drivers(user_id, phone, car_model, car_color, car_plate, service, available, created_at)
           VALUES(?,?,?,?,?,?,1,?)
           ON CONFLICT(user_id) DO UPDATE SET
             phone=excluded.phone, car_model=excluded.car_model, car_color=excluded.car_color,
             car_plate=excluded.car_plate, service=excluded.service""",
        (user["id"], phone, car_model, car_color, car_plate, service, now),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.put("/driver/available")
async def set_driver_available(request: Request, x_telegram_init_data: str = Header(default="")):
    """Haydovchi holatini o'zgartiradi: bo'shman (1) / bandman (0)."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    b = await request.json()
    avail = 1 if b.get("available") else 0
    d = conn.execute("SELECT * FROM drivers WHERE user_id=?", (user["id"],)).fetchone()
    if not d:
        conn.close()
        raise HTTPException(404, "Avval haydovchi sifatida ro'yxatdan o'ting.")

    # Faol taxi/dostavka zakazi tugamaguncha qo'lda Bo'shman holatiga qaytib bo'lmaydi.
    if avail:
        active = conn.execute(
            "SELECT id FROM rides WHERE driver_id=? AND status IN ('accepted','arrived','ongoing','arrived_store','pickup_requested','in_delivery','arrived_customer','delivered_waiting_customer') LIMIT 1",
            (d["id"],),
        ).fetchone()
        if active:
            conn.close()
            raise HTTPException(400, "Joriy zakazni yakunlamaguningizcha yangi zakaz ololmaysiz.")

    conn.execute("UPDATE drivers SET available=? WHERE id=?", (avail, d["id"]))
    conn.commit()
    conn.close()
    return {"ok": True, "available": bool(avail)}


# ====================================================================
# TAXI ZAKAZLARI (v1384)
# ====================================================================

# Masofa bo'yicha taxminiy narx (so'mda). BU NAMUNA STAVKALAR — egasi o'zgartirishi mumkin.
PRICING = {
    "taxi":     {"base": 5000,  "per_km": 2000, "min": 9000},
    "dostavka": {"base": 10000, "per_km": 2500, "min": 15000},
}

# Har qabul qilingan zakaz uchun haydovchi balansidan yechiladigan komissiya (so'm).
# BU NAMUNA STAVKA — egasi o'zgartirishi mumkin.
COMMISSION_PER_ORDER = 1000

# Admin (egasi) Telegram ID'lari — balansni qo'lda to'ldirish huquqi shularda.
ADMIN_TG_IDS = {1423181561, 607563067}


def _calc_price(kind, dist_km):
    """Boshlang'ich haq + (har km narxi × masofa); minimaldan kam bo'lmaydi; 500 so'mgacha yaxlitlanadi."""
    cfg = PRICING.get(kind) or PRICING["taxi"]
    try:
        km = float(dist_km)
    except (TypeError, ValueError):
        return None
    if km <= 0:
        return None
    p = cfg["base"] + cfg["per_km"] * km
    if p < cfg["min"]:
        p = cfg["min"]
    return int(p / 500.0 + 0.5) * 500


def _haversine_km(la1, lo1, la2, lo2):
    try:
        la1, lo1, la2, lo2 = float(la1), float(lo1), float(la2), float(lo2)
    except Exception:
        return 0
    R = 6371.0
    p1 = math.radians(la1); p2 = math.radians(la2)
    dp = math.radians(la2 - la1); dl = math.radians(lo2 - lo1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)


def _ride_dict(r):
    def g(k):
        try:
            return r[k]
        except Exception:
            return None
    return {
        "id": r["id"], "kind": r["kind"], "from_addr": r["from_addr"], "to_addr": r["to_addr"],
        "from_lat": g("from_lat"), "from_lng": g("from_lng"), "to_lat": g("to_lat"), "to_lng": g("to_lng"),
        "dist_km": g("dist_km"), "dur_min": g("dur_min"),
        "price": _calc_price(r["kind"], g("dist_km")),
        "meter_km": g("meter_km"),
        "final_price": _calc_price(r["kind"], g("meter_km")),
        "ozim": bool(r["ozim"]), "cargo": r["cargo"], "car_type": r["car_type"], "note": r["note"],
        "status": r["status"], "created_at": r["created_at"], "src_order_id": g("src_order_id"),
    }


def _require_driver(conn, init_data):
    user = require_user(conn, init_data)
    d = conn.execute("SELECT * FROM drivers WHERE user_id=?", (user["id"],)).fetchone()
    if not d:
        conn.close()
        raise HTTPException(403, "Avval haydovchi sifatida ro'yxatdan o'ting.")
    return user, d


@router.post("/rides")
async def create_ride(request: Request, x_telegram_init_data: str = Header(default="")):
    """Mijoz yangi zakaz beradi (taxi yoki dostavka)."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    b = await request.json()
    kind = (b.get("kind") or "taxi").strip().lower()
    if kind not in ("taxi", "dostavka"):
        kind = "taxi"
    ozim = 1 if b.get("ozim") else 0
    to_addr = (b.get("to_addr") or "").strip()
    if not ozim and not to_addr:
        conn.close()
        raise HTTPException(400, "Qayerga borishni kiriting yoki 'O'zim aytaman'ni tanlang.")
    active = conn.execute(
        "SELECT id FROM rides WHERE customer_id=? AND status IN ('pending','accepted','arrived','ongoing','arrived_store','pickup_requested','in_delivery','arrived_customer','delivered_waiting_customer') LIMIT 1",
        (user["id"],),
    ).fetchone()
    if active:
        conn.close()
        raise HTTPException(400, "Sizda hali tugamagan zakaz bor.")
    def _num(v):
        try:
            return float(v) if v is not None and v != "" else None
        except Exception:
            return None
    from_lat = _num(b.get("from_lat")); from_lng = _num(b.get("from_lng"))
    to_lat = _num(b.get("to_lat")); to_lng = _num(b.get("to_lng"))
    dist_km = _num(b.get("dist_km"))
    _dm = _num(b.get("dur_min"))
    dur_min = int(_dm) if _dm is not None else None
    now = int(time.time())
    cur = conn.execute(
        """INSERT INTO rides(customer_id, kind, from_addr, to_addr, from_lat, from_lng, to_lat, to_lng, dist_km, dur_min, ozim, cargo, car_type, note, status, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?)""",
        (user["id"], kind, (b.get("from_addr") or "").strip(), to_addr, from_lat, from_lng, to_lat, to_lng, dist_km, dur_min, ozim,
         (b.get("cargo") or "").strip(), (b.get("car_type") or "").strip(), (b.get("note") or "").strip(), now),
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return {"ok": True, "id": rid, "status": "pending"}


@router.get("/rides/my")
async def my_ride(x_telegram_init_data: str = Header(default="")):
    """Mijozning joriy (tugamagan) zakazi + qabul qilingan bo'lsa haydovchi ma'lumoti."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    r = conn.execute(
        "SELECT * FROM rides WHERE customer_id=? AND status IN ('pending','accepted','arrived','ongoing','arrived_store','pickup_requested','in_delivery','arrived_customer','delivered_waiting_customer') ORDER BY id DESC LIMIT 1",
        (user["id"],),
    ).fetchone()
    if not r:
        conn.close()
        return {"ride": None}
    out = _ride_dict(r)
    if r["status"] in ("accepted", "arrived", "ongoing", "arrived_store", "pickup_requested", "in_delivery", "arrived_customer", "delivered_waiting_customer") and r["driver_id"]:
        d = conn.execute("SELECT * FROM drivers WHERE id=?", (r["driver_id"],)).fetchone()
        if d:
            du = conn.execute("SELECT name FROM users WHERE id=?", (d["user_id"],)).fetchone()
            out["driver"] = {
                "name": du["name"] if du else "", "phone": d["phone"],
                "car_model": d["car_model"], "car_color": d["car_color"], "car_plate": d["car_plate"],
            }
    conn.close()
    return {"ride": out}


@router.post("/rides/{ride_id}/cancel")
async def cancel_ride(ride_id: int, x_telegram_init_data: str = Header(default="")):
    """Mijoz o'z zakazini bekor qiladi (pending yoki accepted)."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    prev = conn.execute(
        "SELECT driver_id, status, kind FROM rides WHERE id=? AND customer_id=?",
        (ride_id, user["id"]),
    ).fetchone()
    if not prev:
        conn.close()
        raise HTTPException(404, "Zakaz topilmadi.")

    # Dostavka olib ketilgandan keyin mijoz uni bekor qila olmaydi.
    allowed = ("pending", "accepted") if prev["kind"] == "dostavka" else ("pending", "accepted", "arrived")
    if prev["status"] not in allowed:
        conn.close()
        raise HTTPException(400, "Zakaz bu bosqichda bekor qilinmaydi.")

    cur = conn.execute(
        "UPDATE rides SET status='canceled' WHERE id=? AND customer_id=? AND status=?",
        (ride_id, user["id"], prev["status"]),
    )
    if cur.rowcount and prev["driver_id"]:
        conn.execute("UPDATE drivers SET available=1 WHERE id=?", (prev["driver_id"],))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(409, "Zakaz holati o'zgargan. Qayta tekshiring.")
    return {"ok": True}


@router.get("/rides/pending")
async def pending_rides(x_telegram_init_data: str = Header(default="")):
    """Haydovchi uchun: joriy qabul qilingan zakazi + xizmatiga mos kutilayotgan zakazlar."""
    conn = db()
    user, d = _require_driver(conn, x_telegram_init_data)
    cur_ride = conn.execute(
        "SELECT * FROM rides WHERE driver_id=? AND status IN ('accepted','arrived','ongoing','arrived_store','pickup_requested','in_delivery','arrived_customer','delivered_waiting_customer') ORDER BY id DESC LIMIT 1",
        (d["id"],),
    ).fetchone()
    current = None
    if cur_ride:
        # Faol zakaz topilsa holatni majburan BAND qilib sinxronlaymiz.
        if d["available"]:
            conn.execute("UPDATE drivers SET available=0 WHERE id=?", (d["id"],))
            conn.commit()
            d = conn.execute("SELECT * FROM drivers WHERE id=?", (d["id"],)).fetchone()
        current = _ride_dict(cur_ride)
        cu = conn.execute("SELECT name, phone FROM users WHERE id=?", (cur_ride["customer_id"],)).fetchone()
        current["customer"] = {"name": cu["name"] if cu else "", "phone": cu["phone"] if cu else ""}
    pend = []
    if d["available"] and not current:
        if d["service"] == "both":
            rows = conn.execute("SELECT * FROM rides WHERE status='pending' ORDER BY created_at ASC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM rides WHERE status='pending' AND kind=? ORDER BY created_at ASC",
                (d["service"],),
            ).fetchall()
        for r in rows:
            item = _ride_dict(r)
            cu = conn.execute("SELECT name FROM users WHERE id=?", (r["customer_id"],)).fetchone()
            item["customer_name"] = cu["name"] if cu else ""
            pend.append(item)
    conn.close()
    return {"available": bool(d["available"]), "current": current, "pending": pend}


@router.post("/rides/{ride_id}/accept")
async def accept_ride(ride_id: int, x_telegram_init_data: str = Header(default="")):
    """Haydovchi zakazni qabul qiladi; shu zahoti BAND bo'ladi va yakunlamaguncha boshqasini ololmaydi."""
    conn = db()
    user, d = _require_driver(conn, x_telegram_init_data)
    try:
        # Bir haydovchi bir vaqtda ikki so'rov yuborsa ham faqat bittasi o'tishi uchun yozuvni qulflaymiz.
        conn.execute("BEGIN IMMEDIATE")
        d = conn.execute("SELECT * FROM drivers WHERE id=?", (d["id"],)).fetchone()
        if not d["available"]:
            raise HTTPException(400, "Siz bandsiz. Joriy zakazni yakunlagach yangi zakaz olasiz.")

        busy = conn.execute(
            "SELECT id FROM rides WHERE driver_id=? AND status IN ('accepted','arrived','ongoing','arrived_store','pickup_requested','in_delivery','arrived_customer','delivered_waiting_customer') LIMIT 1",
            (d["id"],),
        ).fetchone()
        if busy:
            raise HTTPException(400, "Sizda hali tugamagan zakaz bor.")

        ride = conn.execute("SELECT * FROM rides WHERE id=?", (ride_id,)).fetchone()
        if not ride or ride["status"] != "pending":
            raise HTTPException(409, "Bu zakazni boshqa haydovchi oldi.")
        if d["service"] != "both" and d["service"] != ride["kind"]:
            raise HTTPException(403, "Bu zakaz siz tanlagan xizmat turiga mos emas.")
        if (d["balance"] or 0) < COMMISSION_PER_ORDER:
            raise HTTPException(400, "Balansingiz yetarli emas. Zakaz olish uchun balansni to'ldiring.")

        now = int(time.time())
        cur = conn.execute(
            "UPDATE rides SET status='accepted', driver_id=?, accepted_at=? WHERE id=? AND status='pending'",
            (d["id"], now, ride_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(409, "Bu zakazni boshqa haydovchi oldi.")

        # Qabul qilish bilan bir tranzaksiyada komissiya yechiladi va haydovchi BAND qilinadi.
        conn.execute(
            "UPDATE drivers SET balance=balance-?, available=0 WHERE id=?",
            (COMMISSION_PER_ORDER, d["id"]),
        )
        if ride["kind"] == "dostavka" and _row_val(ride, "src_order_id", None):
            conn.execute(
                "UPDATE orders SET status='courier_assigned',updated_at=?,customer_seen_at=0,provider_seen_at=0,last_event='delivery' WHERE id=?",
                (now, ride["src_order_id"]),
            )
            order = conn.execute("SELECT * FROM orders WHERE id=?", (ride["src_order_id"],)).fetchone()
            if order:
                driver_name = user["name"] or "Dostavkachi"
                _notify_order_side(conn, order, "customer", "courier_assigned", "Dostavkachi buyurtmani qabul qildi", driver_name)
                _notify_order_side(conn, order, "provider", "courier_assigned", "Dostavkachi biriktirildi", driver_name)
        conn.commit()
    except HTTPException:
        conn.rollback()
        conn.close()
        raise
    except Exception:
        conn.rollback()
        conn.close()
        raise

    r = conn.execute("SELECT * FROM rides WHERE id=?", (ride_id,)).fetchone()
    out = _ride_dict(r)
    cu = conn.execute("SELECT name, phone FROM users WHERE id=?", (r["customer_id"],)).fetchone()
    out["customer"] = {"name": cu["name"] if cu else "", "phone": cu["phone"] if cu else ""}
    new_balance = conn.execute("SELECT balance FROM drivers WHERE id=?", (d["id"],)).fetchone()["balance"]
    conn.close()
    return {
        "ok": True, "ride": out, "commission": COMMISSION_PER_ORDER,
        "balance": new_balance, "available": False,
    }


@router.post("/rides/{ride_id}/complete")
async def complete_ride(ride_id: int, x_telegram_init_data: str = Header(default="")):
    """Haydovchi safarni yakunlaydi."""
    conn = db()
    user, d = _require_driver(conn, x_telegram_init_data)
    cur = conn.execute(
        "UPDATE rides SET status='completed' WHERE id=? AND driver_id=? AND kind<>'dostavka' AND status IN ('accepted','arrived','ongoing')",
        (ride_id, d["id"]),
    )
    if cur.rowcount:
        conn.execute("UPDATE drivers SET available = 1 WHERE id=?", (d["id"],))  # #3: yakunlandi -> bo'sh
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "Zakaz topilmadi.")
    return {"ok": True}


@router.post("/rides/{ride_id}/status")
async def update_ride_status(ride_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    """Taxi va dostavka uchun alohida bosqichlar.

    Taxi: accepted -> arrived -> ongoing -> completed
    Dostavka: accepted -> arrived (dostavkani oldim) -> completed (topshirdim)
    """
    conn = db()
    user, d = _require_driver(conn, x_telegram_init_data)
    b = await request.json()
    new = (b.get("status") or "").strip()
    r = conn.execute(
        "SELECT status, kind, src_order_id FROM rides WHERE id=? AND driver_id=?",
        (ride_id, d["id"]),
    ).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Zakaz topilmadi.")

    if r["kind"] == "dostavka":
        nxt = {
            "accepted": "arrived_store",
            "arrived_store": "pickup_requested",
            "in_delivery": "arrived_customer",
            "arrived_customer": "delivered_waiting_customer",
        }
    else:
        nxt = {"accepted": "arrived", "arrived": "ongoing", "ongoing": "completed"}

    if nxt.get(r["status"]) != new:
        conn.close()
        raise HTTPException(400, "Bu bosqichga o'tib bo'lmaydi.")

    conn.execute("UPDATE rides SET status=? WHERE id=?", (new, ride_id))
    if r["kind"] == "dostavka" and r["src_order_id"]:
        order_status = {
            "arrived_store": "courier_arrived_store",
            "pickup_requested": "handoff_waiting_seller",
            "arrived_customer": "courier_arrived_customer",
            "delivered_waiting_customer": "delivered_waiting_customer",
        }.get(new)
        if order_status:
            conn.execute(
                "UPDATE orders SET status=?,updated_at=?,customer_seen_at=0,provider_seen_at=0,last_event='delivery' WHERE id=?",
                (order_status, int(time.time()), r["src_order_id"]),
            )
            order = conn.execute("SELECT * FROM orders WHERE id=?", (r["src_order_id"],)).fetchone()
            if order and new == "pickup_requested":
                _notify_order_side(conn, order, "provider", "courier_pickup_requested", "Dostavkachi buyurtmani olishga tayyor", "Buyurtmani dostavkachiga topshiring.", ride_id, "confirm_handoff")
            elif order and new == "arrived_customer":
                _notify_order_side(conn, order, "customer", "courier_arrived", "Dostavkachi yetib keldi", "Buyurtmani qabul qilishga tayyorlaning.", ride_id)
            elif order and new == "delivered_waiting_customer":
                _notify_order_side(conn, order, "customer", "delivery_handed", "Buyurtma topshirildi", "Buyurtmani olganingizni tasdiqlang.", ride_id, "confirm_received")
    if new == "completed":
        # Faqat yakunlangandan keyin yana zakaz olishga ruxsat beriladi.
        conn.execute("UPDATE drivers SET available=1 WHERE id=?", (d["id"],))
    else:
        conn.execute("UPDATE drivers SET available=0 WHERE id=?", (d["id"],))
    conn.commit()
    conn.close()
    return {"ok": True, "status": new, "available": new == "completed"}


@router.post("/rides/{ride_id}/progress")
async def update_ride_progress(ride_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    """Jonli GPS hisoblagich: haydovchi bosib o'tilgan masofani (km) yangilaydi.
    Faqat o'sha haydovchi va faqat 'ongoing' (safar davom etayotgan) holatda yoziladi."""
    conn = db()
    user, d = _require_driver(conn, x_telegram_init_data)
    b = await request.json()
    try:
        km = float(b.get("km"))
    except (TypeError, ValueError):
        km = None
    if km is None or km < 0:
        km = 0.0
    conn.execute(
        "UPDATE rides SET meter_km=? WHERE id=? AND driver_id=? AND status='ongoing'",
        (km, ride_id, d["id"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/pricing")
async def get_pricing(x_telegram_init_data: str = Header(default="")):
    """Frontend jonli narx ko'rsatishi uchun stavkalar."""
    conn = db()
    require_user(conn, x_telegram_init_data)
    conn.close()
    return {"pricing": PRICING}


def _require_admin(conn, init_data):
    """Admin (egasi) ekanligini tekshiradi. Bo'lmasa 403."""
    user = require_user(conn, init_data)
    if user["tg_id"] not in ADMIN_TG_IDS:
        conn.close()
        raise HTTPException(403, "Bu amal faqat admin uchun.")
    return user


@router.get("/admin/drivers")
async def admin_list_drivers(x_telegram_init_data: str = Header(default="")):
    """Admin uchun: barcha haydovchilar va ularning balansi (qo'lda to'ldirish uchun)."""
    conn = db()
    _require_admin(conn, x_telegram_init_data)
    rows = conn.execute(
        "SELECT d.id, d.phone, d.balance, u.name "
        "FROM drivers d JOIN users u ON u.id=d.user_id ORDER BY u.name"
    ).fetchall()
    conn.close()
    return {"drivers": [{"id": r["id"], "name": r["name"], "phone": r["phone"],
                         "balance": r["balance"] or 0} for r in rows]}


@router.post("/admin/topup")
async def admin_topup(request: Request, x_telegram_init_data: str = Header(default="")):
    """Admin uchun: haydovchi balansini qo'lda to'ldirish (haydovchi pulni o'tkazgach)."""
    conn = db()
    _require_admin(conn, x_telegram_init_data)
    b = await request.json()
    try:
        driver_id = int(b.get("driver_id"))
        amount = int(b.get("amount"))
    except (TypeError, ValueError):
        conn.close()
        raise HTTPException(400, "Haydovchi va summani to'g'ri kiriting.")
    if amount <= 0 or amount > 10000000:
        conn.close()
        raise HTTPException(400, "Summa noto'g'ri (0 dan katta bo'lsin).")
    cur = conn.execute("UPDATE drivers SET balance = balance + ? WHERE id=?", (amount, driver_id))
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(404, "Haydovchi topilmadi.")
    new_balance = conn.execute("SELECT balance FROM drivers WHERE id=?", (driver_id,)).fetchone()["balance"]
    conn.close()
    return {"ok": True, "balance": new_balance}


# ====================================================================
# BIZNES PROFILI VA MAHSULOTLAR
# ====================================================================
def _norm_username(v):
    v = (v or "").strip().lower().lstrip("@")
    return v


def _username_error(u):
    """Username qoidalari. Xato bo'lsa matn qaytaradi, to'g'ri bo'lsa None."""
    if u == "":
        return None  # bo'sh = username yo'q (ruxsat)
    if len(u) < 3 or len(u) > 20:
        return "Username 3 tadan 20 tagacha belgidan iborat bo'lsin."
    if not re.match(r"^[a-z][a-z0-9_]*$", u):
        return "Faqat kichik lotin harflari, raqam va pastki chiziq (_). Harf bilan boshlansin."
    return None


def _ensure_pay_columns(conn):
    """To'lov ustunlari yo'q bo'lsa qo'shadi. Har chaqiruvda ishlaydi (migratsiya/restartga bog'liq emas)."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(businesses)").fetchall()]
    if "pay_card" not in cols:
        conn.execute("ALTER TABLE businesses ADD COLUMN pay_card TEXT DEFAULT ''")
    if "pay_holder" not in cols:
        conn.execute("ALTER TABLE businesses ADD COLUMN pay_holder TEXT DEFAULT ''")
    if "pay_qr" not in cols:
        conn.execute("ALTER TABLE businesses ADD COLUMN pay_qr TEXT DEFAULT ''")
    if "username" not in cols:
        conn.execute("ALTER TABLE businesses ADD COLUMN username TEXT DEFAULT ''")
    if "director" not in cols:
        conn.execute("ALTER TABLE businesses ADD COLUMN director TEXT DEFAULT ''")
    if "inn" not in cols:
        conn.execute("ALTER TABLE businesses ADD COLUMN inn TEXT DEFAULT ''")
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_businesses_username "
                     "ON businesses(lower(username)) WHERE COALESCE(username,'')<>''")
    except Exception:
        pass


@router.put("/business")
async def update_business(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Do'kon sozlamalari")
    _ensure_pay_columns(conn)   # v1421: to'lov ustunlari kafolatlangan
    biz = conn.execute("SELECT * FROM businesses WHERE id=?", (biz["id"],)).fetchone()  # ustunlar bilan qayta o'qish
    b = await request.json()
    def keep(key, old):
        return b[key].strip() if (key in b and isinstance(b[key], str)) else old
    new_name = keep("name", biz["name"]) or biz["name"]
    new_yon = keep("yon", biz["yon"])
    new_tur = keep("tur", biz["tur"])
    new_descr = keep("descr", biz["descr"])
    new_phone = keep("phone", biz["phone"])
    new_tg = keep("telegram", biz["telegram"])
    new_hours = keep("work_hours", biz["work_hours"])
    new_addr = keep("address", biz["address"])
    new_pay_card = keep("pay_card", _row_val(biz, "pay_card", ""))
    new_pay_holder = keep("pay_holder", _row_val(biz, "pay_holder", ""))
    new_pay_qr = keep("pay_qr", _row_val(biz, "pay_qr", ""))
    # v1425: username (ixtiyoriy, band emasligi tekshiriladi)
    new_username = _row_val(biz, "username", "") or ""
    new_director = keep("director", _row_val(biz, "director", ""))
    new_inn = keep("inn", _row_val(biz, "inn", "")).strip()[:20]
    if "username" in b:
        cand = _norm_username(b.get("username"))
        err = _username_error(cand)
        if err:
            conn.close()
            raise HTTPException(400, err)
        if cand:
            taken = conn.execute(
                "SELECT id FROM businesses WHERE lower(username)=? AND id<>?",
                (cand, biz["id"]),
            ).fetchone()
            if taken:
                conn.close()
                raise HTTPException(400, "Bu username band. Boshqasini tanlang.")
        new_username = cand
    # lat/lng: faqat yuborilgan bo'lsa yangilaymiz, aks holda eskisi qoladi
    new_lat = b["lat"] if ("lat" in b and b["lat"] is not None) else biz["lat"]
    new_lng = b["lng"] if ("lng" in b and b["lng"] is not None) else biz["lng"]
    conn.execute(
        """UPDATE businesses SET name=?, yon=?, tur=?, descr=?, phone=?, telegram=?,
           work_hours=?, address=?, lat=?, lng=?, pay_card=?, pay_holder=?, pay_qr=?, username=?, director=?, inn=? WHERE id=?""",
        (new_name, new_yon, new_tur, new_descr, new_phone, new_tg,
         new_hours, new_addr, new_lat, new_lng,
         new_pay_card, new_pay_holder, new_pay_qr, new_username, new_director, new_inn, biz["id"]),
    )
    # 3-talab: biznes metkasi belgilanganda, agar bosh sahifa manzili HALI BO'SH bo'lsa,
    # o'sha joyning viloyat/tumani avtomatik bosh sahifa manziliga yoziladi.
    # B variant: faqat birinchi marta (bo'sh bo'lsa). Keyin foydalanuvchi qo'lda o'zgartira oladi.
    marker_sent = ("lat" in b and b["lat"] is not None) and ("lng" in b and b["lng"] is not None)
    home_empty = not ((user["region"] or "").strip() or (user["district"] or "").strip())
    if marker_sent and home_empty and new_lat is not None and new_lng is not None:
        from main import reverse_geocode
        geo = await reverse_geocode(new_lat, new_lng)
        gr = (geo.get("region") or "").strip()
        gd = (geo.get("district") or "").strip()
        if gr or gd:
            conn.execute("UPDATE users SET region=?, district=?, lat=?, lng=? WHERE id=?", (gr, gd, new_lat, new_lng, user["id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


def _item_group_for_business(conn, biz_id, group_id):
    """Guruh shu biznesnikimi — tekshiradi. group_id bo'sh bo'lsa None qaytadi."""
    if group_id in (None, "", 0, "0"):
        return None
    try:
        gid = int(group_id)
    except Exception:
        raise HTTPException(400, "Guruh noto'g'ri tanlangan.")
    g = conn.execute(
        "SELECT * FROM item_groups WHERE id=? AND business_id=?",
        (gid, biz_id),
    ).fetchone()
    if not g:
        raise HTTPException(400, "Tanlangan guruh topilmadi.")
    return g


def _item_kind_and_group(conn, biz_id, body):
    """
    v1379 qoidasi: agar haqiqiy guruh tanlansa, tovar turini guruh hal qiladi.
    Guruhsiz bo'lsa, frontend yuborgan kind ishlaydi.
    """
    g = _item_group_for_business(conn, biz_id, (body or {}).get("group_id"))
    if g:
        return g["kind"], g["id"]
    kind = (body or {}).get("kind") if (body or {}).get("kind") in ("product", "service") else "product"
    return kind, None


@router.get("/item-groups")
async def item_groups(x_telegram_init_data: str = Header(default="")):
    """Biznesning mahsulot/xizmat guruhlari ro'yxati."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    rows = conn.execute(
        "SELECT * FROM item_groups WHERE business_id=? ORDER BY created_at ASC, id ASC",
        (biz["id"],),
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "kind": r["kind"], "created_at": r["created_at"]} for r in rows]


@router.post("/item-groups")
async def add_item_group(request: Request, x_telegram_init_data: str = Header(default="")):
    """Yangi guruh qo'shadi. Guruh turi faqat yaratilganda belgilanadi."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    b = await request.json()
    name = (b.get("name") or "").strip()
    if not name:
        conn.close()
        raise HTTPException(400, "Guruh nomi kiritilishi shart.")
    kind = b.get("kind") if b.get("kind") in ("product", "service") else "product"
    cur = conn.execute(
        "INSERT INTO item_groups(business_id, name, kind, created_at) VALUES(?,?,?,?)",
        (biz["id"], name, kind, int(time.time())),
    )
    conn.commit()
    gid = cur.lastrowid
    conn.close()
    return {"id": gid, "name": name, "kind": kind}


@router.put("/item-groups/{group_id}")
async def edit_item_group(group_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    """Guruhning faqat nomini o'zgartiradi. kind o'zgartirilmaydi."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    row = conn.execute(
        "SELECT * FROM item_groups WHERE id=? AND business_id=?",
        (group_id, biz["id"]),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Guruh topilmadi.")
    b = await request.json()
    name = (b.get("name") or "").strip()
    if not name:
        conn.close()
        raise HTTPException(400, "Guruh nomi kiritilishi shart.")
    conn.execute("UPDATE item_groups SET name=? WHERE id=? AND business_id=?", (name, group_id, biz["id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/item-groups/{group_id}")
async def delete_item_group(group_id: int, x_telegram_init_data: str = Header(default="")):
    """Guruhni xavfsiz o'chiradi: avval ichidagi tovarlar Guruhsizga o'tadi."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    row = conn.execute(
        "SELECT id FROM item_groups WHERE id=? AND business_id=?",
        (group_id, biz["id"]),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Guruh topilmadi.")
    conn.execute("UPDATE items SET group_id=NULL WHERE group_id=? AND business_id=?", (group_id, biz["id"]))
    conn.execute("DELETE FROM item_groups WHERE id=? AND business_id=?", (group_id, biz["id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/items")
async def my_items(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    _ensure_item_min_qty(conn)
    rows = conn.execute(
        """SELECT i.*, g.name AS group_name, g.kind AS group_kind
           FROM items i
           LEFT JOIN item_groups g ON g.id=i.group_id AND g.business_id=i.business_id
           WHERE i.business_id=?
           ORDER BY i.created_at DESC""",
        (biz["id"],),
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "price": r["price"], "unit": r["unit"] or "dona",
             "track_stock": r["track_stock"] or 0, "stock_qty": r["stock_qty"] or 0,
             "min_qty": _row_val(r, "min_qty", 0) or 0,
             "note": r["note"], "kind": r["kind"], "group_id": r["group_id"],
             "group_name": r["group_name"], "group_kind": r["group_kind"],
             "photo_file": r["photo_file"]} for r in rows]


@router.post("/items")
async def add_item(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    b = await request.json()
    name = (b.get("name") or "").strip()
    if not name:
        conn.close()
        raise HTTPException(400, "Mahsulot/xizmat nomi kiritilishi shart.")
    kind, group_id = _item_kind_and_group(conn, biz["id"], b)
    photo = (b.get("photo_file") or "").strip()
    _ensure_item_min_qty(conn)
    cur = conn.execute(
        "INSERT INTO items(business_id, group_id, name, price, unit, track_stock, note, kind, photo_file, min_qty, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (biz["id"], group_id, name, (b.get("price") or "").strip(), _clean_unit(b.get("unit")),
         1 if str(b.get("track_stock") or 0) in ("1", "true", "True") else 0,
         (b.get("note") or "").strip(), kind, photo, _parse_min_qty(b), int(time.time())),
    )
    conn.commit()
    item_id = cur.lastrowid
    conn.close()
    return {"id": item_id}


@router.put("/items/{item_id}")
async def edit_item(item_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    row = conn.execute(
        "SELECT id FROM items WHERE id=? AND business_id=?", (item_id, biz["id"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Mahsulot topilmadi.")
    b = await request.json()
    name = (b.get("name") or "").strip()
    if not name:
        conn.close()
        raise HTTPException(400, "Mahsulot/xizmat nomi kiritilishi shart.")
    kind, group_id = _item_kind_and_group(conn, biz["id"], b)
    photo = (b.get("photo_file") or "").strip()
    _ensure_item_min_qty(conn)
    conn.execute(
        "UPDATE items SET name=?, price=?, unit=?, track_stock=?, note=?, kind=?, group_id=?, photo_file=?, min_qty=? WHERE id=? AND business_id=?",
        (name, (b.get("price") or "").strip(), _clean_unit(b.get("unit")),
         1 if str(b.get("track_stock") or 0) in ("1", "true", "True") else 0,
         (b.get("note") or "").strip(), kind, group_id, photo, _parse_min_qty(b), item_id, biz["id"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/items/image")
async def upload_item_image(request: Request, x_telegram_init_data: str = Header(default="")):
    """Tovar rasmini yuklash. Rasm UPLOAD_DIR/items papkasiga saqlanadi va /uploads/items/... URL qaytariladi."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    conn.close()
    ctype = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    allowed = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/heic": ".heic",
        "image/heif": ".heif",
    }
    if ctype not in allowed:
        raise HTTPException(400, "Faqat rasm fayli yuborish mumkin.")
    raw = await request.body()
    max_size = 8 * 1024 * 1024
    if not raw:
        raise HTTPException(400, "Rasm fayli topilmadi.")
    if len(raw) > max_size:
        raise HTTPException(400, "Rasm hajmi 8 MB dan oshmasin.")
    from main import UPLOAD_DIR
    folder = os.path.join(UPLOAD_DIR, "items")
    os.makedirs(folder, exist_ok=True)
    ext = allowed[ctype]
    safe_name = "item_" + str(biz["id"]) + "_" + str(int(time.time())) + "_" + secrets.token_hex(8) + ext
    path = os.path.join(folder, safe_name)
    with open(path, "wb") as f:
        f.write(raw)
    return {"ok": True, "photo_file": "/uploads/items/" + safe_name}


@router.delete("/items/{item_id}")
async def delete_item(item_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    conn.execute("DELETE FROM items WHERE id=? AND business_id=?", (item_id, biz["id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


# ====================================================================
# MEDIA QUTISI (botga yuborilgan rasm/videolar)
# ====================================================================
@router.get("/media/inbox")
async def media_inbox(x_telegram_init_data: str = Header(default="")):
    """Foydalanuvchi botga yuborgan oxirgi rasm/videolar — e'lon formasi shundan tanlaydi."""
    from main import require_tg
    tg = require_tg(x_telegram_init_data)
    conn = db()
    rows = conn.execute(
        "SELECT file_id, mtype FROM media_inbox WHERE tg_id=? ORDER BY id DESC LIMIT 20",
        (tg["id"],),
    ).fetchall()
    conn.close()
    return [{"file_id": r["file_id"], "type": r["mtype"]} for r in rows]


@router.delete("/media/inbox")
async def clear_media_inbox(x_telegram_init_data: str = Header(default="")):
    from main import require_tg
    tg = require_tg(x_telegram_init_data)
    conn = db()
    conn.execute("DELETE FROM media_inbox WHERE tg_id=?", (tg["id"],))
    conn.commit()
    conn.close()
    return {"ok": True}


# ====================================================================
# BOSH SAHIFA REKLAMALARI (v1472)
# ====================================================================
AD_RATES = {
    "district": 10_000,   # bitta tuman / 1 kun
    "region": 30_000,     # bitta viloyat / 1 kun
    "republic": 100_000,  # butun O'zbekiston / 1 kun
}


def _ad_discount(days):
    days = int(days or 1)
    if days >= 30:
        return 25
    if days >= 14:
        return 15
    if days >= 7:
        return 10
    return 0


def _clean_ad_targets(raw):
    if not isinstance(raw, list):
        raise HTTPException(400, "Reklama hududlarini tanlang.")
    result = []
    seen = set()
    for x in raw[:30]:
        if not isinstance(x, dict):
            continue
        level = str(x.get("level") or "").strip().lower()
        region = str(x.get("region") or "").strip()
        district = str(x.get("district") or "").strip()
        if level not in ("district", "region", "republic"):
            continue
        if level == "district" and not (region and district):
            continue
        if level == "region" and not region:
            continue
        if level == "republic":
            region = ""
            district = ""
        key = (level, region.lower(), district.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append({"level": level, "region": region, "district": district})
    if not result:
        raise HTTPException(400, "Kamida bitta hudud tanlang.")
    if any(x["level"] == "republic" for x in result) and len(result) > 1:
        raise HTTPException(400, "Respublika tanlansa boshqa hudud qo'shilmaydi.")
    return result


def _ad_price(targets, days):
    days = max(1, min(int(days or 1), 90))
    daily = sum(AD_RATES[t["level"]] for t in targets)
    subtotal = daily * days
    discount = _ad_discount(days)
    total = int(round(subtotal * (100 - discount) / 100))
    return {"daily": daily, "subtotal": subtotal, "discount": discount, "total": total, "days": days}


def _ad_norm(v):
    v = str(v or "").lower().replace("ʻ", "'").replace("’", "'").strip()
    v = re.sub(r"\b(viloyati|viloyat|shahri|shahar|tumani|tuman)\b", "", v)
    return re.sub(r"[^a-z0-9'\u0400-\u04ff]+", "", v)


def _ad_matches(targets, user_region, user_district):
    ur = _ad_norm(user_region)
    ud = _ad_norm(user_district)
    for t in targets:
        level = t.get("level")
        if level == "republic":
            return True
        if level == "region" and ur and _ad_norm(t.get("region")) == ur:
            return True
        if level == "district" and ur and ud:
            if _ad_norm(t.get("region")) == ur and _ad_norm(t.get("district")) == ud:
                return True
    return False


def _ad_status(row, now=None):
    now = int(now or time.time())
    if row["status"] != "active":
        return row["status"]
    if now < row["start_at"]:
        return "scheduled"
    if now >= row["end_at"]:
        return "ended"
    return "active"


def _ad_dict(row):
    try:
        targets = json.loads(row["targets_json"] or "[]")
    except Exception:
        targets = []
    return {
        "id": row["id"], "user_id": row["user_id"], "business_id": row["business_id"],
        "actor_type": row["actor_type"], "title": row["title"], "caption": row["caption"],
        "image_file": row["image_file"], "targets": targets,
        "crop_x": float(_row_val(row, "crop_x", 50) or 50),
        "crop_y": float(_row_val(row, "crop_y", 50) or 50),
        "crop_zoom": float(_row_val(row, "crop_zoom", 1) or 1),
        "daily_all_day": bool(int(_row_val(row, "daily_all_day", 1) or 0)),
        "daily_start": str(_row_val(row, "daily_start", "00:00") or "00:00"),
        "daily_end": str(_row_val(row, "daily_end", "23:59") or "23:59"),
        "start_at": row["start_at"], "end_at": row["end_at"],
        "duration_days": row["duration_days"], "price": row["price"],
        "status": _ad_status(row), "views": row["views"], "clicks": row["clicks"],
        "created_at": row["created_at"],
    }


def _demo_advertisements():
    """Haqiqiy reklama navbati to'lmaganda ko'rinishni sinash uchun demo bannerlar."""
    rows = [
        ("Mahalla Market", "Bugungi mahsulotlarga maxsus chegirma", "/demo_ads/demo_market.svg", 38, 50, 1.08),
        ("Samarqand Coffee", "Issiq qahva va yangi desertlar", "/demo_ads/demo_cafe.svg", 72, 52, 1.12),
        ("Smart Texnika", "Telefon va aksessuarlarga foydali taklif", "/demo_ads/demo_tech.svg", 77, 48, 1.05),
        ("Orzu Mebel", "Uyingiz uchun zamonaviy yechimlar", "/demo_ads/demo_home.svg", 78, 50, 1.10),
        ("Nafis Beauty", "Go'zalligingiz uchun yangi xizmatlar", "/demo_ads/demo_beauty.svg", 76, 50, 1.10),
    ]
    return [{
        "id": -(i + 1), "user_id": None, "business_id": None, "actor_type": "demo",
        "title": title, "caption": caption, "image_file": image,
        "crop_x": x, "crop_y": y, "crop_zoom": zoom,
        "daily_all_day": True, "daily_start": "00:00", "daily_end": "23:59",
        "targets": [{"level": "republic", "region": "", "district": ""}],
        "start_at": 0, "end_at": 0, "duration_days": 0, "price": 0,
        "status": "demo", "views": 0, "clicks": 0, "created_at": 0, "is_demo": True,
    } for i, (title, caption, image, x, y, zoom) in enumerate(rows)]


@router.get("/advertisements/rates")
async def advertisement_rates(x_telegram_init_data: str = Header(default="")):
    conn = db()
    require_user(conn, x_telegram_init_data)
    conn.close()
    return {
        "rates": AD_RATES,
        "discounts": {"7": 10, "14": 15, "30": 25},
        "currency": "UZS",
        "note": "To'lov tizimi ulanmaguncha reklama sinov rejimida darhol faol qilinadi.",
    }


@router.post("/advertisements/price")
async def advertisement_price(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    require_user(conn, x_telegram_init_data)
    conn.close()
    b = await request.json()
    targets = _clean_ad_targets(b.get("targets"))
    return _ad_price(targets, b.get("duration_days"))


@router.post("/advertisements/image")
async def upload_advertisement_image(
    request: Request,
    actor_type: str = "user",
    x_telegram_init_data: str = Header(default=""),
):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Reklama")
    if (actor_type or "user").lower() == "business":
        resolve_actor(conn, user, "business")
    conn.close()
    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    allowed = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if ctype not in allowed:
        raise HTTPException(400, "Reklama uchun JPG, PNG yoki WEBP rasm yuboring.")
    raw = await request.body()
    if not raw:
        raise HTTPException(400, "Rasm topilmadi.")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(400, "Reklama rasmi 5 MB dan oshmasin.")
    from main import UPLOAD_DIR
    folder = os.path.join(UPLOAD_DIR, "ads")
    os.makedirs(folder, exist_ok=True)
    name = "ad_" + str(user["id"]) + "_" + str(int(time.time())) + "_" + secrets.token_hex(8) + allowed[ctype]
    with open(os.path.join(folder, name), "wb") as f:
        f.write(raw)
    return {"ok": True, "image_file": "/uploads/ads/" + name}


@router.post("/advertisements")
async def create_advertisement(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Reklama")
    b = await request.json()
    actor = actor_from_body(conn, user, b)
    title = str(b.get("title") or "").strip()
    caption = str(b.get("caption") or "").strip()
    image_file = str(b.get("image_file") or "").strip()
    try:
        crop_x = max(0.0, min(100.0, float(b.get("crop_x", 50))))
        crop_y = max(0.0, min(100.0, float(b.get("crop_y", 50))))
        crop_zoom = max(1.0, min(3.0, float(b.get("crop_zoom", 1))))
    except (TypeError, ValueError):
        crop_x, crop_y, crop_zoom = 50.0, 50.0, 1.0
    daily_all_day = bool(b.get("daily_all_day", True))
    daily_start = str(b.get("daily_start") or "00:00").strip()
    daily_end = str(b.get("daily_end") or "23:59").strip()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", daily_start) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", daily_end):
        conn.close()
        raise HTTPException(400, "Kunlik reklama vaqtini to'g'ri kiriting.")
    if not daily_all_day and daily_start == daily_end:
        conn.close()
        raise HTTPException(400, "Boshlanish va tugash vaqti bir xil bo'lmasin.")
    if not title:
        conn.close()
        raise HTTPException(400, "Reklama sarlavhasini kiriting.")
    if not image_file.startswith("/uploads/ads/"):
        conn.close()
        raise HTTPException(400, "Reklama rasmini yuklang.")
    targets = _clean_ad_targets(b.get("targets"))
    try:
        start_at = int(b.get("start_at") or 0)
    except Exception:
        start_at = 0
    now = int(time.time())
    if start_at < now - 300:
        conn.close()
        raise HTTPException(400, "Reklama boshlanish vaqti o'tib ketgan.")
    if start_at > now + 180 * 86400:
        conn.close()
        raise HTTPException(400, "Boshlanish vaqtini 180 kundan uzoqqa qo'yib bo'lmaydi.")
    price = _ad_price(targets, b.get("duration_days"))
    end_at = start_at + price["days"] * 86400
    cur = conn.execute(
        """INSERT INTO advertisements(user_id,business_id,actor_type,title,caption,image_file,crop_x,crop_y,crop_zoom,daily_all_day,daily_start,daily_end,
                                       targets_json,start_at,end_at,duration_days,price,status,
                                       views,clicks,created_at,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,?,?)""",
        (user["id"], actor["business_id"], actor["type"], title[:120], caption[:240], image_file, crop_x, crop_y, crop_zoom,
         1 if daily_all_day else 0, daily_start, daily_end,
         json.dumps(targets, ensure_ascii=False), start_at, end_at, price["days"], price["total"],
         "active", now, now),
    )
    conn.commit()
    ad_id = cur.lastrowid
    row = conn.execute("SELECT * FROM advertisements WHERE id=?", (ad_id,)).fetchone()
    out = _ad_dict(row)
    out["pricing"] = price
    conn.close()
    return out


@router.get("/advertisements/my")
async def my_advertisements(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, user, actor_type)
    if actor["type"] == "business":
        rows = conn.execute("SELECT * FROM advertisements WHERE business_id=? ORDER BY created_at DESC", (actor["business_id"],)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM advertisements WHERE user_id=? AND business_id IS NULL ORDER BY created_at DESC", (user["id"],)).fetchall()
    out = [_ad_dict(r) for r in rows]
    conn.close()
    return out


@router.delete("/advertisements/{ad_id}")
async def cancel_advertisement(ad_id: int, actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Reklama")
    actor = resolve_actor(conn, user, actor_type)
    now = int(time.time())
    if actor["type"] == "business":
        cur = conn.execute("UPDATE advertisements SET status='cancelled',updated_at=? WHERE id=? AND business_id=?", (now, ad_id, actor["business_id"]))
    else:
        cur = conn.execute("UPDATE advertisements SET status='cancelled',updated_at=? WHERE id=? AND user_id=? AND business_id IS NULL", (now, ad_id, user["id"]))
    conn.commit()
    conn.close()
    if not cur.rowcount:
        raise HTTPException(404, "Reklama topilmadi.")
    return {"ok": True}


@router.get("/advertisements/active")
async def active_advertisements(x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = optional_user(conn, x_telegram_init_data)
    region = me["region"] if me else ""
    district = me["district"] if me else ""
    now = int(time.time())
    rows = conn.execute(
        "SELECT * FROM advertisements WHERE status='active' AND start_at<=? AND end_at>? ORDER BY views ASC, created_at ASC, id ASC LIMIT 200",
        (now, now),
    ).fetchall()
    matched = []
    uz_now = time.gmtime(now + 5 * 3600)
    minute_now = uz_now.tm_hour * 60 + uz_now.tm_min
    for r in rows:
        if not bool(int(_row_val(r, "daily_all_day", 1) or 0)):
            try:
                sh, sm = map(int, str(_row_val(r, "daily_start", "00:00")).split(":"))
                eh, em = map(int, str(_row_val(r, "daily_end", "23:59")).split(":"))
                start_minute, end_minute = sh * 60 + sm, eh * 60 + em
                in_window = (start_minute <= minute_now < end_minute) if start_minute < end_minute else (minute_now >= start_minute or minute_now < end_minute)
                if not in_window:
                    continue
            except Exception:
                pass
        try:
            targets = json.loads(r["targets_json"] or "[]")
        except Exception:
            targets = []
        if _ad_matches(targets, region, district):
            d = _ad_dict(r)
            matched.append(d)
            if len(matched) >= 5:
                break
    if len(matched) < 5:
        matched.extend(_demo_advertisements()[:5 - len(matched)])
    conn.close()
    return matched


@router.post("/advertisements/views")
async def advertisement_views(request: Request, x_telegram_init_data: str = Header(default="")):
    """Ekranda kamida 2 soniya ko'ringan reklamalarning paket hisobini yozadi."""
    conn = db()
    require_user(conn, x_telegram_init_data)
    body = await request.json()
    clean_ids = []
    for value in (body.get("ids") if isinstance(body, dict) else []) or []:
        try:
            ad_id = int(value)
        except (TypeError, ValueError):
            continue
        if ad_id > 0 and ad_id not in clean_ids:
            clean_ids.append(ad_id)
        if len(clean_ids) >= 5:
            break
    if clean_ids:
        q = ",".join("?" for _ in clean_ids)
        conn.execute("UPDATE advertisements SET views=views+1 WHERE id IN (" + q + ") AND status='active'", clean_ids)
        conn.commit()
    conn.close()
    return {"ok": True, "count": len(clean_ids)}


@router.post("/advertisements/{ad_id}/click")
async def advertisement_click(ad_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    optional_user(conn, x_telegram_init_data)
    conn.execute("UPDATE advertisements SET clicks=clicks+1 WHERE id=? AND status='active'", (ad_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ====================================================================
# E'LONLAR
# ====================================================================
@router.post("/listings/media")
async def upload_listing_media(request: Request, actor_type: str = "user",
                               x_telegram_init_data: str = Header(default="")):
    """E'lon rasmi yoki videosini qurilmadan bevosita serverga yuklaydi."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "E'lon mediasi")
    resolve_actor(conn, user, actor_type)
    conn.close()

    ctype = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    allowed_images = {
        "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
        "image/webp": ".webp", "image/gif": ".gif", "image/heic": ".heic",
        "image/heif": ".heif",
    }
    allowed_videos = {
        "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
        "video/x-m4v": ".m4v",
    }
    if ctype in allowed_images:
        mtype, ext, max_size = "photo", allowed_images[ctype], 10 * 1024 * 1024
    elif ctype in allowed_videos:
        mtype, ext, max_size = "video", allowed_videos[ctype], 50 * 1024 * 1024
    else:
        raise HTTPException(400, "JPG, PNG, WEBP, GIF, HEIC, MP4, WEBM yoki MOV fayl tanlang.")

    raw = await request.body()
    if not raw:
        raise HTTPException(400, "Media fayl topilmadi.")
    if len(raw) > max_size:
        limit_mb = 10 if mtype == "photo" else 50
        raise HTTPException(400, "Fayl hajmi " + str(limit_mb) + " MB dan oshmasin.")

    from main import UPLOAD_DIR
    folder = os.path.join(UPLOAD_DIR, "listings")
    os.makedirs(folder, exist_ok=True)
    safe_name = "listing_" + str(user["id"]) + "_" + str(int(time.time())) + "_" + secrets.token_hex(8) + ext
    with open(os.path.join(folder, safe_name), "wb") as f:
        f.write(raw)
    media_url = "/uploads/listings/" + safe_name
    return {"ok": True, "file_id": media_url, "type": mtype, "media_url": media_url}


@router.post("/listings")
async def create_listing(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    b = await request.json()
    title = (b.get("title") or "").strip()
    cat = (b.get("cat") or "").strip()
    if not title or not cat:
        conn.close()
        raise HTTPException(400, "Sarlavha va toifa kiritilishi shart.")

    actor = actor_from_body(conn, user, b)
    visibility = "all"
    business_id = None
    if actor["type"] == "business":
        business_id = actor["business_id"]
        if b.get("visibility") == "own":
            visibility = "own"  # faqat biznes sahifasi mehmonlariga

    cur = conn.execute(
        """INSERT INTO listings(user_id, business_id, cat, title, price, descr, address,
                                lat, lng, visibility, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (user["id"], business_id, cat, title, (b.get("price") or "").strip(),
         (b.get("descr") or "").strip(), (b.get("address") or "").strip(),
         b.get("lat"), b.get("lng"), visibility, int(time.time())),
    )
    listing_id = cur.lastrowid
    for i, m in enumerate((b.get("media") or [])[:10]):
        fid = (m.get("file_id") or "").strip()
        if fid:
            conn.execute(
                "INSERT INTO listing_media(listing_id, tg_file_id, mtype, pos) VALUES(?,?,?,?)",
                (listing_id, fid, "video" if m.get("type") == "video" else "photo", i),
            )
    conn.commit()

    # Bildirishnoma: shu e'longa mos filtri bor foydalanuvchilarga xabar
    targets = []
    if visibility == "all":
        try:
            targets = _match_notify_filters(conn, {
                "cat": cat,
                "title": title,
                "descr": (b.get("descr") or ""),
                "address": (b.get("address") or ""),
                "price_num": _price_to_number(b.get("price") or ""),
                "owner_id": user["id"],
            })
        except Exception:
            targets = []
    conn.close()

    # Telegram xabarlarini yuboramiz (o'ziga emas)
    for t in targets:
        try:
            from main import tg_call, BASE_URL
            await tg_call("sendMessage", {
                "chat_id": t["tg_id"],
                "text": "📢 Yangi e'lon — " + _cat_name(cat) + ":\n" + title +
                        ((" — " + (b.get("price") or "")) if b.get("price") else ""),
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Ko'rish", "web_app": {"url": BASE_URL}}
                ]]},
            })
        except Exception:
            pass
    return {"id": listing_id}


# --- Bildirishnoma yordamchilari ---
_CAT_NAMES = {"uy": "Uy-joy", "ish": "Ish o'rinlari", "moshina": "Moshinalar",
              "hayvon": "Hayvonlar", "texnika": "Texnika", "boshqa": "Boshqalar"}
def _cat_name(cat):
    return _CAT_NAMES.get(cat, cat)

def _price_to_number(price_text):
    """Narx matnidan raqamni ajratadi: '9 800 $' -> 9800, '5 mln so'm' -> 5000000. Topilmasa None."""
    import re
    if not price_text:
        return None
    t = price_text.lower().replace("\u00a0", " ")
    m = re.search(r"[\d][\d\s]*", t)
    if not m:
        return None
    base = int(re.sub(r"\s", "", m.group(0)) or 0)
    if base == 0:
        return None
    if "mln" in t or "million" in t:
        base *= 1_000_000
    elif "ming" in t:
        base *= 1_000
    return base

def _match_notify_filters(conn, listing):
    """E'longa mos keladigan filtrlar egalarini topadi (o'zidan tashqari)."""
    rows = conn.execute(
        "SELECT nf.*, u.tg_id AS u_tg FROM notify_filters nf JOIN users u ON u.id=nf.user_id WHERE nf.cat=?",
        (listing["cat"],),
    ).fetchall()
    text_blob = (listing["title"] + " " + listing["descr"] + " " + listing["address"]).lower()
    seen = set()
    out = []
    for f in rows:
        if f["user_id"] == listing["owner_id"]:
            continue  # o'ziga yubormaymiz
        if not f["u_tg"]:
            continue  # Telegramga bog'lanmagan
        # hudud
        if f["region"] and f["region"].lower() not in text_blob and (f["district"] or "").lower() not in text_blob:
            # agar tuman ham mos kelmasa, o'tkazamiz
            if not (f["district"] and f["district"].lower() in text_blob):
                continue
        if f["district"] and f["district"].lower() not in text_blob:
            continue
        # narx
        pn = listing["price_num"]
        if f["price_min"] and (pn is None or pn < f["price_min"]):
            continue
        if f["price_max"] and (pn is None or pn > f["price_max"]):
            continue
        # kalit so'z
        if f["keyword"] and f["keyword"].lower() not in text_blob:
            continue
        if f["u_tg"] in seen:
            continue
        seen.add(f["u_tg"])
        out.append({"tg_id": f["u_tg"]})
    return out


@router.get("/listings/my")
async def my_listings(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, user, actor_type)
    if actor["type"] == "business":
        rows = conn.execute(
            "SELECT * FROM listings WHERE business_id=? ORDER BY created_at DESC",
            (actor["business_id"],),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM listings WHERE user_id=? AND business_id IS NULL ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    result = [listing_to_dict(conn, r) for r in rows]
    conn.close()
    return result


@router.put("/listings/{listing_id}")
async def edit_listing(listing_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    b = await request.json()
    actor = actor_from_body(conn, user, b)
    if actor["type"] == "business":
        row = conn.execute(
            "SELECT * FROM listings WHERE id=? AND business_id=?",
            (listing_id, actor["business_id"]),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM listings WHERE id=? AND user_id=? AND business_id IS NULL",
            (listing_id, user["id"]),
        ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "E'lon topilmadi.")
    status = b.get("status") if b.get("status") in ("active", "inactive") else row["status"]
    visibility = row["visibility"]
    if actor["type"] == "business" and b.get("visibility") in ("all", "own"):
        visibility = b["visibility"]
    conn.execute(
        """UPDATE listings SET title=?, price=?, descr=?, address=?, lat=?, lng=?,
           status=?, visibility=? WHERE id=?""",
        ((b.get("title") or row["title"]).strip(), (b.get("price") or row["price"]).strip(),
         (b.get("descr") or row["descr"]).strip(), (b.get("address") or row["address"]).strip(),
         b.get("lat", row["lat"]), b.get("lng", row["lng"]), status, visibility, listing_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/listings/{listing_id}")
async def delete_listing(listing_id: int, actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, user, actor_type)
    if actor["type"] == "business":
        conn.execute("DELETE FROM listings WHERE id=? AND business_id=?", (listing_id, actor["business_id"]))
    else:
        conn.execute("DELETE FROM listings WHERE id=? AND user_id=? AND business_id IS NULL", (listing_id, user["id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/listings/counts")
async def listing_counts(x_telegram_init_data: str = Header(default="")):
    """Har toifadagi ochiq e'lonlar soni (bosh sahifa kartochkalari uchun)."""
    conn = db()
    rows = conn.execute(
        "SELECT cat, COUNT(*) AS n FROM listings WHERE status='active' AND visibility='all' GROUP BY cat"
    ).fetchall()
    conn.close()
    return {r["cat"]: r["n"] for r in rows}


@router.get("/listings")
async def public_listings(cat: str = "", q: str = "", x_telegram_init_data: str = Header(default="")):
    """Ochiq e'lonlar (faqat 'butun platforma' ko'rinishidagilar)."""
    conn = db()
    me = optional_user(conn, x_telegram_init_data)
    saved_ids = set()
    if me:
        for s in conn.execute("SELECT target_id FROM saved WHERE user_id=? AND target_kind='listing'", (me["id"],)).fetchall():
            saved_ids.add(s["target_id"])
    sql = "SELECT * FROM listings WHERE status='active' AND visibility='all'"
    args = []
    if cat:
        sql += " AND cat=?"
        args.append(cat)
    if q:
        sql += " AND title LIKE ?"
        args.append("%" + q + "%")
    sql += " ORDER BY created_at DESC LIMIT 100"
    rows = conn.execute(sql, args).fetchall()
    result = []
    for r in rows:
        d = listing_to_dict(conn, r)
        d["is_saved"] = r["id"] in saved_ids
        result.append(d)
    conn.close()
    return result


@router.get("/listings/{listing_id}")
async def listing_detail(listing_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    r = conn.execute("SELECT * FROM listings WHERE id=? AND status='active'", (listing_id,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "E'lon topilmadi.")
    result = listing_to_dict(conn, r)
    conn.close()
    return result


# ====================================================================
# OBUNA (FOLLOW)
# ====================================================================
@router.post("/follow")
async def toggle_follow(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    b = await request.json()
    actor = actor_from_body(conn, user, b)
    kind = b.get("target_kind")
    target_id = b.get("target_id")
    if kind not in ("user", "business") or not target_id:
        conn.close()
        raise HTTPException(400, "Obuna nishoni noto'g'ri.")
    try:
        target_id = int(target_id)
    except Exception:
        conn.close()
        raise HTTPException(400, "Obuna nishoni noto'g'ri.")

    # Nishon haqiqatda mavjudligini tekshiramiz.
    if kind == "business":
        target = conn.execute("SELECT id FROM businesses WHERE id=? AND status='active'", (target_id,)).fetchone()
    else:
        target = conn.execute("SELECT id FROM users WHERE id=?", (target_id,)).fetchone()
    if not target:
        conn.close()
        raise HTTPException(404, "Obuna bo'linadigan profil topilmadi.")

    if actor["type"] == "business":
        business_id = actor["business_id"]
        if kind == "business" and target_id == business_id:
            conn.close()
            raise HTTPException(400, "Biznes o'ziga obuna bo'la olmaydi.")
        if kind == "user" and target_id == user["id"]:
            conn.close()
            raise HTTPException(400, "Biznes egasining o'z profiliga obuna bo'lib bo'lmaydi.")
        existing = conn.execute(
            "SELECT id FROM business_follows WHERE business_id=? AND target_kind=? AND target_id=?",
            (business_id, kind, target_id),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM business_follows WHERE id=?", (existing["id"],))
            following = False
        else:
            conn.execute(
                "INSERT INTO business_follows(business_id, target_kind, target_id, created_at) VALUES(?,?,?,?)",
                (business_id, kind, target_id, int(time.time())),
            )
            following = True
    else:
        if kind == "user" and target_id == user["id"]:
            conn.close()
            raise HTTPException(400, "O'zingizga obuna bo'la olmaysiz.")
        existing = conn.execute(
            "SELECT id FROM follows WHERE follower_id=? AND target_kind=? AND target_id=?",
            (user["id"], kind, target_id),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM follows WHERE id=?", (existing["id"],))
            following = False
        else:
            conn.execute(
                "INSERT INTO follows(follower_id, target_kind, target_id, created_at) VALUES(?,?,?,?)",
                (user["id"], kind, target_id, int(time.time())),
            )
            following = True
    conn.commit()
    count = follower_count(conn, kind, target_id)
    conn.close()
    return {"following": following, "followers": count, "actor_type": actor["type"]}


@router.get("/follows/my")
async def my_follows(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    """Joriy kabinet (user yoki biznes) obuna bo'lgan profillar."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, user, actor_type)
    if actor["type"] == "business":
        rows = conn.execute(
            "SELECT target_kind, target_id, created_at FROM business_follows WHERE business_id=? ORDER BY created_at DESC",
            (actor["business_id"],),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT target_kind, target_id, created_at FROM follows WHERE follower_id=? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    result = []
    for r in rows:
        if r["target_kind"] == "business":
            t = conn.execute("SELECT id, name, yon FROM businesses WHERE id=?", (r["target_id"],)).fetchone()
            if t:
                result.append({"kind": "business", "id": t["id"], "name": t["name"], "info": t["yon"]})
        else:
            t = conn.execute("SELECT id, name, district FROM users WHERE id=?", (r["target_id"],)).fetchone()
            if t:
                result.append({"kind": "user", "id": t["id"], "name": t["name"], "info": t["district"]})
    conn.close()
    return result


@router.get("/followers/my")
async def my_followers(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    """Joriy profilga obuna bo'lgan oddiy foydalanuvchi va bizneslar."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, user, actor_type)
    if actor["type"] == "business":
        target_kind, target_id = "business", actor["business_id"]
    else:
        target_kind, target_id = "user", user["id"]

    result = []
    user_rows = conn.execute(
        "SELECT follower_id FROM follows WHERE target_kind=? AND target_id=? ORDER BY created_at DESC",
        (target_kind, target_id),
    ).fetchall()
    for r in user_rows:
        u = conn.execute("SELECT id, name, district FROM users WHERE id=?", (r["follower_id"],)).fetchone()
        if u:
            result.append({"kind": "user", "id": u["id"], "name": u["name"], "info": u["district"]})

    business_rows = conn.execute(
        "SELECT business_id FROM business_follows WHERE target_kind=? AND target_id=? ORDER BY created_at DESC",
        (target_kind, target_id),
    ).fetchall()
    for r in business_rows:
        b = conn.execute("SELECT id, name, yon FROM businesses WHERE id=? AND status='active'", (r["business_id"],)).fetchone()
        if b:
            result.append({"kind": "business", "id": b["id"], "name": b["name"], "info": b["yon"]})
    conn.close()
    return result



# ====================================================================
# XARITA (bosh ekran): platforma ko'rsatadiganlar + obunalar
# ====================================================================
def _map_business_dict(row, source, following=False):
    """Bosh xarita uchun biznesni ixcham ko'rinishga o'tkazadi."""
    return {
        "id": row["id"],
        "name": row["name"],
        "yon": row["yon"],
        "tur": row["tur"],
        "address": row["address"],
        "logo_file": _row_val(row, "logo_file", "") or "",
        "logo_x": float(_row_val(row, "logo_x", 50) or 50),
        "logo_y": float(_row_val(row, "logo_y", 50) or 50),
        "logo_zoom": float(_row_val(row, "logo_zoom", 1) or 1),
        "lat": row["lat"],
        "lng": row["lng"],
        "source": source,
        "following": following,
    }


def _map_specialist_dict(row):
    """Bosh xarita uchun mutaxasis/foydalanuvchini ixcham ko'rinishga o'tkazadi."""
    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "kasb": row["kasb"],
        "narx": row["narx"],
        "is_gov": bool(row["is_gov"]),
        "available": bool(row["available"]),
        "district": row["district"],
        "avatar_file": _row_val(row, "avatar_file", "") or "",
        "avatar_x": float(_row_val(row, "avatar_x", 50) or 50),
        "avatar_y": float(_row_val(row, "avatar_y", 50) or 50),
        "avatar_zoom": float(_row_val(row, "avatar_zoom", 1) or 1),
        "lat": row["lat"],
        "lng": row["lng"],
        "source": "obuna",
    }


@router.get("/map")
async def home_map(actor: str = "", x_telegram_init_data: str = Header(default="")):
    """
    Bosh sahifa xaritasi uchun obyektlar.

    Bu endpoint HAMMA biznesni qaytarmaydi. Faqat:
      1) platforma tomonidan bosh xaritada ko'rsatishga belgilangan bizneslar;
      2) joriy foydalanuvchi obuna bo'lgan, joylashuvi bor bizneslar;
      3) joriy foydalanuvchi obuna bo'lgan, ko'rinadigan va joylashuvi bor mutaxasislar.
    """
    conn = db()
    user = require_user(conn, x_telegram_init_data)

    # 1) Platforma tomonidan ko'rsatiladigan bizneslar
    platform_rows = conn.execute(
        """SELECT * FROM businesses
           WHERE status='active'
             AND lat IS NOT NULL AND lng IS NOT NULL
             AND COALESCE(map_visible, 0)=1
           ORDER BY created_at DESC
           LIMIT 200"""
    ).fetchall()

    business_map = {}
    for b in platform_rows:
        business_map[b["id"]] = _map_business_dict(b, "platforma", following=False)

    # 2) Joriy kabinet obuna bo'lgan bizneslar
    actor_ctx = resolve_actor(conn, user, "business" if (actor or "").strip().lower() == "business" else "user")
    if actor_ctx["type"] == "business":
        followed_rows = conn.execute(
            """SELECT b.* FROM business_follows f
               JOIN businesses b ON b.id=f.target_id
               WHERE f.business_id=?
                 AND f.target_kind='business'
                 AND b.status='active'
                 AND b.lat IS NOT NULL AND b.lng IS NOT NULL
               ORDER BY f.created_at DESC
               LIMIT 200""",
            (actor_ctx["business_id"],),
        ).fetchall()
    else:
        followed_rows = conn.execute(
            """SELECT b.* FROM follows f
               JOIN businesses b ON b.id=f.target_id
               WHERE f.follower_id=?
                 AND f.target_kind='business'
                 AND b.status='active'
                 AND b.lat IS NOT NULL AND b.lng IS NOT NULL
               ORDER BY f.created_at DESC
               LIMIT 200""",
            (user["id"],),
        ).fetchall()

    for b in followed_rows:
        if b["id"] in business_map:
            business_map[b["id"]]["source"] = "platforma+obuna"
            business_map[b["id"]]["following"] = True
        else:
            business_map[b["id"]] = _map_business_dict(b, "obuna", following=True)

    # 3) Joriy kabinet obuna bo'lgan, xaritada ko'rinishga ruxsat bergan mutaxassislar
    if actor_ctx["type"] == "business":
        specialist_rows = conn.execute(
            """SELECT s.*, u.name, u.district, u.avatar_file, u.avatar_x, u.avatar_y, u.avatar_zoom
               FROM business_follows f
               JOIN specialists s ON s.user_id=f.target_id
               JOIN users u ON u.id=s.user_id
               WHERE f.business_id=?
                 AND f.target_kind='user'
                 AND s.visible=1
                 AND s.lat IS NOT NULL AND s.lng IS NOT NULL
               ORDER BY f.created_at DESC
               LIMIT 200""",
            (actor_ctx["business_id"],),
        ).fetchall()
    else:
        specialist_rows = conn.execute(
            """SELECT s.*, u.name, u.district, u.avatar_file, u.avatar_x, u.avatar_y, u.avatar_zoom
               FROM follows f
               JOIN specialists s ON s.user_id=f.target_id
               JOIN users u ON u.id=s.user_id
               WHERE f.follower_id=?
                 AND f.target_kind='user'
                 AND s.visible=1
                 AND s.lat IS NOT NULL AND s.lng IS NOT NULL
               ORDER BY f.created_at DESC
               LIMIT 200""",
            (user["id"],),
        ).fetchall()

    result = {
        "businesses": list(business_map.values()),
        "specialists": [_map_specialist_dict(s) for s in specialist_rows],
    }
    conn.close()
    return result

# ====================================================================
# SAQLANGANLAR
# ====================================================================
@router.post("/save")
async def toggle_save(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    b = await request.json()
    actor = actor_from_body(conn, user, b)
    if actor["type"] != "user":
        conn.close()
        raise HTTPException(400, "Saqlanganlar hozircha oddiy kabinet uchun.")
    kind = b.get("target_kind")
    target_id = b.get("target_id")
    if kind not in ("listing", "business") or not target_id:
        conn.close()
        raise HTTPException(400, "Saqlash nishoni noto'g'ri.")
    existing = conn.execute(
        "SELECT id FROM saved WHERE user_id=? AND target_kind=? AND target_id=?",
        (user["id"], kind, target_id),
    ).fetchone()
    if existing:
        conn.execute("DELETE FROM saved WHERE id=?", (existing["id"],))
        saved = False
    else:
        conn.execute(
            "INSERT INTO saved(user_id, target_kind, target_id, created_at) VALUES(?,?,?,?)",
            (user["id"], kind, target_id, int(time.time())),
        )
        saved = True
    conn.commit()
    conn.close()
    return {"saved": saved}


@router.get("/saved")
async def my_saved(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, user, actor_type)
    if actor["type"] != "user":
        conn.close()
        return []
    rows = conn.execute(
        "SELECT * FROM saved WHERE user_id=? ORDER BY created_at DESC", (user["id"],)
    ).fetchall()
    result = []
    for r in rows:
        if r["target_kind"] == "listing":
            t = conn.execute(
                "SELECT id, title, price, cat FROM listings WHERE id=? AND status='active'",
                (r["target_id"],),
            ).fetchone()
            if t:
                result.append({"kind": "listing", "id": t["id"], "name": t["title"],
                               "info": t["price"], "cat": t["cat"]})
        else:
            t = conn.execute("SELECT id, name, yon FROM businesses WHERE id=?", (r["target_id"],)).fetchone()
            if t:
                result.append({"kind": "business", "id": t["id"], "name": t["name"], "info": t["yon"]})
    conn.close()
    return result


# ====================================================================
# QARZ DAFTARI (biznes kabineti)
# ====================================================================
def qarz_balance(conn, debtor_id):
    row = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN type='debt' THEN amount ELSE -amount END),0) b "
        "FROM qarz_tx WHERE debtor_id=?", (debtor_id,),
    ).fetchone()
    return row["b"] or 0


# ================== OMBOR (qoldiq + kirim-chiqim tarixi) ==================
_STOCK_REASON_TEXT = {"kirim": "Kirim", "chiqim": "Chiqim", "sotuv": "Sotuv (buyurtma)", "tuzatish": "Tuzatish"}


def _stock_delta(v):
    """Kirim/chiqim miqdori: kasr ham bo'ladi, vergul ham qabul qilinadi."""
    try:
        d = float(str(v if v is not None else 0).replace(",", ".").strip() or 0)
    except Exception:
        d = 0.0
    if d != d:
        d = 0.0
    d = round(d, 3)
    if abs(d) > 100000:
        raise HTTPException(400, "Miqdor juda katta.")
    return d


def _stock_deduct_for_order(conn, order, actor_user_id):
    """Buyurtma "Bajarildi" bo'lganda ombordan avtomatik chiqim.
    Faqat bir marta ishlaydi (shu buyurtma uchun harakat bo'lsa — qaytadan ayirmaydi).
    Faqat "Omborda hisoblash" yoqilgan mahsulotlarga ta'sir qiladi."""
    if (order["provider_kind"] or "") != "business":
        return
    already = conn.execute(
        "SELECT COUNT(*) FROM stock_moves WHERE order_id=?", (order["id"],)
    ).fetchone()[0]
    if already:
        return
    rows = conn.execute(
        "SELECT item_id, qty FROM order_items WHERE order_id=?", (order["id"],)
    ).fetchall()
    now = int(time.time())
    for oi in rows:
        if not oi["item_id"]:
            continue
        it = conn.execute(
            "SELECT id, business_id, track_stock FROM items WHERE id=?", (oi["item_id"],)
        ).fetchone()
        if not it or not (it["track_stock"] or 0):
            continue
        if int(it["business_id"]) != int(order["provider_actor_id"] or 0):
            continue
        q = round(float(oi["qty"] or 1), 3)
        if q <= 0:
            continue
        conn.execute("UPDATE items SET stock_qty=ROUND(COALESCE(stock_qty,0)-?, 3) WHERE id=?", (q, it["id"]))
        conn.execute(
            "INSERT INTO stock_moves(business_id, item_id, delta, reason, note, order_id, user_id, created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (it["business_id"], it["id"], -q, "sotuv", "Buyurtma #%d" % order["id"], order["id"], actor_user_id, now),
        )


def _stock_restore_for_order(conn, order, actor_user_id):
    """Buyurtma bekor qilinsa: 'Bajarildi'da ayirilgan qoldiq qaytadi va kassadagi
    avtomatik savdo yozuvlari olib tashlanadi. Faqat bir marta ishlaydi."""
    if (order["provider_kind"] or "") != "business":
        return
    sold = conn.execute(
        "SELECT * FROM stock_moves WHERE order_id=? AND reason='sotuv'", (order["id"],)
    ).fetchall()
    if sold:
        already = conn.execute(
            "SELECT COUNT(*) FROM stock_moves WHERE order_id=? AND reason='tuzatish'", (order["id"],)
        ).fetchone()[0]
        if not already:
            now = int(time.time())
            for m in sold:
                q = round(abs(float(m["delta"] or 0)), 3)
                if q <= 0:
                    continue
                conn.execute("UPDATE items SET stock_qty=ROUND(COALESCE(stock_qty,0)+?, 3) WHERE id=?", (q, m["item_id"]))
                conn.execute(
                    "INSERT INTO stock_moves(business_id, item_id, delta, reason, note, order_id, user_id, created_at) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (m["business_id"], m["item_id"], q, "tuzatish",
                     "Buyurtma #%d bekor qilindi" % order["id"], order["id"], actor_user_id, now),
                )
    conn.execute("DELETE FROM sales WHERE order_id=? AND source='order'", (order["id"],))


def _stock_move_deletable(r):
    """Faqat qo'lda qilingan kirim/chiqimni o'chirish mumkin (buyurtma/kassa bilan bog'liqlarni emas)."""
    if r["order_id"]:
        return False
    if (r["reason"] or "") not in ("kirim", "chiqim"):
        return False
    if (r["note"] or "").startswith("Kassa") or (r["note"] or "").startswith("Chek"):
        return False
    return True


@router.get("/stock")
async def stock_list(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    need_perm(conn, x_telegram_init_data, "ombor")
    _ensure_item_min_qty(conn)
    rows = conn.execute(
        "SELECT i.id, i.name, i.unit, i.stock_qty, i.cost_price, i.min_qty, i.photo_file, i.group_id, "
        "g.name AS group_name FROM items i "
        "LEFT JOIN item_groups g ON g.id = i.group_id "
        "WHERE i.business_id=? AND i.track_stock=1 "
        "ORDER BY i.name COLLATE NOCASE",
        (biz["id"],),
    ).fetchall()
    result = [{"id": r["id"], "name": r["name"], "unit": r["unit"] or "dona",
               "stock_qty": r["stock_qty"] or 0, "cost_price": r["cost_price"] or 0,
               "min_qty": _row_val(r, "min_qty", 0) or 0,
               "photo_file": r["photo_file"] or "", "group_id": r["group_id"],
               "group_name": r["group_name"] or ""} for r in rows]
    conn.close()
    return result


@router.post("/stock/move")
async def stock_move(body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    need_perm(conn, x_telegram_init_data, "ombor")
    item_id = int(body.get("item_id") or 0)
    it = conn.execute("SELECT * FROM items WHERE id=? AND business_id=?", (item_id, biz["id"])).fetchone()
    if not it:
        conn.close()
        raise HTTPException(404, "Mahsulot topilmadi.")
    delta = _stock_delta(body.get("delta"))
    unit = _row_val(it, "unit", "dona") or "dona"
    if unit not in FRACTIONAL_UNITS and not float(delta).is_integer():
        # sanaladigan birlik — butun songa keltiramiz
        sgn = 1 if delta > 0 else -1
        delta = sgn * float(int(math.floor(abs(delta) + 0.5)))
    if delta == 0:
        conn.close()
        raise HTTPException(400, "Miqdor kiritilmadi.")
    reason = (body.get("reason") or "").strip()
    if reason not in _STOCK_REASON_TEXT:
        reason = "kirim" if delta > 0 else "chiqim"
    note = (body.get("note") or "").strip()[:200]
    try:
        cost = int(str(body.get("cost") or "0").replace(" ", "") or 0)
    except Exception:
        cost = 0
    if cost < 0:
        cost = 0
    now = int(time.time())
    conn.execute("UPDATE items SET stock_qty=ROUND(COALESCE(stock_qty,0)+?, 3) WHERE id=?", (delta, item_id))
    if delta > 0 and cost > 0:
        # oxirgi tannarx mahsulotda saqlanadi (foyda hisobi uchun)
        conn.execute("UPDATE items SET cost_price=? WHERE id=?", (cost, item_id))
    cur_m = conn.execute(
        "INSERT INTO stock_moves(business_id, item_id, delta, reason, note, cost, order_id, user_id, created_at) "
        "VALUES(?,?,?,?,?,?,NULL,?,?)",
        (biz["id"], item_id, delta, reason, note, cost, user["id"], now),
    )
    # v1414: kirim (tannarx bilan) -> "Tovar xaridi" xarajati avtomatik
    if delta > 0 and cost > 0:
        _spent = int(round(cost * float(delta)))
        if _spent > 0:
            _iname = conn.execute("SELECT name FROM items WHERE id=?", (item_id,)).fetchone()
            _expense_add(conn, biz["id"], "Tovar xaridi", _spent,
                         (_iname["name"] if _iname else "") + (" — " + note if note else ""),
                         user["id"], source="stock", stock_move_id=cur_m.lastrowid)
    conn.commit()
    new_q = conn.execute("SELECT stock_qty FROM items WHERE id=?", (item_id,)).fetchone()["stock_qty"]
    conn.close()
    return {"ok": True, "stock_qty": new_q or 0}


@router.delete("/stock/moves/{move_id}")
async def stock_move_delete(move_id: int, x_telegram_init_data: str = Header(default="")):
    """Xato yozilgan qo'lda kirim/chiqimni o'chirish — qoldiq teskarisiga qaytadi."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    need_perm(conn, x_telegram_init_data, "ombor")
    r = conn.execute("SELECT * FROM stock_moves WHERE id=? AND business_id=?", (move_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Harakat topilmadi.")
    if not _stock_move_deletable(r):
        conn.close()
        raise HTTPException(400, "Bu harakat buyurtma yoki kassa bilan bog'liq — o'chirib bo'lmaydi.")
    conn.execute("UPDATE items SET stock_qty=ROUND(COALESCE(stock_qty,0)-?, 3) WHERE id=?",
                 (float(r["delta"] or 0), r["item_id"]))
    conn.execute("DELETE FROM expenses WHERE source='stock' AND stock_move_id=?", (move_id,))
    conn.execute("DELETE FROM stock_moves WHERE id=?", (move_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/stock/moves")
async def stock_moves_list(item_id: int = 0, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    it = conn.execute("SELECT unit FROM items WHERE id=? AND business_id=?", (item_id, biz["id"])).fetchone()
    if not it:
        conn.close()
        raise HTTPException(404, "Mahsulot topilmadi.")
    unit = it["unit"] or "dona"
    rows = conn.execute(
        "SELECT m.*, u.name AS who FROM stock_moves m "
        "LEFT JOIN users u ON u.id = m.user_id "
        "WHERE m.business_id=? AND m.item_id=? "
        "ORDER BY m.created_at DESC, m.id DESC LIMIT 100",
        (biz["id"], item_id),
    ).fetchall()
    result = [{"id": r["id"], "delta": r["delta"], "reason": r["reason"],
               "reason_text": _STOCK_REASON_TEXT.get(r["reason"], r["reason"] or ""),
               "note": r["note"] or "", "who": r["who"] or "",
               "cost": _row_val(r, "cost", 0) or 0,
               "can_delete": _stock_move_deletable(r),
               "order_id": r["order_id"], "created_at": r["created_at"], "unit": unit}
              for r in rows]
    conn.close()
    return result


# ================== ULASHISH / DEEP-LINK RESOLVE ==================
_BOT_UNAME_CACHE = ""
_BOT_HASAPP_CACHE = None   # True bo'lsa keshlanadi; False/None bo'lsa har safar qayta so'raladi


@router.get("/config")
async def app_config():
    """Frontend sozlamalari: bot username + botda Mini App yoqilganmi (getMe)."""
    global _BOT_UNAME_CACHE, _BOT_HASAPP_CACHE
    if (not _BOT_UNAME_CACHE) or (_BOT_HASAPP_CACHE is not True):
        try:
            from main import tg_call
            r = await tg_call("getMe", {})
            res = (r or {}).get("result") or {}
            u = (res.get("username") or "").strip()
            if u:
                _BOT_UNAME_CACHE = u
            if "has_main_web_app" in res:
                _BOT_HASAPP_CACHE = bool(res.get("has_main_web_app"))
        except Exception:
            pass
    return {"bot_username": _BOT_UNAME_CACHE or "TARTIBLANGANkoprik_bot",
            "has_main_web_app": _BOT_HASAPP_CACHE}


@router.get("/resolve")
async def resolve_share(param: str = "", x_telegram_init_data: str = Header(default="")):
    """startapp parametrini sahifaga aylantiradi: shop_<username|id> yoki user_<username>."""
    _tg(x_telegram_init_data)  # faqat ilova ichidan
    conn = db()
    p = (param or "").strip()
    try:
        if p.startswith("shop_"):
            rest = p[5:]
            if rest.isdigit():
                r = conn.execute("SELECT id, name FROM businesses WHERE id=? AND status='active'", (int(rest),)).fetchone()
            else:
                r = conn.execute("SELECT id, name FROM businesses WHERE lower(username)=? AND status='active'", (rest.lower(),)).fetchone()
            if r:
                conn.close()
                return {"type": "business", "id": r["id"], "name": r["name"]}
        elif p.startswith("user_"):
            rest = p[5:]
            if rest.isdigit():
                r = conn.execute("SELECT id, name FROM users WHERE id=?", (int(rest),)).fetchone()
            else:
                r = conn.execute("SELECT id, name FROM users WHERE lower(pub_username)=?", (rest.lower(),)).fetchone()
            if r:
                conn.close()
                return {"type": "user", "id": r["id"], "name": r["name"]}
    except Exception:
        pass
    conn.close()
    return {"type": None}


@router.get("/user/{user_id}")
async def public_user(user_id: int, x_telegram_init_data: str = Header(default="")):
    """Foydalanuvchining ommaviy sahifasi: ism, avatar, e'lonlari, (bo'lsa) mutaxassislik."""
    conn = db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not u:
        conn.close()
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    # Shaxsiy e'lonlar (biznesga tegishli emas, faol)
    rows = conn.execute(
        "SELECT * FROM listings WHERE user_id=? AND business_id IS NULL AND status='active' "
        "ORDER BY created_at DESC LIMIT 100",
        (user_id,),
    ).fetchall()
    listings = [listing_to_dict(conn, r) for r in rows]
    # Mutaxassislik (agar bor va ko'rinadigan bo'lsa)
    sp = conn.execute("SELECT * FROM specialists WHERE user_id=? AND visible=1", (user_id,)).fetchone()
    specialist = None
    if sp:
        specialist = {
            "kasb": sp["kasb"] or "", "descr": sp["descr"] or "",
            **_specialist_content(conn, user_id),
        }
    result = {
        "id": u["id"], "name": u["name"] or "Foydalanuvchi",
        "avatar_file": _row_val(u, "avatar_file", "") or "",
        "avatar_x": float(_row_val(u, "avatar_x", 50) or 50), "avatar_y": float(_row_val(u, "avatar_y", 50) or 50),
        "avatar_zoom": float(_row_val(u, "avatar_zoom", 1) or 1),
        "pub_username": _row_val(u, "pub_username", "") or "",
        "region": u["region"] or "", "district": u["district"] or "",
        "listings": listings, "specialist": specialist,
        "followers": follower_count(conn, "user", u["id"]),
    }
    conn.close()
    return result


# ================== XODIMLAR (kadr) ==================
_DEFAULT_PROFESSIONS = ["Sotuvchi", "Kassir", "Menejer", "Hisobchi", "Omborchi",
                        "Yuk tashuvchi", "Haydovchi", "Farrosh", "Qorovul", "Boshqa"]


def _ensure_staff_tables(conn):
    """staff/staff_professions jadvallarini kafolatlaydi. Mavjud jadvalga yetishmagan
    ustunlarni ham qo'shadi (har biri alohida, xavfsiz). Hech narsa o'chirilmaydi."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS staff("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL, name TEXT NOT NULL, "
        "profession TEXT DEFAULT '', phone TEXT DEFAULT '', salary INTEGER DEFAULT 0, "
        "hire_date TEXT DEFAULT '', status TEXT DEFAULT 'active', note TEXT DEFAULT '', "
        "user_id INTEGER, created_at INTEGER NOT NULL, fired_at INTEGER)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS staff_professions("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL, "
        "name TEXT NOT NULL, created_at INTEGER NOT NULL)")
    # Eski staff jadvaliga yetishmagan ustunlarni majburan qo'shamiz (faqat yo'q bo'lsa)
    try:
        _sc = [r["name"] for r in conn.execute("PRAGMA table_info(staff)").fetchall()]
        _need = {"profession": "TEXT DEFAULT ''", "phone": "TEXT DEFAULT ''",
                 "salary": "INTEGER DEFAULT 0", "hire_date": "TEXT DEFAULT ''",
                 "status": "TEXT DEFAULT 'active'", "note": "TEXT DEFAULT ''",
                 "user_id": "INTEGER", "created_at": "INTEGER", "fired_at": "INTEGER",
                 "schedule_json": "TEXT DEFAULT ''",
                 "login": "TEXT DEFAULT ''", "pass_hash": "TEXT DEFAULT ''",
                 "pass_plain": "TEXT DEFAULT ''",
                 "perms": "TEXT DEFAULT ''", "can_login": "INTEGER DEFAULT 0"}
        for _col, _decl in _need.items():
            if _col not in _sc:
                try:
                    conn.execute("ALTER TABLE staff ADD COLUMN %s %s" % (_col, _decl))
                except Exception:
                    pass
    except Exception:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_staff_biz ON staff(business_id, status)")
    except Exception:
        pass
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS staff_attendance("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL, "
            "staff_id INTEGER NOT NULL, date TEXT NOT NULL, status TEXT DEFAULT '', "
            "time_in TEXT DEFAULT '', time_out TEXT DEFAULT '', created_at INTEGER NOT NULL, "
            "UNIQUE(staff_id, date))")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS staff_sessions("
            "token TEXT PRIMARY KEY, staff_id INTEGER NOT NULL, business_id INTEGER NOT NULL, "
            "created_at INTEGER NOT NULL)")
        conn.execute("DROP INDEX IF EXISTS uq_staff_login")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_staff_login_biz ON staff(business_id, lower(login)) WHERE COALESCE(login,'')<>''")
    except Exception:
        pass


def _professions(conn, biz_id):
    extra = [r["name"] for r in conn.execute(
        "SELECT name FROM staff_professions WHERE business_id=? ORDER BY name COLLATE NOCASE", (biz_id,)
    ).fetchall()]
    out = list(_DEFAULT_PROFESSIONS)
    for e in extra:
        if e not in out:
            out.append(e)
    return out


_STAFF_PERM_KEYS = ("kassa", "ombor", "buyurtma")


def _perms_parse(raw):
    try:
        arr = json.loads(raw) if raw else []
    except Exception:
        arr = []
    if not isinstance(arr, list):
        arr = []
    return [p for p in _STAFF_PERM_KEYS if p in arr]


def _perms_clean(arr):
    if not isinstance(arr, list):
        arr = []
    return [p for p in _STAFF_PERM_KEYS if p in arr]


def _norm_login(v):
    return (v or "").strip().lower()


def _staff_dict(r):
    return {"id": r["id"], "name": r["name"] or "", "profession": r["profession"] or "",
            "phone": r["phone"] or "", "salary": r["salary"] or 0,
            "hire_date": r["hire_date"] or "", "status": r["status"] or "active",
            "note": r["note"] or "", "created_at": r["created_at"],
            "fired_at": _row_val(r, "fired_at", None),
            "schedule": _staff_schedule(_row_val(r, "schedule_json", "") or ""),
            "login": _row_val(r, "login", "") or "",
            "can_login": _row_val(r, "can_login", 0) or 0,
            "has_pass": 1 if (_row_val(r, "pass_hash", "") or "") else 0,
            "password": _row_val(r, "pass_plain", "") or "",
            "perms": _perms_parse(_row_val(r, "perms", "") or "")}


def _staff_schedule(raw):
    try:
        d = json.loads(raw or "{}")
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _clean_hhmm(v):
    v = (v or "").strip()[:5]
    # "9:00" -> "09:00" (bir xonali soatni normallaymiz)
    if len(v) == 4 and v[1] == ":":
        v = "0" + v
    return v if _TIME_RE.match(v) else ""


def _hhmm_min(v):
    try:
        h, m = v.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


@router.get("/staff-professions")
async def staff_professions_list(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    _ensure_staff_tables(conn)
    profs = _professions(conn, biz["id"])
    conn.close()
    return {"professions": profs, "default": _DEFAULT_PROFESSIONS}


@router.post("/staff-professions")
async def staff_professions_add(body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Kasblar")
    _ensure_staff_tables(conn)
    name = (body.get("name") or "").strip()[:40]
    if not name:
        conn.close()
        raise HTTPException(400, "Kasb nomi kiritilmadi.")
    if name not in _professions(conn, biz["id"]):
        conn.execute("INSERT INTO staff_professions(business_id, name, created_at) VALUES(?,?,?)",
                     (biz["id"], name, int(time.time())))
        conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/staff")
async def staff_list(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Xodimlar bo'limi")
    _ensure_staff_tables(conn)
    rows = conn.execute(
        "SELECT * FROM staff WHERE business_id=? ORDER BY "
        "CASE status WHEN 'active' THEN 0 ELSE 1 END, name COLLATE NOCASE",
        (biz["id"],),
    ).fetchall()
    firm_login = _row_val(biz, "biz_login", "") or ""
    active, fired = [], []
    total_salary = 0
    for r in rows:
        d = _staff_dict(r)
        if d["status"] == "fired":
            fired.append(d)
        else:
            active.append(d)
            total_salary += int(d["salary"] or 0)
    conn.close()
    return {"active": active, "fired": fired,
            "active_count": len(active), "fired_count": len(fired),
            "total_salary": total_salary, "firm_login": firm_login}


@router.post("/staff")
async def staff_add(body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Xodim qo'shish")
    _ensure_staff_tables(conn)
    name = (body.get("name") or "").strip()
    if not name:
        conn.close()
        raise HTTPException(400, "Xodim ismini kiriting.")
    profession = (body.get("profession") or "").strip()[:40]
    phone = (body.get("phone") or "").strip()[:30]
    try:
        salary = int(str(body.get("salary") or "0").replace(" ", "") or 0)
    except Exception:
        salary = 0
    if salary < 0:
        salary = 0
    hire_date = (body.get("hire_date") or "").strip()[:20]
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO staff(business_id, name, profession, phone, salary, hire_date, status, note, user_id, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (biz["id"], name, profession, phone, salary, hire_date, "active", "", user["id"], now),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return {"ok": True, "id": sid}


@router.put("/staff/{staff_id}")
async def staff_update(staff_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Xodimni tahrirlash")
    _ensure_staff_tables(conn)
    r = conn.execute("SELECT * FROM staff WHERE id=? AND business_id=?", (staff_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Xodim topilmadi.")
    name = (body.get("name") or r["name"]).strip() or r["name"]
    profession = (body.get("profession") or "").strip()[:40] if "profession" in body else (r["profession"] or "")
    phone = (body.get("phone") or "").strip()[:30] if "phone" in body else (r["phone"] or "")
    if "salary" in body:
        try:
            salary = int(str(body.get("salary") or "0").replace(" ", "") or 0)
        except Exception:
            salary = 0
        if salary < 0:
            salary = 0
    else:
        salary = r["salary"] or 0
    hire_date = (body.get("hire_date") or "").strip()[:20] if "hire_date" in body else (r["hire_date"] or "")
    conn.execute(
        "UPDATE staff SET name=?, profession=?, phone=?, salary=?, hire_date=? WHERE id=?",
        (name, profession, phone, salary, hire_date, staff_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/staff/{staff_id}/fire")
async def staff_fire(staff_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Xodim")
    _ensure_staff_tables(conn)
    r = conn.execute("SELECT id FROM staff WHERE id=? AND business_id=?", (staff_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Xodim topilmadi.")
    conn.execute("UPDATE staff SET status='fired', fired_at=? WHERE id=?", (int(time.time()), staff_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/staff/{staff_id}/rehire")
async def staff_rehire(staff_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Xodim")
    _ensure_staff_tables(conn)
    r = conn.execute("SELECT id FROM staff WHERE id=? AND business_id=?", (staff_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Xodim topilmadi.")
    conn.execute("UPDATE staff SET status='active', fired_at=NULL WHERE id=?", (staff_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/staff/{staff_id}")
async def staff_delete(staff_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Xodim")
    _ensure_staff_tables(conn)
    r = conn.execute("SELECT id FROM staff WHERE id=? AND business_id=?", (staff_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Xodim topilmadi.")
    conn.execute("DELETE FROM staff WHERE id=?", (staff_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.put("/staff/{staff_id}/schedule")
async def staff_set_schedule(staff_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    """M1b: Xodim haftalik ish grafigi (d0=Dushanba ... d6=Yakshanba)."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    _ensure_staff_tables(conn)
    r = conn.execute("SELECT id FROM staff WHERE id=? AND business_id=?", (staff_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Xodim topilmadi.")
    sched = body.get("schedule") or {}
    clean = {}
    for i in range(7):
        d = sched.get("d%d" % i) or {}
        on = 1 if str(d.get("on") or 0) in ("1", "true", "True") else 0
        clean["d%d" % i] = {"on": on, "s": _clean_hhmm(d.get("s")), "e": _clean_hhmm(d.get("e"))}
    conn.execute("UPDATE staff SET schedule_json=? WHERE id=?", (json.dumps(clean, ensure_ascii=False), staff_id))
    conn.commit()
    conn.close()
    return {"ok": True}


def _tabel_today_iso():
    import datetime as _dt
    return _dt.datetime.fromtimestamp(int(time.time()) + TASHKENT_TZ, _dt.timezone.utc).date().isoformat()


@router.get("/tabel")
async def tabel_get(date: str = "", x_telegram_init_data: str = Header(default="")):
    """M1c: Kunlik davomat + shu oy hisobi (kun / soat)."""
    import datetime as _dt
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    _ensure_staff_tables(conn)
    date = (date or "").strip()
    try:
        d = _dt.date.fromisoformat(date) if date else _dt.date.fromisoformat(_tabel_today_iso())
    except Exception:
        conn.close()
        raise HTTPException(400, "Sana noto'g'ri.")
    iso = d.isoformat()
    wd = d.weekday()  # 0=Dushanba
    staff_rows = conn.execute(
        "SELECT * FROM staff WHERE business_id=? AND status='active' ORDER BY name COLLATE NOCASE",
        (biz["id"],),
    ).fetchall()
    att = {r["staff_id"]: r for r in conn.execute(
        "SELECT * FROM staff_attendance WHERE business_id=? AND date=?", (biz["id"], iso)).fetchall()}
    month_rows = conn.execute(
        "SELECT staff_id, status, time_in, time_out FROM staff_attendance "
        "WHERE business_id=? AND date LIKE ?", (biz["id"], iso[:7] + "-%")).fetchall()
    mk, mm = {}, {}
    for r in month_rows:
        if (r["status"] or "") != "keldi":
            continue
        mk[r["staff_id"]] = mk.get(r["staff_id"], 0) + 1
        a, b = _hhmm_min(r["time_in"] or ""), _hhmm_min(r["time_out"] or "")
        if a is not None and b is not None and b > a:
            mm[r["staff_id"]] = mm.get(r["staff_id"], 0) + (b - a)
    out = []
    for st in staff_rows:
        sch = _staff_schedule(_row_val(st, "schedule_json", "") or "")
        day = sch.get("d%d" % wd) or {}
        a = att.get(st["id"])
        out.append({
            "id": st["id"], "name": st["name"] or "", "profession": st["profession"] or "",
            "status": (a["status"] if a else "") or "",
            "time_in": (a["time_in"] if a else "") or "",
            "time_out": (a["time_out"] if a else "") or "",
            "sched_on": int(day.get("on") or 0), "sched_s": day.get("s") or "", "sched_e": day.get("e") or "",
            "month_keldi": mk.get(st["id"], 0), "month_min": mm.get(st["id"], 0),
        })
    conn.close()
    return {"date": iso, "weekday": wd, "staff": out}


@router.post("/tabel")
async def tabel_set(body: dict, x_telegram_init_data: str = Header(default="")):
    """M1c: Belgilash. status='' bo'lsa yozuv o'chiriladi (bekor qilish)."""
    import datetime as _dt
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Ish tabeli")
    _ensure_staff_tables(conn)
    staff_id = int(body.get("staff_id") or 0)
    r = conn.execute("SELECT id FROM staff WHERE id=? AND business_id=?", (staff_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Xodim topilmadi.")
    try:
        iso = _dt.date.fromisoformat((body.get("date") or "").strip()).isoformat()
    except Exception:
        conn.close()
        raise HTTPException(400, "Sana noto'g'ri.")
    if iso > _tabel_today_iso():
        conn.close()
        raise HTTPException(400, "Kelajak sanaga tabel yozilmaydi.")
    status = (body.get("status") or "").strip()
    if status not in ("", "keldi", "kelmadi", "dam"):
        conn.close()
        raise HTTPException(400, "Holat noto'g'ri.")
    if status == "":
        conn.execute("DELETE FROM staff_attendance WHERE business_id=? AND staff_id=? AND date=?",
                     (biz["id"], staff_id, iso))
        conn.commit()
        conn.close()
        return {"ok": True, "cleared": True}
    t_in = _clean_hhmm(body.get("time_in")) if status == "keldi" else ""
    t_out = _clean_hhmm(body.get("time_out")) if status == "keldi" else ""
    ex = conn.execute("SELECT id FROM staff_attendance WHERE business_id=? AND staff_id=? AND date=?",
                      (biz["id"], staff_id, iso)).fetchone()
    if ex:
        conn.execute("UPDATE staff_attendance SET status=?, time_in=?, time_out=? WHERE id=?",
                     (status, t_in, t_out, ex["id"]))
    else:
        conn.execute(
            "INSERT INTO staff_attendance(business_id, staff_id, date, status, time_in, time_out, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (biz["id"], staff_id, iso, status, t_in, t_out, int(time.time())),
        )
    conn.commit()
    conn.close()
    return {"ok": True, "status": status}


@router.put("/business/credentials")
async def update_business_credentials(request: Request, x_telegram_init_data: str = Header(default="")):
    """Do'kon login/parolini o'zgartirish (biz_login + biz_pass). Egasi allaqachon sessiya orqali
    tasdiqlangan, shuning uchun joriy parol so'ralmaydi."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Login va parol")
    b = await request.json()
    from main import hash_password
    new_login = (b.get("new_login") or "").strip().lower()
    new_pass = (b.get("new_password") or "").strip()
    if not new_login and not new_pass:
        conn.close()
        raise HTTPException(400, "O'zgartirish uchun yangi login yoki parol kiriting.")
    # Login o'zgartirish
    if new_login and new_login != (_row_val(biz, "biz_login", "") or "").lower():
        if len(new_login) < 4 or len(new_login) > 20 or not re.match(r"^[a-z][a-z0-9_]*$", new_login):
            conn.close()
            raise HTTPException(400, "Login 4-20 belgi, kichik lotin harfi bilan boshlansin (harf, raqam, _).")
        dup = conn.execute("SELECT 1 FROM businesses WHERE lower(biz_login)=? AND id<>?", (new_login, biz["id"])).fetchone()
        dup2 = conn.execute("SELECT 1 FROM users WHERE lower(login)=?", (new_login,)).fetchone()
        if dup or dup2:
            conn.close()
            raise HTTPException(400, "Bu login band. Boshqasini tanlang.")
        conn.execute("UPDATE businesses SET biz_login=? WHERE id=?", (new_login, biz["id"]))
    # Parol o'zgartirish
    if new_pass:
        if len(new_pass) < 4:
            conn.close()
            raise HTTPException(400, "Yangi parol kamida 4 belgi bo'lsin.")
        conn.execute("UPDATE businesses SET biz_pass_hash=? WHERE id=?", (hash_password(new_pass), biz["id"]))
    conn.commit()
    row = conn.execute("SELECT biz_login FROM businesses WHERE id=?", (biz["id"],)).fetchone()
    conn.close()
    return {"ok": True, "biz_login": row["biz_login"] if row else new_login}


# ================== KONTRAGENTLAR (M2a) ==================
_CONTRACTOR_TYPES = ["Yetkazib beruvchi", "Mijoz", "Hamkor", "Boshqa"]


def _ensure_contractors(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS contractors("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL, "
        "name TEXT NOT NULL, ctype TEXT DEFAULT '', director TEXT DEFAULT '', "
        "phone TEXT DEFAULT '', address TEXT DEFAULT '', inn TEXT DEFAULT '', "
        "account TEXT DEFAULT '', bank TEXT DEFAULT '', mfo TEXT DEFAULT '', "
        "note TEXT DEFAULT '', created_at INTEGER NOT NULL)")
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_contractors_biz ON contractors(business_id)")
    except Exception:
        pass


def _contractor_dict(r):
    return {"id": r["id"], "name": r["name"] or "", "ctype": r["ctype"] or "",
            "director": r["director"] or "", "phone": r["phone"] or "",
            "address": r["address"] or "", "inn": r["inn"] or "",
            "account": r["account"] or "", "bank": r["bank"] or "",
            "mfo": r["mfo"] or "", "note": r["note"] or "", "created_at": r["created_at"]}


def _contractor_fields(b):
    return (
        (b.get("name") or "").strip(),
        (b.get("ctype") or "").strip()[:40],
        (b.get("director") or "").strip()[:120],
        (b.get("phone") or "").strip()[:40],
        (b.get("address") or "").strip()[:200],
        (b.get("inn") or "").strip()[:20],
        (b.get("account") or "").strip()[:40],
        (b.get("bank") or "").strip()[:120],
        (b.get("mfo") or "").strip()[:20],
        (b.get("note") or "").strip()[:300],
    )


@router.get("/contractors")
async def contractors_list(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    _ensure_contractors(conn)
    rows = conn.execute("SELECT * FROM contractors WHERE business_id=? ORDER BY name COLLATE NOCASE", (biz["id"],)).fetchall()
    out = [_contractor_dict(r) for r in rows]
    conn.close()
    return {"contractors": out, "count": len(out), "types": _CONTRACTOR_TYPES}


@router.post("/contractors")
async def contractors_add(body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Kontragentlar")
    _ensure_contractors(conn)
    f = _contractor_fields(body)
    if not f[0]:
        conn.close()
        raise HTTPException(400, "Kontragent nomini kiriting.")
    cur = conn.execute(
        "INSERT INTO contractors(business_id, name, ctype, director, phone, address, inn, account, bank, mfo, note, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (biz["id"],) + f + (int(time.time()),),
    )
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return {"ok": True, "id": cid}


@router.put("/contractors/{cid}")
async def contractors_update(cid: int, body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Kontragentlar")
    _ensure_contractors(conn)
    r = conn.execute("SELECT id FROM contractors WHERE id=? AND business_id=?", (cid, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Kontragent topilmadi.")
    f = _contractor_fields(body)
    if not f[0]:
        conn.close()
        raise HTTPException(400, "Kontragent nomini kiriting.")
    conn.execute(
        "UPDATE contractors SET name=?, ctype=?, director=?, phone=?, address=?, inn=?, account=?, bank=?, mfo=?, note=? WHERE id=?",
        f + (cid,),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/contractors/{cid}")
async def contractors_delete(cid: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Kontragentlar")
    _ensure_contractors(conn)
    r = conn.execute("SELECT id FROM contractors WHERE id=? AND business_id=?", (cid, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Kontragent topilmadi.")
    conn.execute("DELETE FROM contractors WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ================== HUJJATLAR (M2: Hujjat yaratish) ==================
_DOC_DIRECTIONS = ("ichki", "kiruvchi", "chiquvchi")


def _ensure_documents(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS documents("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER NOT NULL, "
        "direction TEXT DEFAULT '', doc_type TEXT DEFAULT '', title TEXT DEFAULT '', "
        "number TEXT DEFAULT '', doc_date TEXT DEFAULT '', contractor_id INTEGER, "
        "body TEXT DEFAULT '', created_at INTEGER NOT NULL)")
    try:
        _dcols = [r["name"] for r in conn.execute("PRAGMA table_info(documents)").fetchall()]
        for _c, _t in (("sender_business_id", "INTEGER"), ("sender_name", "TEXT DEFAULT ''"),
                       ("receiver_inn", "TEXT DEFAULT ''"), ("status", "TEXT DEFAULT ''")):
            if _c not in _dcols:
                conn.execute("ALTER TABLE documents ADD COLUMN %s %s" % (_c, _t))
    except Exception:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_biz ON documents(business_id, direction)")
    except Exception:
        pass


def _doc_dict(r, contr_name=""):
    return {"id": r["id"], "direction": r["direction"] or "", "doc_type": r["doc_type"] or "",
            "title": r["title"] or "", "number": r["number"] or "", "doc_date": r["doc_date"] or "",
            "contractor_id": _row_val(r, "contractor_id", None), "contractor_name": contr_name,
            "body": r["body"] or "", "created_at": r["created_at"],
            "sender_name": _row_val(r, "sender_name", "") or "",
            "receiver_inn": _row_val(r, "receiver_inn", "") or "",
            "status": _row_val(r, "status", "") or ""}


@router.get("/documents")
async def documents_list(direction: str = "", x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    _ensure_documents(conn)
    if direction in _DOC_DIRECTIONS:
        rows = conn.execute("SELECT * FROM documents WHERE business_id=? AND direction=? ORDER BY id DESC",
                            (biz["id"], direction)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM documents WHERE business_id=? ORDER BY id DESC", (biz["id"],)).fetchall()
    cmap = {}
    try:
        for c in conn.execute("SELECT id, name FROM contractors WHERE business_id=?", (biz["id"],)).fetchall():
            cmap[c["id"]] = c["name"]
    except Exception:
        pass
    out = [_doc_dict(r, cmap.get(_row_val(r, "contractor_id", None), "")) for r in rows]
    conn.close()
    return {"documents": out, "count": len(out)}


@router.get("/documents/{doc_id}")
async def document_get(doc_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    _ensure_documents(conn)
    r = conn.execute("SELECT * FROM documents WHERE id=? AND business_id=?", (doc_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Hujjat topilmadi.")
    cn = ""
    cid = _row_val(r, "contractor_id", None)
    if cid:
        try:
            cr = conn.execute("SELECT name FROM contractors WHERE id=?", (cid,)).fetchone()
            cn = cr["name"] if cr else ""
        except Exception:
            pass
    conn.close()
    return _doc_dict(r, cn)


def _doc_fields(b):
    direction = (b.get("direction") or "").strip().lower()
    if direction not in _DOC_DIRECTIONS:
        direction = "ichki"
    cid = b.get("contractor_id")
    try:
        cid = int(cid) if cid else None
    except Exception:
        cid = None
    return (direction, (b.get("doc_type") or "").strip()[:60], (b.get("title") or "").strip()[:200],
            (b.get("number") or "").strip()[:40], (b.get("doc_date") or "").strip()[:20], cid,
            (b.get("body") or "").strip())


@router.post("/documents")
async def document_add(body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Hujjatlar")
    _ensure_documents(conn)
    f = _doc_fields(body)
    if not f[6]:
        conn.close()
        raise HTTPException(400, "Hujjat matni bo'sh.")
    cur = conn.execute(
        "INSERT INTO documents(business_id, direction, doc_type, title, number, doc_date, contractor_id, body, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (biz["id"],) + f + (int(time.time()),),
    )
    conn.commit()
    did = cur.lastrowid
    conn.close()
    return {"ok": True, "id": did}


@router.put("/documents/{doc_id}")
async def document_update(doc_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Hujjatlar")
    _ensure_documents(conn)
    r = conn.execute("SELECT id FROM documents WHERE id=? AND business_id=?", (doc_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Hujjat topilmadi.")
    f = _doc_fields(body)
    conn.execute(
        "UPDATE documents SET direction=?, doc_type=?, title=?, number=?, doc_date=?, contractor_id=?, body=? WHERE id=?",
        f + (doc_id,),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/documents/{doc_id}")
async def document_delete(doc_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Hujjatlar")
    _ensure_documents(conn)
    r = conn.execute("SELECT id FROM documents WHERE id=? AND business_id=?", (doc_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Hujjat topilmadi.")
    conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/documents/{doc_id}/send")
async def document_send(doc_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    """Chiquvchi hujjatni STIR bo'yicha boshqa firmaga yuboradi (nusxasi 'kiruvchi' bo'ladi)."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Hujjatlar")
    _ensure_documents(conn)
    _ensure_pay_columns(conn)
    doc = conn.execute("SELECT * FROM documents WHERE id=? AND business_id=?", (doc_id, biz["id"])).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(404, "Hujjat topilmadi.")
    inn = (body.get("receiver_inn") or "").strip()
    inn_digits = "".join(ch for ch in inn if ch.isdigit())
    if len(inn_digits) < 9:
        conn.close()
        raise HTTPException(400, "STIR raqami noto'g'ri (kamida 9 raqam).")
    # STIR bo'yicha qabul qiluvchi firmani topamiz
    target = conn.execute(
        "SELECT * FROM businesses WHERE replace(replace(COALESCE(inn,''),' ',''),'-','')=? AND status='active'",
        (inn_digits,),
    ).fetchone()
    if not target:
        conn.close()
        raise HTTPException(404, "Bu STIR raqamli firma ilovada topilmadi. Firma ro'yxatdan o'tганини tekshiring.")
    if target["id"] == biz["id"]:
        conn.close()
        raise HTTPException(400, "Hujjatni o'zingizga yubora olmaysiz.")
    now = int(time.time())
    # Qabul qiluvchi bazasiga 'kiruvchi' nusxa
    conn.execute(
        "INSERT INTO documents(business_id, direction, doc_type, title, number, doc_date, contractor_id, body, created_at, "
        "sender_business_id, sender_name, receiver_inn, status) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (target["id"], "kiruvchi", doc["doc_type"], doc["title"], doc["number"], doc["doc_date"],
         None, doc["body"], now, biz["id"], biz["name"], inn_digits, "kutilmoqda"),
    )
    # Yuboruvchining chiquvchi hujjatida holatni belgilaymiz
    conn.execute("UPDATE documents SET status=?, receiver_inn=? WHERE id=?", ("yuborilgan", inn_digits, doc_id))
    conn.commit()
    conn.close()
    return {"ok": True, "receiver_name": target["name"]}


@router.post("/documents/{doc_id}/respond")
async def document_respond(doc_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    """Kiruvchi hujjatni qabul qilish yoki rad etish."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    _ensure_documents(conn)
    doc = conn.execute("SELECT * FROM documents WHERE id=? AND business_id=?", (doc_id, biz["id"])).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(404, "Hujjat topilmadi.")
    if (doc["direction"] or "") != "kiruvchi":
        conn.close()
        raise HTTPException(400, "Bu amal faqat kiruvchi hujjat uchun.")
    action = (body.get("action") or "").strip()
    if action not in ("qabul", "rad"):
        conn.close()
        raise HTTPException(400, "Amal noto'g'ri.")
    new_status = "qabul qilindi" if action == "qabul" else "rad etildi"
    conn.execute("UPDATE documents SET status=? WHERE id=?", (new_status, doc_id))
    # Yuboruvchining nusxasida ham holatni yangilaymiz (agar topilsa)
    sbid = _row_val(doc, "sender_business_id", None)
    if sbid:
        try:
            conn.execute(
                "UPDATE documents SET status=? WHERE business_id=? AND direction='chiquvchi' "
                "AND doc_type=? AND COALESCE(number,'')=? AND COALESCE(body,'')=?",
                (new_status, sbid, doc["doc_type"], doc["number"] or "", doc["body"] or ""),
            )
        except Exception:
            pass
    conn.commit()
    conn.close()
    return {"ok": True, "status": new_status}


# ================== XODIM KIRISH HUQUQI (Faza 1) ==================
@router.put("/staff/{staff_id}/access")
async def staff_access_set(staff_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    """Rahbar xodimga login/parol/ruxsatlar beradi (yoki o'chiradi)."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Kirish huquqi")
    _ensure_staff_tables(conn)
    st = conn.execute("SELECT * FROM staff WHERE id=? AND business_id=?", (staff_id, biz["id"])).fetchone()
    if not st:
        conn.close()
        raise HTTPException(404, "Xodim topilmadi.")
    can = 1 if str(body.get("can_login") or 0) in ("1", "true", "True") else 0
    perms = _perms_clean(body.get("perms") or [])
    login = _norm_login(body.get("login"))
    password = (body.get("password") or "").strip()

    if can:
        if not login:
            conn.close()
            raise HTTPException(400, "Login kiriting.")
        if len(login) < 3 or len(login) > 20 or not re.match(r"^[a-z][a-z0-9_]*$", login):
            conn.close()
            raise HTTPException(400, "Login 3-20 belgi, kichik lotin harf bilan boshlansin (harf, raqam, _).")
        # login band emasligini tekshiramiz (boshqa xodimda)
        dup = conn.execute("SELECT id FROM staff WHERE business_id=? AND lower(login)=? AND id<>?", (biz["id"], login, staff_id)).fetchone()
        if dup:
            conn.close()
            raise HTTPException(400, "Bu login band. Boshqasini tanlang.")
        has_pass = bool(_row_val(st, "pass_hash", "") or "")
        if not has_pass and not password:
            conn.close()
            raise HTTPException(400, "Yangi xodim uchun parol kiriting.")
        if password and len(password) < 4:
            conn.close()
            raise HTTPException(400, "Parol kamida 4 belgi bo'lsin.")

    from main import hash_password
    if password:
        ph = hash_password(password)
        conn.execute("UPDATE staff SET login=?, pass_hash=?, pass_plain=?, perms=?, can_login=? WHERE id=?",
                     (login, ph, password, json.dumps(perms), can, staff_id))
    else:
        conn.execute("UPDATE staff SET login=?, perms=?, can_login=? WHERE id=?",
                     (login, json.dumps(perms), can, staff_id))
    # O'chirilsa — barcha sessiyalarni bekor qilamiz
    if not can:
        conn.execute("DELETE FROM staff_sessions WHERE staff_id=?", (staff_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/staff-auth")
async def staff_auth_login(body: dict):
    """Xodim login/parol bilan kiradi (Telegram shart emas). Token qaytaradi."""
    conn = db()
    _ensure_staff_tables(conn)
    firm_login = (body.get("firm_login") or "").strip().lower()
    login = _norm_login(body.get("login"))
    password = (body.get("password") or "").strip()
    if not firm_login or not login or not password:
        conn.close()
        raise HTTPException(400, "Firma logini, xodim logini va parolni kiriting.")
    firm = conn.execute("SELECT * FROM businesses WHERE lower(biz_login)=? AND status='active'", (firm_login,)).fetchone()
    if not firm:
        conn.close()
        raise HTTPException(401, "Firma logini noto'g'ri.")
    st = conn.execute("SELECT * FROM staff WHERE business_id=? AND lower(login)=?", (firm["id"], login)).fetchone()
    if not st or not (_row_val(st, "can_login", 0) or 0) or (st["status"] or "") != "active":
        conn.close()
        raise HTTPException(401, "Login yoki parol noto'g'ri.")
    from main import check_password
    if not check_password(password, _row_val(st, "pass_hash", "") or ""):
        conn.close()
        raise HTTPException(401, "Login yoki parol noto'g'ri.")
    biz = conn.execute("SELECT name FROM businesses WHERE id=?", (st["business_id"],)).fetchone()
    token = secrets.token_urlsafe(24)
    conn.execute("INSERT INTO staff_sessions(token, staff_id, business_id, created_at) VALUES(?,?,?,?)",
                 (token, st["id"], st["business_id"], int(time.time())))
    conn.commit()
    result = {"ok": True, "token": token, "name": st["name"] or "Xodim",
              "business_name": (biz["name"] if biz else ""),
              "perms": _perms_parse(_row_val(st, "perms", "") or "")}
    conn.close()
    return result


@router.get("/staff-auth/me")
async def staff_auth_me(x_staff_token: str = Header(default="")):
    """Token bo'yicha xodim ma'lumoti (2-fazada ilova shu bilan yuklanadi)."""
    conn = db()
    _ensure_staff_tables(conn)
    token = (x_staff_token or "").strip()
    if not token:
        conn.close()
        raise HTTPException(401, "Token yo'q.")
    sess = conn.execute("SELECT * FROM staff_sessions WHERE token=?", (token,)).fetchone()
    if not sess:
        conn.close()
        raise HTTPException(401, "Sessiya topilmadi. Qayta kiring.")
    st = conn.execute("SELECT * FROM staff WHERE id=?", (sess["staff_id"],)).fetchone()
    if not st or not (_row_val(st, "can_login", 0) or 0) or (st["status"] or "") != "active":
        conn.execute("DELETE FROM staff_sessions WHERE token=?", (token,))
        conn.commit()
        conn.close()
        raise HTTPException(401, "Kirish huquqi o'chirilgan.")
    biz = conn.execute("SELECT name FROM businesses WHERE id=?", (sess["business_id"],)).fetchone()
    result = {"name": st["name"] or "Xodim", "business_name": (biz["name"] if biz else ""),
              "perms": _perms_parse(_row_val(st, "perms", "") or "")}
    conn.close()
    return result


@router.post("/staff-auth/logout")
async def staff_auth_logout(x_staff_token: str = Header(default="")):
    conn = db()
    _ensure_staff_tables(conn)
    token = (x_staff_token or "").strip()
    if token:
        conn.execute("DELETE FROM staff_sessions WHERE token=?", (token,))
        conn.commit()
    conn.close()
    return {"ok": True}


# ================== STATISTIKA ==================
def _ts_day(d):
    return calendar.timegm(d.timetuple()) - TASHKENT_TZ


def _tashkent_today():
    import datetime as _dt
    return _dt.datetime.fromtimestamp(time.time() + TASHKENT_TZ, _dt.timezone.utc).date()


def _add_months(d, n):
    import datetime as _dt
    m = d.month - 1 + n
    y = d.year + m // 12
    return _dt.date(y, m % 12 + 1, 1)


_MON = ["Yan", "Fev", "Mar", "Apr", "May", "Iyn", "Iyl", "Avg", "Sen", "Okt", "Noy", "Dek"]
_WD = ["Du", "Se", "Cho", "Pa", "Ju", "Sha", "Ya"]
_PERIODS = ("kun", "hafta", "oy", "chorak", "yarim", "yil")


def _period_bounds(period, anchor):
    """(start_ts, end_ts, label, buckets[]) — Toshkent vaqti bo'yicha. bucket: {start,end,label}."""
    import datetime as _dt
    today = _tashkent_today()
    a = today
    if (anchor or "").strip():
        try:
            a = _dt.date.fromisoformat(anchor.strip())
        except Exception:
            a = today
    P = (period or "oy").lower()
    if P not in _PERIODS:
        P = "oy"
    buckets = []
    if P == "kun":
        s0 = _ts_day(a)
        for h in range(24):
            buckets.append({"start": s0 + h * 3600, "end": s0 + (h + 1) * 3600, "label": "%02d" % h})
        return s0, s0 + 86400, a.isoformat(), buckets
    if P == "hafta":
        start = a - _dt.timedelta(days=a.weekday())
        for i in range(7):
            d = start + _dt.timedelta(days=i)
            buckets.append({"start": _ts_day(d), "end": _ts_day(d) + 86400, "label": _WD[i]})
        return _ts_day(start), _ts_day(start) + 7 * 86400, start.strftime("%d.%m") + " hafta", buckets
    if P == "oy":
        start = _dt.date(a.year, a.month, 1)
        nxt = _add_months(start, 1)
        d = start
        while d < nxt:
            buckets.append({"start": _ts_day(d), "end": _ts_day(d) + 86400, "label": str(d.day)})
            d = d + _dt.timedelta(days=1)
        return _ts_day(start), _ts_day(nxt), _MON[start.month - 1] + " " + str(start.year), buckets
    if P == "chorak":
        q = (a.month - 1) // 3
        start = _dt.date(a.year, q * 3 + 1, 1)
        for i in range(3):
            ms = _add_months(start, i)
            buckets.append({"start": _ts_day(ms), "end": _ts_day(_add_months(start, i + 1)), "label": _MON[ms.month - 1]})
        return _ts_day(start), _ts_day(_add_months(start, 3)), str(q + 1) + "-chorak " + str(a.year), buckets
    if P == "yarim":
        half = 0 if a.month <= 6 else 1
        start = _dt.date(a.year, half * 6 + 1, 1)
        for i in range(6):
            ms = _add_months(start, i)
            buckets.append({"start": _ts_day(ms), "end": _ts_day(_add_months(start, i + 1)), "label": _MON[ms.month - 1]})
        lbl = ("1-yarim yil " if half == 0 else "2-yarim yil ") + str(a.year)
        return _ts_day(start), _ts_day(_add_months(start, 6)), lbl, buckets
    # yil
    start = _dt.date(a.year, 1, 1)
    for i in range(12):
        ms = _add_months(start, i)
        buckets.append({"start": _ts_day(ms), "end": _ts_day(_add_months(start, i + 1)), "label": _MON[i]})
    return _ts_day(start), _ts_day(_dt.date(a.year + 1, 1, 1)), str(a.year), buckets


def _period_shift(period, anchor, direction):
    """Davrni oldinga/orqaga suradi -> yangi anchor sanasi (YYYY-MM-DD)."""
    import datetime as _dt
    start, end, _lbl, _b = _period_bounds(period, anchor)
    P = (period or "oy").lower()
    a = _dt.datetime.fromtimestamp(start + TASHKENT_TZ + 1, _dt.timezone.utc).date()
    if direction < 0:
        if P == "kun":
            return (a - _dt.timedelta(days=1)).isoformat()
        if P == "hafta":
            return (a - _dt.timedelta(days=7)).isoformat()
        if P == "oy":
            return _add_months(a, -1).isoformat()
        if P == "chorak":
            return _add_months(a, -3).isoformat()
        if P == "yarim":
            return _add_months(a, -6).isoformat()
        return _add_months(a, -12).isoformat()
    else:
        if P == "kun":
            return (a + _dt.timedelta(days=1)).isoformat()
        if P == "hafta":
            return (a + _dt.timedelta(days=7)).isoformat()
        if P == "oy":
            return _add_months(a, 1).isoformat()
        if P == "chorak":
            return _add_months(a, 3).isoformat()
        if P == "yarim":
            return _add_months(a, 6).isoformat()
        return _add_months(a, 12).isoformat()


@router.get("/stats")
async def stats(period: str = "oy", anchor: str = "", x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    deny_staff(conn, x_telegram_init_data, "Statistika")
    bid = biz["id"]
    start, end, label, buckets = _period_bounds(period, anchor)
    n = len(buckets)

    # --- Savdolar (qarzpay = qarz to'lovi, tushumga kirmaydi) ---
    sales = conn.execute(
        "SELECT source, pay_type, total, item_id, item_name, qty, price, created_at "
        "FROM sales WHERE business_id=? AND created_at>=? AND created_at<?",
        (bid, start, end),
    ).fetchall()
    revenue = 0
    qarzpay = 0
    pay = {"naqd": 0, "karta": 0, "qarz": 0, "order": 0}
    bkt_rev = [0] * n
    prod = {}
    for sl in sales:
        t = int(sl["total"] or 0)
        src = sl["source"] or "manual"
        ca = sl["created_at"] or 0
        if src == "qarzpay":
            qarzpay += t
            continue
        revenue += t
        pt = sl["pay_type"] or ""
        pay[pt if pt in ("naqd", "karta", "qarz") else "order"] += t
        for i in range(n):
            if buckets[i]["start"] <= ca < buckets[i]["end"]:
                bkt_rev[i] += t
                break
        key = sl["item_name"] or "?"
        pr = prod.get(key)
        if not pr:
            pr = {"name": key, "item_id": sl["item_id"], "qty": 0.0, "total": 0, "unit": ""}
            prod[key] = pr
        pr["qty"] += float(sl["qty"] or 0)
        pr["total"] += t

    # --- Xarajatlar ---
    exp_rows = conn.execute(
        "SELECT amount, category, created_at FROM expenses WHERE business_id=? AND created_at>=? AND created_at<?",
        (bid, start, end),
    ).fetchall()
    expenses = 0
    exp_by_cat = {}
    bkt_exp = [0] * n
    for e in exp_rows:
        amt = int(e["amount"] or 0)
        expenses += amt
        cat = e["category"] or "Boshqa"
        exp_by_cat[cat] = exp_by_cat.get(cat, 0) + amt
        ca = e["created_at"] or 0
        for i in range(n):
            if buckets[i]["start"] <= ca < buckets[i]["end"]:
                bkt_exp[i] += amt
                break

    profit = revenue - expenses

    # --- Tovar birliklari + tannarx (foyda uchun) ---
    ids = [pr["item_id"] for pr in prod.values() if pr["item_id"]]
    costs = {}
    units = {}
    if ids:
        qmarks = ",".join("?" * len(ids))
        for r in conn.execute("SELECT id, unit, cost_price FROM items WHERE id IN (" + qmarks + ")", ids).fetchall():
            costs[r["id"]] = r["cost_price"] or 0
            units[r["id"]] = r["unit"] or "dona"
    top = []
    for pr in prod.values():
        u = units.get(pr["item_id"], "")
        cost = costs.get(pr["item_id"], 0)
        margin = None
        if cost and pr["qty"]:
            margin = int(round(pr["total"] - cost * pr["qty"]))
        top.append({"name": pr["name"], "qty": round(pr["qty"], 3), "unit": u,
                    "total": pr["total"], "margin": margin})
    top.sort(key=lambda x: x["total"], reverse=True)
    top = top[:12]

    # --- Kam qolgan tovarlar ---
    low = [{"name": r["name"], "unit": r["unit"] or "dona", "stock_qty": r["stock_qty"] or 0}
           for r in conn.execute(
               "SELECT name, unit, stock_qty FROM items WHERE business_id=? AND track_stock=1 "
               "ORDER BY stock_qty ASC LIMIT 8", (bid,)).fetchall()]

    trend = [{"label": buckets[i]["label"], "rev": bkt_rev[i], "exp": bkt_exp[i],
              "profit": bkt_rev[i] - bkt_exp[i]} for i in range(n)]

    can_next = end <= _ts_day(_tashkent_today())

    conn.close()
    return {
        "period": (period or "oy").lower() if (period or "oy").lower() in _PERIODS else "oy",
        "anchor": anchor or "",
        "label": label,
        "revenue": revenue, "expenses": expenses, "profit": profit, "qarzpay": qarzpay,
        "pay": pay, "exp_by_cat": exp_by_cat,
        "trend": trend, "top_products": top, "low_stock": low,
        "sales_count": len([1 for sl in sales if (sl["source"] or "") != "qarzpay"]),
        "can_next": can_next,
    }


@router.get("/stats/nav")
async def stats_nav(period: str = "oy", anchor: str = "", dir: int = -1, x_telegram_init_data: str = Header(default="")):
    conn = db()
    require_business(conn, x_telegram_init_data)
    conn.close()
    return {"anchor": _period_shift(period, anchor, dir)}


# ================== XARAJATLAR ==================
_DEFAULT_EXP_CATS = ["Ijara", "Kommunal", "Maosh", "Transport", "Tovar xaridi", "Soliq", "Boshqa"]


def _expense_cats(conn, biz_id):
    """Standart kategoriyalar + biznes qo'shgan maxsus kategoriyalar (takrorsiz)."""
    extra = [r["name"] for r in conn.execute(
        "SELECT name FROM expense_cats WHERE business_id=? ORDER BY name COLLATE NOCASE", (biz_id,)
    ).fetchall()]
    out = list(_DEFAULT_EXP_CATS)
    for e in extra:
        if e not in out:
            out.append(e)
    return out


def _expense_add(conn, biz_id, category, amount, note, user_id, source="manual", stock_move_id=None):
    now = int(time.time())
    conn.execute(
        "INSERT INTO expenses(business_id, category, amount, note, source, stock_move_id, user_id, created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (biz_id, category, int(amount), note[:200], source, stock_move_id, user_id, now),
    )
    return conn.execute("SELECT last_insert_rowid() r").fetchone()["r"]


@router.get("/expense-cats")
async def expense_cats_list(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    cats = _expense_cats(conn, biz["id"])
    conn.close()
    return {"cats": cats, "default": _DEFAULT_EXP_CATS}


@router.post("/expense-cats")
async def expense_cats_add(body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    name = (body.get("name") or "").strip()[:40]
    if not name:
        conn.close()
        raise HTTPException(400, "Kategoriya nomi kiritilmadi.")
    if name in _expense_cats(conn, biz["id"]):
        conn.close()
        return {"ok": True, "exists": True}
    conn.execute("INSERT INTO expense_cats(business_id, name, created_at) VALUES(?,?,?)",
                 (biz["id"], name, int(time.time())))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/expenses")
async def expenses_list(day: str = "", x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    start, end, dstr = _day_bounds(day)
    rows = conn.execute(
        "SELECT e.*, u.name AS who FROM expenses e LEFT JOIN users u ON u.id=e.user_id "
        "WHERE e.business_id=? AND e.created_at>=? AND e.created_at<? "
        "ORDER BY e.created_at DESC, e.id DESC LIMIT 200",
        (biz["id"], start, end),
    ).fetchall()
    total = 0
    by_cat = {}
    out = []
    for r in rows:
        amt = int(r["amount"] or 0)
        total += amt
        cat = r["category"] or "Boshqa"
        by_cat[cat] = by_cat.get(cat, 0) + amt
        out.append({"id": r["id"], "category": cat, "amount": amt, "note": r["note"] or "",
                    "source": r["source"] or "manual", "who": r["who"] or "",
                    "created_at": r["created_at"]})
    conn.close()
    return {"day": dstr, "expenses": out, "total": total, "by_cat": by_cat}


@router.post("/expenses")
async def expenses_add(body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    category = (body.get("category") or "Boshqa").strip()[:40] or "Boshqa"
    try:
        amount = int(str(body.get("amount") or "0").replace(" ", "") or 0)
    except Exception:
        amount = 0
    if amount <= 0:
        conn.close()
        raise HTTPException(400, "Summa kiritilmadi.")
    note = (body.get("note") or "").strip()
    eid = _expense_add(conn, biz["id"], category, amount, note, user["id"])
    conn.commit()
    conn.close()
    return {"ok": True, "id": eid}


@router.delete("/expenses/{expense_id}")
async def expenses_delete(expense_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    r = conn.execute("SELECT * FROM expenses WHERE id=? AND business_id=?", (expense_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Xarajat topilmadi.")
    if (r["source"] or "") == "stock":
        conn.close()
        raise HTTPException(400, "Bu xarajat ombor kirimidan — uni Ombordagi kirimni o'chirsangiz yo'qoladi.")
    conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ================== KASSA (savdo daftari) ==================
TASHKENT_TZ = 5 * 3600   # O'zbekiston vaqti (UTC+5) — "bugun" chegarasi uchun
def _ensure_item_min_qty(conn):
    """items.min_qty ustunini kafolatlaydi (O3: kam qoldi chegarasi)."""
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(items)").fetchall()]
        if "min_qty" not in cols:
            conn.execute("ALTER TABLE items ADD COLUMN min_qty REAL DEFAULT 0")
    except Exception:
        pass


def _parse_min_qty(b):
    try:
        v = float(str(b.get("min_qty") or "0").replace(",", "."))
    except Exception:
        v = 0.0
    if v < 0:
        v = 0.0
    return round(v, 3)


_PAY_TYPES = ("naqd", "karta", "qarz")
_PAY_TEXT = {"naqd": "Naqd", "karta": "Karta", "qarz": "Qarz", "": "Buyurtma"}


def _day_bounds(day):
    """'YYYY-MM-DD' (Toshkent kuni) -> (boshlanish_ts, tugash_ts, kun). Bo'sh bo'lsa bugun."""
    import datetime as _dt
    d = None
    try:
        if (day or "").strip():
            d = _dt.date.fromisoformat((day or "").strip())
    except Exception:
        d = None
    if d is None:
        d = _dt.datetime.fromtimestamp(time.time() + TASHKENT_TZ, _dt.timezone.utc).date()
    start = calendar.timegm(d.timetuple()) - TASHKENT_TZ
    return start, start + 86400, d.isoformat()


def _sale_dict(r):
    src = r["source"] or "manual"
    pt = r["pay_type"] or ""
    pay_text = "Qarz to'lovi" if src == "qarzpay" else _PAY_TEXT.get(pt, pt)
    return {"id": r["id"], "source": src, "order_id": r["order_id"],
            "chek_no": _row_val(r, "chek_no", None),
            "item_id": r["item_id"], "item_name": r["item_name"] or "",
            "qty": r["qty"] or 1, "unit": r["unit"] or "", "price": r["price"] or 0,
            "total": r["total"] or 0, "pay_type": pt,
            "pay_text": pay_text,
            "debtor_id": r["debtor_id"], "note": r["note"] or "",
            "created_at": r["created_at"]}


def _next_chek_no(conn, biz_id):
    return int(conn.execute(
        "SELECT COALESCE(MAX(chek_no), 0) + 1 FROM sales WHERE business_id=?", (biz_id,)
    ).fetchone()[0])


def _kassa_add_for_order(conn, order, actor_user_id):
    """Buyurtma "Bajarildi" bo'lganda savdo daftariga avtomatik yozish (faqat bir marta)."""
    if (order["provider_kind"] or "") != "business":
        return
    if conn.execute("SELECT COUNT(*) FROM sales WHERE order_id=?", (order["id"],)).fetchone()[0]:
        return
    rows = conn.execute("SELECT * FROM order_items WHERE order_id=?", (order["id"],)).fetchall()
    now = int(time.time())
    for oi in rows:
        total = int(oi["line_total"] or 0)
        qty = round(float(oi["qty"] or 1), 3)
        price = int(round(total / qty)) if (total and qty) else _price_to_int(oi["price_text"] or "")
        conn.execute(
            "INSERT INTO sales(business_id, source, order_id, item_id, item_name, qty, unit, price, total, pay_type, note, user_id, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (int(order["provider_actor_id"] or 0), "order", order["id"], oi["item_id"],
             oi["item_name"] or "", qty, _row_val(oi, "unit", "") or "", price, total,
             "", "Buyurtma #%d" % order["id"], actor_user_id, now),
        )


@router.get("/kassa")
async def kassa_list(day: str = "", x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    need_perm(conn, x_telegram_init_data, "kassa")
    start, end, dstr = _day_bounds(day)
    rows = conn.execute(
        "SELECT s.*, u.name AS who FROM sales s LEFT JOIN users u ON u.id=s.user_id "
        "WHERE s.business_id=? AND s.created_at>=? AND s.created_at<? "
        "ORDER BY s.created_at DESC, s.id DESC LIMIT 200",
        (biz["id"], start, end),
    ).fetchall()
    totals = {"all": 0, "naqd": 0, "karta": 0, "qarz": 0, "qarzpay": 0, "order": 0}
    out = []
    for r in rows:
        d = _sale_dict(r)
        d["who"] = r["who"] or ""
        out.append(d)
        t = int(r["total"] or 0)
        totals["all"] += t
        pt = r["pay_type"] or ""
        if (r["source"] or "") == "qarzpay":
            totals["qarzpay"] += t
        elif pt in ("naqd", "karta", "qarz"):
            totals[pt] += t
        else:
            totals["order"] += t
    conn.close()
    return {"day": dstr, "sales": out, "totals": totals}


@router.post("/kassa")
async def kassa_add(body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    need_perm(conn, x_telegram_init_data, "kassa")
    item_id = int(body.get("item_id") or 0) or None
    name = (body.get("name") or "").strip()
    unit = "dona"
    it = None
    if item_id:
        it = conn.execute("SELECT * FROM items WHERE id=? AND business_id=?", (item_id, biz["id"])).fetchone()
        if not it:
            conn.close()
            raise HTTPException(404, "Mahsulot topilmadi.")
        name = it["name"]
        unit = _row_val(it, "unit", "dona") or "dona"
    if not name:
        conn.close()
        raise HTTPException(400, "Mahsulot nomi kiritilmadi.")
    qty = _clean_qty(body.get("qty"))
    if unit not in FRACTIONAL_UNITS:
        qty = max(1, int(math.floor(float(qty) + 0.5)))
    try:
        price = int(str(body.get("price") or "0").replace(" ", "") or 0)
    except Exception:
        price = 0
    if price < 0:
        price = 0
    total = int(round(price * float(qty)))
    if total <= 0:
        conn.close()
        raise HTTPException(400, "Narx kiritilmadi.")
    pay = (body.get("pay_type") or "naqd").strip()
    if pay not in _PAY_TYPES:
        pay = "naqd"
    note = (body.get("note") or "").strip()[:200]
    now = int(time.time())
    debtor_id = None
    qtx_id = None
    if pay == "qarz":
        debtor_id = int(body.get("debtor_id") or 0)
        owns = conn.execute("SELECT id FROM debtors WHERE id=? AND business_id=?", (debtor_id, biz["id"])).fetchone()
        if not owns:
            conn.close()
            raise HTTPException(400, "Qarz uchun qarzdorni tanlang.")
        import datetime as _dt
        conn.execute(
            "INSERT INTO qarz_tx(debtor_id, type, amount, date, note, created_at) VALUES(?,?,?,?,?,?)",
            (debtor_id, "debt", total,
             _dt.datetime.fromtimestamp(now + TASHKENT_TZ, _dt.timezone.utc).date().isoformat(),
             ("Kassa: " + name)[:120], now),
        )
        qtx_id = conn.execute("SELECT last_insert_rowid() r").fetchone()["r"]
    chek = _next_chek_no(conn, biz["id"])
    cur = conn.execute(
        "INSERT INTO sales(business_id, source, order_id, item_id, item_name, qty, unit, price, total, pay_type, debtor_id, qarz_tx_id, note, user_id, created_at, chek_no) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (biz["id"], "manual", None, item_id, name, qty, unit, price, total, pay, debtor_id, qtx_id, note, user["id"], now, chek),
    )
    sale_id = cur.lastrowid
    # Ombor yoqilgan bo'lsa — savdo qoldiqdan ayiradi
    if it is not None and (_row_val(it, "track_stock", 0) or 0):
        conn.execute("UPDATE items SET stock_qty=ROUND(COALESCE(stock_qty,0)-?, 3) WHERE id=?", (float(qty), item_id))
        conn.execute(
            "INSERT INTO stock_moves(business_id, item_id, delta, reason, note, order_id, user_id, created_at) "
            "VALUES(?,?,?,?,?,NULL,?,?)",
            (biz["id"], item_id, -float(qty), "sotuv", "Kassa #%d" % sale_id, user["id"], now),
        )
    conn.commit()
    conn.close()
    return {"ok": True, "id": sale_id, "total": total}


@router.post("/kassa/multi")
async def kassa_add_multi(body: dict, x_telegram_init_data: str = Header(default="")):
    """Bitta chekda bir nechta mahsulot. Avval hammasi tekshiriladi, keyin yoziladi."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    need_perm(conn, x_telegram_init_data, "kassa")
    raw_items = body.get("items") or []
    if not isinstance(raw_items, list) or not raw_items:
        conn.close()
        raise HTTPException(400, "Mahsulot tanlanmadi.")
    if len(raw_items) > 30:
        conn.close()
        raise HTTPException(400, "Bir chekda ko'pi bilan 30 ta mahsulot.")
    pay = (body.get("pay_type") or "naqd").strip()
    if pay not in _PAY_TYPES:
        pay = "naqd"
    note = (body.get("note") or "").strip()[:200]
    debtor_id = None
    if pay == "qarz":
        debtor_id = int(body.get("debtor_id") or 0)
        owns = conn.execute("SELECT id FROM debtors WHERE id=? AND business_id=?", (debtor_id, biz["id"])).fetchone()
        if not owns:
            conn.close()
            raise HTTPException(400, "Qarz uchun qarzdorni tanlang.")
    # 1-bosqich: hammasini tekshirib tayyorlaymiz (hech narsa yozilmaydi)
    prepared = []
    for x in raw_items:
        item_id = int(x.get("item_id") or 0) or None
        name = (x.get("name") or "").strip()
        unit = "dona"
        it = None
        if item_id:
            it = conn.execute("SELECT * FROM items WHERE id=? AND business_id=?", (item_id, biz["id"])).fetchone()
            if not it:
                conn.close()
                raise HTTPException(404, "Mahsulot topilmadi.")
            name = it["name"]
            unit = _row_val(it, "unit", "dona") or "dona"
        if not name:
            conn.close()
            raise HTTPException(400, "Mahsulot nomi kiritilmadi.")
        qty = _clean_qty(x.get("qty"))
        if unit not in FRACTIONAL_UNITS:
            qty = max(1, int(math.floor(float(qty) + 0.5)))
        try:
            price = int(str(x.get("price") or "0").replace(" ", "") or 0)
        except Exception:
            price = 0
        if price < 0:
            price = 0
        total = int(round(price * float(qty)))
        if total <= 0:
            conn.close()
            raise HTTPException(400, "Narx kiritilmadi: " + name)
        prepared.append({"item_id": item_id, "it": it, "name": name, "unit": unit,
                         "qty": qty, "price": price, "total": total})
    # 2-bosqich: yozamiz (bitta commit)
    now = int(time.time())
    import datetime as _dt
    # K5: tanlangan o'tgan sana bo'lsa — savdo o'sha kunga (12:00) yoziladi
    sana = (body.get("sana") or "").strip()
    if sana:
        try:
            _d = _dt.date.fromisoformat(sana)
        except Exception:
            conn.close()
            raise HTTPException(400, "Sana noto'g'ri.")
        _today = _dt.datetime.fromtimestamp(int(time.time()) + TASHKENT_TZ, _dt.timezone.utc).date()
        if _d > _today:
            conn.close()
            raise HTTPException(400, "Kelajak sanaga savdo yozib bo'lmaydi.")
        if _d < _today:
            now = calendar.timegm(_d.timetuple()) - TASHKENT_TZ + 12 * 3600
    day_str = _dt.datetime.fromtimestamp(now + TASHKENT_TZ, _dt.timezone.utc).date().isoformat()
    chek = _next_chek_no(conn, biz["id"])
    grand = 0
    for pr in prepared:
        qtx_id = None
        if pay == "qarz":
            conn.execute(
                "INSERT INTO qarz_tx(debtor_id, type, amount, date, note, created_at) VALUES(?,?,?,?,?,?)",
                (debtor_id, "debt", pr["total"], day_str, ("Kassa: " + pr["name"])[:120], now),
            )
            qtx_id = conn.execute("SELECT last_insert_rowid() r").fetchone()["r"]
        cur = conn.execute(
            "INSERT INTO sales(business_id, source, order_id, item_id, item_name, qty, unit, price, total, pay_type, debtor_id, qarz_tx_id, note, user_id, created_at, chek_no) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (biz["id"], "manual", None, pr["item_id"], pr["name"], pr["qty"], pr["unit"],
             pr["price"], pr["total"], pay, debtor_id, qtx_id, note, user["id"], now, chek),
        )
        sale_id = cur.lastrowid
        it = pr["it"]
        if it is not None and (_row_val(it, "track_stock", 0) or 0):
            conn.execute("UPDATE items SET stock_qty=ROUND(COALESCE(stock_qty,0)-?, 3) WHERE id=?", (float(pr["qty"]), pr["item_id"]))
            conn.execute(
                "INSERT INTO stock_moves(business_id, item_id, delta, reason, note, order_id, user_id, created_at) "
                "VALUES(?,?,?,?,?,NULL,?,?)",
                (biz["id"], pr["item_id"], -float(pr["qty"]), "sotuv", "Kassa #%d" % sale_id, user["id"], now),
            )
        grand += pr["total"]
    conn.commit()
    conn.close()
    return {"ok": True, "count": len(prepared), "total": grand}


@router.put("/sales/{sale_id}/pay")
async def set_order_sale_pay(sale_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    """K3: Buyurtmadan kelgan savdoga to'lov turini belgilash (butun buyurtma uchun)."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    r = conn.execute("SELECT * FROM sales WHERE id=? AND business_id=?", (sale_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Savdo topilmadi.")
    if (r["source"] or "") != "order":
        conn.close()
        raise HTTPException(400, "Bu faqat buyurtma savdosi uchun.")
    pt = (body.get("pay_type") or "").strip()
    if pt not in ("naqd", "karta"):
        conn.close()
        raise HTTPException(400, "To'lov turi noto'g'ri.")
    conn.execute(
        "UPDATE sales SET pay_type=? WHERE business_id=? AND source='order' AND order_id=?",
        (pt, biz["id"], r["order_id"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "pay_type": pt}


@router.delete("/kassa/chek/{chek_no}")
async def kassa_delete_chek(chek_no: int, x_telegram_init_data: str = Header(default="")):
    """Chekni butun o'chirish: hamma qatorlari, ombor va qarz daftari qaytariladi."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    need_perm(conn, x_telegram_init_data, "kassa")
    rows = conn.execute(
        "SELECT * FROM sales WHERE business_id=? AND chek_no=? AND source='manual'",
        (biz["id"], chek_no),
    ).fetchall()
    if not rows:
        conn.close()
        raise HTTPException(404, "Chek topilmadi.")
    now = int(time.time())
    for r in rows:
        if r["item_id"]:
            it = conn.execute("SELECT track_stock FROM items WHERE id=?", (r["item_id"],)).fetchone()
            if it and (it["track_stock"] or 0):
                q = round(float(r["qty"] or 0), 3)
                if q > 0:
                    conn.execute("UPDATE items SET stock_qty=ROUND(COALESCE(stock_qty,0)+?, 3) WHERE id=?", (q, r["item_id"]))
                    conn.execute(
                        "INSERT INTO stock_moves(business_id, item_id, delta, reason, note, order_id, user_id, created_at) "
                        "VALUES(?,?,?,?,?,NULL,?,?)",
                        (biz["id"], r["item_id"], q, "tuzatish", "Chek #%d o'chirildi" % chek_no, user["id"], now),
                    )
        if r["qarz_tx_id"]:
            conn.execute("DELETE FROM qarz_tx WHERE id=?", (r["qarz_tx_id"],))
    conn.execute("DELETE FROM sales WHERE business_id=? AND chek_no=? AND source='manual'", (biz["id"], chek_no))
    conn.commit()
    conn.close()
    return {"ok": True, "count": len(rows)}


@router.delete("/kassa/{sale_id}")
async def kassa_delete(sale_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    need_perm(conn, x_telegram_init_data, "kassa")
    r = conn.execute("SELECT * FROM sales WHERE id=? AND business_id=?", (sale_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Savdo topilmadi.")
    if (r["source"] or "") not in ("manual", "qarzpay"):
        conn.close()
        raise HTTPException(400, "Buyurtma orqali kelgan savdo bu yerdan o'chirilmaydi.")
    now = int(time.time())
    # Ombor qaytariladi (agar hisob yoqilgan bo'lsa)
    if r["item_id"]:
        it = conn.execute("SELECT track_stock FROM items WHERE id=?", (r["item_id"],)).fetchone()
        if it and (it["track_stock"] or 0):
            q = round(float(r["qty"] or 0), 3)
            if q > 0:
                conn.execute("UPDATE items SET stock_qty=ROUND(COALESCE(stock_qty,0)+?, 3) WHERE id=?", (q, r["item_id"]))
                conn.execute(
                    "INSERT INTO stock_moves(business_id, item_id, delta, reason, note, order_id, user_id, created_at) "
                    "VALUES(?,?,?,?,?,NULL,?,?)",
                    (biz["id"], r["item_id"], q, "tuzatish", "Kassa #%d o'chirildi" % sale_id, user["id"], now),
                )
    # Qarz daftaridagi yozuv ham olib tashlanadi
    if r["qarz_tx_id"]:
        conn.execute("DELETE FROM qarz_tx WHERE id=?", (r["qarz_tx_id"],))
    conn.execute("DELETE FROM sales WHERE id=?", (sale_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/qarz/debtors")
async def qarz_list(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    rows = conn.execute(
        "SELECT * FROM debtors WHERE business_id=? ORDER BY created_at DESC", (biz["id"],)
    ).fetchall()
    result = [{"id": r["id"], "name": r["name"], "phone": r["phone"], "note": r["note"],
               "due": r["due"], "balance": qarz_balance(conn, r["id"])} for r in rows]
    conn.close()
    return result


@router.post("/qarz/debtors")
async def qarz_add_debtor(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    b = await request.json()
    name = (b.get("name") or "").strip()
    if not name:
        conn.close()
        raise HTTPException(400, "Ism kiritilishi shart.")
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO debtors(business_id, name, phone, note, due, created_at) VALUES(?,?,?,?,?,?)",
        (biz["id"], name, (b.get("phone") or "").strip(), (b.get("note") or "").strip(),
         (b.get("due") or "").strip(), now),
    )
    debtor_id = cur.lastrowid
    try:
        initial = int(b.get("initial_debt") or 0)
    except Exception:
        initial = 0
    if initial > 0:
        from datetime import date
        conn.execute(
            "INSERT INTO qarz_tx(debtor_id, type, amount, date, note, created_at) VALUES(?,?,?,?,?,?)",
            (debtor_id, "debt", initial, date.today().isoformat(),
             (b.get("note") or "Boshlang'ich qarz").strip(), now),
        )
    conn.commit()
    conn.close()
    return {"id": debtor_id}


@router.get("/qarz/debtors/{debtor_id}")
async def qarz_debtor(debtor_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    r = conn.execute(
        "SELECT * FROM debtors WHERE id=? AND business_id=?", (debtor_id, biz["id"])
    ).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Qarzdor topilmadi.")
    txs = conn.execute(
        "SELECT type, amount, date, note FROM qarz_tx WHERE debtor_id=? ORDER BY date, id", (debtor_id,)
    ).fetchall()
    result = {
        "id": r["id"], "name": r["name"], "phone": r["phone"], "note": r["note"], "due": r["due"],
        "balance": qarz_balance(conn, debtor_id),
        "tx": [{"type": t["type"], "amount": t["amount"], "date": t["date"], "note": t["note"]} for t in txs],
    }
    conn.close()
    return result


@router.post("/qarz/debtors/{debtor_id}/tx")
async def qarz_add_tx(debtor_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    owns = conn.execute(
        "SELECT id FROM debtors WHERE id=? AND business_id=?", (debtor_id, biz["id"])
    ).fetchone()
    if not owns:
        conn.close()
        raise HTTPException(404, "Qarzdor topilmadi.")
    b = await request.json()
    if b.get("type") not in ("debt", "payment"):
        conn.close()
        raise HTTPException(400, "Amaliyot turi noto'g'ri.")
    try:
        amount = int(b.get("amount"))
    except Exception:
        amount = 0
    if amount <= 0:
        conn.close()
        raise HTTPException(400, "Summa noto'g'ri.")
    from datetime import date
    cur = conn.execute(
        "INSERT INTO qarz_tx(debtor_id, type, amount, date, note, created_at) VALUES(?,?,?,?,?,?)",
        (debtor_id, b["type"], amount, (b.get("date") or date.today().isoformat()).strip(),
         (b.get("note") or "").strip(), int(time.time())),
    )
    # v1412 (K1): qarz TO'LOVI o'sha kun kassasiga tushadi — "«Falonchi» qarz to'lovi"
    if b["type"] == "payment":
        _tx_id = cur.lastrowid
        _d = conn.execute("SELECT name FROM debtors WHERE id=?", (debtor_id,)).fetchone()
        _dname = (_d["name"] if _d else "") or "Qarzdor"
        conn.execute(
            "INSERT INTO sales(business_id, source, order_id, item_id, item_name, qty, unit, price, total, pay_type, debtor_id, qarz_tx_id, note, user_id, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (biz["id"], "qarzpay", None, None, "«" + _dname + "» qarz to'lovi",
             1, "", amount, amount, "", debtor_id, _tx_id,
             (b.get("note") or "").strip()[:200], user["id"], int(time.time())),
        )
    conn.commit()
    conn.close()
    return {"ok": True}


# ====================================================================
# QIDIRUV (mahsulot + e'lon + mutaxasis + biznes)
# ====================================================================
def _search_terms(q):
    """Qidiruv so'zini tozalab, variantlar va sinonimlarni tayyorlaydi.
    Apostrof (', ', `, ʻ, ʼ) bir xil qilinadi va so'z ichidan olib tashlanadi
    (do'kon -> dokon); apostrof so'z chegarasi deb hisoblanmaydi."""
    base = (q or "").strip().lower()
    norm = base
    for a in ("’", "‘", "`", "ʻ", "ʼ"):
        norm = norm.replace(a, "'")
    canon = norm.replace("'", "")          # apostrofsiz shakl: do'kon -> dokon

    variants = []

    def add(x):
        x = (x or "").strip().lower()
        if len(x) >= 2 and x not in variants:
            variants.append(x)

    add(base)
    add(norm)
    add(canon)
    # so'zlarga ajratish: faqat bo'shliq va chiziqcha bo'yicha (apostrof bo'yicha EMAS)
    for part in canon.replace("-", " ").split():
        add(part)
    for part in norm.replace("-", " ").split():
        add(part.replace("'", ""))

    # Sinonimlar — ANIQ so'z bo'yicha (substring emas: "telefon" ichidagi "non" kabi
    # noto'g'ri mosliklarning oldini oladi). Kalitlar apostrofsiz (kanonik) yoziladi.
    words = set(canon.replace("-", " ").split())
    words.add(canon)

    syns = {
        "muhr": ["muhr", "tamga", "pechat", "shtamp", "stamp"],
        "tamga": ["muhr", "tamga", "pechat", "shtamp"],
        "pechat": ["muhr", "tamga", "pechat", "shtamp"],
        "shtamp": ["muhr", "tamga", "pechat", "shtamp"],
        "taksi": ["taksi", "taxi", "yo'lovchi", "mashina"],
        "taxi": ["taksi", "taxi", "yo'lovchi", "mashina"],
        "dori": ["dori", "dorixona", "apteka", "farmatsevtika"],
        "dorixona": ["dori", "dorixona", "apteka", "farmatsevtika"],
        "apteka": ["dori", "dorixona", "apteka", "farmatsevtika"],
        "usta": ["usta", "ta'mir", "santexnik", "elektrik", "montaj", "quruvchi"],
        "repetitor": ["repetitor", "o'qituvchi", "ustoz", "kurs"],
        "advokat": ["advokat", "yurist", "huquq", "konsalting"],
        "dokon": ["dokon", "do'kon", "magazin", "market"],
        "magazin": ["dokon", "do'kon", "magazin", "market"],
        "oshxona": ["oshxona", "restoran", "kafe", "choyxona", "ovqat"],
        "restoran": ["oshxona", "restoran", "kafe", "choyxona"],
        "kafe": ["oshxona", "restoran", "kafe", "choyxona"],
        "non": ["non", "nonvoy", "nonvoyxona", "pekarnya"],
        "gosht": ["gosht", "qassob", "molgosht"],
        "qassob": ["gosht", "qassob"],
        "kiyim": ["kiyim", "kiyim-kechak", "odejda"],
        "sartarosh": ["sartarosh", "salon", "soch", "go'zallik"],
        "salon": ["sartarosh", "salon", "go'zallik"],
        "shifokor": ["shifokor", "klinika", "poliklinika", "tibbiyot", "vrach"],
        "klinika": ["shifokor", "klinika", "poliklinika", "tibbiyot"],
        "mebel": ["mebel", "divan", "stol", "shkaf"],
        "gul": ["gul", "gulchi", "guldasta", "buket"],
        "telefon": ["telefon", "smartfon", "aksessuar", "gadjet"],
        "qurilish": ["qurilish", "gisht", "stroymaterial", "sement"],
        "avtoservis": ["avtoservis", "avtomashina", "remont", "moylash"],
    }
    for key, arr in syns.items():
        if key in words:
            for x in arr:
                add(x)

    return variants[:24]


_APOS_CHARS = ("'", "’", "‘", "`", "ʻ", "ʼ")


def _canon_sql(col):
    """Ustun qiymatini kanonik shaklga keltiruvchi SQL ifoda:
    kichik harf + barcha apostrof ko'rinishlarini olib tashlash."""
    expr = "LOWER(COALESCE(" + col + ", ''))"
    for a in _APOS_CHARS:
        expr = "REPLACE(" + expr + ", '" + a.replace("'", "''") + "', '')"
    return expr


def _like_where(columns, terms):
    """Ustunlar bo'yicha LIKE shartini quradi. Ustun ham, qidiruv so'zi ham bir xil
    'kanonik' (kichik harf, apostrofsiz) shaklga keltirilib taqqoslanadi — shu sabab
    "dokon" ham "do'koni"ni topadi (ikki tomonlama apostrof moslash)."""
    cterms = []
    for t in terms:
        ct = (t or "").lower()
        for a in _APOS_CHARS:
            ct = ct.replace(a, "")
        ct = ct.strip()
        if len(ct) >= 2 and ct not in cterms:
            cterms.append(ct)
    if not cterms:
        return "1=0", []
    clauses = []
    params = []
    for col in columns:
        cexpr = _canon_sql(col)
        for ct in cterms:
            clauses.append(cexpr + " LIKE ?")
            params.append("%" + ct + "%")
    return "(" + " OR ".join(clauses) + ")", params


def _fts_match(q):
    """Qidiruv so'zidan FTS5 MATCH so'rovini quradi: kanonik tokenlar (apostrofsiz,
    kichik harf), har biriga prefiks '*' (qismini ham topadi), OR bilan bog'lanadi.
    Sinonimlar ham qo'shiladi (_search_terms orqali)."""
    toks = []
    for term in _search_terms(q):
        for w in term.replace("-", " ").split():
            w2 = "".join(ch for ch in w.lower() if ch.isalnum())
            if len(w2) >= 2 and w2 not in toks:
                toks.append(w2)
    if not toks:
        return ""
    return " OR ".join(t + "*" for t in toks)


def _search_quality_sql(primary_columns, q, secondary_columns=None):
    """Tartib: nomda aniq/barcha so'z -> tavsifda aniq/barcha so'z -> qisman."""
    raw = (q or "").strip().lower()
    for a in _APOS_CHARS:
        raw = raw.replace(a, "")
    words = [w for w in re.findall(r"[0-9a-z\u0400-\u04ff]+", raw) if len(w) >= 2]
    if not words:
        return "0", []
    secondary_columns = secondary_columns or []
    pblob = " || ' ' || ".join("COALESCE(" + col + ",'')" for col in primary_columns)
    sblob = " || ' ' || ".join("COALESCE(" + col + ",'')" for col in secondary_columns) or "''"
    pcanon = _canon_sql("(" + pblob + ")")
    scanon = _canon_sql("(" + sblob + ")")
    phrase = " ".join(words)
    p_all = " AND ".join(pcanon + " LIKE ?" for _ in words)
    s_all = " AND ".join(scanon + " LIKE ?" for _ in words)
    params = (["%" + phrase + "%"] + ["%" + w + "%" for w in words] +
              ["%" + phrase + "%"] + ["%" + w + "%" for w in words])
    sql = ("CASE WHEN " + pcanon + " LIKE ? THEN 0 "
           "WHEN (" + p_all + ") THEN 1 "
           "WHEN " + scanon + " LIKE ? THEN 2 "
           "WHEN (" + s_all + ") THEN 3 ELSE 4 END")
    return sql, params


# Qidiruv kengligi (scope) -> radius (km). None = cheklovsiz (Respublika).
_SCOPE_RADIUS_KM = {
    "Mahalla": 3.0,
    "Tuman": 12.0,
    "Shahar": 35.0,
    "Viloyat": 150.0,
    "Respublika": None,
}


def _scope_text(v):
    """Hudud nomlarini registr va ortiqcha bo'shliqlardan mustaqil taqqoslaydi."""
    return " ".join(str(v or "").strip().lower().split())


def _within_admin_scope(row, scope, viewer_region, viewer_district, viewer_mahalla):
    """Natijani haqiqiy ma'muriy hudud bo'yicha tekshiradi.

    target_region/target_district/target_mahalla SELECT so'rovlarida natija egasining
    users profilidan olinadi. Respublika cheklanmaydi. Hudud tanlangan, ammo tomonda
    zarur ma'lumot bo'lmasa natija mos hisoblanmaydi; radius hudud o'rnini bosmaydi.
    """
    if scope == "Respublika":
        return True
    try:
        keys = row.keys()
    except Exception:
        keys = []
    tr = _scope_text(row["target_region"] if "target_region" in keys else "")
    td = _scope_text(row["target_district"] if "target_district" in keys else "")
    tm = _scope_text(row["target_mahalla"] if "target_mahalla" in keys else "")
    vr = _scope_text(viewer_region)
    vd = _scope_text(viewer_district)
    vm = _scope_text(viewer_mahalla)
    if scope == "Viloyat":
        return bool(vr and tr and vr == tr)
    if scope in ("Tuman", "Shahar"):
        return bool(vr and vd and tr and td and vr == tr and vd == td)
    if scope == "Mahalla":
        return bool(vr and vd and vm and tr and td and tm and vr == tr and vd == td and vm == tm)
    return False


def _within_radius(row, ulat, ulng, radius_km):
    """Natija foydalanuvchidan radius_km ichidami? Koordinatasi yo'q bo'lsa True (yashirmaymiz)."""
    try:
        keys = row.keys()
    except Exception:
        keys = []
    lat = row["lat"] if "lat" in keys else None
    lng = row["lng"] if "lng" in keys else None
    if lat is None or lng is None:
        return True
    dlat = (lat - ulat) * 111.0
    dlng = (lng - ulng) * 111.0 * math.cos(math.radians(ulat))
    return (dlat * dlat + dlng * dlng) <= (radius_km * radius_km)


def _distance_km_value(lat, lng, ulat, ulng):
    """Frontendga ko'rsatish uchun Haversine bo'yicha masofa (km)."""
    try:
        lat, lng, ulat, ulng = float(lat), float(lng), float(ulat), float(ulng)
    except (TypeError, ValueError):
        return None
    p1, p2 = math.radians(ulat), math.radians(lat)
    dp = math.radians(lat - ulat)
    dl = math.radians(lng - ulng)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a))), 1)


def _has_search_marker(row):
    """Qidiruvga faqat haqiqiy xarita metkasi bor yozuvlarni o'tkazadi."""
    try:
        keys = row.keys()
        lat = row["lat"] if "lat" in keys else None
        lng = row["lng"] if "lng" in keys else None
        lat = float(lat)
        lng = float(lng)
        return -90 <= lat <= 90 and -180 <= lng <= 180
    except (TypeError, ValueError, KeyError):
        return False


_SERVICE_DIRECTIONS = {
    "transport va logistika", "xizmat korsatish", "maishiy xizmatlar",
    "umumiy ovqatlanish", "qurilish", "tibbiy xizmatlar", "talim faoliyati",
    "kochmas mulk", "axborot texnologiyalari", "konsalting va professional",
    "madaniyat sport kongilochar", "turizm va mehmonxona", "reklama va marketing",
    "poligrafiya va nashriyot", "moliyaviy faoliyat", "import eksport",
}


def _service_text(v):
    s = _scope_text(v)
    for a in _APOS_CHARS:
        s = s.replace(a, "")
    return " ".join(re.sub(r"[^0-9a-z\u0400-\u04ff ]+", " ", s).split())


def _business_is_service(row):
    yon = _service_text(_row_val(row, "yon", ""))
    tur = _service_text(_row_val(row, "tur", ""))
    if yon in _SERVICE_DIRECTIONS:
        return True
    markers = ("xizmat", "tamir", "usta", "konsult", "kurs", "tashish", "yetkazib", "ijara")
    return any(x in tur for x in markers)


def _listing_is_service(row):
    yon = _service_text(_row_val(row, "listing_business_yon", ""))
    tur = _service_text(_row_val(row, "listing_business_tur", ""))
    if yon in _SERVICE_DIRECTIONS:
        return True
    text = _service_text(" ".join(str(_row_val(row, k, "") or "") for k in ("cat", "title", "descr")))
    markers = (
        "xizmat", "tamir", "usta", "santexnik", "elektrik", "massaj", "tozalash",
        "repetitor", "advokat", "buxgalter", "konsult", "dizayn", "dasturlash",
        "yetkazib", "tashish", "ijara", "montaj", "qurilish", "shifokor",
    )
    return any(x in (tur + " " + text) for x in markers)


def _edit_distance(a, b):
    """Levenshtein masofasi (necha harf o'zgargani). Katta farqni tez rad etadi."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > 2:
        return 99
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ai = a[i - 1]
        for j in range(1, lb + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (0 if ai == b[j - 1] else 1))
        prev = cur
    return prev[lb]


# Fuzzy uchun keng tarqalgan atamalar (kanonik: kichik harf, apostrofsiz).
_FUZZY_VOCAB = {
    "dokon", "magazin", "market", "oshxona", "restoran", "kafe", "choyxona", "ovqat",
    "non", "nonvoyxona", "gosht", "qassob", "kiyim", "sartarosh", "salon", "soch",
    "shifokor", "klinika", "poliklinika", "dorixona", "apteka", "dori", "mebel",
    "gul", "gulchi", "telefon", "smartfon", "kompyuter", "qurilish", "avtoservis",
    "taksi", "usta", "repetitor", "advokat", "fotograf", "tikuvchi", "shirinlik",
    "kabob", "somsa", "pizza", "burger", "stomatolog", "vrach", "kir", "yuvish",
}


def _fuzzy_correct(conn, q):
    """Qidiruv bo'sh natija berganda: xato yozilgan so'zlarni yaqin (mavjud) so'zlarga
    tuzatadi. Lug'at: FTS nom ustunlaridagi haqiqiy so'zlar + keng tarqalgan atamalar."""
    vocab = set(_FUZZY_VOCAB)
    try:
        for tbl in ("businesses_fts", "listings_fts", "items_fts", "specialists_fts"):
            for row in conn.execute("SELECT name FROM " + tbl):
                for w in (row[0] or "").split():
                    if len(w) >= 3:
                        vocab.add(w)
    except Exception:
        pass
    raw = (q or "").lower()
    for a in _APOS_CHARS:
        raw = raw.replace(a, "")
    toks = [w for w in re.findall(r"[0-9a-z\u0400-\u04ff]+", raw) if len(w) >= 2]
    if not toks:
        return None
    changed = False
    out = []
    for t in toks:
        if t in vocab:
            out.append(t)
            continue
        thr = 1 if len(t) < 7 else 2
        best, bestd = None, thr + 1
        for v in vocab:
            if abs(len(v) - len(t)) > thr:
                continue
            d = _edit_distance(t, v)
            if d < bestd:
                bestd, best = d, v
        if best is not None and bestd <= thr:
            out.append(best)
            changed = True
        else:
            out.append(t)
    if not changed:
        return None
    return " ".join(out)


# O'lchov birliklari — ruxsat etilgan ro'yxat (frontend tanlovi bilan bir xil bo'lishi shart)
UNITS = ("dona", "kg", "g", "litr", "ml", "metr", "sm", "m²",
         "to'plam", "quti", "juft", "porsiya", "soat", "kun", "marta")


def _clean_unit(v):
    """Birlikni tekshiradi; ro'yxatda bo'lmasa yoki bo'sh bo'lsa 'dona' qaytaradi."""
    v = (v or "").strip()
    return v if v in UNITS else "dona"


# Kasr miqdorga ruxsat etilgan (o'lchanadigan) birliklar; qolganlari butun son bo'ladi
FRACTIONAL_UNITS = ("kg", "g", "litr", "ml", "metr", "sm", "m²", "soat")


@router.get("/search")
async def search(q: str = "", scope: str = "", result_type: str = "all", actor_type: str = "user",
                 x_telegram_init_data: str = Header(default="")):
    q = (q or "").strip()
    if not q:
        raise HTTPException(400, "Qidiruv so'zi kiritilmadi.")
    conn = db()
    result_type = (result_type or "all").strip().lower()
    if result_type not in ("all", "product", "service", "business", "specialist", "user"):
        conn.close()
        raise HTTPException(400, "Qidiruv turi noto'g'ri.")
    try:
        _ensure_pay_columns(conn)       # businesses.username kafolati
        _ensure_user_username(conn)     # users.pub_username kafolati
        conn.commit()
    except Exception:
        pass
    # Qidiruv joriy kabinet nomidan bajariladi. Oddiy kabinet uchun users,
    # biznes kabinet uchun businesses koordinatasi olinadi; ular aralashtirilmaydi.
    ulat = ulng = None
    viewer_region = viewer_district = viewer_mahalla = ""
    _u = require_user(conn, x_telegram_init_data)
    actor_ctx = resolve_actor(conn, _u, actor_type)
    if actor_ctx["type"] == "business":
        _biz = actor_ctx["business"]
        ulat, ulng = _biz["lat"], _biz["lng"]
        # Biznesda alohida ma'muriy ustunlar yo'q; egasining profil hududi olinadi.
        viewer_region, viewer_district, viewer_mahalla = _u["region"], _u["district"], _u["mahalla"]
    else:
        if int(_row_val(_u, "location_exact", 0) or 0):
            ulat, ulng = _u["lat"], _u["lng"]
        viewer_region, viewer_district, viewer_mahalla = _u["region"], _u["district"], _u["mahalla"]

    def _search_prefilter_sql(user_alias, geo_alias):
        """Metka va ma'muriy hududni LIMITdan oldin SQL ichida filtrlaydi."""
        parts = [
            geo_alias + ".lat IS NOT NULL", geo_alias + ".lng IS NOT NULL",
            geo_alias + ".lat BETWEEN -90 AND 90", geo_alias + ".lng BETWEEN -180 AND 180",
        ]
        params = []
        vr, vd, vm = _scope_text(viewer_region), _scope_text(viewer_district), _scope_text(viewer_mahalla)
        if scope == "Viloyat":
            if vr:
                parts.append("LOWER(TRIM(COALESCE(" + user_alias + ".region,'')))=?")
                params.append(vr)
        elif scope in ("Tuman", "Shahar"):
            if vr and vd:
                parts.extend([
                    "LOWER(TRIM(COALESCE(" + user_alias + ".region,'')))=?",
                    "LOWER(TRIM(COALESCE(" + user_alias + ".district,'')))=?",
                ])
                params.extend([vr, vd])
        elif scope == "Mahalla":
            if vr and vd and vm:
                parts.extend([
                    "LOWER(TRIM(COALESCE(" + user_alias + ".region,'')))=?",
                    "LOWER(TRIM(COALESCE(" + user_alias + ".district,'')))=?",
                    "LOWER(TRIM(COALESCE(" + user_alias + ".mahalla,'')))=?",
                ])
                params.extend([vr, vd, vm])
        return " AND " + " AND ".join(parts), params

    def _distance_order_sql(alias):
        """SQLite qo'shimcha geografik funksiyasiz taxminiy masofa kvadrati."""
        try:
            la, lo = float(ulat), float(ulng)
        except (TypeError, ValueError):
            return "1e30"
        return ("(((" + alias + ".lat-(" + repr(la) + "))*111.0)*((" + alias + ".lat-(" + repr(la) + "))*111.0) + "
                "((" + alias + ".lng-(" + repr(lo) + "))*85.0)*((" + alias + ".lng-(" + repr(lo) + "))*85.0))")

    def _fetch(qq):
        search_q = qq.strip()[1:] if qq.strip().startswith("@") else qq
        terms = _search_terms(search_q)
        _match = _fts_match(search_q)
        product_filter, product_filter_params = _search_prefilter_sql("bu", "b")
        listing_filter, listing_filter_params = _search_prefilter_sql("u", "l")
        specialist_filter, specialist_filter_params = _search_prefilter_sql("u", "s")
        business_filter, business_filter_params = _search_prefilter_sql("u", "b")
        product_quality, product_quality_params = _search_quality_sql(
            ["i.name"], search_q, ["i.note", "b.name", "b.yon", "b.tur", "b.descr", "b.address"])
        listing_quality, listing_quality_params = _search_quality_sql(
            ["l.title"], search_q, ["l.cat", "l.descr", "l.address"])
        specialist_quality, specialist_quality_params = _search_quality_sql(
            ["s.kasb", "u.name"], search_q, ["s.descr", "s.hudud", "s.org", "s.lavozim"])
        business_quality, business_quality_params = _search_quality_sql(
            ["b.name"], search_q, ["b.yon", "b.tur", "b.descr", "b.address", "b.username"])
        product_distance = _distance_order_sql("b")
        listing_distance = _distance_order_sql("l")
        specialist_distance = _distance_order_sql("s")
        business_distance = _distance_order_sql("b")
        product_rating = "CASE WHEN COALESCE(b.rating_cnt,0)>0 THEN b.rating_sum*1.0/b.rating_cnt ELSE 0 END"
        listing_rating = "0"
        specialist_rating = "CASE WHEN COALESCE(s.rating_cnt,0)>0 THEN s.rating_sum*1.0/s.rating_cnt ELSE 0 END"
        business_rating = "CASE WHEN COALESCE(b.rating_cnt,0)>0 THEN b.rating_sum*1.0/b.rating_cnt ELSE 0 END"

        # Mahsulotlar — FTS (bm25 moslik, mahsulot nomi 10x). Xatolik bo'lsa eski LIKE'ga qaytadi.
        products = None
        if _match:
            try:
                products = conn.execute(
                    "SELECT i.id, i.name, i.price, i.unit, i.note, i.kind, i.photo_file, "
                    "b.id biz_id, b.name biz_name, b.yon biz_yon, b.tur biz_tur, b.address, b.lat, b.lng, "
                    "bu.region target_region, bu.district target_district, bu.mahalla target_mahalla, "
                    "bm25(items_fts, 10.0, 1.0) AS _rank "
                    "FROM items_fts JOIN items i ON i.id = items_fts.rowid "
                    "JOIN businesses b ON b.id = i.business_id JOIN users bu ON bu.id=b.user_id "
                    "WHERE items_fts MATCH ? AND b.status='active' " + product_filter + " "
                    "ORDER BY " + product_quality + ", " + product_distance + ", " + product_rating + " DESC, _rank LIMIT 50",
                    [_match] + product_filter_params + product_quality_params,
                ).fetchall()
            except Exception:
                products = None
        if not products:   # FTS xato BERSA ham, BO'SH bo'lsa ham oddiy qidiruvga o'tamiz
            product_where, product_params = _like_where(
                ["i.name", "i.note", "i.kind", "b.name", "b.yon", "b.tur", "b.descr", "b.address"],
                terms,
            )
            products = conn.execute(
                """SELECT i.id, i.name, i.price, i.unit, i.note, i.kind, i.photo_file,
                          b.id biz_id, b.name biz_name, b.yon biz_yon, b.tur biz_tur, b.address, b.lat, b.lng,
                          bu.region target_region, bu.district target_district, bu.mahalla target_mahalla
                   FROM items i JOIN businesses b ON b.id=i.business_id JOIN users bu ON bu.id=b.user_id
                   WHERE b.status='active' AND """ + product_where + product_filter + """
                   ORDER BY """ + product_quality + ", " + product_distance + ", " + product_rating + " DESC, i.created_at DESC LIMIT 50",
                product_params + product_filter_params + product_quality_params,
            ).fetchall()

        # E'lonlar — FTS (bm25 moslik). Xatolik yoki indeks bo'lmasa eski LIKE'ga qaytadi.
        listings = None
        if _match:
            try:
                listings = conn.execute(
                    "SELECT l.*, lb.yon listing_business_yon, lb.tur listing_business_tur, "
                    "u.region target_region, u.district target_district, u.mahalla target_mahalla, "
                    "bm25(listings_fts, 10.0, 1.0) AS _rank "
                    "FROM listings_fts JOIN listings l ON l.id = listings_fts.rowid "
                    "JOIN users u ON u.id=l.user_id LEFT JOIN businesses lb ON lb.id=l.business_id "
                    "WHERE listings_fts MATCH ? AND l.status='active' AND l.visibility='all' " + listing_filter + " "
                    "ORDER BY " + listing_quality + ", " + listing_distance + ", " + listing_rating + " DESC, _rank LIMIT 50",
                    [_match] + listing_filter_params + listing_quality_params,
                ).fetchall()
            except Exception:
                listings = None
        if not listings:   # FTS xato BERSA ham, BO'SH bo'lsa ham oddiy qidiruvga o'tamiz
            listing_where, listing_params = _like_where(
                ["l.title", "l.cat", "l.price", "l.descr", "l.address"],
                terms,
            )
            listings = conn.execute(
                "SELECT l.*, lb.yon listing_business_yon, lb.tur listing_business_tur, "
                "u.region target_region, u.district target_district, u.mahalla target_mahalla "
                "FROM listings l JOIN users u ON u.id=l.user_id LEFT JOIN businesses lb ON lb.id=l.business_id "
                "WHERE l.status='active' AND l.visibility='all' AND " + listing_where + listing_filter +
                " ORDER BY " + listing_quality + ", " + listing_distance + ", l.created_at DESC LIMIT 50",
                listing_params + listing_filter_params + listing_quality_params,
            ).fetchall()

        # Mutaxassislar — FTS (bm25 moslik, kasb+ism 10x). Bo'sh (available) birinchi, keyin moslik.
        specialists = None
        if _match:
            try:
                specialists = conn.execute(
                    "SELECT s.*, u.name, u.region, u.district, u.mahalla, u.region target_region, "
                    "u.district target_district, u.mahalla target_mahalla, u.avatar_file, u.avatar_x, u.avatar_y, u.avatar_zoom, "
                    "bm25(specialists_fts, 10.0, 1.0) AS _rank "
                    "FROM specialists_fts JOIN specialists s ON s.user_id = specialists_fts.rowid "
                    "JOIN users u ON u.id = s.user_id "
                    "WHERE specialists_fts MATCH ? AND s.visible=1 " + specialist_filter + " "
                    "ORDER BY " + specialist_quality + ", " + specialist_distance + ", " + specialist_rating + " DESC, s.available DESC, _rank LIMIT 50",
                    [_match] + specialist_filter_params + specialist_quality_params,
                ).fetchall()
            except Exception:
                specialists = None
        if not specialists:   # FTS xato BERSA ham, BO'SH bo'lsa ham oddiy qidiruvga o'tamiz
            specialist_where, specialist_params = _like_where(
                ["s.kasb", "s.descr", "s.narx", "s.hudud", "s.org", "s.dept", "s.lavozim",
                 "u.name", "u.region", "u.district", "u.mahalla"],
                terms,
            )
            specialists = conn.execute(
                """SELECT s.*, u.name, u.region, u.district, u.mahalla, u.region target_region,
                          u.district target_district, u.mahalla target_mahalla, u.avatar_file, u.avatar_x, u.avatar_y, u.avatar_zoom
                   FROM specialists s JOIN users u ON u.id=s.user_id
                   WHERE s.visible=1 AND """ + specialist_where + specialist_filter + """
                   ORDER BY """ + specialist_quality + ", " + specialist_distance + ", " + specialist_rating + " DESC, s.available DESC, s.created_at DESC LIMIT 50",
                specialist_params + specialist_filter_params + specialist_quality_params,
            ).fetchall()

        # Bizneslar — FTS (bm25 moslik bo'yicha tartiblash). Xatolik yoki indeks bo'lmasa
        # avtomatik eski LIKE usuliga qaytadi (biznes qidiruvi hech qachon buzilmaydi).
        businesses = None
        if _match:
            try:
                businesses = conn.execute(
                    "SELECT b.*, u.region target_region, u.district target_district, u.mahalla target_mahalla, "
                    "bm25(businesses_fts, 10.0, 1.0) AS _rank "
                    "FROM businesses_fts JOIN businesses b ON b.id = businesses_fts.rowid JOIN users u ON u.id=b.user_id "
                    "WHERE businesses_fts MATCH ? AND b.status='active' " + business_filter + " "
                    "ORDER BY " + business_quality + ", " + business_distance + ", " + business_rating + " DESC, _rank LIMIT 50",
                    [_match] + business_filter_params + business_quality_params,
                ).fetchall()
            except Exception:
                businesses = None
        if not businesses:   # FTS xato BERSA ham, BO'SH bo'lsa ham oddiy qidiruvga o'tamiz
            business_where, business_params = _like_where(
                ["b.name", "b.yon", "b.tur", "b.descr", "b.address", "b.phone", "b.telegram", "b.work_hours", "b.username"],
                terms,
            )
            businesses = conn.execute(
                "SELECT b.*, u.region target_region, u.district target_district, u.mahalla target_mahalla "
                "FROM businesses b JOIN users u ON u.id=b.user_id WHERE b.status='active' AND " + business_where + business_filter +
                " ORDER BY " + business_quality + ", " + business_distance + ", " + business_rating + " DESC, b.created_at DESC LIMIT 50",
                business_params + business_filter_params + business_quality_params,
            ).fetchall()

        # Metkasi yo'q obyekt hech bir qidiruv kengligida ko'rinmaydi.
        products = [r for r in products if _has_search_marker(r)]
        listings = [r for r in listings if _has_search_marker(r)]
        specialists = [r for r in specialists if _has_search_marker(r)]
        businesses = [r for r in businesses if _has_search_marker(r)]

        # Qidiruv kengligi haqiqiy viloyat/tuman/mahalla nomlari bo'yicha ishlaydi.
        scope_ready = (
            scope == "Respublika" or
            (scope == "Viloyat" and bool(_scope_text(viewer_region))) or
            (scope in ("Tuman", "Shahar") and bool(_scope_text(viewer_region) and _scope_text(viewer_district))) or
            (scope == "Mahalla" and bool(_scope_text(viewer_region) and _scope_text(viewer_district) and _scope_text(viewer_mahalla)))
        )
        if scope_ready:
            products = [r for r in products if _within_admin_scope(r, scope, viewer_region, viewer_district, viewer_mahalla)]
            listings = [r for r in listings if _within_admin_scope(r, scope, viewer_region, viewer_district, viewer_mahalla)]
            specialists = [r for r in specialists if _within_admin_scope(r, scope, viewer_region, viewer_district, viewer_mahalla)]
            businesses = [r for r in businesses if _within_admin_scope(r, scope, viewer_region, viewer_district, viewer_mahalla)]

        if result_type == "product":
            products = [r for r in products if str(_row_val(r, "kind", "product") or "product").lower() != "service"]
            listings, specialists, businesses = [], [], []
        elif result_type == "service":
            products = [r for r in products if str(_row_val(r, "kind", "") or "").lower() == "service"]
            listings = [r for r in listings if _listing_is_service(r)]
            businesses = [r for r in businesses if _business_is_service(r)]
        elif result_type == "business":
            products, listings, specialists = [], [], []
        elif result_type == "specialist":
            products, listings, businesses = [], [], []
        elif result_type == "user":
            products, listings, specialists, businesses = [], [], [], []
        return products, listings, specialists, businesses

    products, listings, specialists, businesses = _fetch(q)
    corrected = None
    if (len(products) + len(listings) + len(specialists) + len(businesses)) == 0:
        cq = _fuzzy_correct(conn, q)
        if cq and cq != q:
            p2, l2, s2, b2 = _fetch(cq)
            if (len(p2) + len(l2) + len(s2) + len(b2)) > 0:
                products, listings, specialists, businesses = p2, l2, s2, b2
                corrected = cq

    result = {
        "q": q,
        "scope": scope,
        "result_type": result_type,
        "actor_type": actor_ctx["type"],
        "location_available": ulat is not None and ulng is not None,
        "location_required": False,
        "corrected": corrected,
        "terms": _search_terms(corrected or q),
        "products": [{"id": p["id"], "name": p["name"], "price": p["price"], "unit": p["unit"] or "dona",
                      "note": p["note"], "kind": p["kind"],
                      "photo_file": _row_val(p, "photo_file", "") or "",
                      "business_id": p["biz_id"], "business_name": p["biz_name"],
                      "business_yon": p["biz_yon"], "business_tur": p["biz_tur"],
                      "address": p["address"], "lat": p["lat"], "lng": p["lng"],
                      "distance_km": _distance_km_value(p["lat"], p["lng"], ulat, ulng)} for p in products],
        "listings": [{**listing_to_dict(conn, r, with_media=True),
                       "distance_km": _distance_km_value(r["lat"], r["lng"], ulat, ulng)} for r in listings],
        "specialists": [{"user_id": s["user_id"], "name": s["name"], "kasb": s["kasb"],
                         "descr": s["descr"], "narx": s["narx"], "is_gov": bool(s["is_gov"]),
                         "available": bool(s["available"]), "region": s["region"],
                         "district": s["district"], "mahalla": s["mahalla"],
                         "avatar_file": _row_val(s, "avatar_file", "") or "",
                         "avatar_x": float(_row_val(s, "avatar_x", 50) or 50), "avatar_y": float(_row_val(s, "avatar_y", 50) or 50),
                         "avatar_zoom": float(_row_val(s, "avatar_zoom", 1) or 1),
                         "lat": s["lat"], "lng": s["lng"],
                         "distance_km": _distance_km_value(s["lat"], s["lng"], ulat, ulng),
                         "rating": (round(_row_val(s,"rating_sum",0)/_row_val(s,"rating_cnt",0),1) if _row_val(s,"rating_cnt",0) else 0),
                         "rating_cnt": _row_val(s,"rating_cnt",0) or 0} for s in specialists],
        "businesses": [{"id": b["id"], "name": b["name"], "yon": b["yon"], "tur": b["tur"],
                        "descr": b["descr"], "address": b["address"],
                        "logo_file": _row_val(b, "logo_file", "") or "",
                        "logo_x": float(_row_val(b, "logo_x", 50) or 50), "logo_y": float(_row_val(b, "logo_y", 50) or 50),
                        "logo_zoom": float(_row_val(b, "logo_zoom", 1) or 1),
                        "lat": b["lat"], "lng": b["lng"],
                        "distance_km": _distance_km_value(b["lat"], b["lng"], ulat, ulng),
                        "rating": (round(_row_val(b,"rating_sum",0)/_row_val(b,"rating_cnt",0),1) if _row_val(b,"rating_cnt",0) else 0),
                        "rating_cnt": _row_val(b,"rating_cnt",0) or 0} for b in businesses],
    }
    # Foydalanuvchilarni username (yoki ism) bo'yicha topamiz — mutaxassis bo'lmasa ham
    try:
        raw_user_q = (corrected or q).strip()
        username_mode = raw_user_q.startswith("@")
        uq = raw_user_q.lstrip("@").lower()
        users = []
        if uq and result_type in ("all", "user"):
            like = "%" + uq + "%"
            prefix_like = uq + "%"
            # FAQAT username maydonlari bo'yicha (ism/mahsulot aralashmaydi):
            #  - tanlangan pub_username, YOKI
            #  - pub_username bo'sh bo'lsa, Telegram username (registratsiyadagi)
            user_name_clause = "" if username_mode else " OR lower(name) LIKE ?"
            user_params = [like, like]
            if not username_mode:
                user_params.append(like)
            user_params.extend([uq, uq, prefix_like, prefix_like])
            urows = conn.execute(
                "SELECT id, name, pub_username, username, region, district, avatar_file, avatar_x, avatar_y, avatar_zoom FROM users "
                "WHERE ((COALESCE(pub_username,'')<>'' AND lower(pub_username) LIKE ?) "
                "   OR (COALESCE(username,'')<>'' AND lower(username) LIKE ?) "
                + user_name_clause + ") "
                "ORDER BY CASE "
                " WHEN lower(COALESCE(pub_username,''))=? THEN 0 "
                " WHEN lower(COALESCE(username,''))=? THEN 1 "
                " WHEN lower(COALESCE(pub_username,'')) LIKE ? THEN 2 "
                " WHEN lower(COALESCE(username,'')) LIKE ? THEN 3 ELSE 4 END, name COLLATE NOCASE "
                "LIMIT 30",
                user_params,
            ).fetchall()
            for u in urows:
                handle = (u["pub_username"] or "").strip() or (_row_val(u, "username", "") or "").strip()
                users.append({"id": u["id"], "name": u["name"] or "Foydalanuvchi",
                              "pub_username": handle,
                              "region": u["region"] or "", "district": u["district"] or "",
                              "avatar_file": _row_val(u, "avatar_file", "") or "",
                              "avatar_x": float(_row_val(u, "avatar_x", 50) or 50),
                              "avatar_y": float(_row_val(u, "avatar_y", 50) or 50),
                              "avatar_zoom": float(_row_val(u, "avatar_zoom", 1) or 1)})
        result["users"] = users
        # @username oddiy/Barchasi rejimida foydalanuvchi identifikatori ustuvor.
        # Biznes username qidiruvi alohida "Biznes" filtrida ishlashda davom etadi.
        if username_mode and result_type in ("all", "user"):
            result["products"] = []
            result["listings"] = []
            result["specialists"] = []
            result["businesses"] = []
    except Exception:
        result["users"] = []
    conn.close()
    return result


@router.get("/browse")
async def browse_by_type(tur: str = "", scope: str = "Tuman", actor_type: str = "user",
                         x_telegram_init_data: str = Header(default="")):
    """Katalogdan faoliyat turi tanlanganda: shu turdagi biznes va mutaxasislar."""
    tur = (tur or "").strip()
    if not tur:
        raise HTTPException(400, "Faoliyat turi kiritilmadi.")
    terms = _search_terms(tur)
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    actor_ctx = resolve_actor(conn, user, actor_type)
    viewer_region = user["region"] or ""
    viewer_district = user["district"] or ""
    viewer_mahalla = user["mahalla"] or ""
    if actor_ctx["type"] == "business":
        _ab = actor_ctx["business"]
        browse_lat, browse_lng = _ab["lat"], _ab["lng"]
    else:
        if int(_row_val(user, "location_exact", 0) or 0):
            browse_lat, browse_lng = user["lat"], user["lng"]
        else:
            browse_lat = browse_lng = None

    def browse_distance(alias):
        try:
            la, lo = float(browse_lat), float(browse_lng)
        except (TypeError, ValueError):
            return "1e30"
        return ("((" + alias + ".lat-(" + repr(la) + "))*(" + alias + ".lat-(" + repr(la) + "))*12321.0 + "
                "(" + alias + ".lng-(" + repr(lo) + "))*(" + alias + ".lng-(" + repr(lo) + "))*7225.0)")

    def browse_filter(user_alias, geo_alias):
        parts = [
            geo_alias + ".lat IS NOT NULL", geo_alias + ".lng IS NOT NULL",
            geo_alias + ".lat BETWEEN -90 AND 90", geo_alias + ".lng BETWEEN -180 AND 180",
        ]
        params = []
        vr, vd, vm = _scope_text(viewer_region), _scope_text(viewer_district), _scope_text(viewer_mahalla)
        if scope == "Viloyat":
            if vr:
                parts.append("LOWER(TRIM(COALESCE(" + user_alias + ".region,'')))=?")
                params.append(vr)
        elif scope in ("Tuman", "Shahar"):
            if vr and vd:
                parts.extend([
                    "LOWER(TRIM(COALESCE(" + user_alias + ".region,'')))=?",
                    "LOWER(TRIM(COALESCE(" + user_alias + ".district,'')))=?",
                ])
                params.extend([vr, vd])
        elif scope == "Mahalla":
            if vr and vd and vm:
                parts.extend([
                    "LOWER(TRIM(COALESCE(" + user_alias + ".region,'')))=?",
                    "LOWER(TRIM(COALESCE(" + user_alias + ".district,'')))=?",
                    "LOWER(TRIM(COALESCE(" + user_alias + ".mahalla,'')))=?",
                ])
                params.extend([vr, vd, vm])
        return " AND " + " AND ".join(parts), params

    biz_filter, biz_filter_params = browse_filter("u", "b")
    spec_filter, spec_filter_params = browse_filter("u", "s")

    business_where, business_params = _like_where(["b.tur", "b.yon", "b.name", "b.descr"], terms)
    businesses = conn.execute(
        "SELECT b.* FROM businesses b JOIN users u ON u.id=b.user_id "
        "WHERE b.status='active' AND " + business_where + biz_filter +
        " ORDER BY " + browse_distance("b") + ", "
        "CASE WHEN COALESCE(b.rating_cnt,0)>0 THEN b.rating_sum*1.0/b.rating_cnt ELSE 0 END DESC, "
        "b.created_at DESC LIMIT 100",
        business_params + biz_filter_params,
    ).fetchall()

    specialist_where, specialist_params = _like_where(
        ["s.kasb", "s.descr", "s.hudud", "s.org", "s.lavozim", "u.name", "u.district"],
        terms,
    )
    specialists = conn.execute(
        """SELECT s.*, u.name, u.region, u.district, u.mahalla, u.avatar_file, u.avatar_x, u.avatar_y, u.avatar_zoom
           FROM specialists s JOIN users u ON u.id=s.user_id
           WHERE s.visible=1 AND """ + specialist_where + spec_filter + """
           ORDER BY """ + browse_distance("s") + ", "
        "CASE WHEN COALESCE(s.rating_cnt,0)>0 THEN s.rating_sum*1.0/s.rating_cnt ELSE 0 END DESC, "
        "s.available DESC, s.created_at DESC LIMIT 100",
        specialist_params + spec_filter_params,
    ).fetchall()
    result = {
        "scope": scope,
        "actor_type": actor_ctx["type"],
        "location_available": browse_lat is not None and browse_lng is not None,
        "location_required": False,
        "businesses": [{"id": b["id"], "name": b["name"], "yon": b["yon"], "tur": b["tur"],
                        "descr": b["descr"], "address": b["address"],
                        "logo_file": _row_val(b, "logo_file", "") or "",
                        "logo_x": float(_row_val(b, "logo_x", 50) or 50), "logo_y": float(_row_val(b, "logo_y", 50) or 50),
                        "logo_zoom": float(_row_val(b, "logo_zoom", 1) or 1),
                        "lat": b["lat"], "lng": b["lng"],
                        "distance_km": _distance_km_value(b["lat"], b["lng"], browse_lat, browse_lng),
                        "rating": (round(_row_val(b,"rating_sum",0)/_row_val(b,"rating_cnt",0),1) if _row_val(b,"rating_cnt",0) else 0),
                        "rating_cnt": _row_val(b,"rating_cnt",0) or 0} for b in businesses],
        "specialists": [{"user_id": s["user_id"], "name": s["name"], "kasb": s["kasb"],
                         "descr": s["descr"], "narx": s["narx"], "is_gov": bool(s["is_gov"]),
                         "available": bool(s["available"]), "region": s["region"],
                         "district": s["district"], "mahalla": s["mahalla"],
                         "avatar_file": _row_val(s, "avatar_file", "") or "",
                         "avatar_x": float(_row_val(s, "avatar_x", 50) or 50), "avatar_y": float(_row_val(s, "avatar_y", 50) or 50),
                         "avatar_zoom": float(_row_val(s, "avatar_zoom", 1) or 1),
                         "lat": s["lat"], "lng": s["lng"],
                         "distance_km": _distance_km_value(s["lat"], s["lng"], browse_lat, browse_lng),
                         "rating": (round(_row_val(s,"rating_sum",0)/_row_val(s,"rating_cnt",0),1) if _row_val(s,"rating_cnt",0) else 0),
                         "rating_cnt": _row_val(s,"rating_cnt",0) or 0} for s in specialists],
    }
    conn.close()
    return result


# ====================================================================
# SAHIFALAR (biznes / mutaxasis)
# ====================================================================
@router.get("/business/{business_id}")
async def business_page(business_id: int, actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    conn = db()
    viewer = optional_user(conn, x_telegram_init_data)
    biz = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    if not biz:
        conn.close()
        raise HTTPException(404, "Biznes topilmadi.")
    items = conn.execute(
        """SELECT i.id, i.name, i.price, i.unit, i.note, i.kind, i.group_id, i.photo_file,
                  g.name AS group_name, g.kind AS group_kind
           FROM items i
           LEFT JOIN item_groups g ON g.id=i.group_id AND g.business_id=i.business_id
           WHERE i.business_id=? ORDER BY i.created_at DESC""",
        (business_id,),
    ).fetchall()
    item_groups = conn.execute(
        "SELECT id, name, kind FROM item_groups WHERE business_id=? ORDER BY created_at ASC, id ASC",
        (business_id,),
    ).fetchall()
    # Biznes sahifasida HAMMA e'lonlari ko'rinadi (shu jumladan 'own' — faqat mehmonlarga)
    listings = conn.execute(
        "SELECT * FROM listings WHERE business_id=? AND status='active' ORDER BY created_at DESC",
        (business_id,),
    ).fetchall()
    viewer_actor = resolve_actor(conn, viewer, actor_type) if viewer else None
    result = {
        "id": biz["id"], "name": biz["name"], "yon": biz["yon"], "tur": biz["tur"],
        "descr": biz["descr"], "phone": biz["phone"], "telegram": biz["telegram"],
        "logo_file": _row_val(biz, "logo_file", "") or "",
        "logo_x": float(_row_val(biz, "logo_x", 50) or 50), "logo_y": float(_row_val(biz, "logo_y", 50) or 50),
        "logo_zoom": float(_row_val(biz, "logo_zoom", 1) or 1),
        "work_hours": biz["work_hours"], "address": biz["address"],
        "lat": biz["lat"], "lng": biz["lng"],
        "followers": follower_count(conn, "business", biz["id"]),
        "is_following": is_following(
            conn, viewer["id"] if viewer else None, "business", biz["id"],
            viewer_actor["type"] if viewer_actor else "user",
            viewer_actor["business_id"] if viewer_actor and viewer_actor["type"] == "business" else None,
        ),
        "item_groups": [{"id": g["id"], "name": g["name"], "kind": g["kind"]} for g in item_groups],
        "items": [{"id": i["id"], "name": i["name"], "price": i["price"],
                   "unit": i["unit"] or "dona",
                   "note": i["note"], "kind": i["kind"], "group_id": i["group_id"],
                   "group_name": i["group_name"], "group_kind": i["group_kind"],
                   "photo_file": i["photo_file"]} for i in items],
        "listings": [listing_to_dict(conn, r) for r in listings],
    }
    conn.close()
    return result


@router.get("/person/{user_id}")
async def person_page(user_id: int, actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    conn = db()
    viewer = optional_user(conn, x_telegram_init_data)
    u = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not u:
        conn.close()
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    sp = conn.execute("SELECT * FROM specialists WHERE user_id=? AND visible=1", (user_id,)).fetchone()
    listings = conn.execute(
        "SELECT * FROM listings WHERE user_id=? AND business_id IS NULL AND status='active' AND visibility='all' "
        "ORDER BY created_at DESC", (user_id,),
    ).fetchall()
    viewer_actor = resolve_actor(conn, viewer, actor_type) if viewer else None
    result = {
        "id": u["id"], "name": u["name"], "district": u["district"],
        "followers": follower_count(conn, "user", u["id"]),
        "is_following": is_following(
            conn, viewer["id"] if viewer else None, "user", u["id"],
            viewer_actor["type"] if viewer_actor else "user",
            viewer_actor["business_id"] if viewer_actor and viewer_actor["type"] == "business" else None,
        ),
        "specialist": None,
        "listings": [listing_to_dict(conn, r) for r in listings],
    }
    if sp:
        result["specialist"] = {
            "kasb": sp["kasb"] or "", "descr": sp["descr"] or "",
            **_specialist_content(conn, user_id),
        }
    conn.close()
    return result


# ====================================================================
# CHAT / XABARLAR
# ====================================================================
def _actor_identity(actor):
    """resolve_actor() natijasini chat uchun (kind, actor_id, owner_user_id) ko'rinishiga keltiradi."""
    if actor["type"] == "business":
        return "business", int(actor["business_id"]), int(actor["user_id"])
    return "user", int(actor["user_id"]), int(actor["user_id"])


def _resolve_target_actor(conn, target_kind, target_id):
    """Xabar qabul qiluvchi aktyorni topadi: oddiy user yoki biznes."""
    kind = (target_kind or "user").strip().lower()
    try:
        aid = int(target_id)
    except Exception:
        raise HTTPException(400, "Qabul qiluvchi noto'g'ri.")

    if kind == "user":
        u = conn.execute("SELECT id, tg_id, name, role FROM users WHERE id=?", (aid,)).fetchone()
        if not u:
            raise HTTPException(404, "Qabul qiluvchi topilmadi.")
        return {
            "kind": "user",
            "actor_id": int(u["id"]),
            "owner_user_id": int(u["id"]),
            "tg_id": u["tg_id"],
            "name": u["name"] or "Foydalanuvchi",
            "role": "user",
        }

    if kind == "business":
        biz = conn.execute(
            """SELECT b.id, b.user_id, b.name, u.tg_id
               FROM businesses b JOIN users u ON u.id=b.user_id
               WHERE b.id=?""",
            (aid,),
        ).fetchone()
        if not biz:
            raise HTTPException(404, "Biznes topilmadi.")
        return {
            "kind": "business",
            "actor_id": int(biz["id"]),
            "owner_user_id": int(biz["user_id"]),
            "tg_id": biz["tg_id"],
            "name": biz["name"] or "Biznes",
            "role": "business",
        }

    raise HTTPException(400, "Qabul qiluvchi turi noto'g'ri.")


def _actor_brief(conn, kind, actor_id):
    """Chat ro'yxati uchun aktyor nomi: user bo'lsa user nomi, business bo'lsa biznes nomi."""
    return _resolve_target_actor(conn, kind, actor_id)


def _clean_message_reply_to_id(conn, my_kind, my_actor_id, other_kind, other_actor_id, value):
    """Umumiy chatda reply qilinayotgan xabar aynan shu ikki aktyor suhbatiga tegishlimi — tekshiradi."""
    try:
        mid = int(value or 0)
    except Exception:
        return None
    if mid <= 0:
        return None
    r = conn.execute(
        """SELECT id FROM messages
           WHERE id=? AND (
             (sender_kind=? AND sender_actor_id=? AND receiver_kind=? AND receiver_actor_id=?)
             OR
             (sender_kind=? AND sender_actor_id=? AND receiver_kind=? AND receiver_actor_id=?)
           )""",
        (mid, my_kind, my_actor_id, other_kind, other_actor_id,
         other_kind, other_actor_id, my_kind, my_actor_id),
    ).fetchone()
    if not r:
        raise HTTPException(400, "Javob berilayotgan xabar topilmadi.")
    return mid


def _message_preview_text(row):
    """Suhbatlar ro'yxatida oxirgi xabarni qisqa ko'rsatish."""
    if int(_row_val(row, "is_deleted", 0) or 0):
        return "Xabar o'chirildi"
    media_type = _row_val(row, "media_type", "text") or "text"
    text = (_row_val(row, "text", "") or "").strip()
    if media_type == "photo":
        return text if text else "📷 Rasm"
    return text


@router.post("/messages/send")
async def send_message(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    b = await request.json()
    text = (b.get("text") or "").strip()
    to_id = b.get("to") or b.get("target_id")
    to_kind = b.get("to_kind") or b.get("target_kind") or b.get("target_type") or "user"
    if not to_id or not text:
        conn.close()
        raise HTTPException(400, "Qabul qiluvchi va matn kiritilishi shart.")
    if len(text) > 2000:
        text = text[:2000]

    actor = actor_from_body(conn, me, b)
    sender_kind, sender_actor_id, sender_owner_id = _actor_identity(actor)
    receiver = _resolve_target_actor(conn, to_kind, to_id)

    # Faqat aynan bir aktyor o'ziga o'zi yozishi bloklanadi.
    # Masalan user -> o'z biznesi boshqa aktyor hisoblanadi va test uchun ruxsatli bo'lishi mumkin.
    if sender_kind == receiver["kind"] and sender_actor_id == receiver["actor_id"]:
        conn.close()
        raise HTTPException(400, "O'zingizga xabar yubora olmaysiz.")

    reply_to_id = _clean_message_reply_to_id(conn, sender_kind, sender_actor_id, receiver["kind"], receiver["actor_id"], b.get("reply_to_id"))
    now = int(time.time())
    cur = conn.execute(
        """INSERT INTO messages(sender_id, receiver_id, sender_kind, sender_actor_id,
                                  receiver_kind, receiver_actor_id, text, media_type, media_url,
                                  file_name, reply_to_id, is_read, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?)""",
        (sender_owner_id, receiver["owner_user_id"], sender_kind, sender_actor_id,
         receiver["kind"], receiver["actor_id"], text, "text", "", "", reply_to_id, now),
    )
    mid = cur.lastrowid
    conn.commit()

    # Telegram bildirishnomasi qabul qiluvchining egasi akkauntiga boradi.
    sender_name = _actor_brief(conn, sender_kind, sender_actor_id)["name"]
    receiver_tg = receiver["tg_id"]
    conn.close()
    if receiver_tg:
        try:
            from main import tg_call, BASE_URL
            await tg_call("sendMessage", {
                "chat_id": receiver_tg,
                "text": "💬 Sizga yangi xabar: " + sender_name + "\n\n" + (text[:200]),
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Ochish", "web_app": {"url": BASE_URL}}
                ]]},
            })
        except Exception:
            pass
    return {"ok": True, "id": mid, "created_at": now}


@router.post("/messages/image")
async def send_message_image(request: Request, to: int, to_kind: str = "user", actor_type: str = "user",
                             text: str = "", reply_to_id: int = 0,
                             x_telegram_init_data: str = Header(default="")):
    """Umumiy Suhbatlarim chatiga rasm yuborish. Rasm UPLOAD_DIR/chat papkasiga saqlanadi."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, me, actor_type)
    sender_kind, sender_actor_id, sender_owner_id = _actor_identity(actor)
    receiver = _resolve_target_actor(conn, to_kind, to)

    if sender_kind == receiver["kind"] and int(sender_actor_id) == int(receiver["actor_id"]):
        conn.close()
        raise HTTPException(400, "O'zingizga xabar yubora olmaysiz.")

    ctype = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    allowed = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/heic": ".heic",
        "image/heif": ".heif",
    }
    if ctype not in allowed:
        conn.close()
        raise HTTPException(400, "Faqat rasm fayli yuborish mumkin.")

    raw = await request.body()
    max_size = 8 * 1024 * 1024
    if not raw:
        conn.close()
        raise HTTPException(400, "Rasm fayli topilmadi.")
    if len(raw) > max_size:
        conn.close()
        raise HTTPException(400, "Rasm hajmi 8 MB dan oshmasin.")

    from main import UPLOAD_DIR
    folder = os.path.join(UPLOAD_DIR, "chat")
    os.makedirs(folder, exist_ok=True)
    ext = allowed[ctype]
    safe_name = "chat_" + str(sender_kind) + "_" + str(sender_actor_id) + "_" + str(int(time.time())) + "_" + secrets.token_hex(8) + ext
    path = os.path.join(folder, safe_name)
    with open(path, "wb") as f:
        f.write(raw)

    media_url = "/uploads/chat/" + safe_name
    caption = (text or "").strip()[:1000]
    clean_reply_to_id = _clean_message_reply_to_id(conn, sender_kind, sender_actor_id, receiver["kind"], receiver["actor_id"], reply_to_id)
    now = int(time.time())
    cur = conn.execute(
        """INSERT INTO messages(sender_id, receiver_id, sender_kind, sender_actor_id,
                                  receiver_kind, receiver_actor_id, text, media_type, media_url,
                                  file_name, reply_to_id, is_read, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?)""",
        (sender_owner_id, receiver["owner_user_id"], sender_kind, sender_actor_id,
         receiver["kind"], receiver["actor_id"], caption, "photo", media_url, safe_name, clean_reply_to_id, now),
    )
    mid = cur.lastrowid

    sender_name = _actor_brief(conn, sender_kind, sender_actor_id)["name"]
    receiver_tg = receiver["tg_id"]
    conn.commit()
    conn.close()

    if receiver_tg:
        try:
            from main import tg_call, BASE_URL
            msg = "📷 Sizga yangi rasm: " + sender_name
            if caption:
                msg += "\n\n" + caption[:300]
            await tg_call("sendMessage", {
                "chat_id": receiver_tg,
                "text": msg,
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Ochish", "web_app": {"url": BASE_URL}}
                ]]},
            })
        except Exception:
            pass
    return {"ok": True, "id": mid, "created_at": now, "media_url": media_url, "media_type": "photo"}


@router.get("/messages/with/{target_id}")
async def conversation_with(target_id: int, target_kind: str = "user", actor_type: str = "user",
                            x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, me, actor_type)
    my_kind, my_actor_id, _my_owner_id = _actor_identity(actor)
    other = _resolve_target_actor(conn, target_kind, target_id)

    rows = conn.execute(
        """SELECT * FROM messages
           WHERE (sender_kind=? AND sender_actor_id=? AND receiver_kind=? AND receiver_actor_id=?)
              OR (sender_kind=? AND sender_actor_id=? AND receiver_kind=? AND receiver_actor_id=?)
           ORDER BY created_at ASC, id ASC LIMIT 500""",
        (my_kind, my_actor_id, other["kind"], other["actor_id"],
         other["kind"], other["actor_id"], my_kind, my_actor_id),
    ).fetchall()

    # Shu kabinetga kelgan xabarlar o'qilgan deb belgilanadi.
    conn.execute(
        """UPDATE messages SET is_read=1
           WHERE receiver_kind=? AND receiver_actor_id=?
             AND sender_kind=? AND sender_actor_id=? AND is_read=0""",
        (my_kind, my_actor_id, other["kind"], other["actor_id"]),
    )
    conn.commit()

    row_by_id = {int(r["id"]): r for r in rows}

    def msg_reply_preview(reply_id):
        try:
            rid = int(reply_id or 0)
        except Exception:
            rid = 0
        rr = row_by_id.get(rid)
        if not rr:
            return None
        rs = _actor_brief(conn, rr["sender_kind"], rr["sender_actor_id"])
        return {
            "id": rr["id"],
            "text": rr["text"] or "",
            "media_type": _row_val(rr, "media_type", "text") or "text",
            "media_url": _row_val(rr, "media_url", "") or "",
            "is_deleted": bool(_row_val(rr, "is_deleted", 0) or 0),
            "sender_name": rs.get("name") or "",
        }

    msgs = []
    for r in rows:
        mine = (r["sender_kind"] == my_kind and int(r["sender_actor_id"]) == my_actor_id)
        sender = _actor_brief(conn, r["sender_kind"], r["sender_actor_id"])
        msgs.append({
            "id": r["id"],
            "text": r["text"] or "",
            "media_type": _row_val(r, "media_type", "text") or "text",
            "media_url": _row_val(r, "media_url", "") or "",
            "file_name": _row_val(r, "file_name", "") or "",
            "reply_to_id": _row_val(r, "reply_to_id", None),
            "reply": msg_reply_preview(_row_val(r, "reply_to_id", None)),
            "edited_at": int(_row_val(r, "edited_at", 0) or 0),
            "deleted_at": int(_row_val(r, "deleted_at", 0) or 0),
            "is_deleted": bool(_row_val(r, "is_deleted", 0) or 0),
            "mine": mine,
            "sender_name": sender.get("name") or "",
            "sender_kind": r["sender_kind"],
            "created_at": r["created_at"],
        })
    conn.close()
    return {"other": other, "messages": msgs}


@router.get("/messages/conversations")
async def conversations(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, me, actor_type)
    my_kind, my_actor_id, _my_owner_id = _actor_identity(actor)

    # Shu kabinetga tegishli suhbatlar ro'yxati — oddiy va biznes chatlari aralashmaydi.
    rows = conn.execute(
        """SELECT * FROM messages
           WHERE (sender_kind=? AND sender_actor_id=?) OR (receiver_kind=? AND receiver_actor_id=?)
           ORDER BY created_at DESC, id DESC""",
        (my_kind, my_actor_id, my_kind, my_actor_id),
    ).fetchall()

    seen = {}
    order = []
    for r in rows:
        sent_by_me = (r["sender_kind"] == my_kind and int(r["sender_actor_id"]) == my_actor_id)
        if sent_by_me:
            other_kind = r["receiver_kind"]
            other_id = int(r["receiver_actor_id"])
        else:
            other_kind = r["sender_kind"]
            other_id = int(r["sender_actor_id"])
        key = other_kind + ":" + str(other_id)
        if key not in seen:
            seen[key] = {"kind": other_kind, "id": other_id, "last": _message_preview_text(r), "created_at": r["created_at"], "unread": 0}
            order.append(key)
        if (r["receiver_kind"] == my_kind and int(r["receiver_actor_id"]) == my_actor_id and not r["is_read"]):
            seen[key]["unread"] += 1

    result = []
    for key in order:
        info = seen[key]
        brief = _actor_brief(conn, info["kind"], info["id"])
        result.append({
            "target_kind": info["kind"],
            "target_id": info["id"],
            "user_id": brief["owner_user_id"],  # eski frontendlar uchun moslik
            "name": brief["name"],
            "role": brief["role"],
            "last": info["last"],
            "created_at": info["created_at"],
            "unread": info["unread"],
        })
    conn.close()
    return result


@router.put("/messages/{message_id}")
async def edit_message(message_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    """Suhbatlarim bo'limidagi o'z matnli xabarini tahrirlash."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    b = await request.json()
    text = (b.get("text") or "").strip()
    if not text:
        conn.close()
        raise HTTPException(400, "Tahrirlash uchun matn kiriting.")
    if len(text) > 2000:
        text = text[:2000]

    actor = actor_from_body(conn, me, b)
    kind, actor_id, _owner_user_id = _actor_identity(actor)
    msg = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    if not msg:
        conn.close()
        raise HTTPException(404, "Xabar topilmadi.")
    if msg["sender_kind"] != kind or int(msg["sender_actor_id"]) != int(actor_id):
        conn.close()
        raise HTTPException(403, "Faqat o'zingiz yuborgan xabarni tahrirlashingiz mumkin.")
    if int(_row_val(msg, "is_deleted", 0) or 0):
        conn.close()
        raise HTTPException(400, "O'chirilgan xabarni tahrirlab bo'lmaydi.")
    if not (msg["text"] or "").strip():
        conn.close()
        raise HTTPException(400, "Bu xabarda tahrirlanadigan matn yo'q.")

    now = int(time.time())
    conn.execute("UPDATE messages SET text=?, edited_at=?, is_read=0 WHERE id=?", (text, now, message_id))
    conn.commit()
    conn.close()
    return {"ok": True, "id": message_id, "edited_at": now}


@router.delete("/messages/{message_id}")
async def delete_message(message_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    """Suhbatlarim bo'limidagi o'z xabarini xavfsiz o'chirish: o'rnida 'Xabar o'chirildi' qoladi."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    try:
        b = await request.json()
    except Exception:
        b = {}
    actor = actor_from_body(conn, me, b)
    kind, actor_id, _owner_user_id = _actor_identity(actor)
    msg = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    if not msg:
        conn.close()
        raise HTTPException(404, "Xabar topilmadi.")
    if msg["sender_kind"] != kind or int(msg["sender_actor_id"]) != int(actor_id):
        conn.close()
        raise HTTPException(403, "Faqat o'zingiz yuborgan xabarni o'chirishingiz mumkin.")
    if int(_row_val(msg, "is_deleted", 0) or 0):
        conn.close()
        return {"ok": True, "id": message_id, "already_deleted": True}

    now = int(time.time())
    conn.execute(
        "UPDATE messages SET is_deleted=1, deleted_at=?, text='', is_read=0 WHERE id=?",
        (now, message_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "id": message_id, "deleted_at": now}


@router.get("/messages/unread_count")
async def unread_count(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, me, actor_type)
    my_kind, my_actor_id, _my_owner_id = _actor_identity(actor)
    n = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE receiver_kind=? AND receiver_actor_id=? AND is_read=0",
        (my_kind, my_actor_id),
    ).fetchone()[0]
    conn.close()
    return {"count": n}



# ====================================================================
# BUYURTMALAR / NAVBATLAR
# ====================================================================
def _price_to_int(text):
    """Narx matnidan taxminiy so'm qiymatini oladi: '12 000 so'm' -> 12000."""
    raw = str(text or "")
    digits = re.sub(r"[^0-9]", "", raw)
    if not digits:
        return 0
    try:
        return int(digits[:12])
    except Exception:
        return 0


def _fmt_summa(n):
    try:
        n = int(n or 0)
    except Exception:
        n = 0
    if n <= 0:
        return ""
    return f"{n:,}".replace(",", " ") + " so'm"


def _clean_qty(v):
    """Miqdor: kasr ham bo'ladi (0.5 kg). Vergul ham qabul qilinadi ("0,5")."""
    try:
        q = float(str(v if v is not None else 1).replace(",", ".").strip() or 1)
    except Exception:
        q = 1.0
    if q != q or q <= 0:
        q = 1.0
    if q > 999:
        q = 999.0
    q = round(q, 3)
    return int(q) if float(q).is_integer() else q


def _clean_coord(v, minv, maxv):
    try:
        n = float(v)
    except Exception:
        return None
    if n < minv or n > maxv:
        return None
    return n


def _load_order_items_payload(conn, body, provider, item_id=None):
    """Frontend yuborgan items ro'yxatini tekshiradi va normal ko'rinishga keltiradi."""
    raw_items = body.get("items") if isinstance(body, dict) else None
    items = []
    if isinstance(raw_items, list):
        for x in raw_items[:50]:
            if not isinstance(x, dict):
                continue
            iid = x.get("item_id") or x.get("id")
            try:
                iid = int(iid)
            except Exception:
                continue
            q = _clean_qty(x.get("qty"))
            items.append({"item_id": iid, "qty": q})
    elif item_id:
        items.append({"item_id": int(item_id), "qty": _clean_qty(body.get("qty"))})

    if not items:
        return []
    if provider["kind"] != "business":
        raise HTTPException(400, "Mahsulot/xizmatli buyurtma faqat biznesga yuboriladi.")

    normalized = []
    seen = {}
    for x in items:
        iid = int(x["item_id"])
        seen[iid] = seen.get(iid, 0) + _clean_qty(x.get("qty"))
    for iid, qty in seen.items():
        it = conn.execute("SELECT * FROM items WHERE id=?", (iid,)).fetchone()
        if not it:
            raise HTTPException(404, "Mahsulot/xizmat topilmadi.")
        if int(it["business_id"]) != int(provider["actor_id"]):
            raise HTTPException(400, "Mahsulot/xizmat bu biznesga tegishli emas.")
        price_text = it["price"] or ""
        price_val = _price_to_int(price_text)
        unit = _row_val(it, "unit", "dona") or "dona"
        if unit not in FRACTIONAL_UNITS:
            # sanaladigan birlik (dona, quti...) — butun songa keltiramiz (0.5 -> yuqoriga)
            qty = max(1, int(math.floor(qty + 0.5)))
        normalized.append({
            "item_id": int(it["id"]),
            "item_name": it["name"] or "Mahsulot/xizmat",
            "price_text": price_text,
            "qty": qty,
            "unit": unit,
            "line_total": int(round(price_val * qty)) if price_val else 0,
            "note": it["note"] or "",
        })
    return normalized


def _order_title(conn, body, provider, item_id=None, listing_id=None, order_items=None):
    """Buyurtma kartasida ko'rinadigan nomni aniqlaydi."""
    title = (body.get("title") or "").strip() if isinstance(body, dict) else ""
    if title:
        return title[:180]
    order_items = order_items or []
    if order_items:
        first = order_items[0]["item_name"]
        if len(order_items) > 1:
            return (first + " + " + str(len(order_items)-1) + " ta")[:180]
        return first[:180]
    if item_id:
        it = conn.execute("SELECT name FROM items WHERE id=?", (item_id,)).fetchone()
        if it and it["name"]:
            return it["name"][:180]
    if listing_id:
        li = conn.execute("SELECT title FROM listings WHERE id=?", (listing_id,)).fetchone()
        if li and li["title"]:
            return li["title"][:180]
    if provider and provider.get("kind") == "business":
        return "Biznesga buyurtma"
    return "Qabul / xizmatga yozilish"


def _clean_order_type(value):
    v = (value or "delivery").strip().lower()
    aliases = {
        "1": "delivery", "yetkazish": "delivery", "yetkazib": "delivery", "delivery": "delivery",
        "2": "pickup", "olib": "pickup", "pickup": "pickup",
        "3": "booking", "navbat": "booking", "qabul": "booking", "booking": "booking", "service": "booking",
    }
    return aliases.get(v, "delivery")


def _order_items_to_dict(conn, order_id):
    rows = conn.execute(
        "SELECT * FROM order_items WHERE order_id=? ORDER BY id ASC", (order_id,)
    ).fetchall()
    return [{
        "id": r["id"],
        "item_id": r["item_id"],
        "name": r["item_name"],
        "price": r["price_text"] or "",
        "qty": r["qty"] or 1,
        "unit": _row_val(r, "unit", "") or "",
        "line_total": r["line_total"] or 0,
        "note": r["note"] or "",
    } for r in rows]


def _row_val(row, key, default=None):
    try:
        v = row[key]
        return default if v is None else v
    except Exception:
        return default


def _order_seen_value(r, view):
    if view == "provider":
        return int(_row_val(r, "provider_seen_at", 0) or 0)
    return int(_row_val(r, "customer_seen_at", 0) or 0)


def _add_notification(conn, user_id, actor_kind, actor_id, event_key, title, body="", order_id=None, ride_id=None, action_type=""):
    """Faqat amal/tasdiq talab qiladigan hodisani bir marta yozadi."""
    if not user_id or not actor_id or not event_key or not action_type:
        return
    conn.execute(
        """INSERT OR IGNORE INTO notifications
           (user_id,actor_kind,actor_id,event_key,title,body,order_id,ride_id,requires_action,action_type,is_read,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,0,?)""",
        (int(user_id), actor_kind, int(actor_id), str(event_key), title, body,
         order_id, ride_id, 1 if action_type else 0, action_type, int(time.time())),
    )
    notification = conn.execute(
        "SELECT id FROM notifications WHERE user_id=? AND actor_kind=? AND actor_id=? AND event_key=?",
        (int(user_id), actor_kind, int(actor_id), str(event_key)),
    ).fetchone()
    pref = conn.execute(
        "SELECT enabled,orders_enabled FROM push_preferences WHERE user_id=? AND actor_kind=? AND actor_id=?",
        (int(user_id), actor_kind, int(actor_id)),
    ).fetchone()
    if notification and (not pref or (pref["enabled"] and pref["orders_enabled"])):
        now = int(time.time())
        devices = conn.execute("SELECT id FROM push_devices WHERE user_id=? AND enabled=1", (int(user_id),)).fetchall()
        for device in devices:
            conn.execute(
                """INSERT OR IGNORE INTO push_outbox(notification_id,device_id,status,attempts,created_at)
                   VALUES(?,?,'pending',0,?)""", (notification["id"], device["id"], now))


def _notify_order_side(conn, order, side, event, title, body="", ride_id=None, action_type=""):
    if side == "customer":
        _add_notification(conn, order["customer_user_id"], order["customer_kind"],
                          order["customer_actor_id"], "order:%s:%s" % (order["id"], event),
                          title, body, order["id"], ride_id, action_type)
    else:
        _add_notification(conn, order["provider_user_id"], order["provider_kind"],
                          order["provider_actor_id"], "order:%s:%s" % (order["id"], event),
                          title, body, order["id"], ride_id, action_type)


def _resolve_order_action(conn, order_id, action_type):
    conn.execute("""UPDATE notifications SET resolved_at=?,is_read=1,read_at=?
        WHERE order_id=? AND action_type=? AND resolved_at=0""",
        (int(time.time()), int(time.time()), order_id, action_type))


@router.post("/push/devices")
async def register_push_device(request: Request, x_telegram_init_data: str = Header(default="")):
    """Mobil ilova FCM/APNs tokenini joriy akkauntga xavfsiz bog'laydi."""
    conn = db(); me = require_user(conn, x_telegram_init_data); body = await request.json()
    token = str(body.get("token") or "").strip()
    platform = str(body.get("platform") or "android").strip().lower()
    if len(token) < 20 or len(token) > 4096:
        conn.close(); raise HTTPException(400, "Qurilma tokeni noto'g'ri.")
    if platform not in ("android", "ios", "web"):
        conn.close(); raise HTTPException(400, "Qurilma platformasi noto'g'ri.")
    now = int(time.time())
    conn.execute("""INSERT INTO push_devices(user_id,token,platform,device_name,app_version,enabled,created_at,updated_at,last_seen_at)
        VALUES(?,?,?,?,?,1,?,?,?) ON CONFLICT(token) DO UPDATE SET user_id=excluded.user_id,
        platform=excluded.platform,device_name=excluded.device_name,app_version=excluded.app_version,
        enabled=1,updated_at=excluded.updated_at,last_seen_at=excluded.last_seen_at""",
        (me["id"], token, platform, str(body.get("device_name") or "")[:120],
         str(body.get("app_version") or "")[:40], now, now, now))
    conn.commit(); row = conn.execute("SELECT id FROM push_devices WHERE token=?", (token,)).fetchone(); conn.close()
    return {"ok": True, "device_id": row["id"]}


@router.delete("/push/devices")
async def unregister_push_device(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db(); me = require_user(conn, x_telegram_init_data); body = await request.json()
    token = str(body.get("token") or "").strip()
    conn.execute("UPDATE push_devices SET enabled=0,updated_at=? WHERE user_id=? AND token=?",
                 (int(time.time()), me["id"], token)); conn.commit(); conn.close()
    return {"ok": True}


@router.get("/push/preferences")
async def get_push_preferences(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    conn = db(); me = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, me, actor_type); kind, actor_id, _ = _actor_identity(actor)
    row = conn.execute("SELECT * FROM push_preferences WHERE user_id=? AND actor_kind=? AND actor_id=?",
                       (me["id"], kind, actor_id)).fetchone(); conn.close()
    return {"enabled": bool(row["enabled"]) if row else True,
            "orders_enabled": bool(row["orders_enabled"]) if row else True}


@router.put("/push/preferences")
async def set_push_preferences(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db(); me = require_user(conn, x_telegram_init_data); body = await request.json()
    actor = actor_from_body(conn, me, body); kind, actor_id, _ = _actor_identity(actor); now = int(time.time())
    enabled = 1 if body.get("enabled", True) else 0
    orders_enabled = 1 if body.get("orders_enabled", True) else 0
    conn.execute("""INSERT INTO push_preferences(user_id,actor_kind,actor_id,enabled,orders_enabled,updated_at)
        VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,actor_kind,actor_id) DO UPDATE SET
        enabled=excluded.enabled,orders_enabled=excluded.orders_enabled,updated_at=excluded.updated_at""",
        (me["id"], kind, actor_id, enabled, orders_enabled, now)); conn.commit(); conn.close()
    return {"ok": True, "enabled": bool(enabled), "orders_enabled": bool(orders_enabled)}


@router.get("/push/status")
async def push_status(x_telegram_init_data: str = Header(default="")):
    conn = db(); me = require_user(conn, x_telegram_init_data)
    devices = conn.execute("SELECT COUNT(*) FROM push_devices WHERE user_id=? AND enabled=1", (me["id"],)).fetchone()[0]
    pending = conn.execute("""SELECT COUNT(*) FROM push_outbox po JOIN push_devices pd ON pd.id=po.device_id
        WHERE pd.user_id=? AND po.status='pending'""", (me["id"],)).fetchone()[0]; conn.close()
    return {"provider": "firebase", "configured": bool(os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON") or os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")),
            "active_devices": devices, "pending": pending}
@router.get("/notifications")
async def list_notifications(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    conn = db(); me = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, me, actor_type); kind, actor_id, _ = _actor_identity(actor)
    rows = conn.execute(
        """SELECT * FROM notifications WHERE user_id=? AND actor_kind=? AND actor_id=? AND requires_action=1
           ORDER BY created_at DESC,id DESC LIMIT 200""", (me["id"], kind, actor_id)).fetchall()
    unread = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id=? AND actor_kind=? AND actor_id=? AND requires_action=1 AND resolved_at=0 AND is_read=0",
        (me["id"], kind, actor_id)).fetchone()[0]
    out = [dict(r) for r in rows]; conn.close()
    return {"items": out, "unread": unread}


@router.get("/notifications/actions")
async def actionable_notifications(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    """Bosh ekranda faqat hali amal bajarilmagan tasdiqlovchi xabarlar chiqadi."""
    conn = db(); me = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, me, actor_type); kind, actor_id, _ = _actor_identity(actor)
    rows = conn.execute(
        """SELECT * FROM notifications WHERE user_id=? AND actor_kind=? AND actor_id=?
           AND requires_action=1 AND resolved_at=0 AND is_read=0
           ORDER BY created_at ASC,id ASC LIMIT 20""",
        (me["id"], kind, actor_id)
    ).fetchall()
    out = [dict(r) for r in rows]; conn.close()
    return {"items": out, "count": len(out)}


@router.put("/notifications/{notification_id}/read")
async def read_notification(notification_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db(); me = require_user(conn, x_telegram_init_data); body = await request.json()
    actor = actor_from_body(conn, me, body); kind, actor_id, _ = _actor_identity(actor); now = int(time.time())
    cur = conn.execute("""UPDATE notifications SET is_read=1,read_at=?,
        resolved_at=CASE WHEN action_type='view_ready' THEN ? ELSE resolved_at END
        WHERE id=? AND user_id=? AND actor_kind=? AND actor_id=?""",
        (now, now, notification_id, me["id"], kind, actor_id))
    conn.commit(); conn.close()
    if not cur.rowcount: raise HTTPException(404, "Bildirishnoma topilmadi.")
    return {"ok": True, "read_at": now}


@router.put("/notifications/read-all/all")
async def read_all_notifications(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db(); me = require_user(conn, x_telegram_init_data); body = await request.json()
    actor = actor_from_body(conn, me, body); kind, actor_id, _ = _actor_identity(actor); now = int(time.time())
    conn.execute("""UPDATE notifications SET is_read=1,read_at=?
        WHERE user_id=? AND actor_kind=? AND actor_id=? AND is_read=0""", (now, me["id"], kind, actor_id))
    conn.commit(); conn.close(); return {"ok": True}


def _ensure_order_pay_column(conn):
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(orders)").fetchall()]
    if "payment_status" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT DEFAULT ''")


def _order_to_dict(conn, r, view="customer"):
    customer = _actor_brief(conn, r["customer_kind"], r["customer_actor_id"])
    provider = _actor_brief(conn, r["provider_kind"], r["provider_actor_id"])
    # Provayder biznes bo'lsa — to'lov ma'lumotini qo'shamiz (onlayn to'lov uchun)
    _pay_card = _pay_holder = _pay_qr = ""
    _provider_address = _provider_phone = _provider_hours = ""
    _provider_lat = _provider_lng = None
    if (r["provider_kind"] or "") == "business":
        _pb = conn.execute("SELECT * FROM businesses WHERE id=?", (r["provider_actor_id"],)).fetchone()
        if _pb:
            _pbk = _pb.keys()
            _pay_card = (_pb["pay_card"] if "pay_card" in _pbk else "") or ""
            _pay_holder = (_pb["pay_holder"] if "pay_holder" in _pbk else "") or ""
            _pay_qr = (_pb["pay_qr"] if "pay_qr" in _pbk else "") or ""
            _provider_address = _pb["address"] or ""
            _provider_phone = _pb["phone"] or ""
            _provider_hours = _pb["work_hours"] or ""
            _provider_lat, _provider_lng = _pb["lat"], _pb["lng"]
    items = _order_items_to_dict(conn, r["id"])
    total_amount = sum(int(x.get("line_total") or 0) for x in items)
    chat_count = conn.execute("SELECT COUNT(*) FROM order_messages WHERE order_id=?", (r["id"],)).fetchone()[0]
    last_chat = conn.execute("SELECT text, media_type, created_at FROM order_messages WHERE order_id=? AND COALESCE(is_deleted,0)=0 ORDER BY created_at DESC, id DESC LIMIT 1", (r["id"],)).fetchone()
    delivery = None
    if (r["order_type"] or "") == "delivery":
        rr = conn.execute(
            """SELECT rd.status AS ride_status,u.name AS driver_name,d.phone AS driver_phone,
                      d.car_model,d.car_color,d.car_plate
               FROM rides rd LEFT JOIN drivers d ON d.id=rd.driver_id
               LEFT JOIN users u ON u.id=d.user_id WHERE rd.src_order_id=? ORDER BY rd.id DESC LIMIT 1""",
            (r["id"],),
        ).fetchone()
        if rr:
            delivery = dict(rr)
    return {
        "id": r["id"],
        "customer_kind": r["customer_kind"],
        "customer_actor_id": r["customer_actor_id"],
        "provider_kind": r["provider_kind"],
        "provider_actor_id": r["provider_actor_id"],
        "customer_name": customer["name"],
        "provider_name": provider["name"],
        "item_id": r["item_id"],
        "listing_id": r["listing_id"],
        "title": r["title"] or "Buyurtma",
        "note": r["note"] or "",
        "phone": r["phone"] or "",
        "order_type": r["order_type"] or "delivery",
        "address": r["address"] or "",
        "desired_time": r["desired_time"] or "",
        "delivery_lat": r["delivery_lat"],
        "delivery_lng": r["delivery_lng"],
        "qty": r["qty"] or 1,
        "items": items,
        "total_amount": total_amount,
        "total_text": _fmt_summa(total_amount),
        "status": r["status"],
        "payment_status": _row_val(r, "payment_status", "") or "",
        "problem_open": bool(_row_val(r, "problem_open", 0) or 0),
        "problem_reason": _row_val(r, "problem_reason", "") or "",
        "problem_note": _row_val(r, "problem_note", "") or "",
        "problem_solution": _row_val(r, "problem_solution", "") or "",
        "problem_opened_at": int(_row_val(r, "problem_opened_at", 0) or 0),
        "problem_resolved_at": int(_row_val(r, "problem_resolved_at", 0) or 0),
        "seller_completed_at": int(_row_val(r, "seller_completed_at", 0) or 0),
        "customer_received_at": int(_row_val(r, "customer_received_at", 0) or 0),
        "pay_card": _pay_card, "pay_holder": _pay_holder, "pay_qr": _pay_qr,
        "provider_address": _provider_address, "provider_phone": _provider_phone,
        "provider_work_hours": _provider_hours,
        "provider_lat": _provider_lat, "provider_lng": _provider_lng,
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
        "provider_seen_at": _row_val(r, "provider_seen_at", 0),
        "customer_seen_at": _row_val(r, "customer_seen_at", 0),
        "is_unread": _order_seen_value(r, view) <= 0,
        "last_event": _row_val(r, "last_event", "") or "",
        "chat_count": chat_count,
        "last_chat": ((last_chat["text"] if last_chat and last_chat["text"] else "📷 Rasm") if last_chat else ""),
        "last_chat_at": (last_chat["created_at"] if last_chat else 0),
        "delivery": delivery,
        "view": view,
    }


@router.post("/orders")
async def create_order(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    b = await request.json()
    actor = actor_from_body(conn, me, b)
    customer_kind, customer_actor_id, customer_user_id = _actor_identity(actor)

    provider_kind = b.get("provider_kind") or b.get("target_kind") or "business"
    provider_id = b.get("provider_id") or b.get("target_id") or b.get("business_id") or b.get("user_id")
    if not provider_id:
        conn.close()
        raise HTTPException(400, "Buyurtma qabul qiluvchi topilmadi.")
    provider = _resolve_target_actor(conn, provider_kind, provider_id)

    # Faqat aynan bir aktyor o'ziga o'zi buyurtma berishi bloklanadi.
    if customer_kind == provider["kind"] and customer_actor_id == provider["actor_id"]:
        conn.close()
        raise HTTPException(400, "O'zingizga buyurtma bera olmaysiz.")

    item_id = b.get("item_id")
    listing_id = b.get("listing_id")
    try:
        item_id = int(item_id) if item_id else None
    except Exception:
        item_id = None
    try:
        listing_id = int(listing_id) if listing_id else None
    except Exception:
        listing_id = None

    # Mahsulot/xizmatlar ro'yxatini tekshiramiz.
    try:
        order_items = _load_order_items_payload(conn, b, provider, item_id)
    except HTTPException:
        conn.close()
        raise

    # Agar listing_id yuborilsa, providerga mosligini imkon qadar tekshiramiz.
    if listing_id:
        li = conn.execute("SELECT user_id, business_id FROM listings WHERE id=? AND status='active'", (listing_id,)).fetchone()
        if not li:
            conn.close()
            raise HTTPException(404, "E'lon topilmadi.")
        if provider["kind"] == "business" and li["business_id"] and int(li["business_id"]) != int(provider["actor_id"]):
            conn.close()
            raise HTTPException(400, "E'lon bu biznesga tegishli emas.")
        if provider["kind"] == "user" and int(li["user_id"]) != int(provider["actor_id"]):
            conn.close()
            raise HTTPException(400, "E'lon bu foydalanuvchiga tegishli emas.")

    note = (b.get("note") or "").strip()[:1000]
    phone = (b.get("phone") or "").strip()[:80]
    order_type = _clean_order_type(b.get("order_type"))
    address = (b.get("address") or "").strip()[:500]
    desired_time = (b.get("desired_time") or "").strip()[:160]
    delivery_lat = _clean_coord(b.get("delivery_lat"), -90, 90)
    delivery_lng = _clean_coord(b.get("delivery_lng"), -180, 180)
    qty = _clean_qty(b.get("qty"))
    if order_items:
        qty = round(sum(float(x["qty"] or 1) for x in order_items), 3)
        item_id = order_items[0]["item_id"] if len(order_items) == 1 else None

    title = _order_title(conn, b, provider, item_id, listing_id, order_items)
    now = int(time.time())
    cur = conn.execute(
        """INSERT INTO orders(customer_kind, customer_actor_id, customer_user_id,
                              provider_kind, provider_actor_id, provider_user_id,
                              item_id, listing_id, title, note, phone, order_type, address, desired_time,
                              delivery_lat, delivery_lng, qty, status, created_at, updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (customer_kind, customer_actor_id, customer_user_id,
         provider["kind"], provider["actor_id"], provider["owner_user_id"],
         item_id, listing_id, title, note, phone, order_type, address, desired_time,
         delivery_lat, delivery_lng, qty, "new", now, now),
    )
    oid = cur.lastrowid
    conn.execute("UPDATE orders SET customer_seen_at=?, provider_seen_at=0 WHERE id=?", (now, oid))
    created_order = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    _notify_order_side(conn, created_order, "provider", "created", "Yangi buyurtma keldi",
                       "Buyurtmani ko'rib, qabul qiling.", action_type="accept_order")
    for oi in order_items:
        conn.execute(
            """INSERT INTO order_items(order_id, item_id, item_name, price_text, qty, unit, line_total, note, created_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (oid, oi["item_id"], oi["item_name"], oi["price_text"], oi["qty"], oi.get("unit") or "", oi["line_total"], oi["note"], now),
        )
    conn.commit()

    customer_name = _actor_brief(conn, customer_kind, customer_actor_id)["name"]
    total_amount = sum(int(x.get("line_total") or 0) for x in order_items)
    total_text = _fmt_summa(total_amount)
    items_text = ""
    if order_items:
        items_text = "\n" + "\n".join(["• " + x["item_name"] + " × " + str(x["qty"]) for x in order_items[:8]])
    provider_tg = provider.get("tg_id")
    conn.close()

    if provider_tg:
        try:
            from main import tg_call, BASE_URL
            msg = "📥 Yangi buyurtma: " + customer_name + "\n\n" + title + items_text
            if total_text:
                msg += "\nJami: " + total_text
            detail_lines = []
            if order_type:
                detail_lines.append("Turi: " + ({"delivery":"Yetkazib berish", "pickup":"Olib ketish", "booking":"Navbat/qabul"}.get(order_type, order_type)))
            if phone:
                detail_lines.append("Telefon: " + phone)
            if address:
                detail_lines.append("Manzil: " + address[:160])
            if delivery_lat is not None and delivery_lng is not None:
                detail_lines.append("Xarita: " + str(round(delivery_lat, 6)) + ", " + str(round(delivery_lng, 6)))
            if desired_time:
                detail_lines.append("Vaqt: " + desired_time[:120])
            if detail_lines:
                msg += "\n" + "\n".join(detail_lines)
            if note:
                msg += "\n\nIzoh: " + note[:200]
            await tg_call("sendMessage", {
                "chat_id": provider_tg,
                "text": msg,
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Ochish", "web_app": {"url": BASE_URL}}
                ]]},
            })
        except Exception:
            pass
    return {"ok": True, "id": oid, "status": "new", "created_at": now}


@router.get("/orders/my")
async def my_orders(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    """Joriy kabinet nomidan berilgan buyurtmalar."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, me, actor_type)
    kind, actor_id, _owner = _actor_identity(actor)
    rows = conn.execute(
        """SELECT * FROM orders
           WHERE customer_kind=? AND customer_actor_id=?
           ORDER BY created_at DESC, id DESC LIMIT 200""",
        (kind, actor_id),
    ).fetchall()
    out = [_order_to_dict(conn, r, "customer") for r in rows]
    conn.close()
    return out


@router.get("/orders/inbox")
async def inbox_orders(actor_type: str = "business", x_telegram_init_data: str = Header(default="")):
    """Joriy kabinetga kelgan buyurtmalar."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    need_perm(conn, x_telegram_init_data, "buyurtma")
    actor = resolve_actor(conn, me, actor_type)
    kind, actor_id, _owner = _actor_identity(actor)
    rows = conn.execute(
        """SELECT * FROM orders
           WHERE provider_kind=? AND provider_actor_id=?
           ORDER BY created_at DESC, id DESC LIMIT 200""",
        (kind, actor_id),
    ).fetchall()
    out = [_order_to_dict(conn, r, "provider") for r in rows]
    conn.close()
    return out


@router.put("/orders/{order_id}/seen")
async def mark_order_seen(order_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    """Joriy kabinet buyurtmani ko'rdi deb belgilaydi."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    b = await request.json()
    actor = actor_from_body(conn, me, b)
    kind, actor_id, _owner = _actor_identity(actor)
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Buyurtma topilmadi.")

    is_provider = (row["provider_kind"] == kind and int(row["provider_actor_id"]) == actor_id)
    is_customer = (row["customer_kind"] == kind and int(row["customer_actor_id"]) == actor_id)
    if not (is_provider or is_customer):
        conn.close()
        raise HTTPException(403, "Bu buyurtma sizga tegishli emas.")

    now = int(time.time())
    if is_provider:
        conn.execute("UPDATE orders SET provider_seen_at=? WHERE id=?", (now, order_id))
    if is_customer:
        conn.execute("UPDATE orders SET customer_seen_at=? WHERE id=?", (now, order_id))
    conn.commit()
    conn.close()
    return {"ok": True, "seen_at": now}


def _auto_dostavka_for_order(conn, order_row):
    """#4: Yetkazib berish buyurtmasi 'Tayyor' bo'lganda do'kondan mijozgacha dostavka zakazi yaratadi.
    Faqat: order_type=delivery, mijoz manzili (delivery_lat/lng) bor, provayder=business, dublikatsiz."""
    try:
        otype = (order_row["order_type"] or "").strip().lower()
        if otype != "delivery":
            return None
        if (order_row["provider_kind"] or "") != "business":
            return None
        dlat = order_row["delivery_lat"]; dlng = order_row["delivery_lng"]
        if dlat is None or dlng is None:
            return None
        oid = order_row["id"]
        # Dublikat: shu buyurtma uchun faol dostavka zakazi bormi
        ex = conn.execute(
            "SELECT id FROM rides WHERE src_order_id=? AND status IN ('pending','accepted','arrived','ongoing') LIMIT 1",
            (oid,),
        ).fetchone()
        if ex:
            return ex["id"]
        # Do'kon (jo'natuvchi) ma'lumoti
        biz = conn.execute("SELECT id, user_id, name, address, lat, lng FROM businesses WHERE id=?",
                           (order_row["provider_actor_id"],)).fetchone()
        if not biz:
            return None
        from_lat = biz["lat"]; from_lng = biz["lng"]
        from_addr = biz["name"] or "Do'kon"
        if biz["address"]:
            from_addr += ", " + biz["address"]
        to_addr = order_row["address"] or "Mijoz manzili (xaritada)"
        dist = _haversine_km(from_lat, from_lng, dlat, dlng) if (from_lat is not None and from_lng is not None) else 0
        note = "Do'kon buyurtmasi #%d" % oid
        if order_row["title"]:
            note += " — " + (order_row["title"] or "")
        # Zakaz egasi = do'kon egasi (kuryerni chaqirayotgan tomon)
        requester = biz["user_id"]
        now = int(time.time())
        cur = conn.execute(
            "INSERT INTO rides(customer_id, kind, from_addr, to_addr, from_lat, from_lng, to_lat, to_lng, "
            "dist_km, dur_min, ozim, cargo, car_type, note, status, src_order_id, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?, ?)",
            (requester, "dostavka", from_addr, to_addr, from_lat, from_lng, dlat, dlng,
             dist, 0, 0, "", "", note, oid, now),
        )
        return cur.lastrowid
    except Exception:
        return None


@router.put("/orders/{order_id}/status")
async def update_order_status(order_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    b = await request.json()
    actor = actor_from_body(conn, me, b)
    kind, actor_id, _owner = _actor_identity(actor)
    new_status = (b.get("status") or "").strip().lower()
    allowed = {"accepted", "rejected", "done", "cancelled", "tayyor"}
    if new_status not in allowed:
        conn.close()
        raise HTTPException(400, "Buyurtma holati noto'g'ri.")

    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Buyurtma topilmadi.")

    if bool(_row_val(row, "problem_open", 0) or 0) and new_status in ("tayyor", "done"):
        conn.close()
        raise HTTPException(409, "Muammoli buyurtmani tayyorlash yoki yakunlash mumkin emas. Avval to'lov muammosini hal qiling.")
    if new_status in ("tayyor", "done") and (_row_val(row, "payment_status", "") or "") != "confirmed":
        conn.close()
        raise HTTPException(409, "To'lov tasdiqlanmaguncha buyurtmani tayyorlash yoki yakunlash mumkin emas.")
    if new_status == "tayyor" and row["status"] != "preparing":
        conn.close()
        raise HTTPException(409, "Buyurtma faqat Tayyorlanmoqda holatidan tayyor qilinadi.")
    if new_status == "done":
        conn.close()
        raise HTTPException(409, "Buyurtmani sotuvchi bu bosqichda yakunlay olmaydi. Topshirish va qabul tasdig'i kerak.")

    is_provider = (row["provider_kind"] == kind and int(row["provider_actor_id"]) == actor_id)
    is_customer = (row["customer_kind"] == kind and int(row["customer_actor_id"]) == actor_id)
    if new_status in ("accepted", "rejected", "done", "tayyor") and not is_provider:
        conn.close()
        raise HTTPException(403, "Bu buyurtma holatini faqat qabul qiluvchi kabinet o'zgartira oladi.")
    if new_status == "cancelled" and not (is_customer or is_provider):
        conn.close()
        raise HTTPException(403, "Bu buyurtma sizga tegishli emas.")

    now = int(time.time())
    notify_tg = None
    notify_text = ""

    if new_status in ("accepted", "rejected", "done", "tayyor") or (new_status == "cancelled" and is_provider):
        # Qabul qiluvchi/biznes statusni o'zgartirdi — mijoz tomonda yangilanish belgisi chiqadi.
        conn.execute(
            "UPDATE orders SET status=?, updated_at=?, customer_seen_at=0, provider_seen_at=?, last_event='status' WHERE id=?",
            (new_status, now, now, order_id),
        )
        if new_status == "accepted":
            conn.execute("UPDATE orders SET payment_status='pending' WHERE id=?", (order_id,))
            _notify_order_side(conn, row, "customer", "accepted", "Buyurtma qabul qilindi",
                               "To'lovni amalga oshirib, chekni yuboring.", action_type="make_payment")
        elif new_status == "tayyor":
            _notify_order_side(conn, row, "customer", "ready", "Buyurtma tayyor bo'ldi",
                               ("Do'kondan olib ketishingiz mumkin." if (row["order_type"] or "") == "pickup"
                                else "Dostavka jarayoni boshlandi."), action_type="view_ready")
        elif new_status in ("rejected", "cancelled"):
            _notify_order_side(conn, row, "customer", new_status, "Buyurtma bekor qilindi", row["title"] or "Buyurtma")
        cu = conn.execute("SELECT tg_id FROM users WHERE id=?", (row["customer_user_id"],)).fetchone()
        notify_tg = cu["tg_id"] if cu else None
        notify_text = "🔔 Buyurtma holati: " + {
            "accepted": "Qabul qilindi",
            "rejected": "Rad etildi",
            "done": "Yakunlandi",
            "cancelled": "Bekor qilindi",
            "tayyor": "Tayyor bo'ldi — yetkazish uchun kuryer qidirilmoqda",
        }.get(new_status, new_status) + "\n\n" + (row["title"] or "Buyurtma")
        if new_status == "tayyor" and (row["order_type"] or "") == "pickup":
            notify_text = "🔔 Buyurtmangiz tayyor. Do'kondan olib ketishingiz mumkin.\n\n" + (row["title"] or "Buyurtma")
    elif new_status == "cancelled" and is_customer:
        # Mijoz bekor qildi — biznes tomonda yangi o'zgarish sifatida ko'rinadi.
        conn.execute(
            "UPDATE orders SET status=?, updated_at=?, provider_seen_at=0, customer_seen_at=?, last_event='status' WHERE id=?",
            (new_status, now, now, order_id),
        )
        pu = conn.execute("SELECT tg_id FROM users WHERE id=?", (row["provider_user_id"],)).fetchone()
        notify_tg = pu["tg_id"] if pu else None
        notify_text = "⚠️ Mijoz buyurtmani bekor qildi\n\n" + (row["title"] or "Buyurtma")
        _notify_order_side(conn, row, "provider", "cancelled_by_customer", "Mijoz buyurtmani bekor qildi", row["title"] or "Buyurtma")
    else:
        conn.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?", (new_status, now, order_id))

    # v1407: Buyurtma "Bajarildi" — ombordan avtomatik chiqim (faqat bir marta)
    if new_status in ("accepted", "rejected", "cancelled"):
        _resolve_order_action(conn, order_id, "accept_order")
    if new_status == "done":
        _stock_deduct_for_order(conn, row, me["id"])
        _kassa_add_for_order(conn, row, me["id"])   # v1408: kassaga avtomatik savdo
    # v1412 (O5): bekor qilinsa — qoldiq qaytadi, kassadagi avto-savdo o'chadi
    if new_status == "cancelled":
        _stock_restore_for_order(conn, row, me["id"])

    # #4: "Tayyor bo'ldi" + yetkazib berish buyurtmasi -> avtomatik dostavka zakazi (dostavka haydovchilari ko'radi)
    if new_status == "tayyor":
        _auto_dostavka_for_order(conn, row)

    conn.commit()
    conn.close()

    if notify_tg:
        try:
            from main import tg_call, BASE_URL
            await tg_call("sendMessage", {
                "chat_id": notify_tg,
                "text": notify_text,
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Ilovada ko'rish", "web_app": {"url": BASE_URL}}
                ]]},
            })
        except Exception:
            pass

    return {"ok": True, "status": new_status, "updated_at": now}


def _order_actor_side(row, kind, actor_id):
    """Joriy aktyor buyurtmaning mijozimi yoki qabul qiluvchisimi — aniqlaydi."""
    if row["customer_kind"] == kind and int(row["customer_actor_id"]) == int(actor_id):
        return "customer"
    if row["provider_kind"] == kind and int(row["provider_actor_id"]) == int(actor_id):
        return "provider"
    return ""


def _order_other_side_info(conn, row, side):
    """Buyurtma chatidagi qarshi tomonni qaytaradi."""
    if side == "customer":
        brief = _actor_brief(conn, row["provider_kind"], row["provider_actor_id"])
        return {
            "side": "provider",
            "kind": row["provider_kind"],
            "actor_id": row["provider_actor_id"],
            "owner_user_id": row["provider_user_id"],
            "tg_id": brief.get("tg_id"),
            "name": brief.get("name") or "Qabul qiluvchi",
        }
    brief = _actor_brief(conn, row["customer_kind"], row["customer_actor_id"])
    return {
        "side": "customer",
        "kind": row["customer_kind"],
        "actor_id": row["customer_actor_id"],
        "owner_user_id": row["customer_user_id"],
        "tg_id": brief.get("tg_id"),
        "name": brief.get("name") or "Mijoz",
    }


def _mark_order_seen_for_side(conn, order_id, side, now=None):
    now = now or int(time.time())
    if side == "provider":
        conn.execute("UPDATE orders SET provider_seen_at=? WHERE id=?", (now, order_id))
    elif side == "customer":
        conn.execute("UPDATE orders SET customer_seen_at=? WHERE id=?", (now, order_id))
    return now


def _clean_order_reply_to_id(conn, order_id, value):
    """Reply qilinayotgan xabar shu buyurtmaga tegishli ekanini tekshiradi."""
    try:
        mid = int(value or 0)
    except Exception:
        return None
    if mid <= 0:
        return None
    r = conn.execute(
        "SELECT id FROM order_messages WHERE id=? AND order_id=?",
        (mid, order_id),
    ).fetchone()
    if not r:
        raise HTTPException(400, "Javob berilayotgan xabar topilmadi.")
    return mid


def _mark_order_changed_for_side(conn, order_id, side, now=None):
    """Chatdagi o'zgarishda yuborgan tomon ko'rdi, qarshi tomonda yangilanish belgisi chiqadi."""
    now = now or int(time.time())
    if side == "provider":
        conn.execute("UPDATE orders SET updated_at=?, provider_seen_at=?, customer_seen_at=0, last_event='msg' WHERE id=?", (now, now, order_id))
    else:
        conn.execute("UPDATE orders SET updated_at=?, customer_seen_at=?, provider_seen_at=0, last_event='msg' WHERE id=?", (now, now, order_id))
    return now


@router.post("/orders/{order_id}/problem")
async def open_order_problem(order_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    """Sotuvchi to'lov muammosini ochadi; dostavka va yakunlash bloklanadi."""
    conn = db(); user, biz = require_business(conn, x_telegram_init_data)
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row or row["provider_kind"] != "business" or int(row["provider_actor_id"]) != int(biz["id"]):
        conn.close(); raise HTTPException(404, "Buyurtma topilmadi.")
    if row["status"] in ("done", "cancelled", "rejected"):
        conn.close(); raise HTTPException(409, "Yakunlangan buyurtmada muammo ochib bo'lmaydi.")
    if (_row_val(row, "payment_status", "") or "") not in ("submitted", "recheck", "disputed"):
        conn.close(); raise HTTPException(409, "Avval buyurtmachi to'lov qilganini bildirishi kerak.")
    reasons = {
        "not_received": "Pul hisobga tushmadi",
        "amount_short": "To'langan summa kam",
        "receipt_mismatch": "Chek ma'lumoti mos kelmadi",
        "receipt_unreadable": "Chek rasmi o'qilmaydi",
        "wrong_receipt": "Noto'g'ri chek yuborilgan",
        "other": "Boshqa to'lov muammosi",
    }
    reason = str(body.get("reason") or "").strip()
    if reason not in reasons:
        conn.close(); raise HTTPException(400, "Muammo sababini tanlang.")
    note = str(body.get("note") or "").strip()[:1000]
    now = int(time.time())
    conn.execute(
        """UPDATE orders SET problem_open=1,problem_reason=?,problem_note=?,problem_solution='',
           problem_opened_at=?,problem_resolved_at=0,payment_status='disputed',updated_at=?,
           customer_seen_at=0,provider_seen_at=?,last_event='problem' WHERE id=?""",
        (reason, note, now, now, now, order_id),
    )
    conn.commit(); conn.close()
    return {"ok": True, "problem_open": True, "reason": reason, "reason_text": reasons[reason]}


@router.put("/orders/{order_id}/problem/solution")
async def choose_order_problem_solution(order_id: int, request: Request,
                                        x_telegram_init_data: str = Header(default="")):
    """Buyurtmachi: do'konga borish, kutish yoki yangi chek yuborishni tanlaydi."""
    conn = db(); me = require_user(conn, x_telegram_init_data); body = await request.json()
    actor = actor_from_body(conn, me, body); kind, actor_id, _ = _actor_identity(actor)
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row or row["customer_kind"] != kind or int(row["customer_actor_id"]) != int(actor_id):
        conn.close(); raise HTTPException(404, "Buyurtma topilmadi.")
    if not bool(_row_val(row, "problem_open", 0) or 0):
        conn.close(); raise HTTPException(409, "Bu buyurtmada ochiq muammo yo'q.")
    solution = str(body.get("solution") or "").strip()
    if solution not in ("pickup", "wait", "new_receipt"):
        conn.close(); raise HTTPException(400, "Yechimni tanlang.")
    now = int(time.time())
    payment_status = "recheck" if solution == "new_receipt" else "disputed"
    order_type = "pickup" if solution == "pickup" else row["order_type"]
    conn.execute(
        """UPDATE orders SET problem_solution=?,payment_status=?,order_type=?,updated_at=?,
           provider_seen_at=0,customer_seen_at=?,last_event='problem' WHERE id=?""",
        (solution, payment_status, order_type, now, now, order_id),
    )
    conn.commit(); conn.close()
    return {"ok": True, "solution": solution, "order_type": order_type, "payment_status": payment_status}


@router.post("/orders/{order_id}/payment/submit")
async def submit_order_payment(order_id: int, request: Request,
                               x_telegram_init_data: str = Header(default="")):
    """Buyurtmachi chek rasmini yuborgach, to'lovni tekshirishga topshiradi."""
    conn = db(); me = require_user(conn, x_telegram_init_data); body = await request.json()
    actor = actor_from_body(conn, me, body); kind, actor_id, _ = _actor_identity(actor)
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row or row["customer_kind"] != kind or int(row["customer_actor_id"]) != int(actor_id):
        conn.close(); raise HTTPException(404, "Buyurtma topilmadi.")
    if row["status"] != "accepted":
        conn.close(); raise HTTPException(409, "Buyurtma sotuvchi tomonidan qabul qilinmagan.")
    receipt = conn.execute(
        """SELECT id FROM order_messages WHERE order_id=? AND sender_kind=? AND sender_actor_id=?
           AND media_type='photo' AND COALESCE(is_deleted,0)=0 ORDER BY id DESC LIMIT 1""",
        (order_id, kind, actor_id),
    ).fetchone()
    if not receipt:
        conn.close(); raise HTTPException(400, "Avval to'lov cheki rasmini buyurtma chatiga yuboring.")
    now = int(time.time())
    conn.execute(
        """UPDATE orders SET payment_status='submitted',updated_at=?,provider_seen_at=0,
           customer_seen_at=?,last_event='payment' WHERE id=?""",
        (now, now, order_id),
    )
    _notify_order_side(conn, row, "provider", "payment_submitted", "To'lov qilindi",
                       "To'lov cheki yuborildi. To'lovni tekshirib tasdiqlang.", action_type="confirm_payment")
    _resolve_order_action(conn, order_id, "make_payment")
    conn.commit(); conn.close()
    return {"ok": True, "payment_status": "submitted", "receipt_message_id": receipt["id"]}


@router.post("/orders/{order_id}/payment")
async def set_order_payment(order_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    """Provayder biznes buyurtma to'lovini tasdiqlaydi yoki rad etadi. Suhbatga xabar yoziladi."""
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    _ensure_order_pay_column(conn)
    r = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Buyurtma topilmadi.")
    if (r["provider_kind"] or "") != "business" or int(r["provider_actor_id"] or 0) != int(biz["id"]):
        conn.close()
        raise HTTPException(403, "Bu buyurtma sizniki emas.")
    status = (body.get("status") or "").strip()
    if status not in ("confirmed", "rejected", "pending"):
        conn.close()
        raise HTTPException(400, "Holat noto'g'ri.")
    current_payment = _row_val(r, "payment_status", "") or ""
    if status == "confirmed" and current_payment not in ("submitted", "recheck", "disputed"):
        conn.close()
        raise HTTPException(409, "Buyurtmachi to'lov cheki va 'To'lov qildim' tasdig'ini yubormagan.")
    now = int(time.time())
    if status == "confirmed":
        conn.execute(
            """UPDATE orders SET payment_status=?,status='preparing',problem_open=0,problem_resolved_at=?,updated_at=?,
               customer_seen_at=0,last_event='payment' WHERE id=?""",
            (status, now, now, order_id),
        )
        _notify_order_side(conn, r, "customer", "payment_confirmed", "To'lov tasdiqlandi",
                           "Buyurtma tayyorlanmoqda.")
        _resolve_order_action(conn, order_id, "confirm_payment")
    else:
        conn.execute("UPDATE orders SET payment_status=?, updated_at=? WHERE id=?", (status, now, order_id))
    # Suhbatga tizim xabari
    msg = {"confirmed": "✅ To'lov tasdiqlandi. Rahmat!",
           "rejected": "❌ To'lov tasdiqlanmadi. Iltimos, to'lovni tekshiring yoki qayta yuboring.",
           "pending": "⏳ To'lov kutilmoqda."}.get(status, "")
    if msg:
        conn.execute(
            """INSERT INTO order_messages(order_id, sender_kind, sender_actor_id, sender_user_id,
                                          text, media_type, media_url, file_name, reply_to_id, created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (order_id, "business", biz["id"], user["id"], msg, "text", "", "", None, now),
        )
    conn.commit()
    conn.close()
    return {"ok": True, "payment_status": status, "status": ("preparing" if status == "confirmed" else r["status"])}


@router.post("/orders/{order_id}/handoff")
async def confirm_order_handoff(order_id: int, x_telegram_init_data: str = Header(default="")):
    """Sotuvchi buyurtmani dostavkachiga yoki olib ketayotgan mijozga topshirganini tasdiqlaydi."""
    conn = db(); user, biz = require_business(conn, x_telegram_init_data)
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row or row["provider_kind"] != "business" or int(row["provider_actor_id"]) != int(biz["id"]):
        conn.close(); raise HTTPException(404, "Buyurtma topilmadi.")
    now = int(time.time())
    if row["order_type"] == "delivery":
        ride = conn.execute("SELECT * FROM rides WHERE src_order_id=? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
        if not ride or ride["status"] != "pickup_requested":
            conn.close(); raise HTTPException(409, "Dostavkachi 'Dostavkani oldim' tugmasini hali bosmagan.")
        conn.execute("UPDATE rides SET status='in_delivery' WHERE id=?", (ride["id"],))
        new_status = "in_delivery"
    else:
        if row["status"] != "tayyor":
            conn.close(); raise HTTPException(409, "Buyurtma hali topshirishga tayyor emas.")
        new_status = "pickup_waiting_customer"
    conn.execute(
        "UPDATE orders SET status=?,seller_completed_at=?,updated_at=?,customer_seen_at=0,provider_seen_at=?,last_event='delivery' WHERE id=?",
        (new_status, now, now, now, order_id),
    )
    _notify_order_side(conn, row, "customer", "seller_handoff", "Buyurtma topshirildi",
                       "Buyurtma sizga yo'l oldi." if row["order_type"] == "delivery" else "Buyurtmani qabul qilganingizni tasdiqlang.",
                       action_type=("" if row["order_type"] == "delivery" else "confirm_received"))
    _resolve_order_action(conn, order_id, "confirm_handoff")
    _resolve_order_action(conn, order_id, "view_ready")
    _stock_deduct_for_order(conn, row, user["id"])
    _kassa_add_for_order(conn, row, user["id"])
    conn.commit(); conn.close()
    return {"ok": True, "status": new_status, "seller_completed_at": now}


@router.post("/orders/{order_id}/received")
async def confirm_order_received(order_id: int, request: Request,
                                 x_telegram_init_data: str = Header(default="")):
    """Buyurtmachi buyurtmani olganini tasdiqlaydi; shundan keyin hamma tomon yakunlanadi."""
    conn = db(); me = require_user(conn, x_telegram_init_data); body = await request.json()
    actor = actor_from_body(conn, me, body); kind, actor_id, _ = _actor_identity(actor)
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row or row["customer_kind"] != kind or int(row["customer_actor_id"]) != int(actor_id):
        conn.close(); raise HTTPException(404, "Buyurtma topilmadi.")
    allowed_status = "delivered_waiting_customer" if row["order_type"] == "delivery" else "pickup_waiting_customer"
    if row["status"] != allowed_status:
        conn.close(); raise HTTPException(409, "Buyurtmani qabul qilish bosqichi hali kelmagan.")
    now = int(time.time())
    if row["order_type"] == "delivery":
        ride = conn.execute("SELECT * FROM rides WHERE src_order_id=? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
        if not ride or ride["status"] != "delivered_waiting_customer":
            conn.close(); raise HTTPException(409, "Dostavkachi topshirishni hali tasdiqlamagan.")
        conn.execute("UPDATE rides SET status='completed' WHERE id=?", (ride["id"],))
        if ride["driver_id"]:
            conn.execute("UPDATE drivers SET available=1 WHERE id=?", (ride["driver_id"],))
    conn.execute(
        "UPDATE orders SET status='done',customer_received_at=?,updated_at=?,customer_seen_at=?,provider_seen_at=0,last_event='delivery' WHERE id=?",
        (now, now, now, order_id),
    )
    _notify_order_side(conn, row, "provider", "customer_received", "Buyurtma qabul qilindi",
                       "Buyurtmachi buyurtmani olganini tasdiqladi.")
    _resolve_order_action(conn, order_id, "confirm_received")
    conn.commit(); conn.close()
    return {"ok": True, "status": "done", "customer_received_at": now}


@router.get("/orders/{order_id}/chat")
async def order_chat_messages(order_id: int, actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    """Buyurtma ichidagi alohida chat xabarlari. Umumiy chatga aralashmaydi."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, me, actor_type)
    kind, actor_id, _owner = _actor_identity(actor)
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Buyurtma topilmadi.")
    side = _order_actor_side(row, kind, actor_id)
    if not side:
        conn.close()
        raise HTTPException(403, "Bu buyurtma sizga tegishli emas.")

    rows = conn.execute(
        "SELECT * FROM order_messages WHERE order_id=? ORDER BY created_at ASC, id ASC LIMIT 500",
        (order_id,),
    ).fetchall()
    now = _mark_order_seen_for_side(conn, order_id, side)
    conn.commit()

    row_by_id = {int(r["id"]): r for r in rows}

    def msg_reply_preview(reply_id):
        try:
            rid = int(reply_id or 0)
        except Exception:
            rid = 0
        rr = row_by_id.get(rid)
        if not rr:
            return None
        rs = _actor_brief(conn, rr["sender_kind"], rr["sender_actor_id"])
        return {
            "id": rr["id"],
            "text": rr["text"] or "",
            "media_type": _row_val(rr, "media_type", "text") or "text",
            "media_url": _row_val(rr, "media_url", "") or "",
            "is_deleted": bool(_row_val(rr, "is_deleted", 0) or 0),
            "sender_name": rs.get("name") or "",
        }

    msgs = []
    for r in rows:
        mine = (r["sender_kind"] == kind and int(r["sender_actor_id"]) == int(actor_id))
        sender = _actor_brief(conn, r["sender_kind"], r["sender_actor_id"])
        msgs.append({
            "id": r["id"],
            "text": r["text"] or "",
            "media_type": _row_val(r, "media_type", "text") or "text",
            "media_url": _row_val(r, "media_url", "") or "",
            "file_name": _row_val(r, "file_name", "") or "",
            "reply_to_id": _row_val(r, "reply_to_id", None),
            "reply": msg_reply_preview(_row_val(r, "reply_to_id", None)),
            "edited_at": int(_row_val(r, "edited_at", 0) or 0),
            "deleted_at": int(_row_val(r, "deleted_at", 0) or 0),
            "is_deleted": bool(_row_val(r, "is_deleted", 0) or 0),
            "mine": mine,
            "sender_name": sender.get("name") or "",
            "sender_kind": r["sender_kind"],
            "created_at": r["created_at"],
        })
    other = _order_other_side_info(conn, row, side)
    order = _order_to_dict(conn, row, "provider" if side == "provider" else "customer")
    conn.close()
    return {"ok": True, "side": side, "seen_at": now, "other": other, "order": order, "messages": msgs}


@router.post("/orders/{order_id}/chat")
async def send_order_chat_message(order_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    """Buyurtma ichida xabar yuborish. Xabar faqat shu buyurtmaga bog'lanadi."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    b = await request.json()
    text = (b.get("text") or "").strip()
    if not text:
        conn.close()
        raise HTTPException(400, "Xabar matni kiritilishi shart.")
    if len(text) > 2000:
        text = text[:2000]

    actor = actor_from_body(conn, me, b)
    kind, actor_id, owner_user_id = _actor_identity(actor)
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Buyurtma topilmadi.")
    side = _order_actor_side(row, kind, actor_id)
    if not side:
        conn.close()
        raise HTTPException(403, "Bu buyurtma sizga tegishli emas.")

    reply_to_id = _clean_order_reply_to_id(conn, order_id, b.get("reply_to_id"))
    now = int(time.time())
    cur = conn.execute(
        """INSERT INTO order_messages(order_id, sender_kind, sender_actor_id, sender_user_id,
                                      text, media_type, media_url, file_name, reply_to_id, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (order_id, kind, actor_id, owner_user_id, text, "text", "", "", reply_to_id, now),
    )
    mid = cur.lastrowid
    _mark_order_changed_for_side(conn, order_id, side, now)

    sender_name = _actor_brief(conn, kind, actor_id)["name"]
    other = _order_other_side_info(conn, row, side)
    notify_tg = other.get("tg_id")
    order_title = row["title"] or "Buyurtma"
    conn.commit()
    conn.close()

    if notify_tg:
        try:
            from main import tg_call, BASE_URL
            await tg_call("sendMessage", {
                "chat_id": notify_tg,
                "text": "💬 Buyurtma bo'yicha yangi xabar: " + sender_name + "\n\n" + order_title + "\n" + text[:300],
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Ilovada ko'rish", "web_app": {"url": BASE_URL}}
                ]]},
            })
        except Exception:
            pass
    return {"ok": True, "id": mid, "created_at": now}


@router.post("/orders/{order_id}/chat/image")
async def send_order_chat_image(order_id: int, request: Request, actor_type: str = "user",
                                text: str = "", reply_to_id: int = 0,
                                x_telegram_init_data: str = Header(default="")):
    """Buyurtma chatiga rasm yuborish. Rasm UPLOAD_DIR/order_chat papkasiga saqlanadi."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, me, actor_type)
    kind, actor_id, owner_user_id = _actor_identity(actor)
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Buyurtma topilmadi.")
    side = _order_actor_side(row, kind, actor_id)
    if not side:
        conn.close()
        raise HTTPException(403, "Bu buyurtma sizga tegishli emas.")

    ctype = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    allowed = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/heic": ".heic",
        "image/heif": ".heif",
    }
    if ctype not in allowed:
        conn.close()
        raise HTTPException(400, "Faqat rasm fayli yuborish mumkin.")

    raw = await request.body()
    max_size = 8 * 1024 * 1024
    if not raw:
        conn.close()
        raise HTTPException(400, "Rasm fayli topilmadi.")
    if len(raw) > max_size:
        conn.close()
        raise HTTPException(400, "Rasm hajmi 8 MB dan oshmasin.")

    from main import UPLOAD_DIR
    folder = os.path.join(UPLOAD_DIR, "order_chat")
    os.makedirs(folder, exist_ok=True)
    ext = allowed[ctype]
    safe_name = "order_" + str(order_id) + "_" + str(int(time.time())) + "_" + secrets.token_hex(8) + ext
    path = os.path.join(folder, safe_name)
    with open(path, "wb") as f:
        f.write(raw)

    media_url = "/uploads/order_chat/" + safe_name
    caption = (text or "").strip()[:1000]
    reply_to_id = _clean_order_reply_to_id(conn, order_id, reply_to_id)
    now = int(time.time())
    cur = conn.execute(
        """INSERT INTO order_messages(order_id, sender_kind, sender_actor_id, sender_user_id,
                                      text, media_type, media_url, file_name, reply_to_id, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (order_id, kind, actor_id, owner_user_id, caption, "photo", media_url, safe_name, reply_to_id, now),
    )
    mid = cur.lastrowid

    _mark_order_changed_for_side(conn, order_id, side, now)

    sender_name = _actor_brief(conn, kind, actor_id)["name"]
    other = _order_other_side_info(conn, row, side)
    notify_tg = other.get("tg_id")
    order_title = row["title"] or "Buyurtma"
    conn.commit()
    conn.close()

    if notify_tg:
        try:
            from main import tg_call, BASE_URL
            msg = "📷 Buyurtma bo'yicha yangi rasm: " + sender_name + "\n\n" + order_title
            if caption:
                msg += "\n" + caption[:300]
            await tg_call("sendMessage", {
                "chat_id": notify_tg,
                "text": msg,
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Ilovada ko'rish", "web_app": {"url": BASE_URL}}
                ]]},
            })
        except Exception:
            pass
    return {"ok": True, "id": mid, "created_at": now, "media_url": media_url, "media_type": "photo"}


@router.put("/orders/{order_id}/chat/{message_id}")
async def edit_order_chat_message(order_id: int, message_id: int, request: Request,
                                  x_telegram_init_data: str = Header(default="")):
    """Buyurtma chatidagi o'z xabarini tahrirlash."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    b = await request.json()
    text = (b.get("text") or "").strip()
    if not text:
        conn.close()
        raise HTTPException(400, "Tahrirlash uchun matn kiriting.")
    if len(text) > 2000:
        text = text[:2000]

    actor = actor_from_body(conn, me, b)
    kind, actor_id, _owner_user_id = _actor_identity(actor)
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Buyurtma topilmadi.")
    side = _order_actor_side(row, kind, actor_id)
    if not side:
        conn.close()
        raise HTTPException(403, "Bu buyurtma sizga tegishli emas.")

    msg = conn.execute(
        "SELECT * FROM order_messages WHERE id=? AND order_id=?",
        (message_id, order_id),
    ).fetchone()
    if not msg:
        conn.close()
        raise HTTPException(404, "Xabar topilmadi.")
    if msg["sender_kind"] != kind or int(msg["sender_actor_id"]) != int(actor_id):
        conn.close()
        raise HTTPException(403, "Faqat o'zingiz yuborgan xabarni tahrirlashingiz mumkin.")
    if int(_row_val(msg, "is_deleted", 0) or 0):
        conn.close()
        raise HTTPException(400, "O'chirilgan xabarni tahrirlab bo'lmaydi.")
    if not (msg["text"] or "").strip():
        conn.close()
        raise HTTPException(400, "Bu xabarda tahrirlanadigan matn yo'q.")

    now = int(time.time())
    conn.execute("UPDATE order_messages SET text=?, edited_at=? WHERE id=?", (text, now, message_id))
    _mark_order_changed_for_side(conn, order_id, side, now)
    conn.commit()
    conn.close()
    return {"ok": True, "id": message_id, "edited_at": now}


@router.delete("/orders/{order_id}/chat/{message_id}")
async def delete_order_chat_message(order_id: int, message_id: int, request: Request,
                                    x_telegram_init_data: str = Header(default="")):
    """Buyurtma chatidagi o'z xabarini xavfsiz o'chirish: xabar o'rnida 'Xabar o'chirildi' qoladi."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    try:
        b = await request.json()
    except Exception:
        b = {}
    actor = actor_from_body(conn, me, b)
    kind, actor_id, _owner_user_id = _actor_identity(actor)
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Buyurtma topilmadi.")
    side = _order_actor_side(row, kind, actor_id)
    if not side:
        conn.close()
        raise HTTPException(403, "Bu buyurtma sizga tegishli emas.")

    msg = conn.execute(
        "SELECT * FROM order_messages WHERE id=? AND order_id=?",
        (message_id, order_id),
    ).fetchone()
    if not msg:
        conn.close()
        raise HTTPException(404, "Xabar topilmadi.")
    if msg["sender_kind"] != kind or int(msg["sender_actor_id"]) != int(actor_id):
        conn.close()
        raise HTTPException(403, "Faqat o'zingiz yuborgan xabarni o'chirishingiz mumkin.")
    if int(_row_val(msg, "is_deleted", 0) or 0):
        conn.close()
        return {"ok": True, "id": message_id, "already_deleted": True}

    now = int(time.time())
    conn.execute(
        "UPDATE order_messages SET is_deleted=1, deleted_at=?, text='' WHERE id=?",
        (now, message_id),
    )
    _mark_order_changed_for_side(conn, order_id, side, now)
    conn.commit()
    conn.close()
    return {"ok": True, "id": message_id, "deleted_at": now}


# ====================================================================
# BILDIRISHNOMA FILTRLARI
# ====================================================================
@router.get("/notify/filters")
async def get_notify_filters(x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    rows = conn.execute(
        "SELECT * FROM notify_filters WHERE user_id=? ORDER BY id DESC", (me["id"],)
    ).fetchall()
    out = [{"id": r["id"], "cat": r["cat"], "region": r["region"], "district": r["district"],
            "price_min": r["price_min"], "price_max": r["price_max"], "keyword": r["keyword"]} for r in rows]
    conn.close()
    return out


@router.post("/notify/filters")
async def add_notify_filter(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    b = await request.json()
    cat = (b.get("cat") or "").strip()
    if not cat:
        conn.close()
        raise HTTPException(400, "Tur tanlanishi shart.")
    def _int(v):
        try:
            return int(v)
        except Exception:
            return 0
    cur = conn.execute(
        """INSERT INTO notify_filters(user_id, cat, region, district, price_min, price_max, keyword, created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (me["id"], cat, (b.get("region") or "").strip(), (b.get("district") or "").strip(),
         _int(b.get("price_min")), _int(b.get("price_max")), (b.get("keyword") or "").strip(),
         int(time.time())),
    )
    fid = cur.lastrowid
    conn.commit()
    conn.close()
    return {"ok": True, "id": fid}


@router.delete("/notify/filters/{filter_id}")
async def delete_notify_filter(filter_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    conn.execute("DELETE FROM notify_filters WHERE id=? AND user_id=?", (filter_id, me["id"]))
    conn.commit()
    conn.close()
    return {"ok": True}

# ================== BAHOLASH VA FIKRLAR (#1) ==================
_REVIEW_KINDS = ("business", "specialist")


def _ensure_reviews(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS reviews("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, target_kind TEXT NOT NULL, target_id INTEGER NOT NULL, "
        "reviewer_user_id INTEGER NOT NULL, order_id INTEGER, stars INTEGER NOT NULL, "
        "comment TEXT DEFAULT '', owner_reply TEXT DEFAULT '', owner_replied_at INTEGER DEFAULT 0, "
        "created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)")
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(reviews)").fetchall()]
        if "owner_reply" not in cols:
            conn.execute("ALTER TABLE reviews ADD COLUMN owner_reply TEXT DEFAULT ''")
        if "owner_replied_at" not in cols:
            conn.execute("ALTER TABLE reviews ADD COLUMN owner_replied_at INTEGER DEFAULT 0")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_review_one ON reviews(target_kind, target_id, reviewer_user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_target ON reviews(target_kind, target_id)")
    except Exception:
        pass


def _review_target_ok(conn, kind, tid):
    """Baholanadigan obyekt bor-yo'qligini tekshiradi."""
    if kind == "business":
        return conn.execute("SELECT id FROM businesses WHERE id=? AND status='active'", (tid,)).fetchone() is not None
    if kind == "specialist":
        return conn.execute("SELECT user_id FROM specialists WHERE user_id=?", (tid,)).fetchone() is not None
    return False


def _review_eligible_order(conn, user_id, kind, tid):
    """Foydalanuvchi shu obyektдan buyurtma/xarid qilganmi? Buyurtma id qaytaradi yoki None."""
    if kind == "business":
        row = conn.execute(
            "SELECT id FROM orders WHERE customer_user_id=? AND provider_kind='business' AND provider_actor_id=? "
            "AND COALESCE(status,'') NOT IN ('bekor','rad','cancelled') ORDER BY id DESC LIMIT 1",
            (user_id, tid),
        ).fetchone()
    elif kind == "specialist":
        row = conn.execute(
            "SELECT id FROM orders WHERE customer_user_id=? AND provider_kind='user' AND provider_actor_id=? "
            "AND COALESCE(status,'') NOT IN ('bekor','rad','cancelled') ORDER BY id DESC LIMIT 1",
            (user_id, tid),
        ).fetchone()
    else:
        return None
    return row["id"] if row else None


def _recompute_rating(conn, kind, tid):
    """reviews jadvalidan reyting yig'indisi va sonini qайta hisoblab, obyektга yozadi."""
    agg = conn.execute(
        "SELECT COALESCE(SUM(stars),0) AS s, COUNT(*) AS c FROM reviews WHERE target_kind=? AND target_id=?",
        (kind, tid),
    ).fetchone()
    ssum, scnt = int(agg["s"] or 0), int(agg["c"] or 0)
    if kind == "business":
        conn.execute("UPDATE businesses SET rating_sum=?, rating_cnt=? WHERE id=?", (ssum, scnt, tid))
    elif kind == "specialist":
        conn.execute("UPDATE specialists SET rating_sum=?, rating_cnt=? WHERE user_id=?", (ssum, scnt, tid))
    return ssum, scnt


def _reviewer_name(conn, uid):
    u = conn.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
    return (u["name"] if u and u["name"] else "Foydalanuvchi")


@router.get("/reviews")
async def reviews_list(target_kind: str = "", target_id: int = 0, x_telegram_init_data: str = Header(default="")):
    """Obyekt uchun fikrlar + o'rtacha reyting + joriy foydalanuvchi holati."""
    conn = db()
    kind = (target_kind or "").strip().lower()
    if kind not in _REVIEW_KINDS or not target_id:
        conn.close()
        raise HTTPException(400, "Noto'g'ri obyekt.")
    _ensure_reviews(conn)
    rows = conn.execute(
        "SELECT * FROM reviews WHERE target_kind=? AND target_id=? ORDER BY id DESC LIMIT 100",
        (kind, target_id),
    ).fetchall()
    items = [{
        "id": r["id"], "stars": r["stars"], "comment": r["comment"] or "",
        "user_name": _reviewer_name(conn, r["reviewer_user_id"]),
        "reviewer_user_id": r["reviewer_user_id"], "created_at": r["created_at"],
        "owner_reply": (r["owner_reply"] or "") if "owner_reply" in r.keys() else "",
        "owner_replied_at": (r["owner_replied_at"] or 0) if "owner_replied_at" in r.keys() else 0,
    } for r in rows]
    ssum = sum(r["stars"] for r in rows)
    scnt = len(rows)
    avg = round(ssum / scnt, 1) if scnt else 0

    me = optional_user(conn, x_telegram_init_data)
    can_review = False
    my_review = None
    if me:
        for it in items:
            if it["reviewer_user_id"] == me["id"]:
                my_review = {"stars": it["stars"], "comment": it["comment"]}
                break
        if _review_target_ok(conn, kind, target_id):
            can_review = _review_eligible_order(conn, me["id"], kind, target_id) is not None
    conn.close()
    return {"reviews": items, "avg": avg, "count": scnt, "can_review": can_review, "my_review": my_review}


@router.post("/reviews")
async def review_save(body: dict, x_telegram_init_data: str = Header(default="")):
    """Baho qoldirish yoki yangilash (faqat shu obyektдан buyurtma qilganlar)."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    _ensure_reviews(conn)
    kind = (body.get("target_kind") or "").strip().lower()
    try:
        tid = int(body.get("target_id") or 0)
    except Exception:
        tid = 0
    if kind not in _REVIEW_KINDS or not tid:
        conn.close()
        raise HTTPException(400, "Noto'g'ri obyekt.")
    if not _review_target_ok(conn, kind, tid):
        conn.close()
        raise HTTPException(404, "Obyekt topilmadi.")
    try:
        stars = int(body.get("stars") or 0)
    except Exception:
        stars = 0
    if stars < 1 or stars > 5:
        conn.close()
        raise HTTPException(400, "Yulduzlar 1 dan 5 gacha bo'lsin.")
    comment = (body.get("comment") or "").strip()[:1000]
    # O'ziga baho bermasin
    if kind == "specialist" and tid == me["id"]:
        conn.close()
        raise HTTPException(400, "O'zingizga baho bera olmaysiz.")
    if kind == "business":
        own = conn.execute("SELECT id FROM businesses WHERE user_id=?", (me["id"],)).fetchone()
        if own and own["id"] == tid:
            conn.close()
            raise HTTPException(400, "O'z do'koningizga baho bera olmaysiz.")
    # Eligibility: buyurtma bo'lishi shart
    oid = _review_eligible_order(conn, me["id"], kind, tid)
    if not oid:
        conn.close()
        raise HTTPException(403, "Faqat shu yerdan buyurtma/xarid qilganlar baho bera oladi.")
    now = int(time.time())
    ex = conn.execute(
        "SELECT id FROM reviews WHERE target_kind=? AND target_id=? AND reviewer_user_id=?",
        (kind, tid, me["id"]),
    ).fetchone()
    if ex:
        conn.execute("UPDATE reviews SET stars=?, comment=?, order_id=?, updated_at=? WHERE id=?",
                     (stars, comment, oid, now, ex["id"]))
    else:
        conn.execute(
            "INSERT INTO reviews(target_kind, target_id, reviewer_user_id, order_id, stars, comment, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (kind, tid, me["id"], oid, stars, comment, now, now),
        )
    ssum, scnt = _recompute_rating(conn, kind, tid)
    conn.commit()
    conn.close()
    avg = round(ssum / scnt, 1) if scnt else 0
    return {"ok": True, "avg": avg, "count": scnt}


@router.get("/specialist/reviews")
async def specialist_reviews_manage(x_telegram_init_data: str = Header(default="")):
    """Mutaxassisning o'ziga yozilgan fikrlar. Mutaxassis faqat javob beradi, fikrni o'chira olmaydi."""
    conn = db(); me = require_user(conn, x_telegram_init_data); _ensure_reviews(conn)
    rows = conn.execute(
        "SELECT * FROM reviews WHERE target_kind='specialist' AND target_id=? ORDER BY id DESC LIMIT 200",
        (me["id"],),
    ).fetchall()
    items = [{
        "id": r["id"], "stars": r["stars"], "comment": r["comment"] or "",
        "user_name": _reviewer_name(conn, r["reviewer_user_id"]),
        "created_at": r["created_at"],
        "owner_reply": (r["owner_reply"] or "") if "owner_reply" in r.keys() else "",
        "owner_replied_at": (r["owner_replied_at"] or 0) if "owner_replied_at" in r.keys() else 0,
    } for r in rows]
    conn.close(); return {"reviews": items, "count": len(items)}


@router.get("/business/reviews")
async def business_reviews_manage(x_telegram_init_data: str = Header(default="")):
    """Biznes egasiga o'z do'koniga yozilgan baho va fikrlarni qaytaradi."""
    conn = db(); me, biz = require_business(conn, x_telegram_init_data); _ensure_reviews(conn)
    rows = conn.execute(
        "SELECT * FROM reviews WHERE target_kind='business' AND target_id=? ORDER BY id DESC LIMIT 200",
        (biz["id"],),
    ).fetchall()
    items = [{
        "id": r["id"], "stars": r["stars"], "comment": r["comment"] or "",
        "user_name": _reviewer_name(conn, r["reviewer_user_id"]),
        "created_at": r["created_at"],
        "owner_reply": (r["owner_reply"] or "") if "owner_reply" in r.keys() else "",
        "owner_replied_at": (r["owner_replied_at"] or 0) if "owner_replied_at" in r.keys() else 0,
    } for r in rows]
    total = sum(int(r["stars"] or 0) for r in rows)
    count = len(items)
    conn.close()
    return {"reviews": items, "count": count, "avg": round(total / count, 1) if count else 0}


@router.put("/business/reviews/{review_id}/reply")
async def business_review_reply(review_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    """Biznes egasi fikrni o'chirmasdan unga javob beradi yoki javobini yangilaydi."""
    conn = db(); me, biz = require_business(conn, x_telegram_init_data); _ensure_reviews(conn)
    row = conn.execute(
        "SELECT id FROM reviews WHERE id=? AND target_kind='business' AND target_id=?",
        (review_id, biz["id"]),
    ).fetchone()
    if not row:
        conn.close(); raise HTTPException(404, "Fikr topilmadi.")
    reply = (body.get("reply") or "").strip()[:1500]
    if not reply:
        conn.close(); raise HTTPException(400, "Javob matnini kiriting.")
    conn.execute("UPDATE reviews SET owner_reply=?, owner_replied_at=? WHERE id=?",
                 (reply, int(time.time()), review_id))
    conn.commit(); conn.close(); return {"ok": True}


@router.put("/specialist/reviews/{review_id}/reply")
async def specialist_review_reply(review_id: int, body: dict, x_telegram_init_data: str = Header(default="")):
    """Mutaxassis mijoz fikriga javob beradi yoki javobini tahrirlaydi. Fikr o'chirilmaydi."""
    conn = db(); me = require_user(conn, x_telegram_init_data); _ensure_reviews(conn)
    row = conn.execute(
        "SELECT id FROM reviews WHERE id=? AND target_kind='specialist' AND target_id=?",
        (review_id, me["id"]),
    ).fetchone()
    if not row:
        conn.close(); raise HTTPException(404, "Fikr topilmadi.")
    reply = (body.get("reply") or "").strip()[:1500]
    if not reply:
        conn.close(); raise HTTPException(400, "Javob matnini kiriting.")
    conn.execute("UPDATE reviews SET owner_reply=?, owner_replied_at=? WHERE id=?",
                 (reply, int(time.time()), review_id))
    conn.commit(); conn.close(); return {"ok": True}


@router.delete("/reviews")
async def review_delete(target_kind: str = "", target_id: int = 0, x_telegram_init_data: str = Header(default="")):
    """O'z bahoni o'chirish."""
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    _ensure_reviews(conn)
    kind = (target_kind or "").strip().lower()
    if kind not in _REVIEW_KINDS or not target_id:
        conn.close()
        raise HTTPException(400, "Noto'g'ri obyekt.")
    conn.execute("DELETE FROM reviews WHERE target_kind=? AND target_id=? AND reviewer_user_id=?",
                 (kind, target_id, me["id"]))
    _recompute_rating(conn, kind, target_id)
    conn.commit()
    conn.close()
    return {"ok": True}

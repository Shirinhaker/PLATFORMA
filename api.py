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

from fastapi import APIRouter, Request, Header, HTTPException

from database import db

router = APIRouter(prefix="/api")


# ---------- Yordamchilar ----------
def _tg(init_data):
    from main import require_tg
    return require_tg(init_data)


def require_user(conn, init_data):
    """Ro'yxatdan o'tgan foydalanuvchini talab qiladi."""
    tg = _tg(init_data)
    user = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg["id"],)).fetchone()
    if not user:
        raise HTTPException(401, "Avval ro'yxatdan o'ting yoki tizimga kiring.")
    return user


def require_business(conn, init_data):
    user = require_user(conn, init_data)
    if user["role"] != "business":
        raise HTTPException(403, "Bu bo'lim faqat biznes akkauntlar uchun.")
    biz = conn.execute("SELECT * FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
    if not biz:
        raise HTTPException(404, "Biznes profili topilmadi.")
    return user, biz


def follower_count(conn, kind, target_id):
    return conn.execute(
        "SELECT COUNT(*) c FROM follows WHERE target_kind=? AND target_id=?", (kind, target_id)
    ).fetchone()["c"]


def following_count(conn, user_id):
    return conn.execute(
        "SELECT COUNT(*) c FROM follows WHERE follower_id=?", (user_id,)
    ).fetchone()["c"]


def is_following(conn, user_id, kind, target_id):
    if not user_id:
        return False
    return bool(conn.execute(
        "SELECT 1 FROM follows WHERE follower_id=? AND target_kind=? AND target_id=?",
        (user_id, kind, target_id),
    ).fetchone())


def optional_user(conn, init_data):
    """Kirgan bo'lsa user, bo'lmasa None (mehmon rejimi)."""
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
@router.put("/profile")
async def update_profile(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
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
    conn.execute(
        "UPDATE users SET name=?, phone=?, region=?, district=?, mahalla=?, lat=?, lng=? WHERE id=?",
        (new_name or user["name"], new_phone, new_region, new_district, new_mahalla, new_lat, new_lng, user["id"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/profile")
async def get_profile(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    result = {
        "id": user["id"], "role": user["role"], "name": user["name"], "phone": user["phone"],
        "region": user["region"], "district": user["district"], "mahalla": user["mahalla"],
        "lat": user["lat"], "lng": user["lng"],
        "followers": follower_count(conn, "user", user["id"]),
        "following": following_count(conn, user["id"]),
    }
    if user["role"] == "business":
        biz = conn.execute("SELECT * FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
        if biz:
            result["business_followers"] = follower_count(conn, "business", biz["id"])
            result["business_following"] = 0  # biznes nomidan obuna tizimi hozircha alohida qilinmagan
            result["business_id"] = biz["id"]
    conn.close()
    return result


# ====================================================================
# MUTAXASISLIK ("Mutaxasisligim va xizmatlarim")
# ====================================================================
@router.get("/specialist")
async def get_specialist(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    sp = conn.execute("SELECT * FROM specialists WHERE user_id=?", (user["id"],)).fetchone()
    conn.close()
    if not sp:
        return {"exists": False}
    return {
        "exists": True, "kasb": sp["kasb"], "descr": sp["descr"], "narx": sp["narx"],
        "hudud": sp["hudud"], "is_gov": bool(sp["is_gov"]), "org": sp["org"],
        "dept": sp["dept"], "lavozim": sp["lavozim"], "work_hours": sp["work_hours"],
        "after_hours": sp["after_hours"], "visible": bool(sp["visible"]),
        "available": bool(sp["available"]), "lat": sp["lat"], "lng": sp["lng"],
    }


@router.put("/specialist")
async def update_specialist(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    b = await request.json()
    kasb = (b.get("kasb") or "").strip()
    if b.get("visible") and not kasb:
        conn.close()
        raise HTTPException(400, "Ko'rinish uchun kasb/yo'nalish kiritilishi shart.")
    is_gov = 1 if b.get("is_gov") else 0
    if is_gov and not (b.get("org") or "").strip():
        conn.close()
        raise HTTPException(400, "Davlat ishchisi uchun tashkilot kiritilishi shart.")
    now = int(time.time())
    conn.execute(
        """INSERT INTO specialists(user_id, kasb, descr, narx, hudud, is_gov, org, dept, lavozim,
                                   work_hours, after_hours, visible, available, lat, lng, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET
             kasb=excluded.kasb, descr=excluded.descr, narx=excluded.narx, hudud=excluded.hudud,
             is_gov=excluded.is_gov, org=excluded.org, dept=excluded.dept, lavozim=excluded.lavozim,
             work_hours=excluded.work_hours, after_hours=excluded.after_hours,
             visible=excluded.visible, available=excluded.available,
             lat=excluded.lat, lng=excluded.lng""",
        (user["id"], kasb, (b.get("descr") or "").strip(), (b.get("narx") or "").strip(),
         (b.get("hudud") or "").strip(), is_gov, (b.get("org") or "").strip(),
         (b.get("dept") or "").strip(), (b.get("lavozim") or "").strip(),
         (b.get("work_hours") or "").strip(), (b.get("after_hours") or "").strip(),
         1 if b.get("visible") else 0, 1 if b.get("available", True) else 0,
         b.get("lat"), b.get("lng"), now),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


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
    conn.close()
    if not d:
        return {"exists": False, "name": name, "phone": phone}
    rating = round(d["rating_sum"] / d["rating_cnt"], 1) if d["rating_cnt"] else 0
    return {
        "exists": True, "name": name,
        "phone": d["phone"], "car_model": d["car_model"], "car_color": d["car_color"],
        "car_plate": d["car_plate"], "service": d["service"], "available": bool(d["available"]),
        "rating": rating, "rating_cnt": d["rating_cnt"], "balance": d["balance"],
        "commission": COMMISSION_PER_ORDER, "is_admin": (user["tg_id"] in ADMIN_TG_IDS),
    }


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
    cur = conn.execute("UPDATE drivers SET available=? WHERE user_id=?", (avail, user["id"]))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "Avval haydovchi sifatida ro'yxatdan o'ting.")
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
        "status": r["status"], "created_at": r["created_at"],
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
        "SELECT id FROM rides WHERE customer_id=? AND status IN ('pending','accepted','arrived','ongoing') LIMIT 1",
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
        "SELECT * FROM rides WHERE customer_id=? AND status IN ('pending','accepted','arrived','ongoing') ORDER BY id DESC LIMIT 1",
        (user["id"],),
    ).fetchone()
    if not r:
        conn.close()
        return {"ride": None}
    out = _ride_dict(r)
    if r["status"] == "accepted" and r["driver_id"]:
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
    cur = conn.execute(
        "UPDATE rides SET status='canceled' WHERE id=? AND customer_id=? AND status IN ('pending','accepted','arrived')",
        (ride_id, user["id"]),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "Zakaz topilmadi yoki allaqachon yakunlangan.")
    return {"ok": True}


@router.get("/rides/pending")
async def pending_rides(x_telegram_init_data: str = Header(default="")):
    """Haydovchi uchun: joriy qabul qilingan zakazi + xizmatiga mos kutilayotgan zakazlar."""
    conn = db()
    user, d = _require_driver(conn, x_telegram_init_data)
    cur_ride = conn.execute(
        "SELECT * FROM rides WHERE driver_id=? AND status IN ('accepted','arrived','ongoing') ORDER BY id DESC LIMIT 1",
        (d["id"],),
    ).fetchone()
    current = None
    if cur_ride:
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
    """Haydovchi zakazni qabul qiladi (faqat birinchi bo'lib ulgurgan oladi)."""
    conn = db()
    user, d = _require_driver(conn, x_telegram_init_data)
    if not d["available"]:
        conn.close()
        raise HTTPException(400, "Avval 'Bo'shman' holatiga o'ting.")
    busy = conn.execute("SELECT id FROM rides WHERE driver_id=? AND status IN ('accepted','arrived','ongoing') LIMIT 1", (d["id"],)).fetchone()
    if busy:
        conn.close()
        raise HTTPException(400, "Sizda hali tugamagan zakaz bor.")
    # Balans tekshiruvi: zakaz olish uchun komissiyaga yetarli balans bo'lishi kerak
    if (d["balance"] or 0) < COMMISSION_PER_ORDER:
        conn.close()
        raise HTTPException(400, "Balansingiz yetarli emas. Zakaz olish uchun balansni to'ldiring.")
    now = int(time.time())
    cur = conn.execute(
        "UPDATE rides SET status='accepted', driver_id=?, accepted_at=? WHERE id=? AND status='pending'",
        (d["id"], now, ride_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(409, "Bu zakazni boshqa haydovchi oldi.")
    # Zakaz olindi — komissiyani balansdan yechamiz
    conn.execute("UPDATE drivers SET balance = balance - ? WHERE id=?", (COMMISSION_PER_ORDER, d["id"]))
    conn.commit()
    r = conn.execute("SELECT * FROM rides WHERE id=?", (ride_id,)).fetchone()
    out = _ride_dict(r)
    cu = conn.execute("SELECT name, phone FROM users WHERE id=?", (r["customer_id"],)).fetchone()
    out["customer"] = {"name": cu["name"] if cu else "", "phone": cu["phone"] if cu else ""}
    new_balance = conn.execute("SELECT balance FROM drivers WHERE id=?", (d["id"],)).fetchone()["balance"]
    conn.close()
    return {"ok": True, "ride": out, "commission": COMMISSION_PER_ORDER, "balance": new_balance}


@router.post("/rides/{ride_id}/complete")
async def complete_ride(ride_id: int, x_telegram_init_data: str = Header(default="")):
    """Haydovchi safarni yakunlaydi."""
    conn = db()
    user, d = _require_driver(conn, x_telegram_init_data)
    cur = conn.execute(
        "UPDATE rides SET status='completed' WHERE id=? AND driver_id=? AND status='accepted'",
        (ride_id, d["id"]),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "Zakaz topilmadi.")
    return {"ok": True}


@router.post("/rides/{ride_id}/status")
async def update_ride_status(ride_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    """Haydovchi safar bosqichini oldinga suradi: accepted -> arrived -> ongoing -> completed."""
    conn = db()
    user, d = _require_driver(conn, x_telegram_init_data)
    b = await request.json()
    new = (b.get("status") or "").strip()
    nxt = {"accepted": "arrived", "arrived": "ongoing", "ongoing": "completed"}
    r = conn.execute("SELECT status FROM rides WHERE id=? AND driver_id=?", (ride_id, d["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Zakaz topilmadi.")
    if nxt.get(r["status"]) != new:
        conn.close()
        raise HTTPException(400, "Bu bosqichga o'tib bo'lmaydi.")
    conn.execute("UPDATE rides SET status=? WHERE id=?", (new, ride_id))
    conn.commit()
    conn.close()
    return {"ok": True, "status": new}


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
@router.put("/business")
async def update_business(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
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
    # lat/lng: faqat yuborilgan bo'lsa yangilaymiz, aks holda eskisi qoladi
    new_lat = b["lat"] if ("lat" in b and b["lat"] is not None) else biz["lat"]
    new_lng = b["lng"] if ("lng" in b and b["lng"] is not None) else biz["lng"]
    conn.execute(
        """UPDATE businesses SET name=?, yon=?, tur=?, descr=?, phone=?, telegram=?,
           work_hours=?, address=?, lat=?, lng=? WHERE id=?""",
        (new_name, new_yon, new_tur, new_descr, new_phone, new_tg,
         new_hours, new_addr, new_lat, new_lng, biz["id"]),
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
    cur = conn.execute(
        "INSERT INTO items(business_id, group_id, name, price, unit, track_stock, note, kind, photo_file, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (biz["id"], group_id, name, (b.get("price") or "").strip(), _clean_unit(b.get("unit")),
         1 if str(b.get("track_stock") or 0) in ("1", "true", "True") else 0,
         (b.get("note") or "").strip(), kind, photo, int(time.time())),
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
    conn.execute(
        "UPDATE items SET name=?, price=?, unit=?, track_stock=?, note=?, kind=?, group_id=?, photo_file=? WHERE id=? AND business_id=?",
        (name, (b.get("price") or "").strip(), _clean_unit(b.get("unit")),
         1 if str(b.get("track_stock") or 0) in ("1", "true", "True") else 0,
         (b.get("note") or "").strip(), kind, group_id, photo, item_id, biz["id"]),
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
# E'LONLAR
# ====================================================================
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
    if actor["type"] != "user":
        conn.close()
        raise HTTPException(400, "Obuna hozircha oddiy kabinet orqali bajariladi.")
    kind = b.get("target_kind")
    target_id = b.get("target_id")
    if kind not in ("user", "business") or not target_id:
        conn.close()
        raise HTTPException(400, "Obuna nishoni noto'g'ri.")
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
    return {"following": following, "followers": count}


@router.get("/follows/my")
async def my_follows(actor_type: str = "user", x_telegram_init_data: str = Header(default="")):
    """Men obuna bo'lganlarim (obunalarim)."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, user, actor_type)
    if actor["type"] == "business":
        conn.close()
        return []
    rows = conn.execute(
        "SELECT * FROM follows WHERE follower_id=? ORDER BY created_at DESC", (user["id"],)
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
    """Menga obuna bo'lganlar (obunachilarim) — kabinet turi bo'yicha alohida."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    actor = resolve_actor(conn, user, actor_type)
    if actor["type"] == "business":
        targets = [("business", actor["business_id"])]
    else:
        targets = [("user", user["id"])]
    result = []
    for kind, tid in targets:
        rows = conn.execute(
            "SELECT follower_id FROM follows WHERE target_kind=? AND target_id=?", (kind, tid)
        ).fetchall()
        for r in rows:
            u = conn.execute("SELECT id, name, district FROM users WHERE id=?", (r["follower_id"],)).fetchone()
            if u:
                result.append({"id": u["id"], "name": u["name"], "info": u["district"]})
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
        "lat": row["lat"],
        "lng": row["lng"],
        "source": "obuna",
    }


@router.get("/map")
async def home_map(x_telegram_init_data: str = Header(default="")):
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

    # 2) Foydalanuvchi obuna bo'lgan bizneslar
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

    # 3) Foydalanuvchi obuna bo'lgan mutaxasislar/foydalanuvchilar
    specialist_rows = conn.execute(
        """SELECT s.*, u.name, u.district
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


@router.get("/stock")
async def stock_list(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    rows = conn.execute(
        "SELECT id, name, unit, stock_qty FROM items "
        "WHERE business_id=? AND track_stock=1 ORDER BY name COLLATE NOCASE",
        (biz["id"],),
    ).fetchall()
    result = [{"id": r["id"], "name": r["name"], "unit": r["unit"] or "dona",
               "stock_qty": r["stock_qty"] or 0} for r in rows]
    conn.close()
    return result


@router.post("/stock/move")
async def stock_move(body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
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
    now = int(time.time())
    conn.execute("UPDATE items SET stock_qty=ROUND(COALESCE(stock_qty,0)+?, 3) WHERE id=?", (delta, item_id))
    conn.execute(
        "INSERT INTO stock_moves(business_id, item_id, delta, reason, note, order_id, user_id, created_at) "
        "VALUES(?,?,?,?,?,NULL,?,?)",
        (biz["id"], item_id, delta, reason, note, user["id"], now),
    )
    conn.commit()
    new_q = conn.execute("SELECT stock_qty FROM items WHERE id=?", (item_id,)).fetchone()["stock_qty"]
    conn.close()
    return {"ok": True, "stock_qty": new_q or 0}


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
    result = [{"delta": r["delta"], "reason": r["reason"],
               "reason_text": _STOCK_REASON_TEXT.get(r["reason"], r["reason"] or ""),
               "note": r["note"] or "", "who": r["who"] or "",
               "order_id": r["order_id"], "created_at": r["created_at"], "unit": unit}
              for r in rows]
    conn.close()
    return result


# ================== KASSA (savdo daftari) ==================
TASHKENT_TZ = 5 * 3600   # O'zbekiston vaqti (UTC+5) — "bugun" chegarasi uchun
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
    return {"id": r["id"], "source": r["source"] or "manual", "order_id": r["order_id"],
            "item_id": r["item_id"], "item_name": r["item_name"] or "",
            "qty": r["qty"] or 1, "unit": r["unit"] or "", "price": r["price"] or 0,
            "total": r["total"] or 0, "pay_type": r["pay_type"] or "",
            "pay_text": _PAY_TEXT.get(r["pay_type"] or "", r["pay_type"] or ""),
            "debtor_id": r["debtor_id"], "note": r["note"] or "",
            "created_at": r["created_at"]}


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
    start, end, dstr = _day_bounds(day)
    rows = conn.execute(
        "SELECT s.*, u.name AS who FROM sales s LEFT JOIN users u ON u.id=s.user_id "
        "WHERE s.business_id=? AND s.created_at>=? AND s.created_at<? "
        "ORDER BY s.created_at DESC, s.id DESC LIMIT 200",
        (biz["id"], start, end),
    ).fetchall()
    totals = {"all": 0, "naqd": 0, "karta": 0, "qarz": 0, "order": 0}
    out = []
    for r in rows:
        d = _sale_dict(r)
        d["who"] = r["who"] or ""
        out.append(d)
        t = int(r["total"] or 0)
        totals["all"] += t
        pt = r["pay_type"] or ""
        if pt in ("naqd", "karta", "qarz"):
            totals[pt] += t
        else:
            totals["order"] += t
    conn.close()
    return {"day": dstr, "sales": out, "totals": totals}


@router.post("/kassa")
async def kassa_add(body: dict, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
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
    cur = conn.execute(
        "INSERT INTO sales(business_id, source, order_id, item_id, item_name, qty, unit, price, total, pay_type, debtor_id, qarz_tx_id, note, user_id, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (biz["id"], "manual", None, item_id, name, qty, unit, price, total, pay, debtor_id, qtx_id, note, user["id"], now),
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


@router.delete("/kassa/{sale_id}")
async def kassa_delete(sale_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    r = conn.execute("SELECT * FROM sales WHERE id=? AND business_id=?", (sale_id, biz["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Savdo topilmadi.")
    if (r["source"] or "") != "manual":
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
    conn.execute(
        "INSERT INTO qarz_tx(debtor_id, type, amount, date, note, created_at) VALUES(?,?,?,?,?,?)",
        (debtor_id, b["type"], amount, (b.get("date") or date.today().isoformat()).strip(),
         (b.get("note") or "").strip(), int(time.time())),
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


# Qidiruv kengligi (scope) -> radius (km). None = cheklovsiz (Respublika).
_SCOPE_RADIUS_KM = {
    "Mahalla": 3.0,
    "Tuman": 12.0,
    "Shahar": 35.0,
    "Viloyat": 150.0,
    "Respublika": None,
}


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
async def search(q: str = "", scope: str = "", x_telegram_init_data: str = Header(default="")):
    q = (q or "").strip()
    if not q:
        raise HTTPException(400, "Qidiruv so'zi kiritilmadi.")
    conn = db()
    # Qadam 3: foydalanuvchi joylashuvi (masofa filtri uchun). Bo'lmasa filtr qo'llanmaydi.
    ulat = ulng = None
    try:
        _u = require_user(conn, x_telegram_init_data)
        ulat, ulng = _u["lat"], _u["lng"]
    except Exception:
        ulat = ulng = None

    def _fetch(qq):
        terms = _search_terms(qq)
        _match = _fts_match(qq)

        # Mahsulotlar — FTS (bm25 moslik, mahsulot nomi 10x). Xatolik bo'lsa eski LIKE'ga qaytadi.
        products = None
        if _match:
            try:
                products = conn.execute(
                    "SELECT i.id, i.name, i.price, i.unit, i.note, i.kind, "
                    "b.id biz_id, b.name biz_name, b.yon biz_yon, b.tur biz_tur, b.address, b.lat, b.lng, "
                    "bm25(items_fts, 10.0, 1.0) AS _rank "
                    "FROM items_fts JOIN items i ON i.id = items_fts.rowid "
                    "JOIN businesses b ON b.id = i.business_id "
                    "WHERE items_fts MATCH ? AND b.status='active' "
                    "ORDER BY _rank LIMIT 50",
                    (_match,),
                ).fetchall()
            except Exception:
                products = None
        if products is None:
            product_where, product_params = _like_where(
                ["i.name", "i.note", "i.kind", "b.name", "b.yon", "b.tur", "b.descr", "b.address"],
                terms,
            )
            products = conn.execute(
                """SELECT i.id, i.name, i.price, i.unit, i.note, i.kind,
                          b.id biz_id, b.name biz_name, b.yon biz_yon, b.tur biz_tur, b.address, b.lat, b.lng
                   FROM items i JOIN businesses b ON b.id=i.business_id
                   WHERE b.status='active' AND """ + product_where + """
                   ORDER BY i.created_at DESC LIMIT 50""",
                product_params,
            ).fetchall()

        # E'lonlar — FTS (bm25 moslik). Xatolik yoki indeks bo'lmasa eski LIKE'ga qaytadi.
        listings = None
        if _match:
            try:
                listings = conn.execute(
                    "SELECT l.*, bm25(listings_fts, 10.0, 1.0) AS _rank "
                    "FROM listings_fts JOIN listings l ON l.id = listings_fts.rowid "
                    "WHERE listings_fts MATCH ? AND l.status='active' AND l.visibility='all' "
                    "ORDER BY _rank LIMIT 50",
                    (_match,),
                ).fetchall()
            except Exception:
                listings = None
        if listings is None:
            listing_where, listing_params = _like_where(
                ["title", "cat", "price", "descr", "address"],
                terms,
            )
            listings = conn.execute(
                "SELECT * FROM listings WHERE status='active' AND visibility='all' AND " + listing_where +
                " ORDER BY created_at DESC LIMIT 50",
                listing_params,
            ).fetchall()

        # Mutaxassislar — FTS (bm25 moslik, kasb+ism 10x). Bo'sh (available) birinchi, keyin moslik.
        specialists = None
        if _match:
            try:
                specialists = conn.execute(
                    "SELECT s.*, u.name, u.region, u.district, u.mahalla, "
                    "bm25(specialists_fts, 10.0, 1.0) AS _rank "
                    "FROM specialists_fts JOIN specialists s ON s.user_id = specialists_fts.rowid "
                    "JOIN users u ON u.id = s.user_id "
                    "WHERE specialists_fts MATCH ? AND s.visible=1 "
                    "ORDER BY s.available DESC, _rank LIMIT 50",
                    (_match,),
                ).fetchall()
            except Exception:
                specialists = None
        if specialists is None:
            specialist_where, specialist_params = _like_where(
                ["s.kasb", "s.descr", "s.narx", "s.hudud", "s.org", "s.dept", "s.lavozim",
                 "u.name", "u.region", "u.district", "u.mahalla"],
                terms,
            )
            specialists = conn.execute(
                """SELECT s.*, u.name, u.region, u.district, u.mahalla
                   FROM specialists s JOIN users u ON u.id=s.user_id
                   WHERE s.visible=1 AND """ + specialist_where + """
                   ORDER BY s.available DESC, s.created_at DESC LIMIT 50""",
                specialist_params,
            ).fetchall()

        # Bizneslar — FTS (bm25 moslik bo'yicha tartiblash). Xatolik yoki indeks bo'lmasa
        # avtomatik eski LIKE usuliga qaytadi (biznes qidiruvi hech qachon buzilmaydi).
        businesses = None
        if _match:
            try:
                businesses = conn.execute(
                    "SELECT b.*, bm25(businesses_fts, 10.0, 1.0) AS _rank "
                    "FROM businesses_fts JOIN businesses b ON b.id = businesses_fts.rowid "
                    "WHERE businesses_fts MATCH ? AND b.status='active' "
                    "ORDER BY _rank LIMIT 50",
                    (_match,),
                ).fetchall()
            except Exception:
                businesses = None
        if businesses is None:
            business_where, business_params = _like_where(
                ["name", "yon", "tur", "descr", "address", "phone", "telegram", "work_hours"],
                terms,
            )
            businesses = conn.execute(
                "SELECT * FROM businesses WHERE status='active' AND " + business_where +
                " ORDER BY created_at DESC LIMIT 50",
                business_params,
            ).fetchall()

        # Qadam 3: "Qidiruv kengligi" bo'yicha masofa filtri (qattiq). Koordinatasiz natija qoladi.
        _radius = _SCOPE_RADIUS_KM.get(scope)
        if _radius is not None and ulat is not None and ulng is not None:
            products    = [r for r in products    if _within_radius(r, ulat, ulng, _radius)]
            listings    = [r for r in listings    if _within_radius(r, ulat, ulng, _radius)]
            specialists = [r for r in specialists if _within_radius(r, ulat, ulng, _radius)]
            businesses  = [r for r in businesses  if _within_radius(r, ulat, ulng, _radius)]

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
        "corrected": corrected,
        "terms": _search_terms(corrected or q),
        "products": [{"id": p["id"], "name": p["name"], "price": p["price"], "unit": p["unit"] or "dona",
                      "note": p["note"], "kind": p["kind"],
                      "business_id": p["biz_id"], "business_name": p["biz_name"],
                      "business_yon": p["biz_yon"], "business_tur": p["biz_tur"],
                      "address": p["address"], "lat": p["lat"], "lng": p["lng"]} for p in products],
        "listings": [listing_to_dict(conn, r, with_media=False) for r in listings],
        "specialists": [{"user_id": s["user_id"], "name": s["name"], "kasb": s["kasb"],
                         "descr": s["descr"], "narx": s["narx"], "is_gov": bool(s["is_gov"]),
                         "available": bool(s["available"]), "region": s["region"],
                         "district": s["district"], "mahalla": s["mahalla"],
                         "lat": s["lat"], "lng": s["lng"]} for s in specialists],
        "businesses": [{"id": b["id"], "name": b["name"], "yon": b["yon"], "tur": b["tur"],
                        "descr": b["descr"], "address": b["address"],
                        "lat": b["lat"], "lng": b["lng"]} for b in businesses],
    }
    conn.close()
    return result


@router.get("/browse")
async def browse_by_type(tur: str = "", x_telegram_init_data: str = Header(default="")):
    """Katalogdan faoliyat turi tanlanganda: shu turdagi biznes va mutaxasislar."""
    tur = (tur or "").strip()
    if not tur:
        raise HTTPException(400, "Faoliyat turi kiritilmadi.")
    terms = _search_terms(tur)
    conn = db()

    business_where, business_params = _like_where(["tur", "yon", "name", "descr"], terms)
    businesses = conn.execute(
        "SELECT * FROM businesses WHERE status='active' AND " + business_where +
        " ORDER BY created_at DESC LIMIT 100",
        business_params,
    ).fetchall()

    specialist_where, specialist_params = _like_where(
        ["s.kasb", "s.descr", "s.hudud", "s.org", "s.lavozim", "u.name", "u.district"],
        terms,
    )
    specialists = conn.execute(
        """SELECT s.*, u.name, u.region, u.district, u.mahalla
           FROM specialists s JOIN users u ON u.id=s.user_id
           WHERE s.visible=1 AND """ + specialist_where + """
           ORDER BY s.available DESC, s.created_at DESC LIMIT 100""",
        specialist_params,
    ).fetchall()
    result = {
        "businesses": [{"id": b["id"], "name": b["name"], "yon": b["yon"], "tur": b["tur"],
                        "descr": b["descr"], "address": b["address"],
                        "lat": b["lat"], "lng": b["lng"]} for b in businesses],
        "specialists": [{"user_id": s["user_id"], "name": s["name"], "kasb": s["kasb"],
                         "descr": s["descr"], "narx": s["narx"], "is_gov": bool(s["is_gov"]),
                         "available": bool(s["available"]), "region": s["region"],
                         "district": s["district"], "mahalla": s["mahalla"],
                         "lat": s["lat"], "lng": s["lng"]} for s in specialists],
    }
    conn.close()
    return result


# ====================================================================
# SAHIFALAR (biznes / mutaxasis)
# ====================================================================
@router.get("/business/{business_id}")
async def business_page(business_id: int, x_telegram_init_data: str = Header(default="")):
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
    result = {
        "id": biz["id"], "name": biz["name"], "yon": biz["yon"], "tur": biz["tur"],
        "descr": biz["descr"], "phone": biz["phone"], "telegram": biz["telegram"],
        "work_hours": biz["work_hours"], "address": biz["address"],
        "lat": biz["lat"], "lng": biz["lng"],
        "followers": follower_count(conn, "business", biz["id"]),
        "is_following": is_following(conn, viewer["id"] if viewer else None, "business", biz["id"]),
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
async def person_page(user_id: int, x_telegram_init_data: str = Header(default="")):
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
    result = {
        "id": u["id"], "name": u["name"], "district": u["district"],
        "followers": follower_count(conn, "user", u["id"]),
        "is_following": is_following(conn, viewer["id"] if viewer else None, "user", u["id"]),
        "specialist": None,
        "listings": [listing_to_dict(conn, r) for r in listings],
    }
    if sp:
        result["specialist"] = {
            "kasb": sp["kasb"], "descr": sp["descr"], "narx": sp["narx"], "hudud": sp["hudud"],
            "is_gov": bool(sp["is_gov"]), "org": sp["org"], "dept": sp["dept"],
            "lavozim": sp["lavozim"], "work_hours": sp["work_hours"],
            "after_hours": sp["after_hours"], "available": bool(sp["available"]),
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


def _order_to_dict(conn, r, view="customer"):
    customer = _actor_brief(conn, r["customer_kind"], r["customer_actor_id"])
    provider = _actor_brief(conn, r["provider_kind"], r["provider_actor_id"])
    items = _order_items_to_dict(conn, r["id"])
    total_amount = sum(int(x.get("line_total") or 0) for x in items)
    chat_count = conn.execute("SELECT COUNT(*) FROM order_messages WHERE order_id=?", (r["id"],)).fetchone()[0]
    last_chat = conn.execute("SELECT text, media_type, created_at FROM order_messages WHERE order_id=? AND COALESCE(is_deleted,0)=0 ORDER BY created_at DESC, id DESC LIMIT 1", (r["id"],)).fetchone()
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
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
        "provider_seen_at": _row_val(r, "provider_seen_at", 0),
        "customer_seen_at": _row_val(r, "customer_seen_at", 0),
        "is_unread": _order_seen_value(r, view) <= 0,
        "chat_count": chat_count,
        "last_chat": ((last_chat["text"] if last_chat and last_chat["text"] else "📷 Rasm") if last_chat else ""),
        "last_chat_at": (last_chat["created_at"] if last_chat else 0),
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


@router.put("/orders/{order_id}/status")
async def update_order_status(order_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    b = await request.json()
    actor = actor_from_body(conn, me, b)
    kind, actor_id, _owner = _actor_identity(actor)
    new_status = (b.get("status") or "").strip().lower()
    allowed = {"accepted", "rejected", "done", "cancelled"}
    if new_status not in allowed:
        conn.close()
        raise HTTPException(400, "Buyurtma holati noto'g'ri.")

    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Buyurtma topilmadi.")

    is_provider = (row["provider_kind"] == kind and int(row["provider_actor_id"]) == actor_id)
    is_customer = (row["customer_kind"] == kind and int(row["customer_actor_id"]) == actor_id)
    if new_status in ("accepted", "rejected", "done") and not is_provider:
        conn.close()
        raise HTTPException(403, "Bu buyurtma holatini faqat qabul qiluvchi kabinet o'zgartira oladi.")
    if new_status == "cancelled" and not (is_customer or is_provider):
        conn.close()
        raise HTTPException(403, "Bu buyurtma sizga tegishli emas.")

    now = int(time.time())
    notify_tg = None
    notify_text = ""

    if new_status in ("accepted", "rejected", "done") or (new_status == "cancelled" and is_provider):
        # Qabul qiluvchi/biznes statusni o'zgartirdi — mijoz tomonda yangilanish belgisi chiqadi.
        conn.execute(
            "UPDATE orders SET status=?, updated_at=?, customer_seen_at=0, provider_seen_at=? WHERE id=?",
            (new_status, now, now, order_id),
        )
        cu = conn.execute("SELECT tg_id FROM users WHERE id=?", (row["customer_user_id"],)).fetchone()
        notify_tg = cu["tg_id"] if cu else None
        notify_text = "🔔 Buyurtma holati: " + {
            "accepted": "Qabul qilindi",
            "rejected": "Rad etildi",
            "done": "Yakunlandi",
            "cancelled": "Bekor qilindi",
        }.get(new_status, new_status) + "\n\n" + (row["title"] or "Buyurtma")
    elif new_status == "cancelled" and is_customer:
        # Mijoz bekor qildi — biznes tomonda yangi o'zgarish sifatida ko'rinadi.
        conn.execute(
            "UPDATE orders SET status=?, updated_at=?, provider_seen_at=0, customer_seen_at=? WHERE id=?",
            (new_status, now, now, order_id),
        )
        pu = conn.execute("SELECT tg_id FROM users WHERE id=?", (row["provider_user_id"],)).fetchone()
        notify_tg = pu["tg_id"] if pu else None
        notify_text = "⚠️ Mijoz buyurtmani bekor qildi\n\n" + (row["title"] or "Buyurtma")
    else:
        conn.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?", (new_status, now, order_id))

    # v1407: Buyurtma "Bajarildi" — ombordan avtomatik chiqim (faqat bir marta)
    if new_status == "done":
        _stock_deduct_for_order(conn, row, me["id"])
        _kassa_add_for_order(conn, row, me["id"])   # v1408: kassaga avtomatik savdo

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
        conn.execute("UPDATE orders SET updated_at=?, provider_seen_at=?, customer_seen_at=0 WHERE id=?", (now, now, order_id))
    else:
        conn.execute("UPDATE orders SET updated_at=?, customer_seen_at=?, provider_seen_at=0 WHERE id=?", (now, now, order_id))
    return now


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

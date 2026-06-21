"""
Platforma — kabinet va umumiy API'lar.

Bo'limlar:
  PROFIL        - shaxsiy ma'lumotlarni tahrirlash
  MUTAXASISLIK  - "Mutaxasisligim va xizmatlarim" (davlat ishchisi rejimi bilan)
  BIZNES        - biznes profili va mahsulot/xizmatlar
  E'LONLAR      - joylash (rasm/video Telegram file_id bilan), tahrirlash, ko'rinish turi
  OBUNA         - follow/followers (odamga ham, biznesga ham)
  SAQLANGANLAR  - e'lon va bizneslarni saqlash
  QARZ DAFTARI  - biznes kabineti bo'limi
  QIDIRUV       - mahsulot + e'lon + mutaxasis + biznes (hammasi birga)
  SAHIFALAR     - biznes sahifasi va mutaxasis (odam) sahifasi
"""

import json
import time

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
    conn.execute(
        "UPDATE users SET name=?, phone=?, region=?, district=?, mahalla=? WHERE id=?",
        (new_name or user["name"], new_phone, new_region, new_district, new_mahalla, user["id"]),
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
        "followers": follower_count(conn, "user", user["id"]),
        "following": following_count(conn, user["id"]),
    }
    if user["role"] == "business":
        biz = conn.execute("SELECT * FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
        if biz:
            result["business_followers"] = follower_count(conn, "business", biz["id"])
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
            conn.execute("UPDATE users SET region=?, district=? WHERE id=?", (gr, gd, user["id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/items")
async def my_items(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    rows = conn.execute(
        "SELECT * FROM items WHERE business_id=? ORDER BY created_at DESC", (biz["id"],)
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "price": r["price"],
             "note": r["note"], "kind": r["kind"]} for r in rows]


@router.post("/items")
async def add_item(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user, biz = require_business(conn, x_telegram_init_data)
    b = await request.json()
    name = (b.get("name") or "").strip()
    if not name:
        conn.close()
        raise HTTPException(400, "Mahsulot/xizmat nomi kiritilishi shart.")
    kind = b.get("kind") if b.get("kind") in ("product", "service") else "product"
    cur = conn.execute(
        "INSERT INTO items(business_id, name, price, note, kind, created_at) VALUES(?,?,?,?,?,?)",
        (biz["id"], name, (b.get("price") or "").strip(), (b.get("note") or "").strip(),
         kind, int(time.time())),
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
    conn.execute(
        "UPDATE items SET name=?, price=?, note=?, kind=? WHERE id=?",
        ((b.get("name") or "").strip(), (b.get("price") or "").strip(),
         (b.get("note") or "").strip(),
         b.get("kind") if b.get("kind") in ("product", "service") else "product", item_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


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

    visibility = "all"
    business_id = None
    if user["role"] == "business":
        biz = conn.execute("SELECT id FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
        business_id = biz["id"] if biz else None
        if b.get("visibility") == "own" and business_id:
            visibility = "own"  # faqat sahifa mehmonlariga

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
async def my_listings(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    rows = conn.execute(
        "SELECT * FROM listings WHERE user_id=? ORDER BY created_at DESC", (user["id"],)
    ).fetchall()
    result = [listing_to_dict(conn, r) for r in rows]
    conn.close()
    return result


@router.put("/listings/{listing_id}")
async def edit_listing(listing_id: int, request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    row = conn.execute(
        "SELECT * FROM listings WHERE id=? AND user_id=?", (listing_id, user["id"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "E'lon topilmadi.")
    b = await request.json()
    status = b.get("status") if b.get("status") in ("active", "inactive") else row["status"]
    visibility = row["visibility"]
    if user["role"] == "business" and b.get("visibility") in ("all", "own"):
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
async def delete_listing(listing_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    conn.execute("DELETE FROM listings WHERE id=? AND user_id=?", (listing_id, user["id"]))
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
async def my_follows(x_telegram_init_data: str = Header(default="")):
    """Men obuna bo'lganlarim (obunalarim)."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
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
async def my_followers(x_telegram_init_data: str = Header(default="")):
    """Menga obuna bo'lganlar (obunachilarim) — shaxs va biznes sifatida."""
    conn = db()
    user = require_user(conn, x_telegram_init_data)
    targets = [("user", user["id"])]
    biz = conn.execute("SELECT id FROM businesses WHERE user_id=?", (user["id"],)).fetchone()
    if biz:
        targets.append(("business", biz["id"]))
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
async def my_saved(x_telegram_init_data: str = Header(default="")):
    conn = db()
    user = require_user(conn, x_telegram_init_data)
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
    """Qidiruv uchun asosiy so'z va oddiy sinonimlarni tayyorlaydi."""
    base = (q or "").strip()
    norm = (base.lower()
            .replace("’", "'")
            .replace("‘", "'")
            .replace("`", "'")
            .replace("ʻ", "'")
            .replace("ʼ", "'"))
    variants = []

    def add(x):
        x = (x or "").strip().lower()
        if len(x) >= 2 and x not in variants:
            variants.append(x)

    add(base)
    add(norm)
    add(norm.replace("'", ""))
    add(norm.replace("-", " "))
    add(norm.replace("'", " "))

    for part in norm.replace("-", " ").replace("'", " ").split():
        add(part)

    syns = {
        "muhr": ["muhr", "tamga", "muhr tamga", "muhr-tamga", "pechat", "shtamp", "stamp"],
        "tamga": ["muhr", "tamga", "muhr tamga", "muhr-tamga", "pechat", "shtamp", "stamp"],
        "pechat": ["muhr", "tamga", "muhr tamga", "muhr-tamga", "pechat", "shtamp", "stamp"],
        "shtamp": ["muhr", "tamga", "muhr tamga", "muhr-tamga", "pechat", "shtamp", "stamp"],
        "taxi": ["taxi", "taksi", "yo'lovchi tashish", "yo'lovchi", "mashina"],
        "taksi": ["taxi", "taksi", "yo'lovchi tashish", "yo'lovchi", "mashina"],
        "dori": ["dori", "dorixona", "apteka", "farmatsevtika"],
        "dorixona": ["dori", "dorixona", "apteka", "farmatsevtika"],
        "apteka": ["dori", "dorixona", "apteka", "farmatsevtika"],
        "usta": ["usta", "ta'mir", "tamir", "santexnik", "elektrik", "montaj", "quruvchi"],
        "repetitor": ["repetitor", "o'qituvchi", "ustoz", "ta'lim", "kurs"],
        "advokat": ["advokat", "yurist", "huquq", "konsalting"],
    }
    for key, arr in syns.items():
        if key in norm:
            for x in arr:
                add(x)

    return variants[:18]


def _like_where(columns, terms):
    """Berilgan ustunlar bo'yicha xavfsiz LIKE shartini quradi."""
    clauses = []
    params = []
    for col in columns:
        for term in terms:
            clauses.append("COALESCE(" + col + ", '') LIKE ?")
            params.append("%" + term + "%")
    if not clauses:
        return "1=0", []
    return "(" + " OR ".join(clauses) + ")", params


@router.get("/search")
async def search(q: str = "", scope: str = "", x_telegram_init_data: str = Header(default="")):
    q = (q or "").strip()
    if not q:
        raise HTTPException(400, "Qidiruv so'zi kiritilmadi.")
    terms = _search_terms(q)
    conn = db()

    product_where, product_params = _like_where(
        ["i.name", "i.note", "i.kind", "b.name", "b.yon", "b.tur", "b.descr", "b.address"],
        terms,
    )
    products = conn.execute(
        """SELECT i.id, i.name, i.price, i.note, i.kind,
                  b.id biz_id, b.name biz_name, b.yon biz_yon, b.tur biz_tur, b.address, b.lat, b.lng
           FROM items i JOIN businesses b ON b.id=i.business_id
           WHERE b.status='active' AND """ + product_where + """
           ORDER BY i.created_at DESC LIMIT 50""",
        product_params,
    ).fetchall()

    listing_where, listing_params = _like_where(
        ["title", "cat", "price", "descr", "address"],
        terms,
    )
    listings = conn.execute(
        "SELECT * FROM listings WHERE status='active' AND visibility='all' AND " + listing_where +
        " ORDER BY created_at DESC LIMIT 50",
        listing_params,
    ).fetchall()

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

    business_where, business_params = _like_where(
        ["name", "yon", "tur", "descr", "address", "phone", "telegram", "work_hours"],
        terms,
    )
    businesses = conn.execute(
        "SELECT * FROM businesses WHERE status='active' AND " + business_where +
        " ORDER BY created_at DESC LIMIT 50",
        business_params,
    ).fetchall()

    result = {
        "q": q,
        "scope": scope,
        "terms": terms,
        "products": [{"id": p["id"], "name": p["name"], "price": p["price"],
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
        "SELECT id, name, price, note, kind FROM items WHERE business_id=? ORDER BY created_at DESC",
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
        "items": [{"id": i["id"], "name": i["name"], "price": i["price"],
                   "note": i["note"], "kind": i["kind"]} for i in items],
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
        "SELECT * FROM listings WHERE user_id=? AND status='active' AND visibility='all' "
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
def _user_brief(conn, uid):
    u = conn.execute("SELECT id, name, role FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        return {"id": uid, "name": "Foydalanuvchi", "role": "user"}
    name = u["name"]
    if u["role"] == "business":
        biz = conn.execute("SELECT name FROM businesses WHERE user_id=?", (uid,)).fetchone()
        if biz and biz["name"]:
            name = biz["name"]
    return {"id": u["id"], "name": name or "Foydalanuvchi", "role": u["role"]}


@router.post("/messages/send")
async def send_message(request: Request, x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    b = await request.json()
    to_id = b.get("to")
    text = (b.get("text") or "").strip()
    if not to_id or not text:
        conn.close()
        raise HTTPException(400, "Qabul qiluvchi va matn kiritilishi shart.")
    if int(to_id) == me["id"]:
        conn.close()
        raise HTTPException(400, "O'zingizga xabar yubora olmaysiz.")
    receiver = conn.execute("SELECT id, tg_id FROM users WHERE id=?", (to_id,)).fetchone()
    if not receiver:
        conn.close()
        raise HTTPException(404, "Qabul qiluvchi topilmadi.")
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO messages(sender_id, receiver_id, text, is_read, created_at) VALUES(?,?,?,0,?)",
        (me["id"], receiver["id"], text, now),
    )
    mid = cur.lastrowid
    conn.commit()

    # Telegram bildirishnomasi (qabul qiluvchining asosiy akkauntiga)
    sender_name = _user_brief(conn, me["id"])["name"]
    conn.close()
    if receiver["tg_id"]:
        try:
            from main import tg_call, BASE_URL
            await tg_call("sendMessage", {
                "chat_id": receiver["tg_id"],
                "text": "💬 Sizga yangi xabar: " + sender_name + "\n\n" + (text[:200]),
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Ochish", "web_app": {"url": BASE_URL}}
                ]]},
            })
        except Exception:
            pass
    return {"ok": True, "id": mid, "created_at": now}


@router.get("/messages/with/{user_id}")
async def conversation_with(user_id: int, x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    rows = conn.execute(
        """SELECT * FROM messages
           WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
           ORDER BY created_at ASC, id ASC LIMIT 500""",
        (me["id"], user_id, user_id, me["id"]),
    ).fetchall()
    # kelgan xabarlarni o'qilgan deb belgilaymiz
    conn.execute(
        "UPDATE messages SET is_read=1 WHERE receiver_id=? AND sender_id=? AND is_read=0",
        (me["id"], user_id),
    )
    conn.commit()
    other = _user_brief(conn, user_id)
    msgs = [{"id": r["id"], "text": r["text"], "mine": (r["sender_id"] == me["id"]),
             "created_at": r["created_at"]} for r in rows]
    conn.close()
    return {"other": other, "messages": msgs}


@router.get("/messages/conversations")
async def conversations(x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    # suhbatdoshlar ro'yxati — har biri bilan oxirgi xabar
    rows = conn.execute(
        """SELECT * FROM messages
           WHERE sender_id=? OR receiver_id=?
           ORDER BY created_at DESC, id DESC""",
        (me["id"], me["id"]),
    ).fetchall()
    seen = {}
    order = []
    for r in rows:
        other_id = r["receiver_id"] if r["sender_id"] == me["id"] else r["sender_id"]
        if other_id not in seen:
            seen[other_id] = {"last": r["text"], "created_at": r["created_at"], "unread": 0}
            order.append(other_id)
        # o'qilmagan: menga kelgan va o'qilmagan
        if r["receiver_id"] == me["id"] and not r["is_read"]:
            seen[other_id]["unread"] += 1
    result = []
    for oid in order:
        info = seen[oid]
        brief = _user_brief(conn, oid)
        result.append({"user_id": oid, "name": brief["name"], "role": brief["role"],
                       "last": info["last"], "created_at": info["created_at"], "unread": info["unread"]})
    conn.close()
    return result


@router.get("/messages/unread_count")
async def unread_count(x_telegram_init_data: str = Header(default="")):
    conn = db()
    me = require_user(conn, x_telegram_init_data)
    n = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE receiver_id=? AND is_read=0", (me["id"],)
    ).fetchone()[0]
    conn.close()
    return {"count": n}


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

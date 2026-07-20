"""Ko'prik biznes tariflari va obuna muddatlari uchun yagona domen qoidalari."""

import calendar
import time
from datetime import datetime, timezone


PAID_DURATIONS = (1, 3, 12)

PLAN_FEATURES = {
    "free": {
        "unlimited_items": True,
        "unlimited_stories": True,
        "home_nearby_eligible": False,
        "map_marker_eligible": False,
        "regional_stories_eligible": False,
    },
    "plus": {
        "unlimited_items": True,
        "unlimited_stories": True,
        "home_nearby_eligible": True,
        "map_marker_eligible": False,
        "regional_stories_eligible": False,
    },
    "pro": {
        "unlimited_items": True,
        "unlimited_stories": True,
        "home_nearby_eligible": True,
        "map_marker_eligible": True,
        "regional_stories_eligible": True,
    },
}

PLAN_CATALOG = (
    {
        "code": "free",
        "name": "Bepul",
        "summary": "Biznesni onlayn ko'rsatish uchun asosiy imkoniyatlar",
        "benefits": (
            "Biznes profilidan foydalanish",
            "Mahsulot va xizmatlarni cheksiz joylash",
            "Istoriyalarni cheksiz joylash",
        ),
    },
    {
        "code": "plus",
        "name": "Plus",
        "summary": "Mahsulot va xizmatlarni yaqin mijozlarga ko'rsatish",
        "benefits": (
            "Bepul tarifdagi barcha imkoniyatlar",
            "Sizga yaqin bo'limiga chiqish huquqi",
        ),
    },
    {
        "code": "pro",
        "name": "Pro",
        "summary": "Hudud bo'yicha kengroq ko'rinish",
        "benefits": (
            "Plus tarifdagi barcha imkoniyatlar",
            "Biznes metkasini xaritada ko'rsatish huquqi",
            "Istoriyani hududiy ro'yxatga chiqarish huquqi",
        ),
    },
)


class SubscriptionValidationError(ValueError):
    """Tarif yoki muddat qiymati kelishilgan qoidalarga mos emas."""


def init_subscription_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS business_subscriptions("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "business_id INTEGER NOT NULL,"
        "plan_code TEXT NOT NULL CHECK(plan_code IN ('free','plus','pro')),"
        "duration_months INTEGER NOT NULL DEFAULT 0,"
        "starts_at INTEGER NOT NULL,"
        "expires_at INTEGER NOT NULL DEFAULT 0,"
        "status TEXT NOT NULL DEFAULT 'active' "
        "CHECK(status IN ('active','superseded','expired')),"
        "is_demo INTEGER NOT NULL DEFAULT 1,"
        "created_at INTEGER NOT NULL)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_business_subscriptions_current "
        "ON business_subscriptions(business_id,status,expires_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_business_subscriptions_history "
        "ON business_subscriptions(business_id,id)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_business_subscriptions_active "
        "ON business_subscriptions(business_id) WHERE status='active'"
    )


def subscription_entitlements(plan_code):
    code = str(plan_code or "").strip().lower()
    if code not in PLAN_FEATURES:
        code = "free"
    return dict(PLAN_FEATURES[code])


def _add_calendar_months(timestamp, months):
    current = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    month_index = current.month - 1 + int(months)
    year = current.year + month_index // 12
    month = month_index % 12 + 1
    day = min(current.day, calendar.monthrange(year, month)[1])
    return int(current.replace(year=year, month=month, day=day).timestamp())


def _subscription_dict(row):
    if not row:
        return None
    data = dict(row)
    data["is_demo"] = bool(data.get("is_demo"))
    data["is_virtual"] = False
    return data


def _virtual_free():
    return {
        "id": None,
        "business_id": None,
        "plan_code": "free",
        "duration_months": 0,
        "starts_at": 0,
        "expires_at": 0,
        "status": "active",
        "is_demo": False,
        "created_at": 0,
        "is_virtual": True,
    }


def current_business_subscription(conn, business_id, now=None):
    now = int(time.time() if now is None else now)
    changed = conn.execute(
        "UPDATE business_subscriptions SET status='expired' "
        "WHERE business_id=? AND status='active' AND plan_code IN ('plus','pro') "
        "AND expires_at>0 AND expires_at<=?",
        (int(business_id), now),
    ).rowcount
    if changed:
        conn.commit()
    row = conn.execute(
        "SELECT * FROM business_subscriptions "
        "WHERE business_id=? AND status='active' ORDER BY id DESC LIMIT 1",
        (int(business_id),),
    ).fetchone()
    return _subscription_dict(row) or _virtual_free()


def business_has_entitlement(conn, business_id, feature, now=None):
    """Keyingi bosh sahifa/xarita/istoriya ishlarida ishlatiladigan yagona tekshiruv."""
    current = current_business_subscription(conn, business_id, now=now)
    return bool(subscription_entitlements(current["plan_code"]).get(str(feature or ""), False))


def _validate_activation(plan_code, duration_months):
    code = str(plan_code or "").strip().lower()
    if code not in PLAN_FEATURES:
        raise SubscriptionValidationError("Tarif noto'g'ri tanlangan.")
    if isinstance(duration_months, bool):
        raise SubscriptionValidationError("Obuna muddati noto'g'ri.")
    try:
        duration = int(duration_months)
    except (TypeError, ValueError):
        raise SubscriptionValidationError("Obuna muddati noto'g'ri.") from None
    if code == "free" and duration != 0:
        raise SubscriptionValidationError("Bepul tarif muddatsiz tanlanadi.")
    if code != "free" and duration not in PAID_DURATIONS:
        raise SubscriptionValidationError("Plus va Pro uchun 1, 3 yoki 12 oy tanlang.")
    return code, duration


def activate_demo_subscription(conn, business_id, plan_code, duration_months, now=None):
    code, duration = _validate_activation(plan_code, duration_months)
    business_id = int(business_id)
    now = int(time.time() if now is None else now)
    current = current_business_subscription(conn, business_id, now=now)

    if current["plan_code"] == code and not current["is_virtual"]:
        if code == "free":
            return subscription_payload(conn, business_id, now=now)
        base = max(int(current["expires_at"]), now)
        conn.execute(
            "UPDATE business_subscriptions SET duration_months=?,expires_at=? WHERE id=?",
            (
                int(current["duration_months"]) + duration,
                _add_calendar_months(base, duration),
                int(current["id"]),
            ),
        )
        conn.commit()
        return subscription_payload(conn, business_id, now=now)

    conn.execute(
        "UPDATE business_subscriptions SET status='superseded' "
        "WHERE business_id=? AND status='active'",
        (business_id,),
    )
    expires_at = 0 if code == "free" else _add_calendar_months(now, duration)
    conn.execute(
        "INSERT INTO business_subscriptions("
        "business_id,plan_code,duration_months,starts_at,expires_at,status,is_demo,created_at"
        ") VALUES(?,?,?,?,?,'active',1,?)",
        (business_id, code, duration, now, expires_at, now),
    )
    conn.commit()
    return subscription_payload(conn, business_id, now=now)


def subscription_payload(conn, business_id, now=None):
    current = current_business_subscription(conn, business_id, now=now)
    rows = conn.execute(
        "SELECT * FROM business_subscriptions "
        "WHERE business_id=? AND status<>'active' ORDER BY id DESC",
        (int(business_id),),
    ).fetchall()
    plans = []
    for item in PLAN_CATALOG:
        plan = dict(item)
        plan["benefits"] = list(plan["benefits"])
        plan["features"] = subscription_entitlements(plan["code"])
        plans.append(plan)
    return {
        "current": current,
        "features": subscription_entitlements(current["plan_code"]),
        "history": [_subscription_dict(row) for row in rows],
        "plans": plans,
        "durations": list(PAID_DURATIONS),
        "demo_mode": True,
    }

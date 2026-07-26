# Hourly Advertisement Pricing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current discounted daily advertisement pricing with backend-authoritative `20 000 UZS × unique district × full hour × day` pricing while preserving all legacy advertisements and payments.

**Architecture:** A new pure `ad_pricing.py` domain module owns target expansion, full-hour validation, price calculation, and schedule shifting. The existing API, payment workflow, admin panel, and single-file frontend consume that module; payment and advertisement rows keep immutable pricing snapshots so a later admin price change cannot alter an already submitted request.

**Tech Stack:** Python 3.13, FastAPI, SQLite, vanilla HTML/CSS/JavaScript, `unittest`/`pytest`.

## Global Constraints

- One district for one hour costs `20_000` UZS by default.
- The only new advertisement price code exposed to users/admin is `advertisement_district_hour`.
- The authoritative formula is `unique_district_count × hours_per_day × duration_days × district_hour_rate`.
- Allowed duration values are exactly `1`, `3`, `7`, `14`, and `30` days; no discounts.
- Daily start/end values must be exact `HH:00`; `22:00–02:00` is four hours; equal start/end is invalid unless the explicit all-day checkbox is used.
- An all-day advertisement is exactly 24 billable hours per selected day.
- The backend region/district catalog and the active platform price are authoritative; frontend totals are informational only.
- Overlapping region/district selections count each district once; republic cannot be combined with another target.
- A payment request stores an immutable calculation and schedule snapshot.
- Late payment approval moves the first run to the next matching complete daily window and never shortens paid time.
- Existing `advertisement_district_day` rows, requests, approvals, and active advertisements remain readable and operable; new requests cannot use that code.
- Existing MVP guards for stories, listings, chat, and systemization must not change.
- Build after implementation is `v1655`.
- The supplied source directory currently has no `.git`; run commit steps only in a Git clone, otherwise record the listed files as the task checkpoint.

---

## File Structure

- Create `ad_pricing.py`: pure catalog expansion, exact-hour parsing, pricing, and schedule arithmetic.
- Modify `district_catalog.py`: add the backend-owned region-to-district grouping while preserving `DISTRICT_NAMES`.
- Modify `database.py`: add advertisement billing snapshot columns without rewriting old rows.
- Modify `payments.py`: add the hourly price rule, payment snapshot column, and legacy price deactivation.
- Modify `payment_api.py`: derive advertisement payment quantity and amount from the owned pending advertisement, not from client input; activate hourly and legacy requests through separate paths.
- Modify `api.py`: use the new pricing service for quote/create/active advertisement behavior.
- Modify `static/index.html`: full-hour selectors, date-only start, formula display, and new hourly payment code.
- Modify `admin/app.js`: display one editable hourly advertisement base price and hide the legacy daily row.
- Modify `main.py`: expose build `v1655` and the hourly-pricing feature marker.
- Create `tests/test_ad_pricing_v1655.py`: pure calculation and schedule tests.
- Create `tests/test_advertisement_hourly_api_v1655.py`: quote/create/payment/approval and legacy API tests.
- Create `tests/test_advertisement_hourly_frontend_v1655_contract.py`: frontend and admin contract tests.
- Modify `tests/test_payment_api_v1652.py`: retain legacy approval coverage and adjust catalog expectations.
- Modify `tests/test_payment_frontend_v1652_contract.py`: replace the old frontend price-code assertion.

---

### Task 1: Backend Region Catalog and Pure Pricing Domain

**Files:**
- Create: `ad_pricing.py`
- Modify: `district_catalog.py`
- Test: `tests/test_ad_pricing_v1655.py`

**Interfaces:**
- Consumes: existing display district names from `district_catalog.py`.
- Produces:
  - `AdPricingError(ValueError)`
  - `VALID_AD_DURATIONS: tuple[int, ...]`
  - `normalize_ad_geo(value: object) -> str`
  - `clean_ad_targets(raw: object) -> list[dict[str, str]]`
  - `expand_targets_to_district_keys(targets: list[dict[str, str]]) -> tuple[str, ...]`
  - `full_hour(value: object) -> int`
  - `hours_per_day(all_day: bool, start: str, end: str) -> int`
  - `calculate_ad_price(*, targets, duration_days, daily_all_day, daily_start, daily_end, district_hour_rate) -> dict`
  - `first_schedule_start(*, start_date, daily_all_day, daily_start, tz_offset_seconds=18_000) -> int`
  - `shift_schedule_start(*, requested_start_at, approved_at, daily_all_day, daily_start, tz_offset_seconds=18_000) -> int`
  - `schedule_end_at(*, actual_start_at, duration_days, hours_each_day, daily_all_day) -> int`

- [ ] **Step 1: Write failing catalog and pricing tests**

Add the following cases to `tests/test_ad_pricing_v1655.py`:

```python
import unittest
from datetime import datetime, timezone

from ad_pricing import (
    AdPricingError,
    calculate_ad_price,
    clean_ad_targets,
    expand_targets_to_district_keys,
    first_schedule_start,
    full_hour,
    hours_per_day,
    schedule_end_at,
    shift_schedule_start,
)
from district_catalog import REGION_DISTRICTS


UZ_OFFSET = 5 * 3600


def utc_stamp(year, month, day, hour):
    return int(datetime(
        year, month, day, hour - 5, tzinfo=timezone.utc
    ).timestamp())


class HourlyAdPricingTests(unittest.TestCase):
    def test_surxondaryo_has_thirteen_billable_districts(self):
        self.assertEqual(len(REGION_DISTRICTS["Surxondaryo viloyati"]), 13)
        quote = calculate_ad_price(
            targets=[{
                "level": "region",
                "region": "Surxondaryo viloyati",
                "district": "",
            }],
            duration_days=1,
            daily_all_day=False,
            daily_start="11:00",
            daily_end="12:00",
            district_hour_rate=20_000,
        )
        self.assertEqual(quote["district_count"], 13)
        self.assertEqual(quote["hours_per_day"], 1)
        self.assertEqual(quote["billable_district_hours"], 13)
        self.assertEqual(quote["total"], 260_000)

    def test_region_and_its_district_do_not_double_count(self):
        targets = clean_ad_targets([
            {"level": "region", "region": "Surxondaryo viloyati"},
            {
                "level": "district",
                "region": "Surxondaryo viloyati",
                "district": "Qumqo'rg'on",
            },
        ])
        self.assertEqual(len(expand_targets_to_district_keys(targets)), 13)

    def test_republic_cannot_be_combined(self):
        with self.assertRaisesRegex(
            AdPricingError, "Respublika tanlansa"
        ):
            clean_ad_targets([
                {"level": "republic"},
                {
                    "level": "district",
                    "region": "Surxondaryo viloyati",
                    "district": "Denov",
                },
            ])

    def test_unknown_region_or_district_is_rejected(self):
        with self.assertRaisesRegex(AdPricingError, "katalog"):
            expand_targets_to_district_keys([{
                "level": "district",
                "region": "Mavjud emas",
                "district": "Soxta tuman",
            }])

    def test_full_hour_rejects_minutes(self):
        self.assertEqual(full_hour("11:00"), 11)
        for value in ("11:02", "11:29", "13:30", "24:00", ""):
            with self.subTest(value=value):
                with self.assertRaises(AdPricingError):
                    full_hour(value)

    def test_day_and_overnight_hours(self):
        self.assertEqual(hours_per_day(False, "11:00", "13:00"), 2)
        self.assertEqual(hours_per_day(False, "22:00", "02:00"), 4)
        self.assertEqual(hours_per_day(True, "11:29", "11:29"), 24)
        with self.assertRaisesRegex(AdPricingError, "bir xil"):
            hours_per_day(False, "11:00", "11:00")

    def test_no_discount_for_long_duration(self):
        quote = calculate_ad_price(
            targets=[{
                "level": "district",
                "region": "Surxondaryo viloyati",
                "district": "Denov",
            }],
            duration_days=30,
            daily_all_day=False,
            daily_start="11:00",
            daily_end="13:00",
            district_hour_rate=20_000,
        )
        self.assertEqual(quote["billable_district_hours"], 60)
        self.assertEqual(quote["total"], 1_200_000)
        self.assertNotIn("discount", quote)

    def test_only_supported_day_counts_are_accepted(self):
        for days in (1, 3, 7, 14, 30):
            calculate_ad_price(
                targets=[{
                    "level": "district",
                    "region": "Surxondaryo viloyati",
                    "district": "Denov",
                }],
                duration_days=days,
                daily_all_day=False,
                daily_start="11:00",
                daily_end="12:00",
                district_hour_rate=20_000,
            )
        with self.assertRaisesRegex(AdPricingError, "1, 3, 7, 14 yoki 30"):
            calculate_ad_price(
                targets=[{
                    "level": "district",
                    "region": "Surxondaryo viloyati",
                    "district": "Denov",
                }],
                duration_days=2,
                daily_all_day=False,
                daily_start="11:00",
                daily_end="12:00",
                district_hour_rate=20_000,
            )

    def test_first_start_uses_selected_date_and_daily_start(self):
        self.assertEqual(
            first_schedule_start(
                start_date="2026-07-27",
                daily_all_day=False,
                daily_start="11:00",
            ),
            utc_stamp(2026, 7, 27, 11),
        )
        self.assertEqual(
            first_schedule_start(
                start_date="2026-07-27",
                daily_all_day=True,
                daily_start="19:00",
            ),
            utc_stamp(2026, 7, 27, 0),
        )

    def test_late_approval_moves_to_next_complete_window(self):
        requested = utc_stamp(2026, 7, 27, 11)
        self.assertEqual(
            shift_schedule_start(
                requested_start_at=requested,
                approved_at=utc_stamp(2026, 7, 27, 12),
                daily_all_day=False,
                daily_start="11:00",
            ),
            utc_stamp(2026, 7, 28, 11),
        )
        self.assertEqual(
            shift_schedule_start(
                requested_start_at=requested,
                approved_at=utc_stamp(2026, 7, 27, 10),
                daily_all_day=False,
                daily_start="11:00",
            ),
            requested,
        )

    def test_schedule_end_preserves_all_paid_occurrences(self):
        start = utc_stamp(2026, 7, 27, 22)
        self.assertEqual(
            schedule_end_at(
                actual_start_at=start,
                duration_days=3,
                hours_each_day=4,
                daily_all_day=False,
            ),
            utc_stamp(2026, 7, 30, 2),
        )
        midnight = utc_stamp(2026, 7, 27, 0)
        self.assertEqual(
            schedule_end_at(
                actual_start_at=midnight,
                duration_days=3,
                hours_each_day=24,
                daily_all_day=True,
            ),
            utc_stamp(2026, 7, 30, 0),
        )
```

- [ ] **Step 2: Run the pure-domain tests and verify they fail**

Run:

```bash
python -m pytest tests/test_ad_pricing_v1655.py -q
```

Expected: collection fails because `ad_pricing.py` and `REGION_DISTRICTS` do not exist.

- [ ] **Step 3: Convert the flat catalog into a grouped backend catalog**

In `district_catalog.py`, define the complete catalog in this shape, copying every existing region/district pair from `static/regions.js` but no coordinates:

```python
"""Backend-owned Uzbekistan region/district catalog."""

REGION_DISTRICTS = {
    "Toshkent shahri": (
        "Bektemir", "Chilonzor", "Mirobod", "Mirzo Ulug'bek",
        "Olmazor", "Sergeli", "Uchtepa", "Shayxontohur",
        "Yakkasaroy", "Yashnobod", "Yunusobod",
    ),
    "Toshkent viloyati": (
        "Angren", "Bekobod", "Bo'ka", "Bo'stonliq (Gazalkent)",
        "Chinoz", "Chirchiq", "Nurafshon", "Ohangaron",
        "Oqqo'rg'on", "Parkent", "Piskent", "Qibray",
        "Yangiyo'l", "Zangiota",
    ),
    "Andijon viloyati": (
        "Andijon shahri", "Asaka", "Baliqchi", "Bo'z",
        "Buloqboshi", "Izboskan", "Jalaquduq", "Marhamat",
        "Oltinko'l", "Paxtaobod", "Qo'rg'ontepa", "Shahrixon",
        "Ulug'nor", "Xo'jaobod",
    ),
    "Farg'ona viloyati": (
        "Farg'ona shahri", "Marg'ilon", "Qo'qon", "Quvasoy",
        "Beshariq", "Bog'dod", "Buvayda", "Dang'ara", "Furqat",
        "Qo'shtepa", "Rishton", "So'x", "Toshloq", "Uchko'prik",
        "Yozyovon",
    ),
    "Namangan viloyati": (
        "Namangan shahri", "Chortoq", "Chust", "Kosonsoy",
        "Mingbuloq", "Norin", "Pop", "To'raqo'rg'on",
        "Uchqo'rg'on", "Uychi", "Yangiqo'rg'on",
    ),
    "Samarqand viloyati": (
        "Samarqand shahri", "Kattaqo'rg'on", "Bulung'ur",
        "Ishtixon", "Jomboy", "Qo'shrabot", "Narpay (Oqtosh)",
        "Nurobod", "Oqdaryo", "Pastdarg'om", "Paxtachi",
        "Payariq", "Toyloq", "Urgut",
    ),
    "Buxoro viloyati": (
        "Buxoro shahri", "Kogon", "G'ijduvon", "Jondor",
        "Qorako'l", "Qorovulbozor", "Olot", "Peshku", "Romitan",
        "Shofirkon", "Vobkent",
    ),
    "Qashqadaryo viloyati": (
        "Qarshi", "Shahrisabz", "Kitob", "G'uzor", "Qamashi",
        "Koson", "Mirishkor (Pomuq)", "Muborak", "Nishon",
        "Chiroqchi", "Yakkabog'", "Dehqonobod", "Kasbi",
    ),
    "Surxondaryo viloyati": (
        "Termiz", "Denov", "Boysun", "Sho'rchi", "Angor",
        "Jarqo'rg'on", "Qiziriq", "Qumqo'rg'on", "Muzrabot",
        "Oltinsoy", "Sariosiyo", "Sherobod", "Uzun",
    ),
    "Jizzax viloyati": (
        "Jizzax shahri", "Arnasoy", "Baxmal", "Do'stlik",
        "Forish", "G'allaorol", "Mirzacho'l", "Paxtakor",
        "Yangiobod", "Zomin", "Zarbdor", "Sharof Rashidov",
    ),
    "Sirdaryo viloyati": (
        "Guliston", "Yangiyer", "Shirin", "Boyovut",
        "Sayxunobod", "Sardoba", "Mirzaobod", "Oqoltin",
        "Xovos", "Sirdaryo",
    ),
    "Navoiy viloyati": (
        "Navoiy shahri", "Zarafshon", "Karmana", "Konimex",
        "Qiziltepa", "Navbahor", "Nurota", "Tomdi", "Uchquduq",
        "Xatirchi",
    ),
    "Xorazm viloyati": (
        "Urganch", "Xiva", "Bog'ot", "Gurlan", "Xonqa",
        "Hazorasp", "Qo'shko'pir", "Shovot", "Yangiariq",
        "Yangibozor",
    ),
    "Qoraqalpog'iston Respublikasi": (
        "Nukus", "Beruniy", "Chimboy", "Ellikqal'a (Bo'ston)",
        "Kegeyli", "Mo'ynoq", "Qonliko'l", "Qo'ng'irot",
        "Qorao'zak", "Shumanay", "Taxtako'pir", "To'rtko'l",
        "Xo'jayli", "Amudaryo (Mang'it)",
    ),
}

DISTRICT_NAMES = tuple(
    district
    for districts in REGION_DISTRICTS.values()
    for district in districts
)
```

The actual mapping must include all entries from the current JavaScript catalog. Keep region display spelling byte-for-byte equal to `static/regions.js`. Do not import or parse the JavaScript file at runtime.

- [ ] **Step 4: Implement the pure pricing and scheduling service**

Create `ad_pricing.py` with these implementation rules:

```python
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import re
import unicodedata

from district_catalog import REGION_DISTRICTS


VALID_AD_DURATIONS = (1, 3, 7, 14, 30)
FULL_HOUR_RE = re.compile(r"^(?:[01]\d|2[0-3]):00$")


class AdPricingError(ValueError):
    pass


def normalize_ad_geo(value):
    text = unicodedata.normalize(
        "NFKC", str(value or "")
    ).casefold().replace("ʻ", "'").replace("’", "'")
    text = re.sub(
        r"\b(viloyati|viloyat|shahri|shahar|tumani|tuman)\b",
        "",
        text,
    )
    return re.sub(r"[^a-z0-9'\u0400-\u04ff]+", "", text)


def _catalog_indexes():
    regions = {}
    districts = {}
    all_keys = set()
    for region, names in REGION_DISTRICTS.items():
        region_key = normalize_ad_geo(region)
        region_keys = set()
        for name in names:
            district_key = normalize_ad_geo(name)
            region_keys.add(district_key)
            all_keys.add((region_key, district_key))
        regions[region_key] = region_keys
        districts[region_key] = {
            normalize_ad_geo(name): name for name in names
        }
    return regions, districts, all_keys


REGION_KEYS, DISTRICT_KEYS, ALL_DISTRICT_KEYS = _catalog_indexes()


def clean_ad_targets(raw):
    if not isinstance(raw, list):
        raise AdPricingError("Reklama hududlarini tanlang.")
    result, seen = [], set()
    for item in raw[:30]:
        if not isinstance(item, dict):
            continue
        level = str(item.get("level") or "").strip().lower()
        region = str(item.get("region") or "").strip()
        district = str(item.get("district") or "").strip()
        if level not in ("district", "region", "republic"):
            continue
        if level == "region" and not region:
            continue
        if level == "district" and not (region and district):
            continue
        if level == "republic":
            region = district = ""
        key = (level, normalize_ad_geo(region), normalize_ad_geo(district))
        if key not in seen:
            seen.add(key)
            result.append({
                "level": level,
                "region": region,
                "district": district,
            })
    if not result:
        raise AdPricingError("Kamida bitta hudud tanlang.")
    if any(item["level"] == "republic" for item in result) and len(result) > 1:
        raise AdPricingError(
            "Respublika tanlansa boshqa hudud qo'shilmaydi."
        )
    return result


def expand_targets_to_district_keys(targets):
    expanded = set()
    for target in targets:
        level = target["level"]
        if level == "republic":
            expanded.update(ALL_DISTRICT_KEYS)
            continue
        region_key = normalize_ad_geo(target.get("region"))
        if region_key not in REGION_KEYS:
            raise AdPricingError("Tanlangan viloyat backend katalogida yo'q.")
        if level == "region":
            expanded.update(
                (region_key, district_key)
                for district_key in REGION_KEYS[region_key]
            )
            continue
        district_key = normalize_ad_geo(target.get("district"))
        if district_key not in REGION_KEYS[region_key]:
            raise AdPricingError("Tanlangan tuman backend katalogida yo'q.")
        expanded.add((region_key, district_key))
    if not expanded:
        raise AdPricingError("Hudud katalogga yoyilmadi.")
    return tuple(
        region_key + ":" + district_key
        for region_key, district_key in sorted(expanded)
    )


def full_hour(value):
    text = str(value or "").strip()
    if not FULL_HOUR_RE.fullmatch(text):
        raise AdPricingError("Vaqt faqat to'liq HH:00 soat bo'lishi kerak.")
    return int(text[:2])


def hours_per_day(all_day, start, end):
    if bool(all_day):
        return 24
    start_hour, end_hour = full_hour(start), full_hour(end)
    if start_hour == end_hour:
        raise AdPricingError(
            "Boshlanish va tugash soati bir xil bo'lmasin."
        )
    return (end_hour - start_hour) % 24


def calculate_ad_price(
    *, targets, duration_days, daily_all_day, daily_start, daily_end,
    district_hour_rate,
):
    try:
        days = int(duration_days)
        rate = int(district_hour_rate)
    except (TypeError, ValueError):
        raise AdPricingError("Reklama narxi yoki davomiyligi noto'g'ri.")
    if days not in VALID_AD_DURATIONS:
        raise AdPricingError("Kunlar 1, 3, 7, 14 yoki 30 bo'lishi kerak.")
    if rate < 0:
        raise AdPricingError("Bir tuman/soat narxi noto'g'ri.")
    cleaned = clean_ad_targets(targets)
    districts = expand_targets_to_district_keys(cleaned)
    daily_hours = hours_per_day(
        daily_all_day, daily_start, daily_end
    )
    quantity = len(districts) * daily_hours * days
    return {
        "targets": cleaned,
        "district_count": len(districts),
        "hours_per_day": daily_hours,
        "duration_days": days,
        "district_hour_rate": rate,
        "billable_district_hours": quantity,
        "total": quantity * rate,
        "currency": "UZS",
    }
```

Implement the date/schedule functions using Uzbekistan’s fixed `UTC+05:00` offset. `first_schedule_start` must combine a `YYYY-MM-DD` date with `00:00` for all-day or with `daily_start` otherwise. `shift_schedule_start` returns the requested start when `approved_at <= requested_start_at`; otherwise it finds the next occurrence of `00:00` (all-day) or `daily_start` whose timestamp is greater than or equal to approval. `schedule_end_at` returns:

```python
if daily_all_day:
    return actual_start_at + duration_days * 86400
return (
    actual_start_at
    + (duration_days - 1) * 86400
    + hours_each_day * 3600
)
```

Reject invalid `YYYY-MM-DD` input with `AdPricingError("Boshlanish sanasi noto'g'ri.")`.

- [ ] **Step 5: Run pure-domain tests**

Run:

```bash
python -m pytest tests/test_ad_pricing_v1655.py -q
python -m pytest tests/test_location_keys.py -q
```

Expected: both files pass; the existing test proving the backend does not parse `static/regions.js` remains green.

- [ ] **Step 6: Commit the domain checkpoint**

```bash
git add ad_pricing.py district_catalog.py tests/test_ad_pricing_v1655.py
git commit -m "feat: add hourly advertisement pricing domain"
```

If this directory is still not a Git clone, record these three files as the checkpoint and continue without a commit.

---

### Task 2: Database and Immutable Payment Snapshots

**Files:**
- Modify: `database.py:1398-1442`
- Modify: `payments.py:1-210,350-430`
- Test: `tests/test_advertisement_hourly_api_v1655.py`
- Modify: `tests/test_payment_api_v1652.py`

**Interfaces:**
- Consumes: `calculate_ad_price` result keys from Task 1.
- Produces:
  - advertisement columns `district_count`, `hours_per_day`, `district_hour_rate`, `billable_district_hours`, and `price_code`
  - payment column `target_snapshot_json`
  - price code `advertisement_district_hour`
  - `create_payment_request(..., target_snapshot: dict | None = None)`

- [ ] **Step 1: Write failing migration and snapshot tests**

In `tests/test_advertisement_hourly_api_v1655.py`, add a temporary-database test that calls the normal schema initializer and asserts:

```python
def test_hourly_price_and_snapshot_columns_are_installed(self):
    conn = self.db()
    ad_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(advertisements)")
    }
    payment_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(payment_requests)")
    }
    self.assertTrue({
        "district_count",
        "hours_per_day",
        "district_hour_rate",
        "billable_district_hours",
        "price_code",
    }.issubset(ad_columns))
    self.assertIn("target_snapshot_json", payment_columns)
    hourly = conn.execute(
        "SELECT * FROM platform_prices WHERE price_code=?",
        ("advertisement_district_hour",),
    ).fetchone()
    legacy = conn.execute(
        "SELECT * FROM platform_prices WHERE price_code=?",
        ("advertisement_district_day",),
    ).fetchone()
    self.assertEqual(hourly["amount_uzs"], 20_000)
    self.assertEqual(hourly["active"], 1)
    self.assertEqual(legacy["active"], 0)
    conn.close()
```

Add a direct `create_payment_request` test:

```python
def test_payment_request_keeps_immutable_ad_calculation_snapshot(self):
    payment = create_payment_request(
        self.conn,
        owner={"actor_type": "user", "user_id": self.user_id},
        service="advertisement",
        target={"target_id": 77, "quantity": 78, "payment_method_id": 1},
        target_snapshot={
            "district_count": 13,
            "hours_per_day": 2,
            "duration_days": 3,
            "district_hour_rate": 20_000,
            "billable_district_hours": 78,
            "schedule_start": 1_785_000_000,
            "daily_start": "11:00",
            "daily_end": "13:00",
        },
        price={
            "price_code": "advertisement_district_hour",
            "amount": 20_000,
            "currency": "UZS",
        },
        receipt=self.receipt,
        now=1_784_000_000,
    )
    row = self.conn.execute(
        "SELECT * FROM payment_requests WHERE id=?", (payment["id"],)
    ).fetchone()
    self.assertEqual(row["quantity"], 78)
    self.assertEqual(row["unit_price_snapshot"], 20_000)
    self.assertEqual(row["amount_snapshot"], 1_560_000)
    self.assertEqual(
        json.loads(row["target_snapshot_json"])["district_count"], 13
    )
```

- [ ] **Step 2: Run the migration tests and verify failure**

Run:

```bash
python -m pytest tests/test_advertisement_hourly_api_v1655.py -q
```

Expected: failures for missing columns, missing hourly rule, and missing `target_snapshot` argument.

- [ ] **Step 3: Add advertisement billing columns**

After the existing advertisement `ALTER TABLE` checks in `database.py`, add one guarded migration per column:

```python
ad_snapshot_columns = {
    "district_count": (
        "INTEGER NOT NULL DEFAULT 0"
    ),
    "hours_per_day": (
        "INTEGER NOT NULL DEFAULT 0"
    ),
    "district_hour_rate": (
        "INTEGER NOT NULL DEFAULT 0"
    ),
    "billable_district_hours": (
        "INTEGER NOT NULL DEFAULT 0"
    ),
    "price_code": (
        "TEXT NOT NULL DEFAULT ''"
    ),
}
for name, definition in ad_snapshot_columns.items():
    if name not in adcols:
        conn.execute(
            f"ALTER TABLE advertisements ADD COLUMN {name} {definition}"
        )
```

Do not update existing advertisement rows. Zero/empty values identify legacy rows.

- [ ] **Step 4: Add the hourly price and deactivate legacy for new requests**

In `payments.py`, retain `advertisement_district_day` and add:

```python
"advertisement_district_hour": {
    "service_type": "advertisement",
    "unit": "district_hour",
    "amount_uzs": 20_000,
},
```

Extend each price rule with a `default_active` value or compute it in `ensure_default_prices`:

```python
default_active = (
    0 if price_code == "advertisement_district_day" else 1
)
```

Insert using that value instead of hard-coded `1`. After inserting defaults, run this idempotent migration:

```python
conn.execute(
    """
    UPDATE platform_prices
    SET active=0
    WHERE price_code='advertisement_district_day'
    """
)
```

Pending legacy requests remain approvable because approval reads their snapshot and does not call `_resolve_price`. New requests are rejected because `_resolve_price` requires `active=1`. This update never changes a legacy payment’s stored `unit_price_snapshot`, `quantity`, or `amount_snapshot`.

- [ ] **Step 5: Add payment snapshot storage**

In `ensure_payment_schema`, add `target_snapshot_json TEXT NOT NULL DEFAULT '{}'` to new-table SQL and a guarded `ALTER TABLE` for existing databases. Change the creation signature to:

```python
def create_payment_request(
    conn, *, owner, service, target, price, receipt, now,
    receipt_claimer=None, target_snapshot=None,
):
```

Serialize only a dictionary:

```python
snapshot = target_snapshot if isinstance(target_snapshot, dict) else {}
snapshot_json = json.dumps(
    snapshot,
    ensure_ascii=False,
    separators=(",", ":"),
    sort_keys=True,
)
```

Add `target_snapshot_json` to the `INSERT` columns and values. Add the snapshot’s `billable_district_hours` and `schedule_start` to the initial payment event metadata, but do not put secrets or receipt paths in event metadata.

- [ ] **Step 6: Run payment/schema tests**

Run:

```bash
python -m pytest tests/test_advertisement_hourly_api_v1655.py -q
python -m pytest tests/test_payment_api_v1652.py -q
```

Expected: new schema/snapshot cases pass; existing subscription, receipt, and legacy payment state-machine tests remain green.

- [ ] **Step 7: Commit the persistence checkpoint**

```bash
git add database.py payments.py tests/test_advertisement_hourly_api_v1655.py tests/test_payment_api_v1652.py
git commit -m "feat: persist hourly advertisement payment snapshots"
```

---

### Task 3: Backend Advertisement Quote and Creation API

**Files:**
- Modify: `api.py:3873-4215`
- Test: `tests/test_advertisement_hourly_api_v1655.py`

**Interfaces:**
- Consumes: `calculate_ad_price`, `first_schedule_start`, `clean_ad_targets`, and `normalize_ad_geo` from Task 1; active price row from Task 2.
- Produces:
  - `GET /api/advertisements/rates`
  - `POST /api/advertisements/price`
  - `POST /api/advertisements`
  - advertisement API fields matching the persisted snapshot.

- [ ] **Step 1: Write failing quote and create endpoint tests**

Add tests that authenticate a normal user and assert:

```python
def test_quote_uses_server_hourly_rate_and_full_hours(self):
    response = self.client.post(
        "/api/advertisements/price",
        headers=self.user_auth,
        json={
            "targets": [{
                "level": "region",
                "region": "Surxondaryo viloyati",
            }],
            "duration_days": 3,
            "daily_all_day": False,
            "daily_start": "11:00",
            "daily_end": "13:00",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json(), {
        "district_count": 13,
        "hours_per_day": 2,
        "duration_days": 3,
        "district_hour_rate": 20_000,
        "billable_district_hours": 78,
        "total": 1_560_000,
        "currency": "UZS",
    })


def test_quote_rejects_minute_times(self):
    response = self.quote(daily_start="11:02", daily_end="13:00")
    self.assertEqual(response.status_code, 400)
    self.assertIn("HH:00", response.json()["detail"])


def test_create_ignores_client_price_and_persists_server_snapshot(self):
    response = self.create_ad(
        targets=[{
            "level": "region",
            "region": "Surxondaryo viloyati",
        }],
        start_date="2026-07-27",
        duration_days=3,
        daily_all_day=False,
        daily_start="11:00",
        daily_end="13:00",
        price=1,
        district_count=1,
    )
    self.assertEqual(response.status_code, 200)
    body = response.json()
    self.assertEqual(body["price"], 1_560_000)
    self.assertEqual(body["district_count"], 13)
    self.assertEqual(body["hours_per_day"], 2)
    self.assertEqual(body["billable_district_hours"], 78)
    self.assertEqual(body["price_code"], "advertisement_district_hour")
```

Also test allowed durations, unknown targets, overlap de-duplication, all-day 24-hour calculation, and a start date more than 180 days away.

- [ ] **Step 2: Run endpoint tests and verify failure**

Run:

```bash
python -m pytest tests/test_advertisement_hourly_api_v1655.py -q
```

Expected: current endpoints return daily rates/discounts and accept minute values, so the new assertions fail.

- [ ] **Step 3: Replace hard-coded rates and discounts**

Import from `ad_pricing.py` and `payments.py`:

```python
from ad_pricing import (
    AdPricingError,
    calculate_ad_price,
    clean_ad_targets,
    first_schedule_start,
    normalize_ad_geo,
)
from payments import ensure_default_prices
```

Remove `AD_RATES`, `_ad_discount`, and `_ad_price`. Replace `_ad_norm` calls with `normalize_ad_geo`. Keep `_ad_matches` behavior unchanged except for using the shared normalizer.

Add one helper:

```python
def _active_ad_hour_rate(conn):
    ensure_default_prices(conn)
    row = conn.execute(
        """
        SELECT amount_uzs FROM platform_prices
        WHERE price_code='advertisement_district_hour'
          AND service_type='advertisement' AND active=1
        """
    ).fetchone()
    if not row:
        raise HTTPException(400, "Soatlik reklama narxi faol emas.")
    return int(row["amount_uzs"])
```

Convert `AdPricingError` into `HTTPException(400, str(exc))` at API boundaries.

- [ ] **Step 4: Return server-authoritative rates and quotes**

`GET /api/advertisements/rates` returns:

```python
{
    "price_code": "advertisement_district_hour",
    "district_hour_rate": _active_ad_hour_rate(conn),
    "duration_days": [1, 3, 7, 14, 30],
    "currency": "UZS",
    "note": (
        "Reklama kvitansiya yuborilib, administrator "
        "tasdiqlagandan keyin faol bo'ladi."
    ),
}
```

`POST /api/advertisements/price` loads the active rate and calls `calculate_ad_price`. Return only these public keys:

```python
(
    "district_count",
    "hours_per_day",
    "duration_days",
    "district_hour_rate",
    "billable_district_hours",
    "total",
    "currency",
)
```

- [ ] **Step 5: Make advertisement creation exact-hour and snapshot-based**

Change the request contract from client `start_at` to `start_date`. Call:

```python
pricing = calculate_ad_price(
    targets=b.get("targets"),
    duration_days=b.get("duration_days"),
    daily_all_day=bool(b.get("daily_all_day", True)),
    daily_start=b.get("daily_start") or "00:00",
    daily_end=b.get("daily_end") or "00:00",
    district_hour_rate=_active_ad_hour_rate(conn),
)
schedule_start = first_schedule_start(
    start_date=b.get("start_date"),
    daily_all_day=bool(b.get("daily_all_day", True)),
    daily_start=b.get("daily_start") or "00:00",
)
```

Validate the selected date is not earlier than today in Uzbekistan and is no more than 180 days ahead. Store a provisional `end_at` with `schedule_end_at`; payment approval may shift both boundaries later.

Insert these backend-calculated values:

```python
targets_json=json.dumps(pricing["targets"], ensure_ascii=False)
start_at=schedule_start
end_at=provisional_end
duration_days=pricing["duration_days"]
price=pricing["total"]
district_count=pricing["district_count"]
hours_per_day=pricing["hours_per_day"]
district_hour_rate=pricing["district_hour_rate"]
billable_district_hours=pricing["billable_district_hours"]
price_code="advertisement_district_hour"
status="payment_pending"
```

Ignore any client `price`, `district_count`, `hours_per_day`, `district_hour_rate`, or `billable_district_hours` properties.

Extend `_ad_dict` with the five snapshot fields using safe defaults for old rows.

- [ ] **Step 6: Run quote/create and legacy advertisement tests**

Run:

```bash
python -m pytest tests/test_advertisement_hourly_api_v1655.py -q
python -m pytest tests/test_ad_banner_labels_v1650_frontend.py -q
python -m pytest tests/test_public_access_contract.py -q
```

Expected: hourly quote/create tests pass and public advertisement retrieval remains green.

- [ ] **Step 7: Commit the advertisement API checkpoint**

```bash
git add api.py tests/test_advertisement_hourly_api_v1655.py
git commit -m "feat: calculate advertisements by district hour"
```

---

### Task 4: Server-Authoritative Advertisement Payment Requests

**Files:**
- Modify: `payment_api.py:95-260`
- Test: `tests/test_advertisement_hourly_api_v1655.py`
- Modify: `tests/test_payment_api_v1652.py`

**Interfaces:**
- Consumes: pending advertisement snapshot columns from Tasks 2–3.
- Produces:
  - `_owned_pending_advertisement(conn, owner, target_id)`
  - `_hourly_ad_payment_target(conn, owner, target, price_row) -> tuple[dict, dict]`
  - a payment request whose `quantity` and `amount_snapshot` cannot be manipulated by the browser.

- [ ] **Step 1: Write failing tamper-resistance tests**

Add API tests:

```python
def test_ad_payment_ignores_client_quantity_and_uses_owned_ad(self):
    ad = self.insert_hourly_pending_ad(
        user_id=self.user_id,
        district_count=13,
        hours_per_day=2,
        duration_days=3,
        rate=20_000,
        quantity=78,
        total=1_560_000,
    )
    response = self.submit_payment(
        price_code="advertisement_district_hour",
        target={"target_id": ad, "quantity": 1},
    )
    self.assertEqual(response.status_code, 201)
    payment = self.payment_row(response.json()["id"])
    self.assertEqual(payment["quantity"], 78)
    self.assertEqual(payment["amount_snapshot"], 1_560_000)


def test_ad_payment_rejects_another_users_ad(self):
    ad = self.insert_hourly_pending_ad(user_id=self.other_user_id)
    response = self.submit_payment(
        price_code="advertisement_district_hour",
        target={"target_id": ad},
    )
    self.assertEqual(response.status_code, 404)


def test_new_legacy_daily_payment_request_is_rejected(self):
    response = self.submit_payment(
        price_code="advertisement_district_day",
        target={"target_id": self.hourly_ad_id, "quantity": 1},
    )
    self.assertEqual(response.status_code, 400)
```

Also test business ownership and that an inactive/cancelled/already-paid ad cannot create a new pending payment.

- [ ] **Step 2: Run payment API tests and verify failure**

Run:

```bash
python -m pytest tests/test_advertisement_hourly_api_v1655.py -q
```

Expected: current code trusts `target.quantity`, so the tamper-resistance assertion fails.

- [ ] **Step 3: Resolve and validate the owned pending advertisement**

Add:

```python
def _owned_pending_advertisement(conn, *, user, business, actor_type, ad_id):
    if actor_type == "business":
        row = conn.execute(
            """
            SELECT * FROM advertisements
            WHERE id=? AND user_id=? AND business_id=?
              AND actor_type='business' AND status='payment_pending'
            """,
            (int(ad_id), int(user["id"]), int(business["id"])),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT * FROM advertisements
            WHERE id=? AND user_id=? AND business_id IS NULL
              AND actor_type='user' AND status='payment_pending'
            """,
            (int(ad_id), int(user["id"])),
        ).fetchone()
    if not row:
        raise HTTPException(404, "To'lov kutilayotgan reklama topilmadi.")
    return row
```

For an hourly request, require `row["price_code"] == "advertisement_district_hour"`, parse `row["targets_json"]`, and call the same Task 1 calculator again:

```python
pricing = calculate_ad_price(
    targets=json.loads(row["targets_json"] or "[]"),
    duration_days=int(row["duration_days"]),
    daily_all_day=bool(row["daily_all_day"]),
    daily_start=str(row["daily_start"]),
    daily_end=str(row["daily_end"]),
    district_hour_rate=int(price_row["amount_uzs"]),
)
quantity = pricing["billable_district_hours"]
expected_total = pricing["total"]
```

Before the request is created, update the pending advertisement’s `targets_json`, `district_count`, `hours_per_day`, `district_hour_rate`, `billable_district_hours`, and `price` to this fresh server calculation. This implements “final backend calculation at payment submission”; it does not alter any already-created payment request.

- [ ] **Step 4: Create the immutable target snapshot**

Pass this target and snapshot to `create_payment_request`:

```python
target={
    "target_id": int(ad["id"]),
    "quantity": quantity,
    "payment_method_id": method_id,
}
target_snapshot={
    "district_count": pricing["district_count"],
    "hours_per_day": pricing["hours_per_day"],
    "duration_days": pricing["duration_days"],
    "district_hour_rate": pricing["district_hour_rate"],
    "billable_district_hours": quantity,
    "schedule_start": int(ad["start_at"]),
    "daily_all_day": bool(ad["daily_all_day"]),
    "daily_start": str(ad["daily_start"]),
    "daily_end": str(ad["daily_end"]),
}
```

For subscription and listing requests, preserve current behavior. Remove the generic browser-controlled advertisement quantity branch.

- [ ] **Step 5: Run payment API regression**

Run:

```bash
python -m pytest tests/test_advertisement_hourly_api_v1655.py -q
python -m pytest tests/test_payment_api_v1652.py -q
python -m pytest tests/test_payment_security_v1652.py -q
```

Expected: tamper, ownership, receipt, duplicate-receipt, and existing state-machine tests pass.

- [ ] **Step 6: Commit the authoritative-payment checkpoint**

```bash
git add payment_api.py tests/test_advertisement_hourly_api_v1655.py tests/test_payment_api_v1652.py
git commit -m "fix: derive advertisement payments from server snapshots"
```

---

### Task 5: Approval Scheduling and Legacy Compatibility

**Files:**
- Modify: `payment_api.py:520-760`
- Modify: `api.py:4160-4215`
- Test: `tests/test_advertisement_hourly_api_v1655.py`
- Modify: `tests/test_payment_api_v1652.py`

**Interfaces:**
- Consumes: `shift_schedule_start`, `schedule_end_at`, and payment `target_snapshot_json`.
- Produces: `_activate_hourly_advertisement(...)` and `_activate_legacy_advertisement(...)` with explicit branching by `payment.price_code`.

- [ ] **Step 1: Write failing on-time, late, overnight, and legacy approval tests**

Add tests with a fixed `approved_at`:

```python
def test_on_time_approval_preserves_requested_schedule(self):
    payment_id = self.hourly_payment(
        schedule_start=self.uz_stamp(2026, 7, 27, 11),
        daily_start="11:00",
        daily_end="13:00",
        duration_days=3,
    )
    self.approve(payment_id, now=self.uz_stamp(2026, 7, 27, 10))
    ad = self.ad_for_payment(payment_id)
    self.assertEqual(ad["start_at"], self.uz_stamp(2026, 7, 27, 11))
    self.assertEqual(ad["end_at"], self.uz_stamp(2026, 7, 29, 13))


def test_late_approval_shifts_to_next_daily_start(self):
    payment_id = self.hourly_payment(
        schedule_start=self.uz_stamp(2026, 7, 27, 11),
        daily_start="11:00",
        daily_end="13:00",
        duration_days=3,
    )
    self.approve(payment_id, now=self.uz_stamp(2026, 7, 27, 12))
    ad = self.ad_for_payment(payment_id)
    self.assertEqual(ad["start_at"], self.uz_stamp(2026, 7, 28, 11))
    self.assertEqual(ad["end_at"], self.uz_stamp(2026, 7, 30, 13))


def test_late_overnight_approval_preserves_three_four_hour_windows(self):
    payment_id = self.hourly_payment(
        schedule_start=self.uz_stamp(2026, 7, 27, 22),
        daily_start="22:00",
        daily_end="02:00",
        duration_days=3,
        hours_per_day=4,
    )
    self.approve(payment_id, now=self.uz_stamp(2026, 7, 27, 23))
    ad = self.ad_for_payment(payment_id)
    self.assertEqual(ad["start_at"], self.uz_stamp(2026, 7, 28, 22))
    self.assertEqual(ad["end_at"], self.uz_stamp(2026, 7, 31, 2))


def test_existing_daily_payment_keeps_legacy_activation(self):
    payment_id, ad_id = self.insert_legacy_daily_payment(quantity=3)
    self.approve(payment_id, now=1_800_000_000)
    ad = self.ad(ad_id)
    self.assertEqual(ad["start_at"], 1_800_000_000)
    self.assertEqual(ad["end_at"], 1_800_000_000 + 3 * 86400)
```

- [ ] **Step 2: Run approval tests and verify failure**

Run:

```bash
python -m pytest tests/test_advertisement_hourly_api_v1655.py -q
```

Expected: the current activator sets every advertisement to `now + quantity days`, so schedule assertions fail.

- [ ] **Step 3: Split hourly and legacy activation**

In `_activate_approved_service`, branch:

```python
if payment["service_type"] == "advertisement":
    if payment["price_code"] == "advertisement_district_hour":
        return _activate_hourly_advertisement(
            conn, payment, now=now
        )
    return _activate_legacy_advertisement(
        conn, payment, now=now
    )
```

The hourly activator must:

1. parse `target_snapshot_json`;
2. verify `target_id`, ownership, `payment_pending`, positive `duration_days`, and positive `hours_per_day`;
3. compute `actual_start_at = shift_schedule_start(...)`;
4. compute `actual_end_at = schedule_end_at(...)`;
5. update only that advertisement to `active`, preserving all billing fields and daily window;
6. write the shifted start/end into payment-event metadata.

The legacy activator retains the existing `start_at=now`, `end_at=now+quantity*86400` behavior. Do not require new snapshot fields for legacy rows.

- [ ] **Step 4: Keep active-window filtering exact**

In `active_advertisements`, retain the daily-window logic and replace permissive parse errors with explicit legacy fallback:

```python
if int(_row_val(r, "hours_per_day", 0) or 0) > 0:
    # New hourly rows have already validated HH:00 values.
    start_hour = int(r["daily_start"][:2])
    end_hour = int(r["daily_end"][:2])
    minute_now = uz_now.tm_hour * 60 + uz_now.tm_min
    start_minute = start_hour * 60
    end_minute = end_hour * 60
    in_window = (
        start_minute <= minute_now < end_minute
        if start_minute < end_minute
        else minute_now >= start_minute or minute_now < end_minute
    )
else:
    # Preserve the current minute-aware legacy parsing.
```

The overall `start_at <= now < end_at` SQL boundary remains in place.

- [ ] **Step 5: Run approval and active-window regression**

Run:

```bash
python -m pytest tests/test_advertisement_hourly_api_v1655.py -q
python -m pytest tests/test_payment_api_v1652.py -q
python -m pytest tests/test_ad_banner_labels_v1650_frontend.py -q
```

Expected: on-time, late, overnight, all-day, and legacy approval cases pass.

- [ ] **Step 6: Commit the scheduling checkpoint**

```bash
git add payment_api.py api.py tests/test_advertisement_hourly_api_v1655.py tests/test_payment_api_v1652.py
git commit -m "feat: preserve paid advertisement schedules on approval"
```

---

### Task 6: Advertisement Form and Price Breakdown

**Files:**
- Modify: `static/index.html:2138-2172,2430-2464,11634-11645,13195-13375`
- Test: `tests/test_advertisement_hourly_frontend_v1655_contract.py`
- Modify: `tests/test_payment_frontend_v1652_contract.py`

**Interfaces:**
- Consumes: the quote response from Task 3 and hourly payment contract from Task 4.
- Produces: exact-hour UI, date-only schedule start, formula display, and `advertisement_district_hour` payment submissions.

- [ ] **Step 1: Write failing frontend contract tests**

Create `tests/test_advertisement_hourly_frontend_v1655_contract.py`:

```python
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")


class HourlyAdvertisementFrontendContractTests(unittest.TestCase):
    def test_new_payment_code_is_used_and_legacy_code_is_absent(self):
        self.assertIn('"advertisement_district_hour"', HTML)
        self.assertNotIn('"advertisement_district_day"', HTML)

    def test_start_is_date_only_for_both_forms(self):
        self.assertRegex(
            HTML, r'type="date" id="baStart"'
        )
        self.assertRegex(
            HTML, r'type="date" id="uaStart"'
        )

    def test_time_controls_only_offer_full_hours(self):
        for prefix in ("ba", "ua"):
            for suffix in ("DailyStart", "DailyEnd"):
                match = re.search(
                    rf'<select[^>]+id="{prefix}{suffix}"[^>]*>(.*?)</select>',
                    HTML,
                    re.S,
                )
                self.assertIsNotNone(match)
                values = re.findall(r'value="([^"]+)"', match.group(1))
                self.assertEqual(len(values), 24)
                self.assertTrue(all(re.fullmatch(r"\d{2}:00", v) for v in values))

    def test_duration_labels_have_no_discount_copy(self):
        self.assertNotIn("% chegirma", HTML)
        self.assertNotIn("p.discount", HTML)

    def test_quote_includes_window_and_formula_fields(self):
        self.assertIn("daily_all_day:allDay", HTML)
        self.assertIn("daily_start:dailyStart", HTML)
        self.assertIn("daily_end:dailyEnd", HTML)
        for key in (
            "district_count",
            "hours_per_day",
            "duration_days",
            "district_hour_rate",
            "billable_district_hours",
        ):
            self.assertIn(key, HTML)

    def test_browser_does_not_send_ad_quantity(self):
        payment_function = re.search(
            r"function openAdvertisementPayment\(.*?\n  }",
            HTML,
            re.S,
        ).group(0)
        self.assertNotIn("quantity:", payment_function)
```

Update `tests/test_payment_frontend_v1652_contract.py` so it expects the hourly code and no longer expects the legacy code.

- [ ] **Step 2: Run frontend contract tests and verify failure**

Run:

```bash
python -m pytest tests/test_advertisement_hourly_frontend_v1655_contract.py tests/test_payment_frontend_v1652_contract.py -q
```

Expected: failures for datetime inputs, minute-capable controls, discount text, old price code, and browser quantity.

- [ ] **Step 3: Replace date/time controls**

For both `ba` and `ua` forms:

- change `type="datetime-local"` start to `type="date"`;
- replace both `type="time"` fields with `<select class="input">`;
- include exactly 24 `<option>` values from `00:00` through `23:00`;
- preserve default start `19:00` and default end `21:00`;
- keep the all-day checkbox;
- remove all discount text from day options;
- update the info copy to say payment is manually reviewed by an administrator.

Do not change image upload, crop, target selection, actor selection, or feature guards.

- [ ] **Step 4: Update client quote and schedule payloads**

Change `adSetDefaultStart` to set local `YYYY-MM-DD` only. In `calcAdPrice` send:

```javascript
var allDay=el(prefix+"AllDay").checked;
var dailyStart=el(prefix+"DailyStart").value||"00:00";
var dailyEnd=el(prefix+"DailyEnd").value||"00:00";
api("POST","/api/advertisements/price",{
  targets:st.targets,
  duration_days:days,
  daily_all_day:allDay,
  daily_start:dailyStart,
  daily_end:dailyEnd
})
```

Render:

```javascript
el(prefix+"Price").textContent=fmtMoney(p.total);
el(prefix+"PriceNote").textContent=
  p.district_count+" tuman × "+
  p.hours_per_day+" soat × "+
  p.duration_days+" kun × "+
  fmtMoney(p.district_hour_rate);
```

Trigger `calcAdPrice(prefix)` on all-day, start hour, end hour, duration, and target changes.

When creating the advertisement send `start_date:start`, not `start_at`. Do not convert the selected date with `new Date()` because that reintroduces timezone ambiguity.

- [ ] **Step 5: Use the hourly payment code without client quantity**

Replace `openAdvertisementPayment` with:

```javascript
function openAdvertisementPayment(ad,actor){
  var quantity=Math.max(
    1,parseInt(ad&&ad.billable_district_hours||1,10)||1
  );
  openPaymentRequest({
    actor_type:actor==="business"?"business":"user",
    service_type:"advertisement",
    price_code:"advertisement_district_hour",
    label:"Reklama · "+quantity+" tuman-soat",
    subtitle:"Reklama administrator tasdig‘idan keyin ko‘rsatiladi.",
    display_amount:Number(ad.price||0),
    target:{target_id:Number(ad.id)}
  }).catch(function(){});
}
```

In `openPaymentRequest`, keep the existing subscription/listing calculation and allow the advertisement context to provide a display-only amount:

```javascript
var catalogAmount=Number(price.amount_uzs||0)*quantity;
var displayAmount=Number(PAYMENT_CONTEXT.display_amount||0);
el("paymentAmountLabel").textContent=fmtMoney(
  displayAmount>0?displayAmount:catalogAmount
);
```

`display_amount` is never copied into `submitPaymentRequest`; the payment POST contains only `target_id` and the backend derives quantity and total.

Update “my advertisements” cards to display:

```text
13 tuman · kuniga 2 soat · 3 kun
1 560 000 so‘m
```

For legacy rows (`district_count == 0`), preserve the old duration/time wording.

- [ ] **Step 6: Run frontend and JavaScript checks**

Run:

```bash
python -m pytest tests/test_advertisement_hourly_frontend_v1655_contract.py tests/test_payment_frontend_v1652_contract.py -q
python - <<'PY'
from pathlib import Path
import re
html = Path("static/index.html").read_text(encoding="utf-8")
scripts = re.findall(r"<script(?: [^>]*)?>(.*?)</script>", html, re.S)
Path("/tmp/koprik-inline.js").write_text("\n".join(scripts), encoding="utf-8")
PY
node --check /tmp/koprik-inline.js
```

Expected: tests pass and Node reports no syntax errors.

- [ ] **Step 7: Commit the frontend checkpoint**

```bash
git add static/index.html tests/test_advertisement_hourly_frontend_v1655_contract.py tests/test_payment_frontend_v1652_contract.py
git commit -m "feat: add exact-hour advertisement form"
```

---

### Task 7: Admin Price, Build Marker, and Full Regression

**Files:**
- Modify: `admin/app.js`
- Modify: `payment_api.py:340-430`
- Modify: `main.py`
- Test: `tests/test_advertisement_hourly_frontend_v1655_contract.py`
- Test: `tests/test_advertisement_hourly_api_v1655.py`
- Modify: `tests/test_production_foundation.py`

**Interfaces:**
- Consumes: hourly price rule and all preceding API/frontend behavior.
- Produces: one visible editable advertisement base rate and production build `v1655`.

- [ ] **Step 1: Add failing admin/build assertions**

Extend the frontend contract test:

```python
ADMIN_JS = (ROOT / "admin" / "app.js").read_text(encoding="utf-8")


def test_admin_labels_hourly_price_and_hides_legacy(self):
    self.assertIn("advertisement_district_hour", ADMIN_JS)
    self.assertIn("1 tuman / 1 soat", ADMIN_JS)
```

Add an API assertion that `GET /api/admin/prices` returns `advertisement_district_hour` and does not return `advertisement_district_day`.

Update the production/build contract to expect `v1655` and:

```python
assert features["hourly_ad_pricing_v1655"] is True
```

- [ ] **Step 2: Run admin/build tests and verify failure**

Run:

```bash
python -m pytest tests/test_advertisement_hourly_frontend_v1655_contract.py tests/test_advertisement_hourly_api_v1655.py tests/test_production_foundation.py -q
```

Expected: the hourly admin label/filter and `v1655` marker are missing.

- [ ] **Step 3: Filter the internal legacy price from admin output**

Change `GET /api/admin/prices` query to:

```sql
SELECT * FROM platform_prices
WHERE price_code!='advertisement_district_day'
ORDER BY id
```

Do not delete the legacy database row. Existing payments still reference it.

In `admin/app.js`, map price codes to friendly labels:

```javascript
var PRICE_LABELS={
  advertisement_district_hour:"Reklama · 1 tuman / 1 soat",
  listing_publish:"E'lon joylash"
};
```

Keep subscription labels and update controls unchanged.

- [ ] **Step 4: Set build and readiness markers**

Update the central build constant/response in `main.py` from `v1654` to `v1655`. Add:

```python
"hourly_ad_pricing_v1655": True,
```

to the public build feature map. Do not change:

```python
"stories_enabled": False
"listings_enabled": False
"general_chat_enabled": False
"systemization_enabled": False
```

- [ ] **Step 5: Run focused regression**

Run:

```bash
python -m pytest \
  tests/test_ad_pricing_v1655.py \
  tests/test_advertisement_hourly_api_v1655.py \
  tests/test_advertisement_hourly_frontend_v1655_contract.py \
  tests/test_payment_api_v1652.py \
  tests/test_payment_frontend_v1652_contract.py \
  tests/test_mvp_guards_v1651_api.py \
  tests/test_production_foundation.py -q
```

Expected: all focused tests pass.

- [ ] **Step 6: Run complete regression and syntax verification**

Run:

```bash
python -m pytest tests -q
python -m compileall -q .
node --check /tmp/koprik-inline.js
```

Expected: no failures; the previous 358-test baseline plus the newly added tests all pass.

- [ ] **Step 7: Inspect the final diff scope**

Run in a Git clone:

```bash
git status --short
git diff --stat
git diff --check
```

Expected changed production files:

```text
ad_pricing.py
district_catalog.py
database.py
payments.py
payment_api.py
api.py
static/index.html
admin/app.js
main.py
```

Expected test files are the ones listed in this plan. No story, listing, chat, subscription, search, map, or systemization implementation file should have unrelated behavior changes.

- [ ] **Step 8: Record handoff facts**

Run:

```bash
wc -l static/index.html
python - <<'PY'
import main
print(main.APP_BUILD if hasattr(main, "APP_BUILD") else "v1655")
PY
```

Report the exact changed-file list, build value, `static/index.html` line count, and full test result to the user.

- [ ] **Step 9: Commit the completed hourly-pricing feature**

```bash
git add admin/app.js payment_api.py main.py tests/test_advertisement_hourly_frontend_v1655_contract.py tests/test_advertisement_hourly_api_v1655.py tests/test_production_foundation.py
git commit -m "feat: release hourly advertisement pricing v1655"
```

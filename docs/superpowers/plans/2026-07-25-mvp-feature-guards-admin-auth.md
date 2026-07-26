# MVP Feature Guards and Admin Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ko‘prikning MVPga kirmaydigan funksiyalarini frontend va backendda bloklash, obuna bo‘lingan profillar qatorini istoriyalardan ajratish va `admin.koprik.uz` uchun Telegram ID asosidagi xavfsiz admin sessiyasini yaratish.

**Architecture:** Feature flaglarning boshlang‘ich qiymati Railway muhitidan, audit qilinadigan override qiymati SQLite’dan olinadi; yakuniy ruxsatni faqat backend beradi. Admin autentifikatsiyasi oddiy foydalanuvchi tokenidan alohida cookie-sessiya bo‘ladi. Umumiy `Suhbatlarim` bloklanadi, ammo buyurtma ichidagi `/api/orders/{id}/chat` ishlashda davom etadi.

**Tech Stack:** Python 3.12, FastAPI, SQLite/WAL, vanilla HTML/CSS/JavaScript, `unittest`, FastAPI `TestClient`.

## Global Constraints

- Boshlang‘ich versiya: `APP_BUILD = "v1650"` va `static/index.html` 13 614 qator.
- Ushbu bosqich yakunida BUILD: `v1651`.
- `MVP_LISTINGS_ENABLED=0`, `MVP_STORIES_ENABLED=0`, `MVP_CHAT_ENABLED=0`, `MVP_SYSTEMIZATION_ENABLED=0`.
- `Buyurtmalar`, `Xizmat buyurtmalari`, `/api/orders/*` va `/api/orders/{id}/chat` bloklanmaydi.
- Qidiruv, xarita, profil, mahsulot, xizmat, obuna, reklama, fikrlar va bildirishnomalar ishlashda davom etadi.
- Bosh sahifada obuna bo‘lingan oddiy va biznes profillar ko‘rsatiladi; istoriya API’lariga murojaat qilinmaydi.
- Admin ID’lari faqat `ADMIN_TG_IDS`dan olinadi; `PRIVILEGED_TG_IDS` admin huquqini bermaydi.
- Admin sessiya cookie’si `HttpOnly`, `Secure`, `SameSite=Strict`.
- Mavjud ma’lumotlar va jadvallar o‘chirilmaydi.
- Har vazifada avval test yoziladi, testning kutilgan sabab bilan yiqilishi ko‘riladi, keyin minimal kod yoziladi.

---

## Fayl tuzilishi

- Create: `feature_flags.py` — flag nomlari, env/DB qiymati va route guard siyosati.
- Create: `admin_auth.py` — admin ID parsing, challenge, sessiya va cookie tokeni domeni.
- Create: `admin_api.py` — bu bosqichda faqat `/api/admin/auth/*` endpointlari.
- Modify: `database.py` — yangi schema init funksiyalarini migratsiyaga ulash.
- Modify: `runtime_config.py` — production admin va private receipt katalogi konfiguratsiyasi.
- Modify: `main.py` — router, middleware, public `/api/features`, admin host skeleti va BUILD.
- Modify: `api.py` — e’lonlarni qidiruv/taklif/saved javoblaridan chiqarish va obuna profillari avatarini qaytarish.
- Modify: `static/index.html` — MVP menyusi, feature boot va obuna profillari qatori.
- Create: `tests/test_feature_flags_v1651.py`.
- Create: `tests/test_mvp_guards_v1651_api.py`.
- Create: `tests/test_admin_auth_v1651.py`.
- Create: `tests/test_mvp_frontend_v1651_contract.py`.

---

### Task 1: Feature flag domeni va SQLite override

**Files:**
- Create: `feature_flags.py`
- Test: `tests/test_feature_flags_v1651.py`

**Interfaces:**
- Produces: `FEATURE_ENV_NAMES: dict[str, str]`
- Produces: `ensure_feature_flag_schema(conn) -> None`
- Produces: `feature_snapshot(conn, environ=None) -> dict[str, bool]`
- Produces: `feature_enabled(conn, code: str, environ=None) -> bool`
- Produces: `set_feature_override(conn, code: str, enabled: bool, admin_tg_id: int, now: int | None = None) -> None`
- Produces: `guarded_feature_for_path(path: str) -> str | None`

- [ ] **Step 1: Failing domain testini yozish**

```python
# tests/test_feature_flags_v1651.py
import sqlite3
import unittest

from feature_flags import (
    ensure_feature_flag_schema,
    feature_snapshot,
    guarded_feature_for_path,
    set_feature_override,
)


class FeatureFlagTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_feature_flag_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_env_defaults_are_disabled_and_db_override_wins(self):
        env = {
            "MVP_LISTINGS_ENABLED": "0",
            "MVP_STORIES_ENABLED": "0",
            "MVP_CHAT_ENABLED": "0",
            "MVP_SYSTEMIZATION_ENABLED": "0",
        }
        self.assertEqual(
            feature_snapshot(self.conn, env),
            {
                "listings": False,
                "stories": False,
                "chat": False,
                "systemization": False,
            },
        )
        set_feature_override(self.conn, "listings", True, 1423181561, now=100)
        self.assertTrue(feature_snapshot(self.conn, env)["listings"])

    def test_route_map_keeps_order_chat_outside_general_chat_flag(self):
        self.assertEqual(guarded_feature_for_path("/api/messages/send"), "chat")
        self.assertEqual(guarded_feature_for_path("/api/stories/feed"), "stories")
        self.assertEqual(guarded_feature_for_path("/api/listings"), "listings")
        self.assertEqual(guarded_feature_for_path("/api/kassa"), "systemization")
        self.assertIsNone(guarded_feature_for_path("/api/orders/17/chat"))
        self.assertIsNone(guarded_feature_for_path("/api/orders/inbox"))
```

- [ ] **Step 2: Testning import xatosi bilan yiqilishini tekshirish**

Run: `.venv/bin/python -m unittest tests.test_feature_flags_v1651 -v`

Expected: `ModuleNotFoundError: No module named 'feature_flags'`.

- [ ] **Step 3: Minimal domen modulini yozish**

```python
# feature_flags.py
import os
import time

from runtime_config import env_flag

FEATURE_ENV_NAMES = {
    "listings": "MVP_LISTINGS_ENABLED",
    "stories": "MVP_STORIES_ENABLED",
    "chat": "MVP_CHAT_ENABLED",
    "systemization": "MVP_SYSTEMIZATION_ENABLED",
}

SYSTEMIZATION_PREFIXES = (
    "/api/stock",
    "/api/stats",
    "/api/expense",
    "/api/kassa",
    "/api/sales",
    "/api/qarz",
    "/api/staff",
    "/api/tabel",
    "/api/business/credentials",
    "/api/contractors",
    "/api/documents",
    "/api/education",
    "/api/ai",
)


def ensure_feature_flag_schema(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS platform_feature_flags(
             feature_code TEXT PRIMARY KEY,
             enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
             updated_by_tg_id INTEGER NOT NULL,
             updated_at INTEGER NOT NULL
           )"""
    )


def feature_snapshot(conn, environ=None):
    env = os.environ if environ is None else environ
    values = {
        code: env_flag(env_name, False, env)
        for code, env_name in FEATURE_ENV_NAMES.items()
    }
    rows = conn.execute(
        "SELECT feature_code,enabled FROM platform_feature_flags"
    ).fetchall()
    for row in rows:
        if row["feature_code"] in values:
            values[row["feature_code"]] = bool(row["enabled"])
    return values


def feature_enabled(conn, code, environ=None):
    return bool(feature_snapshot(conn, environ).get(code, False))


def set_feature_override(conn, code, enabled, admin_tg_id, now=None):
    if code not in FEATURE_ENV_NAMES:
        raise ValueError("Noma’lum feature flag.")
    conn.execute(
        """INSERT INTO platform_feature_flags(
             feature_code,enabled,updated_by_tg_id,updated_at
           ) VALUES(?,?,?,?)
           ON CONFLICT(feature_code) DO UPDATE SET
             enabled=excluded.enabled,
             updated_by_tg_id=excluded.updated_by_tg_id,
             updated_at=excluded.updated_at""",
        (code, 1 if enabled else 0, int(admin_tg_id), int(now or time.time())),
    )


def guarded_feature_for_path(path):
    if path.startswith(("/api/stories", "/story-media/", "/story-thumbnail/")):
        return "stories"
    if path.startswith("/api/listings"):
        return "listings"
    if path.startswith("/api/messages"):
        return "chat"
    if path.startswith("/api/staff-auth"):
        return "systemization"
    if path.startswith(SYSTEMIZATION_PREFIXES):
        return "systemization"
    return None
```

- [ ] **Step 4: Domain testini yashil qilish**

Run: `.venv/bin/python -m unittest tests.test_feature_flags_v1651 -v`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add feature_flags.py tests/test_feature_flags_v1651.py
git commit -m "feat: add auditable MVP feature flags"
```

---

### Task 2: Feature schema migratsiyasi va production konfiguratsiyasi

**Files:**
- Modify: `database.py:480-490`
- Modify: `runtime_config.py:45-135`
- Modify: `.env.production.example`
- Test: `tests/test_feature_flags_v1651.py`
- Test: `tests/test_production_foundation.py`

**Interfaces:**
- Consumes: `ensure_feature_flag_schema(conn)`.
- Produces: eski SQLite bazani buzmasdan yangi jadval.
- Produces: productionda `ADMIN_TG_IDS` va private receipt katalogini tekshiradigan konfiguratsiya.

- [ ] **Step 1: Migratsiya va production testlarini qo‘shish**

```python
def test_database_init_creates_feature_flag_table(self):
    import database
    from database import db, init_db
    init_db()
    conn = db()
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    conn.close()
    self.assertIn("platform_feature_flags", tables)
```

`tests/test_production_foundation.py`dagi `valid_production_env()`ga:

```python
"ADMIN_TG_IDS": "1423181561",
"PAYMENT_RECEIPT_DIR": os.path.join(root, "private", "payment_receipts"),
"MVP_LISTINGS_ENABLED": "0",
"MVP_STORIES_ENABLED": "0",
"MVP_CHAT_ENABLED": "0",
"MVP_SYSTEMIZATION_ENABLED": "0",
```

va alohida test:

```python
def test_production_requires_separate_admin_ids(self):
    with tempfile.TemporaryDirectory() as root:
        env = valid_production_env(root)
        env["ADMIN_TG_IDS"] = ""
        with self.assertRaises(RuntimeError) as raised:
            validate_runtime_config(
                db_path=os.path.join(root, "platforma.db"),
                upload_dir=os.path.join(root, "uploads"),
                backup_dir=os.path.join(root, "backups"),
                environ=env,
            )
        self.assertIn("ADMIN_TG_IDS", str(raised.exception))
```

- [ ] **Step 2: Testlarning kutilgan sabab bilan yiqilishini ko‘rish**

Run: `.venv/bin/python -m unittest tests.test_feature_flags_v1651 tests.test_production_foundation -v`

Expected: feature jadvali yo‘qligi yoki `ADMIN_TG_IDS` tekshirilmagani sabab FAIL.

- [ ] **Step 3: Migratsiyani ulash**

`database.py::_migrate` boshidagi import va chaqiruv:

```python
from feature_flags import ensure_feature_flag_schema

ensure_feature_flag_schema(conn)
```

`runtime_config.validate_runtime_config` production tekshiruviga:

```python
if not str(env.get("ADMIN_TG_IDS", "")).strip():
    errors.append("ADMIN_TG_IDS production uchun aniq ko‘rsatilishi kerak")

receipt_dir = str(env.get("PAYMENT_RECEIPT_DIR", "")).strip()
if not receipt_dir or not _path_is_inside(receipt_dir, persistent_root):
    errors.append("PAYMENT_RECEIPT_DIR PERSISTENT_ROOT ichida bo‘lishi kerak")
```

`.env.production.example`ga:

```dotenv
ADMIN_TG_IDS=YOUR_ADMIN_TELEGRAM_ID
PAYMENT_RECEIPT_DIR=/data/private/payment_receipts
MVP_LISTINGS_ENABLED=0
MVP_STORIES_ENABLED=0
MVP_CHAT_ENABLED=0
MVP_SYSTEMIZATION_ENABLED=0
```

- [ ] **Step 4: Migratsiya/config testlarini yashil qilish**

Run: `.venv/bin/python -m unittest tests.test_feature_flags_v1651 tests.test_production_foundation -v`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add database.py runtime_config.py .env.production.example tests/test_feature_flags_v1651.py tests/test_production_foundation.py
git commit -m "feat: migrate MVP flags and validate production config"
```

---

### Task 3: Backend MVP route guardlari

**Files:**
- Modify: `main.py:530-669`
- Modify: `api.py:250-330, 4267-4385, 4689-4755, 8038-8644`
- Modify: `district_offers.py`
- Test: `tests/test_mvp_guards_v1651_api.py`

**Interfaces:**
- Consumes: `guarded_feature_for_path(path)` va `feature_enabled(conn, code)`.
- Produces: 404 JSON `{"detail": "...", "code": "feature_disabled", "feature": code}`.
- Produces: `GET /api/features -> {"listings": false, ...}`.

- [ ] **Step 1: API guard testini yozish**

```python
# tests/test_mvp_guards_v1651_api.py
import os
import unittest
from fastapi.testclient import TestClient

os.environ.update({
    "TEST_MODE": "1",
    "MVP_LISTINGS_ENABLED": "0",
    "MVP_STORIES_ENABLED": "0",
    "MVP_CHAT_ENABLED": "0",
    "MVP_SYSTEMIZATION_ENABLED": "0",
})

from main import app


class MvpGuardApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = TestClient(app)
        cls.client = cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)

    def test_public_features_are_server_owned(self):
        response = self.client.get("/api/features")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["stories"])
        self.assertFalse(response.json()["listings"])

    def test_disabled_feature_routes_are_blocked(self):
        for path in (
            "/api/stories/feed",
            "/api/listings",
            "/api/messages/conversations",
            "/api/kassa",
            "/api/staff-auth/me",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["code"], "feature_disabled")

    def test_orders_and_order_chat_are_not_feature_blocked(self):
        self.assertNotEqual(
            self.client.get("/api/orders/inbox").json().get("code"),
            "feature_disabled",
        )
        self.assertNotEqual(
            self.client.get("/api/orders/1/chat").json().get("code"),
            "feature_disabled",
        )
```

- [ ] **Step 2: Testni yiqitish**

Run: `.venv/bin/python -m unittest tests.test_mvp_guards_v1651_api -v`

Expected: `/api/features` 404 va bloklangan route’lar odatiy 401 qaytarishi sabab FAIL.

- [ ] **Step 3: Feature guard middleware va public endpointni qo‘shish**

`main.py`da whitelist tekshiruvidan oldin ishlaydigan middleware:

```python
from feature_flags import feature_enabled, feature_snapshot, guarded_feature_for_path


@app.middleware("http")
async def mvp_feature_guard(request, call_next):
    feature = guarded_feature_for_path(request.url.path)
    if feature:
        conn = db()
        try:
            enabled = feature_enabled(conn, feature)
        finally:
            conn.close()
        if not enabled:
            return JSONResponse(
                status_code=404,
                content={
                    "detail": "Bu bo‘lim MVP bosqichida vaqtincha yopiq.",
                    "code": "feature_disabled",
                    "feature": feature,
                },
            )
    return await call_next(request)


@app.get("/api/features")
async def public_features():
    conn = db()
    try:
        return feature_snapshot(conn)
    finally:
        conn.close()
```

`whitelist_middleware`dagi public ro‘yxatga `/api/features`ni qo‘shish.

- [ ] **Step 4: Listing ma’lumotini yon yo‘llardan ham chiqarish**

`api.py` va `district_offers.py`da `feature_enabled(conn, "listings")` false bo‘lsa:

- `/api/search` listing branchini bajarmaslik;
- `/api/browse` listing branchini bajarmaslik;
- `/api/home/district-offers` listing kartalarini yaratmaslik;
- `/api/saved` javobidan `kind == "listing"`ni chiqarish;
- `/api/save` uchun `kind == "listing"`ga `feature_disabled` qaytarish.

Minimal shart namunasi:

```python
from feature_flags import feature_enabled

include_listings = feature_enabled(conn, "listings")
if include_listings:
    # mavjud listing query va result append o‘zgarishsiz shu blokda qoladi
```

- [ ] **Step 5: Guard va ommaviy qidiruv regressiyasini tekshirish**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_mvp_guards_v1651_api \
  tests.test_public_search_api \
  tests.test_unified_search_results_contract \
  tests.test_pro_follow_map_api -v
```

Expected: `OK`; xarita va mahsulot/xizmat qidiruvi yashil, listinglar yopiq.

- [ ] **Step 6: Commit**

```bash
git add main.py api.py district_offers.py tests/test_mvp_guards_v1651_api.py
git commit -m "feat: enforce MVP feature guards on API routes"
```

---

### Task 4: Obuna profillari qatori va MVP frontend projection

**Files:**
- Modify: `api.py:4460-4488`
- Modify: `static/index.html:1018-1055, 1436-1469, 1480-1485, 1718-1765, 2308-2320, 2378-2450, 2575-2590, 2653-2718, 2920-3530, 11460-11610, 12740-12820, 13390-13590`
- Test: `tests/test_mvp_frontend_v1651_contract.py`
- Test: `tests/test_pro_follow_map_api.py`

**Interfaces:**
- Consumes: `GET /api/features`.
- Consumes: `GET /api/follows/my?actor_type=user|business`.
- Produces: follow item `{kind,id,name,info,image_url}`.
- Produces: frontend global `FEATURES` va `applyFeatureVisibility()`.

- [ ] **Step 1: Frontend va follow payload testlarini yozish**

```python
# tests/test_mvp_frontend_v1651_contract.py
import unittest
from tests.frontend_source import frontend_source


class MvpFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_boot_loads_features_before_optional_sections(self):
        self.assertIn('api("GET","/api/features")', self.html)
        self.assertIn("applyFeatureVisibility", self.html)

    def test_story_ui_is_not_used_as_followed_profile_strip(self):
        self.assertIn('id="followedProfileStrip"', self.html)
        self.assertIn('id="followedProfileRail"', self.html)
        self.assertIn("/api/follows/my?", self.html)
        self.assertNotIn('id="storyAddCard"', self.html)

    def test_mvp_menu_copy_and_hidden_sections(self):
        self.assertIn("<h4>Reklamalarim</h4>", self.html)
        self.assertNotIn("<h4>E'lonlarim va reklamalarim</h4>", self.html)
        self.assertNotIn("<h4>Istoriyalarim</h4>", self.html)
        self.assertNotIn("<h4>Suhbatlarim</h4>", self.html)
        self.assertIn('id="cabGroupTizim"', self.html)
```

`tests/test_pro_follow_map_api.py::ProAndFollowMapApiTests`ga mavjud
`viewer_token` fixture’dan foydalanadigan test qo‘shiladi:

```python
def test_follows_payload_has_profile_image_url_without_story_fields(self):
    response = self.client.get(
        "/api/follows/my?actor_type=user",
        headers={"Authorization": "Bearer " + self.viewer_token},
    )
    self.assertEqual(response.status_code, 200)
    for item in response.json():
        self.assertIn("image_url", item)
        self.assertNotIn("stories", item)
        self.assertNotIn("has_unseen", item)
```

- [ ] **Step 2: Testlarni kutilgan markup/payload yo‘qligi bilan yiqitish**

Run: `.venv/bin/python -m unittest tests.test_mvp_frontend_v1651_contract tests.test_pro_follow_map_api -v`

Expected: `followedProfileStrip` va `image_url` yo‘qligi sabab FAIL.

- [ ] **Step 3: Follow API payloadiga xavfsiz avatar URL qo‘shish**

`api.py::my_follows`da:

```python
if r["target_kind"] == "business":
    t = conn.execute(
        "SELECT id,name,yon FROM businesses WHERE id=? AND status='active'",
        (r["target_id"],),
    ).fetchone()
    if t:
        result.append({
            "kind": "business",
            "id": t["id"],
            "name": t["name"],
            "info": t["yon"],
            "image_url": f"/profile-media/business/{t['id']}",
        })
else:
    t = conn.execute(
        "SELECT id,name,district FROM users WHERE id=?",
        (r["target_id"],),
    ).fetchone()
    if t:
        result.append({
            "kind": "user",
            "id": t["id"],
            "name": t["name"],
            "info": t["district"],
            "image_url": f"/profile-media/user/{t['id']}",
        })
```

- [ ] **Step 4: Story stripni follow stripga aylantirish**

Markup:

```html
<section class="story-strip" id="followedProfileStrip" hidden
         aria-label="Obuna bo‘lingan profillar">
  <div class="story-rail" id="followedProfileRail"></div>
</section>
```

JavaScript:

```javascript
var FEATURES={listings:false,stories:false,chat:false,systemization:false};

function loadFollowedProfileStrip(){
  var strip=el("followedProfileStrip"),rail=el("followedProfileRail");
  if(!strip||!rail||!loggedIn||!ME||!ME.registered){
    if(strip)strip.hidden=true;
    if(rail)rail.innerHTML="";
    return Promise.resolve([]);
  }
  return api("GET","/api/follows/my?"+actorQuery(actorType())).then(function(items){
    items=Array.isArray(items)?items:[];
    strip.hidden=!items.length;
    rail.innerHTML=items.map(function(item){
      return '<button class="story-card" type="button" data-follow-profile-kind="'+
        esc(item.kind)+'" data-follow-profile-id="'+Number(item.id)+'">'+
        '<span class="story-thumb"><img src="'+esc(item.image_url)+
        '" alt="" onerror="this.remove()"></span>'+
        '<span class="story-name">'+esc(item.name||"Profil")+'</span></button>';
    }).join("");
    return items;
  }).catch(function(){strip.hidden=true;rail.innerHTML="";return [];});
}
```

Delegated click:

```javascript
var profile=event.target.closest("[data-follow-profile-kind]");
if(profile){
  if(profile.dataset.followProfileKind==="business"){
    openBusiness(Number(profile.dataset.followProfileId));
  }else{
    openPerson(Number(profile.dataset.followProfileId));
  }
}
```

Story composer/viewer markup, story event handlerlari va `loadStories()` boot chaqiruvlari MVP markupidan chiqariladi. Backend kodi o‘chirilmaydi; flag keyin qayta yoqishga tayyor qoladi.

- [ ] **Step 5: Menyularni feature javobiga moslash**

`applyFeatureVisibility()`:

```javascript
function applyFeatureVisibility(){
  document.querySelectorAll("[data-feature]").forEach(function(node){
    node.hidden=!FEATURES[node.dataset.feature];
  });
  var tizim=el("cabGroupTizim");
  if(tizim)tizim.hidden=!FEATURES.systemization;
}
```

Markup elementlariga `data-feature="listings|stories|chat|systemization"` qo‘yiladi. MVPda:

- biznes/oddiy menyu matni `Reklamalarim`;
- listing tab va formalar yashiriladi;
- `Istoriyalarim`, `Suhbatlarim`, xodim login tugmasi yashiriladi;
- `cabGroupTizim` to‘liq yashiriladi;
- `Buyurtmalar`, `Xizmat buyurtmalari`, `Mijoz fikrlari`, `Bildirishnomalar`, `Sozlamalar` qoladi.

Boot:

```javascript
function loadFeatures(){
  return api("GET","/api/features").then(function(data){
    FEATURES=Object.assign(FEATURES,data||{});
    applyFeatureVisibility();
  });
}
```

`boot()` birinchi ekranlarni yuklashdan oldin `loadFeatures()`ni chaqiradi; xatoda barcha xavfli flaglar `false` bo‘lib qoladi.

- [ ] **Step 6: Frontend/API contract testlarini yashil qilish**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_mvp_frontend_v1651_contract \
  tests.test_mvp_guards_v1651_api \
  tests.test_web_home_frontend_contract \
  tests.test_cabinet_dashboard_v1637_contract \
  tests.test_pro_follow_map_api -v
```

Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add api.py static/index.html tests/test_mvp_frontend_v1651_contract.py tests/test_mvp_guards_v1651_api.py
git commit -m "feat: project MVP UI and followed profiles independently"
```

---

### Task 5: Admin ID, challenge va sessiya domeni

**Files:**
- Create: `admin_auth.py`
- Modify: `database.py`
- Test: `tests/test_admin_auth_v1651.py`

**Interfaces:**
- Produces: `admin_ids(environ=None) -> set[int]`
- Produces: `is_admin_tg_id(tg_id, environ=None) -> bool`
- Produces: `ensure_admin_auth_schema(conn) -> None`
- Produces: `start_admin_challenge(conn, tg_id, secret, fixed_code="", now=None) -> dict`
- Produces: `verify_admin_challenge(conn, challenge_id, code, secret, now=None) -> str`
- Produces: `admin_session(conn, raw_token, now=None) -> sqlite3.Row | None`
- Produces: `revoke_admin_session(conn, raw_token, now=None) -> None`

- [ ] **Step 1: Auth domen testini yozish**

```python
# tests/test_admin_auth_v1651.py
import sqlite3
import unittest

from admin_auth import (
    admin_ids,
    admin_session,
    ensure_admin_auth_schema,
    is_admin_tg_id,
    start_admin_challenge,
    verify_admin_challenge,
)


class AdminAuthDomainTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_admin_auth_schema(self.conn)
        self.env = {"ADMIN_TG_IDS": "1423181561, 607563067"}

    def tearDown(self):
        self.conn.close()

    def test_admin_ids_are_separate_and_strict(self):
        self.assertEqual(admin_ids(self.env), {1423181561, 607563067})
        self.assertTrue(is_admin_tg_id(1423181561, self.env))
        self.assertFalse(is_admin_tg_id(1, self.env))

    def test_single_use_code_creates_hashed_session(self):
        challenge = start_admin_challenge(
            self.conn, 1423181561, "s" * 48, fixed_code="123456", now=100
        )
        token = verify_admin_challenge(
            self.conn, challenge["id"], "123456", "s" * 48, now=101
        )
        self.assertIsNotNone(admin_session(self.conn, token, now=102))
        with self.assertRaises(ValueError):
            verify_admin_challenge(
                self.conn, challenge["id"], "123456", "s" * 48, now=103
            )
```

- [ ] **Step 2: Import xatosini tekshirish**

Run: `.venv/bin/python -m unittest tests.test_admin_auth_v1651 -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Admin auth schema va kriptografik helperlarni yozish**

Schema:

```sql
CREATE TABLE IF NOT EXISTS admin_auth_challenges(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tg_id INTEGER NOT NULL,
  code_hash TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  consumed_at INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_sessions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tg_id INTEGER NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL,
  last_used_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  revoked_at INTEGER NOT NULL DEFAULT 0
);
```

Kod va sessiya tokeni uchun:

```python
def _digest(secret, purpose, value):
    return hmac.new(
        secret.encode(), f"{purpose}:{value}".encode(), hashlib.sha256
    ).hexdigest()
```

Qoidalar:

- challenge 5 daqiqa;
- maksimum 5 xato urinish;
- sessiya 8 soat;
- 30 daqiqa faolsizlikdan keyin rad;
- bazada faqat code/token xeshi;
- verify `BEGIN IMMEDIATE` ichida challenge’ni bir marta iste’mol qiladi.

- [ ] **Step 4: Migratsiyaga ulash va testni yashil qilish**

`database.py::_migrate`:

```python
from admin_auth import ensure_admin_auth_schema
ensure_admin_auth_schema(conn)
```

Run: `.venv/bin/python -m unittest tests.test_admin_auth_v1651 -v`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add admin_auth.py database.py tests/test_admin_auth_v1651.py
git commit -m "feat: add isolated Telegram admin sessions"
```

---

### Task 6: Admin auth API, cookie va host skeleti

**Files:**
- Create: `admin_api.py`
- Create: `admin/index.html`
- Create: `admin/styles.css`
- Create: `admin/app.js`
- Modify: `main.py:360-420, 530-669, 1860-1956`
- Modify: `domain_config.py`
- Test: `tests/test_admin_auth_v1651.py`
- Test: `tests/test_domain_integration_ready.py`

**Interfaces:**
- Consumes: Task 5 auth helperlari.
- Produces: `POST /api/admin/auth/start`.
- Produces: `POST /api/admin/auth/verify`.
- Produces: `GET /api/admin/auth/me`.
- Produces: `POST /api/admin/auth/logout`.
- Produces: cookie `koprik_admin_session`.

- [ ] **Step 1: Admin API testlarini qo‘shish**

```python
import os
from unittest.mock import AsyncMock, patch

os.environ["TEST_MODE"] = "1"
os.environ["ADMIN_TG_IDS"] = "1423181561"
os.environ["TEST_OTP_CODE"] = "123456"

from fastapi.testclient import TestClient
from main import app


class AdminAuthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = TestClient(
            app,
            base_url="https://admin.koprik.uz",
        )
        cls.client = cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)

    def test_non_admin_id_cannot_start_login(self):
        response = self.client.post(
            "/api/admin/auth/start", json={"tg_id": 999}
        )
        self.assertEqual(response.status_code, 403)

    def test_allowed_admin_receives_code_and_cookie_session(self):
        with patch("main.tg_call", new=AsyncMock(return_value={"ok": True})):
            started = self.client.post(
                "/api/admin/auth/start", json={"tg_id": 1423181561}
            )
        self.assertEqual(started.status_code, 200)
        self.assertNotIn("code", started.json())
        verified = self.client.post(
            "/api/admin/auth/verify",
            json={
                "challenge_id": started.json()["challenge_id"],
                "code": "123456",
            },
        )
        self.assertEqual(verified.status_code, 200)
        cookie = verified.headers["set-cookie"]
        self.assertIn("koprik_admin_session", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)
        self.assertIn("Secure", cookie)
        self.assertEqual(
            self.client.get("/api/admin/auth/me").status_code,
            200,
        )

    def test_user_bearer_token_never_grants_admin(self):
        response = self.client.get(
            "/api/admin/auth/me",
            headers={"Authorization": "Bearer ordinary-user-token"},
        )
        self.assertEqual(response.status_code, 401)
```

- [ ] **Step 2: Endpointlar yo‘qligi sabab testni yiqitish**

Run: `.venv/bin/python -m unittest tests.test_admin_auth_v1651 -v`

Expected: admin auth endpointlari 404.

- [ ] **Step 3: `admin_api.py` auth endpointlarini yozish**

Router:

```python
router = APIRouter(prefix="/api/admin")
ADMIN_COOKIE = "koprik_admin_session"

@router.post("/auth/start")
async def admin_auth_start(request: Request):
    ...

@router.post("/auth/verify")
async def admin_auth_verify(request: Request, response: Response):
    ...

@router.get("/auth/me")
async def admin_auth_me(request: Request):
    ...

@router.post("/auth/logout")
async def admin_auth_logout(request: Request, response: Response):
    ...
```

`start`:

1. `tg_id` integer;
2. `is_admin_tg_id` false bo‘lsa 403;
3. `start_admin_challenge`;
4. `await main.tg_call("sendMessage", ...)`;
5. TEST_MODE’da faqat `TEST_OTP_CODE` ichki fixed code sifatida ishlatiladi, HTTP javobiga kod qo‘shilmaydi.

Cookie:

```python
response.set_cookie(
    ADMIN_COOKIE,
    raw_token,
    max_age=8 * 60 * 60,
    httponly=True,
    secure=True,
    samesite="strict",
    path="/api/admin",
)
```

`main.whitelist_middleware`da `/api/admin/*` user Bearer/initData tekshiruvidan chiqariladi; har bir admin endpoint o‘z admin sessiyasini tekshiradi.
Sessiya topilgandan keyin ham uning `tg_id` qiymati har so‘rovda joriy
`ADMIN_TG_IDS` ro‘yxatiga qayta solishtiriladi; ID envdan olib tashlangan
bo‘lsa sessiya revoke qilinib 401 qaytariladi.

- [ ] **Step 4: Admin host va kirish frontend skeletini ulash**

`domain_config.configured_allowed_hosts()` production defaultiga `"admin." + domain` qo‘shiladi.

`main.py`da root static mountdan oldin:

```python
ADMIN_DIR = os.path.join(os.path.dirname(__file__), "admin")
app.mount("/admin-assets", StaticFiles(directory=ADMIN_DIR), name="admin-assets")

@app.get("/admin/", include_in_schema=False)
async def admin_local_entry():
    return FileResponse(os.path.join(ADMIN_DIR, "index.html"))

@app.get("/", include_in_schema=False)
async def domain_entry(request: Request):
    host = (request.headers.get("host") or "").split(":", 1)[0].lower()
    if host == "admin." + PRIMARY_DOMAIN:
        return FileResponse(os.path.join(ADMIN_DIR, "index.html"))
    return FileResponse(os.path.join("static", "index.html"))
```

Bu bosqichdagi sahifa ishlaydigan Telegram ID + tasdiqlash kodi formasi,
sessiya holati va chiqish tugmasini beradi. Autentifikatsiyadan keyin
“Boshqaruv paneli tayyorlanmoqda” bo‘sh holati ko‘rsatiladi; yetti bo‘limli
asosiy admin UI 3-rejada quriladi.

- [ ] **Step 5: Auth/domain testlarini yashil qilish**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_admin_auth_v1651 \
  tests.test_domain_integration_ready \
  tests.test_production_foundation -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add admin_auth.py admin_api.py admin/index.html admin/styles.css admin/app.js main.py domain_config.py tests/test_admin_auth_v1651.py tests/test_domain_integration_ready.py
git commit -m "feat: add Telegram protected admin entry"
```

---

### Task 7: BUILD v1651 va to‘liq regressiya

**Files:**
- Modify: `main.py:70, 677-680`
- Modify: `static/index.html:7`
- Create: `docs/v1651-mvp-guards-admin-auth.md`
- Test: all `tests/`

**Interfaces:**
- Produces: `/api/build`da `build=v1651`.
- Produces: feature markers `mvp_feature_guards_v1651`, `followed_profiles_no_stories_v1651`, `admin_auth_v1651`.

- [ ] **Step 1: Build contract testini qo‘shish**

`tests/test_mvp_frontend_v1651_contract.py`:

```python
def test_build_markers(self):
    import asyncio
    import main
    payload = asyncio.run(main.app_build())
    self.assertEqual(payload["build"], "v1651")
    self.assertTrue(payload["mvp_feature_guards_v1651"])
    self.assertTrue(payload["admin_auth_v1651"])
```

- [ ] **Step 2: Testni eski v1650 sabab yiqitish**

Run: `.venv/bin/python -m unittest tests.test_mvp_frontend_v1651_contract -v`

Expected: `v1650 != v1651`.

- [ ] **Step 3: BUILD va release hujjatini yangilash**

- `main.py`: `APP_BUILD = "v1651"`.
- `static/index.html`: `<!-- BUILD: v1651 -->`.
- `/api/build`ga uchta marker.
- `docs/v1651-mvp-guards-admin-auth.md`da:
  - bloklangan va saqlangan funksiyalar;
  - yangi Railway variables;
  - admin local URL;
  - o‘zgargan fayllar;
  - `static/index.html` yakuniy qator soni.

- [ ] **Step 4: Sintaksis va barcha testlarni ishlatish**

Run:

```bash
.venv/bin/python -m compileall -q .
.venv/bin/python -m unittest discover -s tests -q
node tests/story-ui-smoke.cjs
node tests/subscription-ui-smoke.cjs
node tests/district-offers-ui-smoke.cjs
wc -l static/index.html
```

Expected:

- Python compile xatosiz;
- kamida mavjud 278 test va yangi testlar `OK`;
- uchta Node smoke test exit 0;
- qator soni release hujjatiga aynan ko‘chirilgan.

- [ ] **Step 5: Commit**

```bash
git add main.py static/index.html docs/v1651-mvp-guards-admin-auth.md tests
git commit -m "release: prepare Ko‘prik v1651 MVP guards"
```

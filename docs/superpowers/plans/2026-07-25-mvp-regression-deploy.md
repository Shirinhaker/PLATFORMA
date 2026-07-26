# MVP Regression, Capacity and Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ko‘prik v1654 MVP’ni mavjud ma’lumotlarni yo‘qotmasdan migratsiya qilish, faol/onlayn funksiyalarni to‘liq regressiyadan o‘tkazish, parallel to‘lov qarorlarini xavfsiz qilish va Railway + Cloudflare’da nazoratli ishga tushirish.

**Architecture:** Deploydan oldin SQLite online backup va integrity check bajariladi, so‘ng idempotent migration. Readiness bazani, uploads, private receipt katalogini va feature flag holatini tekshiradi. Release testlari foydalanuvchi oqimini public guestdan biznes buyurtmasigacha qamrab oladi. SQLite bitta Railway replica + persistent volume bilan MVP uchun ishlatiladi; o‘lchangan write contention chegarasidan oshganda PostgreSQLga ko‘chish release blocker sifatida qayd etiladi.

**Tech Stack:** Python 3.12, FastAPI, SQLite/WAL, Railway Volume, Cloudflare, vanilla frontend, stdlib `unittest` va `concurrent.futures`.

## Global Constraints

- Kirish BUILD: `v1653`; final BUILD: `v1654`.
- Productionda bitta Railway replica ishlaydi. SQLite volume bir nechta replica orasida bo‘linmaydi.
- Deploydan oldin backup; migrationdan keyin `PRAGMA integrity_check`.
- `TEST_MODE=0`, `TEST_OTP_CODE` yo‘q.
- `MVP_LISTINGS_ENABLED=0`.
- `MVP_STORIES_ENABLED=0`.
- `MVP_CHAT_ENABLED=0` — faqat umumiy `/api/messages/*`; order chat saqlanadi.
- `MVP_SYSTEMIZATION_ENABLED=0`.
- Faol: profils, mahsulot/xizmat, search, map, follows, ads, subscriptions, payments, admin, Orders, Service Orders, reviews, notifications.
- Historiya funksiyalari bloklangan bo‘lsa ham followed profile strip bosh sahifada qoladi.
- Oddiy profil va biznes profil followlari alohida.
- Guest search ishlaydi.
- Admin host main saytga redirect bo‘lmaydi.
- Rollback yangi jadvallarni o‘chirmaydi.

## Fayl tuzilishi

- Modify: `backup_database.py` — predeploy backup CLI manifesti.
- Create: `migration_check.py` — backup, migrate, integrity va schema fingerprint.
- Modify: `runtime_config.py` — final production contract.
- Modify: `main.py` — readiness, BUILD va safe diagnostics.
- Modify: `railpack.json` — deterministic start command/health contract.
- Modify: `.env.production.example`.
- Create: `scripts/mvp_load_probe.py` — read/write capacity probe.
- Create: `tests/test_mvp_release_v1654.py`.
- Create: `tests/test_payment_concurrency_v1654.py`.
- Create: `tests/test_migration_check_v1654.py`.
- Create: `tests/test_admin_host_v1654.py`.
- Create: `tests/test_mvp_responsive_v1654_contract.py`.
- Create: `docs/deploy-admin-koprik.md`.
- Create: `docs/v1654-mvp-release.md`.

---

### Task 1: Eski bazani xavfsiz migratsiya qilish

**Files:**
- Create: `migration_check.py`
- Modify: `backup_database.py`
- Modify: `database.py`
- Test: `tests/test_migration_check_v1654.py`
- Test: `tests/test_production_foundation.py`

**Interfaces:**

- `prepare_release_database(db_path, backup_dir, expected_schema, retention=14) -> dict`
- CLI: `.venv/bin/python migration_check.py --db ... --backup-dir ...`

- [ ] **Step 1: Eski schema nusxasiga migration testini yozish**

```python
# tests/test_migration_check_v1654.py
import os
import sqlite3
import tempfile
import unittest

from migration_check import prepare_release_database


class MigrationCheckTests(unittest.TestCase):
    def test_backup_is_created_before_idempotent_migration(self):
        with tempfile.TemporaryDirectory() as root:
            db_path = os.path.join(root, "platforma.db")
            backup_dir = os.path.join(root, "backups")
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE users(id INTEGER PRIMARY KEY, login TEXT)"
            )
            conn.execute("INSERT INTO users(login) VALUES('old-user')")
            conn.commit()
            conn.close()

            first = prepare_release_database(
                db_path, backup_dir, expected_schema="v1654"
            )
            second = prepare_release_database(
                db_path, backup_dir, expected_schema="v1654"
            )
            self.assertEqual(first["integrity"], "ok")
            self.assertEqual(second["integrity"], "ok")
            self.assertTrue(os.path.isfile(first["backup_path"]))
            conn = sqlite3.connect(db_path)
            self.assertEqual(
                conn.execute(
                    "SELECT login FROM users WHERE login='old-user'"
                ).fetchone()[0],
                "old-user",
            )
            for table in (
                "platform_feature_flags",
                "admin_sessions",
                "payment_requests",
                "admin_audit_log",
                "account_restrictions",
            ):
                self.assertIsNotNone(
                    conn.execute(
                        "SELECT 1 FROM sqlite_master "
                        "WHERE type='table' AND name=?",
                        (table,),
                    ).fetchone()
                )
            conn.close()
```

- [ ] **Step 2: Import xatosi bilan testni yiqitish**

Run: `.venv/bin/python -m unittest tests.test_migration_check_v1654 -v`

- [ ] **Step 3: Predeploy ketma-ketligi**

`prepare_release_database`:

1. DB file mavjudligini tekshiradi;
2. `create_database_backup`;
3. backupning `integrity_check`;
4. `database.DB_PATH`ni targetga bog‘lab `init_db`;
5. target `integrity_check`;
6. required tables/index/triggers;
7. `schema_migrations`ga `v1654` marker;
8. safe manifest qaytaradi.

Backup yaratish yoki integrity xato bo‘lsa migration boshlanmaydi.

- [ ] **Step 4: Backup manifest**

`backup_database.py` backup bilan birga secret bo‘lmagan JSON manifest yaratadi:

```json
{
  "created_at": "...",
  "source_size": 123,
  "backup_file": "platforma-....sqlite3",
  "sha256": "...",
  "integrity": "ok"
}
```

Permission `0600`. Retention backup va manifest juftligini birga tozalaydi.

- [ ] **Step 5: Test**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_migration_check_v1654 \
  tests.test_production_foundation -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add migration_check.py backup_database.py database.py tests/test_migration_check_v1654.py tests/test_production_foundation.py
git commit -m "feat: add verified predeploy database migration"
```

---

### Task 2: Production config, readiness va admin host

**Files:**
- Modify: `runtime_config.py`
- Modify: `domain_config.py`
- Modify: `main.py`
- Modify: `.env.production.example`
- Test: `tests/test_admin_host_v1654.py`
- Test: `tests/test_production_foundation.py`
- Test: `tests/test_domain_integration_ready.py`

- [ ] **Step 1: Host va readiness testlarini yozish**

```python
# tests/test_admin_host_v1654.py
import unittest
from fastapi.testclient import TestClient
from main import app


class AdminHostTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_admin_host_serves_admin_shell(self):
        response = self.client.get(
            "/", headers={"host": "admin.koprik.uz"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ko‘prik Admin", response.text)
        self.assertNotIn('id="homeStoryStrip"', response.text)

    def test_main_host_serves_public_site(self):
        response = self.client.get(
            "/", headers={"host": "koprik.uz"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ko‘prik", response.text)
        self.assertNotIn("Ko‘prik Admin", response.text)
```

Readiness test:

```python
def test_readyz_reports_required_private_storage_and_flags(self):
    payload = self.client.get("/readyz").json()
    self.assertIn("database", payload)
    self.assertIn("uploads", payload)
    self.assertIn("payment_receipts", payload)
    self.assertEqual(
        payload["features"],
        {
            "listings": False,
            "stories": False,
            "chat": False,
            "systemization": False,
        },
    )
```

- [ ] **Step 2: Testni missing keys bilan yiqitish**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_admin_host_v1654 \
  tests.test_production_foundation -v
```

- [ ] **Step 3: Final production env contract**

`.env.production.example`:

```dotenv
APP_ENV=production
BASE_URL=https://koprik.uz
PRIMARY_DOMAIN=koprik.uz
ADMIN_TG_IDS=1423181561
BOT_TOKEN=replace
WEBHOOK_SECRET=replace-with-random-32-plus
MOBILE_OTP_SECRET=replace-with-different-random-32-plus
PAYMENT_TOKEN_SECRET=replace-with-random-48-plus
ADMIN_AUDIT_IP_SECRET=replace-with-random-32-plus
PERSISTENT_ROOT=/data
DB_PATH=/data/db/platforma.db
UPLOAD_DIR=/data/uploads
BACKUP_DIR=/data/backups
PAYMENT_RECEIPT_DIR=/data/private/payment_receipts
MVP_LISTINGS_ENABLED=0
MVP_STORIES_ENABLED=0
MVP_CHAT_ENABLED=0
MVP_SYSTEMIZATION_ENABLED=0
TEST_MODE=0
PROJECT_ACCESS_RESTRICTED=0
```

Production validator flaglar aynan `0` ekanini talab qiladi; admin ID bo‘sh bo‘lsa startup fail.

- [ ] **Step 4: `/readyz`ni kengaytirish**

Readiness checks:

- DB `SELECT 1`;
- DB `PRAGMA quick_check` natijasi `ok` (60 soniya cache);
- uploads writable;
- receipt dir writable va public dirsdan tashqarida;
- admin dirning uch asseti mavjud;
- four feature snapshot.

HTTP 200 faqat hammasi ready; aks holda 503. Hech qanday absolute path responsega chiqmaydi.

- [ ] **Step 5: Test**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_admin_host_v1654 \
  tests.test_domain_integration_ready \
  tests.test_production_foundation -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add runtime_config.py domain_config.py main.py .env.production.example tests/test_admin_host_v1654.py tests/test_production_foundation.py
git commit -m "feat: harden production readiness and admin host"
```

---

### Task 3: MVP faol/yopiq funksiyalar regressiya matritsasi

**Files:**
- Create: `tests/test_mvp_release_v1654.py`
- Modify: existing focused tests only when new contract requires it.

- [ ] **Step 1: Release matrix testini yozish**

```python
# tests/test_mvp_release_v1654.py
import unittest


class MvpReleaseMatrixTests(MvpReleaseFixture):
    def test_guest_search_map_and_home_are_active(self):
        self.assertEqual(
            self.client.get("/api/search", params={"q": "non"}).status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/map").status_code, 200)
        self.assertEqual(
            self.client.get("/api/home/district-offers").status_code,
            200,
        )

    def test_active_authenticated_flows_are_not_feature_blocked(self):
        for method, path in (
            ("GET", "/api/follows/my"),
            ("GET", "/api/business/subscription"),
            ("GET", "/api/advertisements/my"),
            ("GET", "/api/orders/inbox"),
            ("GET", "/api/service-orders/inbox"),
            ("GET", "/api/notifications"),
        ):
            response = self.request(method, path, headers=self.owner_auth)
            self.assertNotEqual(
                response.json().get("code"), "feature_disabled", path
            )

    def test_only_approved_mvp_features_are_blocked(self):
        for path in (
            "/api/listings",
            "/api/stories/feed",
            "/api/messages/conversations",
            "/api/kassa",
            "/api/staff-auth/me",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404, path)
            self.assertEqual(response.json()["code"], "feature_disabled")

    def test_order_chat_remains_active(self):
        response = self.client.get(
            f"/api/orders/{self.order_id}/chat",
            headers=self.owner_auth,
        )
        self.assertNotEqual(response.json().get("code"), "feature_disabled")

    def test_followed_profiles_do_not_call_story_contract(self):
        response = self.client.get(
            "/api/follows/my",
            headers=self.user_auth,
        )
        self.assertEqual(response.status_code, 200)
        for row in response.json():
            self.assertIn("image_url", row)
            self.assertNotIn("stories", row)
```

`MvpReleaseFixture` shu faylda temp DB, user/business/mobile sessions, follow, product, service, ad, order va service order seedlarini to‘liq yaratadi; tashqi tarmoq chaqiruvi mock qilinadi.

- [ ] **Step 2: Yangi matrixni ishlatish**

Run: `.venv/bin/python -m unittest tests.test_mvp_release_v1654 -v`

Expected: existing BUILD bilan flag/admin/payment integratsiya xatolari bo‘lsa FAIL.

- [ ] **Step 3: Regression suite guruhlari**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_public_search_api \
  tests.test_unified_search_results_contract \
  tests.test_pro_follow_map_api \
  tests.test_subscription_api \
  tests.test_payment_api_v1652 \
  tests.test_admin_api_v1653 \
  tests.test_mvp_release_v1654 -v
```

Expected:

- guest search 200;
- search vaqtida faqat search markerlari;
- idle mapda pro + followed policy;
- oddiy/biznes follow isolation;
- paid plan regardless of demo;
- pending ad hidden;
- approved ad visible;
- order chat active.

- [ ] **Step 4: Commit**

```bash
git add tests/test_mvp_release_v1654.py tests
git commit -m "test: add Ko‘prik MVP release matrix"
```

---

### Task 4: To‘lov concurrency va SQLite write contention

**Files:**
- Create: `tests/test_payment_concurrency_v1654.py`
- Create: `scripts/mvp_load_probe.py`
- Modify: `database.py`
- Modify: `payment_api.py`

- [ ] **Step 1: Parallel approval testini yozish**

```python
# tests/test_payment_concurrency_v1654.py
from concurrent.futures import ThreadPoolExecutor
import unittest


class PaymentConcurrencyTests(PaymentConcurrencyFixture):
    def test_twenty_parallel_approvals_activate_exactly_once(self):
        def approve_once(_):
            return self.admin_client.post(
                f"/api/admin/payments/{self.payment_id}/approve",
                json={"reason": ""},
            ).status_code

        with ThreadPoolExecutor(max_workers=20) as pool:
            statuses = list(pool.map(approve_once, range(20)))

        self.assertEqual(statuses.count(200), 1)
        self.assertEqual(statuses.count(409), 19)
        conn = db()
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM business_subscriptions "
                "WHERE payment_request_id=?",
                (self.payment_id,),
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM payment_events "
                "WHERE payment_request_id=? AND to_status='approved'",
                (self.payment_id,),
            ).fetchone()[0],
            1,
        )
        conn.close()
```

- [ ] **Step 2: Testni race bilan yiqitish yoki invariantni tasdiqlash**

Run: `.venv/bin/python -m unittest tests.test_payment_concurrency_v1654 -v`

- [ ] **Step 3: DB connection contract**

`database.db()`:

- `timeout=30`;
- `busy_timeout=30000`;
- WAL;
- `synchronous=NORMAL`;
- row factory;
- foreign keys ON;
- connection har request/transactiondan keyin yopiladi.

Payment reviewda faqat bitta qisqa `BEGIN IMMEDIATE`; Telegram/file I/O transactiondan tashqarida.

- [ ] **Step 4: Load probe**

`scripts/mvp_load_probe.py` stdlib bilan:

- target URL va auth token CLI arg;
- 200 concurrent guest search/map reads;
- 50 authenticated home/follow reads;
- 20 pending payment creates faqat `--allow-writes` bilan test DBda;
- p50/p95/p99, error count, status distribution JSON.

Productionda write mode default o‘chiq.

Qabul mezoni stagingda:

- read probe 0 server error;
- p95 < 1000 ms;
- parallel approval exact one winner;
- “database is locked” yo‘q.

Agar bu mezon bajarilmasa release qilinmaydi; PostgreSQL migration alohida blocker bo‘ladi.

- [ ] **Step 5: Test**

Run:

```bash
.venv/bin/python -m unittest tests.test_payment_concurrency_v1654 -v
.venv/bin/python scripts/mvp_load_probe.py --help
```

Expected: `OK`, help exit 0.

- [ ] **Step 6: Commit**

```bash
git add database.py payment_api.py tests/test_payment_concurrency_v1654.py scripts/mvp_load_probe.py
git commit -m "test: prove payment concurrency and add load probe"
```

---

### Task 5: Main/admin responsive va navigation regressiyasi

**Files:**
- Create: `tests/test_mvp_responsive_v1654_contract.py`
- Modify: `static/index.html` only for validated regression fixes.
- Modify: `admin/index.html`, `admin/styles.css`, `admin/app.js` only for validated regression fixes.
- Test: existing Node smoke tests.

- [ ] **Step 1: Source contract testini yozish**

```python
# tests/test_mvp_responsive_v1654_contract.py
import pathlib
import unittest
from tests.frontend_source import frontend_source


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MvpResponsiveContractTests(unittest.TestCase):
    def test_main_has_no_disabled_mvp_navigation(self):
        html = frontend_source()
        self.assertNotIn("<h4>Istoriyalarim</h4>", html)
        self.assertNotIn("<h4>Suhbatlarim</h4>", html)
        self.assertNotIn("<h4>E'lonlarim</h4>", html)
        self.assertIn('id="followedProfileStrip"', html)

    def test_admin_has_mobile_drawer_and_no_main_site_admin_link(self):
        admin_html = (ROOT / "admin" / "index.html").read_text("utf-8")
        admin_css = (ROOT / "admin" / "styles.css").read_text("utf-8")
        main_html = frontend_source()
        self.assertIn('id="adminNavToggle"', admin_html)
        self.assertIn("@media (max-width: 760px)", admin_css)
        self.assertNotIn("admin.koprik.uz", main_html)
```

- [ ] **Step 2: Contractni ishlatish**

Run: `.venv/bin/python -m unittest tests.test_mvp_responsive_v1654_contract -v`

- [ ] **Step 3: Smoke testlar**

Run:

```bash
node tests/admin-ui-smoke.cjs
node tests/ad-upload-ui-smoke.cjs
node tests/subscription-ui-smoke.cjs
node tests/district-offers-ui-smoke.cjs
```

Tekshiriladi:

- mobile main bitta viewportga mos;
- search result xarita ostida;
- ad aspect ratio device bo‘yicha responsive;
- receipt previewda `×`;
- admin payment modal mobileda viewportdan chiqmaydi;
- browser back saytdan chiqmay, oldingi ichki viewga qaytadi.

- [ ] **Step 4: Faqat aniqlangan regressiyalarni tuzatish**

Har fix uchun test avval qizil bo‘ladi. Dizaynni qayta qurish yoki faol bo‘limlarning selector/IDlarini o‘zgartirish mumkin emas.

- [ ] **Step 5: Commit**

```bash
git add static/index.html admin tests/test_mvp_responsive_v1654_contract.py tests
git commit -m "test: lock responsive MVP navigation contracts"
```

---

### Task 6: Railway va Cloudflare deploy runbook

**Files:**
- Modify: `railpack.json`
- Create: `docs/deploy-admin-koprik.md`
- Modify: `.env.production.example`
- Test: `tests/test_production_foundation.py`

- [ ] **Step 1: Deploy contract testini yozish**

```python
def test_railpack_has_explicit_single_process_start(self):
    config = json.loads((ROOT / "railpack.json").read_text("utf-8"))
    self.assertEqual(
        config["deploy"]["startCommand"],
        "uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1",
    )
    self.assertEqual(config["deploy"]["healthcheckPath"], "/readyz")
```

- [ ] **Step 2: Testni missing startCommand bilan yiqitish**

Run: `.venv/bin/python -m unittest tests.test_production_foundation -v`

- [ ] **Step 3: `railpack.json`**

```json
{
  "$schema": "https://schema.railpack.com",
  "provider": "python",
  "deploy": {
    "aptPackages": ["ffmpeg"],
    "startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1",
    "healthcheckPath": "/readyz",
    "healthcheckTimeout": 120,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

- [ ] **Step 4: Runbookni yozish**

`docs/deploy-admin-koprik.md` aniq ketma-ketlik:

1. Railway Volume `/data` va bitta replica;
2. envlarni `.env.production.example` bo‘yicha kiritish;
3. `python migration_check.py`ni staging DB copyda bajarish;
4. deploy;
5. `/healthz`, `/readyz`, `/api/build`;
6. `https://admin.koprik.uz` custom domain qo‘shish;
7. Cloudflare CNAME `admin -> Railway target`, DNS only tekshirish, keyin proxy;
8. SSL/TLS Full (strict);
9. admin OTP login;
10. 1 so‘mlik emas, test-marked pending request bilan approval smoke;
11. load probe read-only;
12. monitoring va backup verification.

Rollback:

1. Railway previous deployment;
2. migrationdan oldingi backup file’ni yangi alohida pathda integrity check;
3. service stop;
4. current DBni timestamp bilan saqlab qo‘yish;
5. backupni explicit DB pathga restore;
6. old release start;
7. `/readyz`;
8. yangi jadvallarni hech qachon qo‘lda drop qilmaslik.

- [ ] **Step 5: Test**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_production_foundation \
  tests.test_domain_integration_ready \
  tests.test_admin_host_v1654 -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add railpack.json .env.production.example docs/deploy-admin-koprik.md tests/test_production_foundation.py
git commit -m "docs: add verified Railway and admin domain runbook"
```

---

### Task 7: Final BUILD v1654, release evidence va handoff

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Modify: `admin/index.html`
- Create: `docs/v1654-mvp-release.md`
- Test: all tests

- [ ] **Step 1: Final build contract**

`/api/build`:

```json
{
  "build": "v1654",
  "mvp_release_v1654": true,
  "admin_site_v1653": true,
  "manual_payments_v1652": true,
  "mvp_feature_guards_v1651": true,
  "stories_enabled": false,
  "listings_enabled": false,
  "general_chat_enabled": false,
  "systemization_enabled": false,
  "orders_enabled": true,
  "service_orders_enabled": true,
  "order_chat_enabled": true
}
```

- [ ] **Step 2: Markerlar**

- `main.py`: `APP_BUILD = "v1654"`;
- main/admin HTML build comments;
- release hujjatida:
  - active/disabled matrix;
  - migrations;
  - env nomlari, sir qiymatlarisiz;
  - tests count;
  - load probe evidence;
  - changed files;
  - line counts;
  - known limit: single SQLite replica;
  - rollback.

- [ ] **Step 3: To‘liq verification**

Run:

```bash
.venv/bin/python -m compileall -q .
.venv/bin/python -m unittest discover -s tests -q
node tests/admin-ui-smoke.cjs
node tests/ad-upload-ui-smoke.cjs
node tests/subscription-ui-smoke.cjs
node tests/district-offers-ui-smoke.cjs
.venv/bin/python scripts/mvp_load_probe.py --help
wc -l static/index.html admin/index.html admin/styles.css admin/app.js
```

Expected:

- compile exit 0;
- eski 278 va barcha yangi tests `OK`;
- Node smoke exit 0;
- load probe help exit 0;
- line count release hujjatiga aynan ko‘chiriladi.

- [ ] **Step 4: Staging acceptance**

Read-only:

```bash
curl -fsS https://STAGING/healthz
curl -fsS https://STAGING/readyz
curl -fsS https://STAGING/api/build
.venv/bin/python scripts/mvp_load_probe.py --base-url https://STAGING
```

Qo‘lda:

- guest search;
- first district;
- login return restore;
- ordinary/business follow isolation;
- map idle/search behavior;
- product/service create;
- order/service-order + order chat;
- subscription payment submit/approve;
- ad submit/approve;
- reject/resubmit;
- cancel reason;
- admin mobile/desktop.

- [ ] **Step 5: Final commit**

```bash
git add main.py static/index.html admin docs/v1654-mvp-release.md
git commit -m "release: Ko‘prik v1654 online MVP"
```

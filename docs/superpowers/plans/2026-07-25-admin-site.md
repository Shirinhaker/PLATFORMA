# Admin Site and Moderation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `admin.koprik.uz`da to‘lovlar, narxlar, foydalanuvchilar, bizneslar, kontent, shikoyatlar va auditni boshqaradigan alohida responsive admin saytini yaratish.

**Architecture:** Admin frontend asosiy saytga link bilan qo‘shilmaydi va alohida hostdan yuklanadi, lekin shu FastAPI backend va SQLite bazadan foydalanadi. Barcha admin endpointlari `koprik_admin_session` cookie’sini tekshiradi. Admin mutatsiyalari append-only `admin_audit_log`ga yoziladi. Kontent avvaldan faol chiqadi; shikoyat yoki admin qarori bilan reaktiv tarzda yashiriladi. Account cheklovlari `content_hidden` va `account_blocked` sifatida alohida saqlanadi.

**Tech Stack:** Python 3.12, FastAPI, SQLite/WAL, vanilla HTML/CSS/JavaScript, responsive CSS, `unittest`.

## Global Constraints

- Kirish BUILD: `v1652`; yakuniy BUILD: `v1653`.
- Faqat `ADMIN_TG_IDS`dagi Telegram ID admin bo‘ladi.
- Oddiy user Bearer tokeni, `PRIVILEGED_TG_IDS` yoki biznes egasi admin huquqini bermaydi.
- Admin linki asosiy `static/index.html`da ko‘rinmaydi.
- Admin API receipt path, parol xeshi, mobil token xeshi, Telegram auth xeshi yoki maxfiy env qiymatlarini JSONga chiqarmaydi.
- `content_hidden`: profil egasi login qila oladi va o‘z materialini ko‘radi, public qidiruv/xarita/feed undan kontent chiqarmaydi.
- `account_blocked`: egasi o‘qish uchun mavjud sessiyasini ko‘rishi mumkin, lekin barcha mutation endpointlari 403 qaytaradi; admin unblock qiladi.
- Individual content hide hisob blokidan alohida.
- Oddiy foydalanuvchining yashash tumani boshqa foydalanuvchiga ochilmaydi.
- Admin UI mobil, planshet va desktopda ishlaydi.
- Historiyalar, umumiy chat, e’lonlar va tizimlashtirish MVP flaglari o‘chiq qoladi.
- Orders va Service Orders faol qoladi.

## Fayl tuzilishi

- Create: `admin_audit.py` — append-only audit schema va yozish helperi.
- Create: `moderation.py` — account/content cheklovlari va report schema.
- Create: `admin_queries.py` — dashboard va admin list querylari.
- Modify: `database.py` — schema migratsiyasi.
- Modify: `admin_api.py` — barcha admin endpointlari.
- Modify: `api.py` — public visibility filterlari va report endpointlari.
- Modify: `main.py` — blocked mutation middleware va BUILD.
- Modify: `admin/index.html`.
- Modify: `admin/styles.css`.
- Modify: `admin/app.js`.
- Create: `tests/test_admin_audit_v1653.py`.
- Create: `tests/test_admin_api_v1653.py`.
- Create: `tests/test_admin_moderation_v1653.py`.
- Create: `tests/test_admin_frontend_v1653_contract.py`.
- Create: `tests/admin-ui-smoke.cjs`.

---

### Task 1: Append-only admin audit va moderation schema

**Files:**
- Create: `admin_audit.py`
- Create: `moderation.py`
- Modify: `database.py`
- Test: `tests/test_admin_audit_v1653.py`
- Test: `tests/test_admin_moderation_v1653.py`

**Interfaces:**

- `ensure_admin_audit_schema(conn) -> None`
- `append_admin_audit(conn, *, admin_tg_id, action, target, before, after, reason, request_meta, now=None) -> int`
- `ensure_moderation_schema(conn) -> None`
- `set_account_restriction(...) -> dict`
- `clear_account_restriction(...) -> dict`
- `account_restrictions(conn, actor_type, actor_id) -> set[str]`
- `set_content_visibility(...) -> dict`
- `content_is_public(conn, kind, content_id) -> bool`

- [ ] **Step 1: Audit va moderation domain testlarini yozish**

```python
# tests/test_admin_audit_v1653.py
import sqlite3
import unittest

from admin_audit import append_admin_audit, ensure_admin_audit_schema


class AdminAuditTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_admin_audit_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_append_records_before_after_reason_and_request(self):
        audit_id = append_admin_audit(
            self.conn,
            admin_tg_id=1423181561,
            action="payment.reject",
            target={"kind": "payment", "id": 15},
            before={"status": "pending"},
            after={"status": "rejected"},
            reason="Kvitansiya o‘qilmaydi",
            request_meta={"ip_hash": "abc", "user_agent": "test"},
            now=100,
        )
        row = self.conn.execute(
            "SELECT * FROM admin_audit_log WHERE id=?", (audit_id,)
        ).fetchone()
        self.assertEqual(row["action"], "payment.reject")
        self.assertEqual(row["reason"], "Kvitansiya o‘qilmaydi")

    def test_sqlite_guards_against_update_and_delete(self):
        audit_id = append_admin_audit(
            self.conn,
            admin_tg_id=1,
            action="test",
            target={"kind": "user", "id": 1},
            before={},
            after={},
            reason="",
            request_meta={},
            now=100,
        )
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute(
                "UPDATE admin_audit_log SET action='changed' WHERE id=?",
                (audit_id,),
            )
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute(
                "DELETE FROM admin_audit_log WHERE id=?", (audit_id,)
            )
```

```python
# tests/test_admin_moderation_v1653.py
import sqlite3
import unittest

from moderation import (
    account_restrictions,
    clear_account_restriction,
    ensure_moderation_schema,
    set_account_restriction,
)


class ModerationDomainTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_moderation_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_two_account_restrictions_are_independent(self):
        set_account_restriction(
            self.conn, "business", 20, "content_hidden",
            1423181561, "Tekshiruv", now=100,
        )
        set_account_restriction(
            self.conn, "business", 20, "account_blocked",
            1423181561, "Soxta profil", now=101,
        )
        clear_account_restriction(
            self.conn, "business", 20, "content_hidden",
            1423181561, "Kontent tekshirildi", now=102,
        )
        self.assertEqual(
            account_restrictions(self.conn, "business", 20),
            {"account_blocked"},
        )
```

- [ ] **Step 2: Import xatolari bilan testlarni yiqitish**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_admin_audit_v1653 \
  tests.test_admin_moderation_v1653 -v
```

- [ ] **Step 3: Schema yozish**

```sql
CREATE TABLE IF NOT EXISTS admin_audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  admin_tg_id INTEGER NOT NULL,
  action TEXT NOT NULL,
  target_kind TEXT NOT NULL,
  target_id TEXT NOT NULL,
  before_json TEXT NOT NULL DEFAULT '{}',
  after_json TEXT NOT NULL DEFAULT '{}',
  reason TEXT NOT NULL DEFAULT '',
  ip_hash TEXT NOT NULL DEFAULT '',
  user_agent TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL
);

CREATE TRIGGER IF NOT EXISTS admin_audit_no_update
BEFORE UPDATE ON admin_audit_log
BEGIN SELECT RAISE(ABORT, 'admin audit is append-only'); END;

CREATE TRIGGER IF NOT EXISTS admin_audit_no_delete
BEFORE DELETE ON admin_audit_log
BEGIN SELECT RAISE(ABORT, 'admin audit is append-only'); END;

CREATE TABLE IF NOT EXISTS account_restrictions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_type TEXT NOT NULL CHECK(actor_type IN ('user','business')),
  actor_id INTEGER NOT NULL,
  restriction TEXT NOT NULL
    CHECK(restriction IN ('content_hidden','account_blocked')),
  status TEXT NOT NULL DEFAULT 'active'
    CHECK(status IN ('active','revoked')),
  reason TEXT NOT NULL,
  created_by_tg_id INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  revoked_by_tg_id INTEGER,
  revoked_reason TEXT NOT NULL DEFAULT '',
  revoked_at INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_account_restriction_active
ON account_restrictions(actor_type,actor_id,restriction)
WHERE status='active';

CREATE TABLE IF NOT EXISTS admin_account_notes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_type TEXT NOT NULL CHECK(actor_type IN ('user','business')),
  actor_id INTEGER NOT NULL,
  note TEXT NOT NULL,
  admin_tg_id INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS content_moderation(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  content_kind TEXT NOT NULL,
  content_id INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('hidden','visible','removed')),
  reason TEXT NOT NULL,
  changed_by_tg_id INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_content_moderation_latest
ON content_moderation(content_kind,content_id,id DESC);

CREATE TABLE IF NOT EXISTS moderation_reports(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reporter_user_id INTEGER NOT NULL,
  content_kind TEXT NOT NULL,
  content_id INTEGER NOT NULL,
  reason_code TEXT NOT NULL,
  comment TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open'
    CHECK(status IN ('open','reviewing','resolved','dismissed')),
  assigned_admin_tg_id INTEGER,
  resolution TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
```

- [ ] **Step 4: Audit tranzaksiya qoidasini yozish**

Admin mutation helperiga callerning ochiq transactioni beriladi. Asosiy row o‘zgarishi va `append_admin_audit` bir commitda bo‘ladi. Audit insert yiqilsa business mutation rollback qilinadi.

- [ ] **Step 5: Migratsiya va domain test**

`database.py::_migrate`:

```python
ensure_admin_audit_schema(conn)
ensure_moderation_schema(conn)
```

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_admin_audit_v1653 \
  tests.test_admin_moderation_v1653 \
  tests.test_production_foundation -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add admin_audit.py moderation.py database.py tests/test_admin_audit_v1653.py tests/test_admin_moderation_v1653.py
git commit -m "feat: add append only admin audit and moderation state"
```

---

### Task 2: Admin dashboard va to‘lov navbati API

**Files:**
- Create: `admin_queries.py`
- Modify: `admin_api.py`
- Modify: `payment_api.py`
- Test: `tests/test_admin_api_v1653.py`

**Endpoints:**

- `GET /api/admin/dashboard`
- `GET /api/admin/payments`
- `GET /api/admin/payments/{id}`
- Task 3 va 4da qo‘shilgan price/payment method/review endpointlari.

- [ ] **Step 1: Admin isolation va aggregate testini yozish**

```python
def test_admin_dashboard_requires_admin_cookie(self):
    response = self.user_client.get(
        "/api/admin/dashboard",
        headers=self.user_auth,
    )
    self.assertEqual(response.status_code, 401)

def test_dashboard_returns_expected_sections_without_secrets(self):
    response = self.admin_client.get("/api/admin/dashboard")
    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertEqual(
        set(payload),
        {
            "payments",
            "users",
            "businesses",
            "content",
            "reports",
            "activity",
        },
    )
    self.assertNotIn("pass_hash", response.text)
    self.assertNotIn("token_hash", response.text)
    self.assertNotIn("receipt_path", response.text)
```

`tests/test_admin_api_v1653.py` temp DB, mobile session va HTTPS admin auth cookie’ni `tests/test_payment_api_v1652.py` fixture usuli bilan yaratadi.

- [ ] **Step 2: Endpoint 404 bilan testni yiqitish**

Run: `.venv/bin/python -m unittest tests.test_admin_api_v1653.AdminDashboardApiTests -v`

- [ ] **Step 3: Bounded aggregate querylar**

`admin_queries.dashboard_snapshot(conn, now)` faqat `COUNT`, `SUM` va indekslangan statuslar bilan:

- pending/approved/rejected payment soni va summasi;
- 24 soat/30 kun yangi users/businesses;
- active products/services/advertisements;
- open reports;
- oxirgi 10 audit hodisasi safe projection.

Har response `generated_at` va server timezone’ni qaytaradi.

- [ ] **Step 4: To‘lov reviewga audit ulash**

`approve/reject/cancel`, price va payment method o‘zgarishlarida:

```python
append_admin_audit(
    conn,
    admin_tg_id=admin["tg_id"],
    action="payment.approve",
    target={"kind": "payment", "id": payment_id},
    before=before,
    after=after,
    reason=reason,
    request_meta=audit_request_meta(request),
)
```

IP raw saqlanmaydi; `ADMIN_AUDIT_IP_SECRET` bilan HMAC hash.

- [ ] **Step 5: Test**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_admin_api_v1653.AdminDashboardApiTests \
  tests.test_payment_api_v1652.AdminPaymentApiTests \
  tests.test_admin_audit_v1653 -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add admin_queries.py admin_api.py payment_api.py tests/test_admin_api_v1653.py
git commit -m "feat: add admin dashboard and audited payment queue"
```

---

### Task 3: Foydalanuvchi va biznes boshqaruvi

**Files:**
- Modify: `admin_queries.py`
- Modify: `admin_api.py`
- Modify: `moderation.py`
- Modify: `main.py`
- Test: `tests/test_admin_api_v1653.py`
- Test: `tests/test_admin_moderation_v1653.py`

**Endpoints:**

- `GET /api/admin/users?q=&status=&page=1`
- `GET /api/admin/users/{user_id}`
- `GET /api/admin/businesses?q=&status=&page=1`
- `GET /api/admin/businesses/{business_id}`
- `POST /api/admin/accounts/{actor_type}/{actor_id}/restrict`
- `POST /api/admin/accounts/{actor_type}/{actor_id}/unrestrict`
- `POST /api/admin/accounts/{actor_type}/{actor_id}/notes`

- [ ] **Step 1: Pagination, privacy va restriction testlari**

```python
def test_user_list_is_paginated_and_hides_private_location(self):
    response = self.admin_client.get(
        "/api/admin/users", params={"q": "Ali", "page": 1}
    )
    self.assertEqual(response.status_code, 200)
    self.assertLessEqual(len(response.json()["items"]), 50)
    self.assertNotIn("pass_hash", response.text)
    self.assertNotIn("token_hash", response.text)

def test_content_hidden_and_account_blocked_can_be_set_independently(self):
    for restriction in ("content_hidden", "account_blocked"):
        response = self.admin_client.post(
            f"/api/admin/accounts/business/{self.business_id}/restrict",
            json={"restriction": restriction, "reason": "Tekshiruv"},
        )
        self.assertEqual(response.status_code, 200)
    detail = self.admin_client.get(
        f"/api/admin/businesses/{self.business_id}"
    ).json()
    self.assertEqual(
        set(detail["active_restrictions"]),
        {"content_hidden", "account_blocked"},
    )
```

- [ ] **Step 2: Testni endpointlar yo‘qligi bilan yiqitish**

Run: `.venv/bin/python -m unittest tests.test_admin_api_v1653.AdminAccountApiTests -v`

- [ ] **Step 3: Safe admin projections**

Admin user detail:

- id, tg_id, login, name, phone, role, status, created_at;
- profile completion;
- counts: businesses/items/services/orders;
- active restrictions;
- never password/token hashes.

Business detail:

- identity, type/activity, public address/phone, owner safe summary;
- subscription summary;
- products/services/ads counts;
- payment summary;
- restrictions.

Search query minimum 2 belgi; max page size 50; SQL parameterized.
Detail javobida `admin_account_notes` faqat admin API orqali qaytadi;
oddiy/public profil endpointlari uni hech qachon chiqarmaydi. Yangi note
maksimum 2 000 belgi va append-only audit hodisasi bilan yoziladi.

- [ ] **Step 4: Blocked mutation middleware**

User aniqlangandan keyin barcha mutation (`POST/PUT/PATCH/DELETE`) uchun actor account restriction tekshiriladi. Quyidagilar istisno:

- admin API;
- auth logout;
- payment status read;
- support/report endpoint.

403:

```json
{
  "detail": "Hisob vaqtincha bloklangan.",
  "code": "account_blocked"
}
```

- [ ] **Step 5: Restriction audit va test**

Restrict/unrestrict reason majburiy; before/after snapshot auditga shu tranzaksiyada yoziladi.

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_admin_api_v1653.AdminAccountApiTests \
  tests.test_admin_moderation_v1653 \
  tests.test_public_access_contract -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add admin_queries.py admin_api.py moderation.py main.py tests/test_admin_api_v1653.py tests/test_admin_moderation_v1653.py
git commit -m "feat: add admin account controls"
```

---

### Task 4: Kontent moderation va public visibility

**Files:**
- Modify: `admin_queries.py`
- Modify: `admin_api.py`
- Modify: `moderation.py`
- Modify: `api.py`
- Modify: `district_offers.py`
- Test: `tests/test_admin_api_v1653.py`
- Test: `tests/test_admin_moderation_v1653.py`
- Test: `tests/test_public_search_api.py`
- Test: `tests/test_pro_follow_map_api.py`

**Endpoints:**

- `GET /api/admin/content?kind=product&status=visible&q=&page=1`
- `GET /api/admin/content/{kind}/{id}`
- `POST /api/admin/content/{kind}/{id}/hide`
- `POST /api/admin/content/{kind}/{id}/restore`
- `POST /api/admin/content/{kind}/{id}/remove`

Supported `kind`: `product`, `service`, `advertisement`, `business`, `profile`. `listing` va `story` kod yo‘li keyingi bosqich uchun schema darajasida qabul qilinadi, ammo MVP flag o‘chiq bo‘lganda admin listda default ko‘rsatilmaydi.

- [ ] **Step 1: Immediate publish va reactive hide testlari**

```python
def test_new_product_is_public_until_admin_hides_it(self):
    before = self.client.get("/api/search", params={"q": "Audit burg‘i"})
    self.assertIn(self.product_id, product_ids(before.json()))
    hidden = self.admin_client.post(
        f"/api/admin/content/product/{self.product_id}/hide",
        json={"reason": "Shikoyat tekshiruvi"},
    )
    self.assertEqual(hidden.status_code, 200)
    after = self.client.get("/api/search", params={"q": "Audit burg‘i"})
    self.assertNotIn(self.product_id, product_ids(after.json()))

def test_content_hidden_account_is_removed_from_search_map_and_home(self):
    self.restrict_business("content_hidden")
    self.assert_business_absent_from_public_search_map_and_home()
    owner = self.client.get(
        "/api/items/my",
        headers=self.owner_auth,
    )
    self.assertIn(self.product_id, {row["id"] for row in owner.json()})

def test_remove_is_soft_delete_with_mandatory_reason(self):
    missing = self.admin_client.post(
        f"/api/admin/content/product/{self.product_id}/remove",
        json={"reason": ""},
    )
    self.assertEqual(missing.status_code, 400)
    removed = self.admin_client.post(
        f"/api/admin/content/product/{self.product_id}/remove",
        json={"reason": "Firibgarlik tasdiqlandi"},
    )
    self.assertEqual(removed.status_code, 200)
    self.assertEqual(removed.json()["moderation_status"], "removed")
```

- [ ] **Step 2: Testni visibility filter yo‘qligi bilan yiqitish**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_admin_moderation_v1653.PublicModerationTests -v
```

- [ ] **Step 3: Markaziy SQL visibility helper**

`moderation.py` raw string interpolation qilmaydigan helper beradi:

```python
def public_owner_allowed(conn, actor_type, actor_id):
    restrictions = account_restrictions(conn, actor_type, actor_id)
    return "content_hidden" not in restrictions and "account_blocked" not in restrictions
```

Public response yig‘ilishidan oldin qo‘llanadi:

- `/api/search`, `/api/browse`;
- `/api/map`;
- `/api/home/district-offers`;
- `/api/advertisements/active`;
- public business/profile detail;
- public product/service list;
- followed profile strip.

Owner/admin endpointlari ushbu filterdan foydalanmaydi.

- [ ] **Step 4: Individual content latest-state filter**

`content_moderation`ning eng oxirgi yozuvi `hidden` yoki `removed` bo‘lsa
public responsega kirmaydi. `remove` fayl/database yozuvini fizik
o‘chirmaydigan moderation holatidir va majburiy sabab talab qiladi. Restore
yangi `visible` event yaratadi; eski event o‘chirilmaydi.

- [ ] **Step 5: Regression**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_admin_moderation_v1653 \
  tests.test_public_search_api \
  tests.test_pro_follow_map_api \
  tests.test_district_offers_api -v
```

Expected: qidiruv/xarita/tuman takliflari ishlaydi; hidden content yo‘q; private district oshkor bo‘lmaydi.

- [ ] **Step 6: Commit**

```bash
git add admin_queries.py admin_api.py moderation.py api.py district_offers.py tests
git commit -m "feat: add reactive content moderation filters"
```

---

### Task 5: Shikoyatlar va ko‘rib chiqish navbati

**Files:**
- Modify: `api.py`
- Modify: `admin_api.py`
- Modify: `admin_queries.py`
- Test: `tests/test_admin_api_v1653.py`
- Test: `tests/test_admin_moderation_v1653.py`

**Endpoints:**

- User: `POST /api/reports`
- Admin: `GET /api/admin/reports?status=open&page=1`
- Admin: `GET /api/admin/reports/{report_id}`
- Admin: `POST /api/admin/reports/{report_id}/assign`
- Admin: `POST /api/admin/reports/{report_id}/resolve`
- Admin: `POST /api/admin/reports/{report_id}/dismiss`

- [ ] **Step 1: Report validation va admin workflow testlari**

```python
def test_user_cannot_duplicate_open_report_for_same_content(self):
    body = {
        "content_kind": "product",
        "content_id": self.product_id,
        "reason_code": "fraud",
        "comment": "Narx va manzil soxta",
    }
    first = self.client.post(
        "/api/reports", headers=self.reporter_auth, json=body
    )
    second = self.client.post(
        "/api/reports", headers=self.reporter_auth, json=body
    )
    self.assertEqual(first.status_code, 201)
    self.assertEqual(second.status_code, 409)

def test_resolve_can_hide_content_in_one_transaction(self):
    response = self.admin_client.post(
        f"/api/admin/reports/{self.report_id}/resolve",
        json={
            "resolution": "Kontent yashirildi",
            "moderation_action": "hide_content",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json()["status"], "resolved")
```

- [ ] **Step 2: Testlarni 404 bilan yiqitish**

Run: `.venv/bin/python -m unittest tests.test_admin_api_v1653.AdminReportApiTests -v`

- [ ] **Step 3: User report validation**

- faqat mavjud va ko‘rinadigan supported content;
- self-report rad;
- `reason_code` allowlist;
- comment maksimum 500 belgi;
- bir reporter + bir content uchun bitta open/reviewing report;
- rate limit: 10 report / 24 soat.

- [ ] **Step 4: Admin qarorini atomar yozish**

Resolve body action:

- `none`;
- `hide_content`;
- `content_hidden`;
- `account_blocked`.

Report status, moderation/restriction va audit bitta transactionda. Dismissda sabab majburiy.

- [ ] **Step 5: Test**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_admin_api_v1653.AdminReportApiTests \
  tests.test_admin_moderation_v1653 \
  tests.test_admin_audit_v1653 -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add api.py admin_api.py admin_queries.py moderation.py tests
git commit -m "feat: add complaint review workflow"
```

---

### Task 6: Audit o‘qish API va eksport

**Files:**
- Modify: `admin_api.py`
- Modify: `admin_queries.py`
- Test: `tests/test_admin_api_v1653.py`

**Endpoints:**

- `GET /api/admin/audit?action=&admin_tg_id=&from=&to=&page=1`
- `GET /api/admin/audit/{audit_id}`
- `GET /api/admin/audit/export.csv?...`

- [ ] **Step 1: Filter, pagination va no-mutation test**

```python
def test_audit_is_paginated_and_read_only(self):
    response = self.admin_client.get(
        "/api/admin/audit",
        params={"action": "payment.approve", "page": 1},
    )
    self.assertEqual(response.status_code, 200)
    self.assertLessEqual(len(response.json()["items"]), 100)
    self.assertEqual(
        self.admin_client.delete("/api/admin/audit/1").status_code,
        405,
    )
```

- [ ] **Step 2: Endpoint 404 bilan testni yiqitish**

- [ ] **Step 3: Safe projection va CSV**

Default page size 50, max 100. CSV maksimum 10 000 row. JSON fieldlar CSVda canonical compact JSON. `Cache-Control: no-store`; admin cookie majburiy.

- [ ] **Step 4: Test**

Run: `.venv/bin/python -m unittest tests.test_admin_api_v1653.AdminAuditApiTests -v`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add admin_api.py admin_queries.py tests/test_admin_api_v1653.py
git commit -m "feat: expose read only admin audit history"
```

---

### Task 7: Yetti bo‘limli responsive admin frontend

**Files:**
- Modify: `admin/index.html`
- Modify: `admin/styles.css`
- Modify: `admin/app.js`
- Test: `tests/test_admin_frontend_v1653_contract.py`
- Test: `tests/admin-ui-smoke.cjs`

**Admin navigation:**

1. Boshqaruv paneli
2. To‘lovlar
3. Narxlar va to‘lov usullari
4. Foydalanuvchilar va bizneslar
5. Kontent
6. Shikoyatlar
7. Audit tarixi

- [ ] **Step 1: Frontend contract testini yozish**

```python
# tests/test_admin_frontend_v1653_contract.py
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AdminFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "admin" / "index.html").read_text("utf-8")
        cls.js = (ROOT / "admin" / "app.js").read_text("utf-8")
        cls.css = (ROOT / "admin" / "styles.css").read_text("utf-8")

    def test_seven_admin_sections_exist(self):
        for key in (
            "dashboard", "payments", "pricing", "accounts",
            "content", "reports", "audit",
        ):
            self.assertIn(f'data-admin-page="{key}"', self.html)

    def test_admin_uses_only_admin_api_and_cookie_session(self):
        self.assertIn("/api/admin/auth/me", self.js)
        self.assertIn("/api/admin/dashboard", self.js)
        self.assertNotIn("Authorization: Bearer", self.js)

    def test_mobile_breakpoint_and_drawer_exist(self):
        self.assertIn("@media (max-width: 760px)", self.css)
        self.assertIn('id="adminNavToggle"', self.html)
```

- [ ] **Step 2: Yetti section yo‘qligi bilan testni yiqitish**

Run: `.venv/bin/python -m unittest tests.test_admin_frontend_v1653_contract -v`

- [ ] **Step 3: App shell**

- topbar: Ko‘prik Admin, current admin ID, logout;
- desktop: chap sidebar;
- mobile: drawer + fixed topbar;
- content: loading/error/empty states;
- global confirm dialog;
- toast region `aria-live="polite"`;
- keyboard focus va 44px touch target.

- [ ] **Step 4: Sahifalarni API bilan ulash**

- dashboard cards va recent activity;
- payment table + receipt modal + approve/reject/cancel;
- price inline edit va payment method active toggle;
- accounts search/detail/restrictions;
- content filters/detail/hide/restore;
- content remove (soft-delete) + mandatory reason;
- reports assign/resolve/dismiss;
- audit filters/detail/CSV link.

Har mutatsiyada reason dialog kerakli holatda majburiy. Double clickni oldini olish uchun request davomida tugma disabled.

- [ ] **Step 5: Responsive smoke**

`tests/admin-ui-smoke.cjs` DOM contractda:

- desktop sidebar;
- mobile drawer;
- payment decision actionlari;
- no main-site link;
- admin fetchlar `/api/admin/` prefix.

Run:

```bash
.venv/bin/python -m unittest tests.test_admin_frontend_v1653_contract -v
node tests/admin-ui-smoke.cjs
```

Expected: `OK`, Node exit 0.

- [ ] **Step 6: Commit**

```bash
git add admin/index.html admin/styles.css admin/app.js tests/test_admin_frontend_v1653_contract.py tests/admin-ui-smoke.cjs
git commit -m "feat: build responsive Ko‘prik admin site"
```

---

### Task 8: BUILD v1653 va to‘liq regressiya

**Files:**
- Modify: `main.py`
- Modify: `admin/index.html`
- Create: `docs/v1653-admin-site.md`
- Test: all tests

- [ ] **Step 1: Build marker**

`/api/build`:

```json
{
  "build": "v1653",
  "admin_site_v1653": true,
  "moderation_v1653": true,
  "append_only_admin_audit_v1653": true
}
```

- [ ] **Step 2: Markerlarni yangilash**

- `main.py`: `APP_BUILD = "v1653"`;
- `admin/index.html`: `<!-- ADMIN BUILD: v1653 -->`;
- release hujjati: endpointlar, restrictions, audit, migration, rollback.

- [ ] **Step 3: To‘liq test**

Run:

```bash
.venv/bin/python -m compileall -q .
.venv/bin/python -m unittest discover -s tests -q
node tests/admin-ui-smoke.cjs
node tests/ad-upload-ui-smoke.cjs
node tests/subscription-ui-smoke.cjs
node tests/district-offers-ui-smoke.cjs
wc -l static/index.html admin/index.html admin/styles.css admin/app.js
```

Expected:

- compile xatosiz;
- avvalgi 278 va yangi testlar `OK`;
- smoke testlar exit 0;
- line count release hujjatida aynan yozilgan.

- [ ] **Step 4: Commit**

```bash
git add main.py admin docs/v1653-admin-site.md
git commit -m "release: prepare Ko‘prik v1653 admin site"
```

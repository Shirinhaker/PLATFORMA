# Manual Payments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ko‘prikda reklama joylash, Plus/Pro obuna sotib olish va kelajakdagi e’lon joylash uchun kvitansiyaga asoslangan, admin tasdiqlaydigan xavfsiz to‘lov tizimini yaratish.

**Architecture:** Foydalanuvchi tanlagan xizmat va narxni server hisoblaydi, kvitansiyani private katalogga yuklaydi va bitta tranzaksiyada `payment_requests` yozuviga biriktiradi. Admin qarori `BEGIN IMMEDIATE` ichidagi qat’iy holat o‘tishi orqali bajariladi. Tasdiqlangandan keyingina reklama yoki obuna faollashadi. Telegram ishlamasa asosiy tranzaksiya bekor bo‘lmaydi; xabar `telegram_outbox` orqali qayta yuboriladi.

**Tech Stack:** Python 3.12, FastAPI, SQLite/WAL, vanilla HTML/CSS/JavaScript, HMAC/SHA-256, `unittest`.

## Global Constraints

- Kirish BUILD: `v1651`; yakuniy BUILD: `v1652`.
- Kvitansiya majburiy; JPG, PNG yoki WEBP; maksimum 5 MB.
- Kvitansiya hech qachon `/uploads` yoki boshqa public static katalogda saqlanmaydi.
- Narxni frontend yubormaydi; frontend faqat xizmat kodi va tanlangan parametrlarni yuboradi.
- Faqat `pending` so‘rov `approved` yoki `rejected`ga o‘tadi.
- Rad etishda va tasdiqni bekor qilishda sabab majburiy.
- Rad etilgan so‘rovga foydalanuvchi yangi kvitansiya bilan qayta topshiradi.
- Tasdiqni bekor qilish tashqi pul qaytarishni avtomatlashtirmaydi; admin sabab yozadi va refundni qo‘lda bajaradi.
- Obuna faollashganda `is_demo=0`; demo endpoint faqat `TEST_MODE=1`da ishlaydi.
- E’lon to‘lovi to‘liq tayyorlanadi, lekin `MVP_LISTINGS_ENABLED=0` sabab UI va public route yopiq qoladi.
- Reklama tasdiqlanmaguncha `status='payment_pending'`; active reklama feediga kirmaydi.
- Boshqa bo‘limlar, ayniqsa buyurtmalar va xizmat buyurtmalari, o‘zgarmaydi.

## Fayl tuzilishi

- Create: `payments.py` — schema, narx snapshoti va holat o‘tishlari.
- Create: `receipt_storage.py` — private kvitansiya saqlash, MIME magic va HMAC token.
- Create: `payment_api.py` — foydalanuvchi va admin to‘lov endpointlari.
- Create: `notification_delivery.py` — sayt bildirishnomasi va Telegram outbox.
- Modify: `database.py` — schema migratsiyasi.
- Modify: `subscriptions.py` — pullik obunani faollashtirish.
- Modify: `api.py` — reklama pending oqimi, demo cheklovi, notification feed.
- Modify: `admin_api.py` — payment routerini admin auth bilan himoyalash.
- Modify: `main.py` — routerlar, private cleanup lifecycle va BUILD.
- Modify: `static/index.html` — tarif/reklama to‘lov oynasi va “To‘lovlarim”.
- Modify: `.env.production.example`.
- Create: `tests/test_payment_domain_v1652.py`.
- Create: `tests/test_receipt_storage_v1652.py`.
- Create: `tests/test_payment_api_v1652.py`.
- Create: `tests/test_payment_security_v1652.py`.
- Create: `tests/test_payment_notification_v1652.py`.
- Create: `tests/test_payment_frontend_v1652_contract.py`.

---

### Task 1: To‘lov schema va qat’iy holat mashinasi

**Files:**
- Create: `payments.py`
- Modify: `database.py`
- Test: `tests/test_payment_domain_v1652.py`

**Interfaces:**
- `ensure_payment_schema(conn) -> None`
- `create_payment_request(conn, *, owner, service, target, price, receipt, now) -> dict`
- `approve_payment(conn, payment_id, admin_tg_id, reason="", now=None) -> dict`
- `reject_payment(conn, payment_id, admin_tg_id, reason, now=None) -> dict`
- `cancel_approved_payment(conn, payment_id, admin_tg_id, reason, now=None) -> dict`
- `resubmit_payment(conn, payment_id, owner, receipt, now=None) -> dict`

- [ ] **Step 1: Holat testlarini yozish**

```python
# tests/test_payment_domain_v1652.py
import sqlite3
import unittest

from payments import (
    PaymentConflict,
    PaymentValidationError,
    approve_payment,
    cancel_approved_payment,
    create_payment_request,
    ensure_payment_schema,
    reject_payment,
    resubmit_payment,
)


class PaymentDomainTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_payment_schema(self.conn)
        self.payment = create_payment_request(
            self.conn,
            owner={"user_id": 10, "actor_type": "business", "business_id": 20},
            service="subscription",
            target={"plan_code": "plus", "duration_months": 1},
            price={"amount": 99000, "currency": "UZS", "price_code": "plus_1m"},
            receipt={"path": "2026/07/r1.webp", "mime": "image/webp", "sha256": "a" * 64},
            now=100,
        )

    def tearDown(self):
        self.conn.close()

    def test_approve_is_single_use(self):
        approved = approve_payment(
            self.conn, self.payment["id"], 1423181561, now=110
        )
        self.assertEqual(approved["status"], "approved")
        with self.assertRaises(PaymentConflict):
            approve_payment(
                self.conn, self.payment["id"], 1423181561, now=111
            )

    def test_reject_requires_reason_and_resubmit_returns_pending(self):
        with self.assertRaises(PaymentValidationError):
            reject_payment(
                self.conn, self.payment["id"], 1423181561, "", now=110
            )
        rejected = reject_payment(
            self.conn, self.payment["id"], 1423181561, "Rasm o‘qilmaydi", now=111
        )
        self.assertEqual(rejected["status"], "rejected")
        pending = resubmit_payment(
            self.conn,
            self.payment["id"],
            {"user_id": 10, "actor_type": "business", "business_id": 20},
            {"path": "2026/07/r2.png", "mime": "image/png", "sha256": "b" * 64},
            now=112,
        )
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["public_reason"], "")

    def test_cancel_approved_requires_reason(self):
        approve_payment(self.conn, self.payment["id"], 1423181561, now=110)
        cancelled = cancel_approved_payment(
            self.conn,
            self.payment["id"],
            1423181561,
            "Bank orqali qo‘lda qaytarildi",
            now=120,
        )
        self.assertEqual(cancelled["status"], "cancelled")
```

- [ ] **Step 2: Testni import xatosi bilan yiqitish**

Run: `.venv/bin/python -m unittest tests.test_payment_domain_v1652 -v`

Expected: `ModuleNotFoundError: payments`.

- [ ] **Step 3: Schema yozish**

```sql
CREATE TABLE IF NOT EXISTS platform_prices(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  price_code TEXT NOT NULL UNIQUE,
  amount_uzs INTEGER NOT NULL CHECK(amount_uzs >= 0),
  active INTEGER NOT NULL DEFAULT 1,
  updated_by_tg_id INTEGER,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_methods(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  method_type TEXT NOT NULL,
  name TEXT NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}',
  recipient_name TEXT NOT NULL DEFAULT '',
  instructions TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_code TEXT NOT NULL UNIQUE,
  actor_type TEXT NOT NULL CHECK(actor_type IN ('user','business')),
  user_id INTEGER NOT NULL,
  business_id INTEGER,
  service_type TEXT NOT NULL CHECK(service_type IN ('advertisement','subscription','listing')),
  target_id INTEGER,
  plan_code TEXT NOT NULL DEFAULT '',
  duration_months INTEGER NOT NULL DEFAULT 0,
  quantity INTEGER NOT NULL DEFAULT 1,
  unit_price_snapshot INTEGER NOT NULL,
  amount_snapshot INTEGER NOT NULL,
  payment_method_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK(status IN ('pending','approved','rejected','cancelled')),
  approved_by_tg_id INTEGER,
  approved_at INTEGER NOT NULL DEFAULT 0,
  rejected_at INTEGER NOT NULL DEFAULT 0,
  cancelled_at INTEGER NOT NULL DEFAULT 0,
  public_reason TEXT NOT NULL DEFAULT '',
  internal_note TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY(payment_method_id) REFERENCES payment_methods(id)
);

CREATE TABLE IF NOT EXISTS payment_attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payment_request_id INTEGER NOT NULL,
  attempt_no INTEGER NOT NULL,
  receipt_filename TEXT NOT NULL,
  receipt_mime TEXT NOT NULL,
  receipt_sha256 TEXT NOT NULL,
  submitted_at INTEGER NOT NULL,
  reviewed_at INTEGER NOT NULL DEFAULT 0,
  review_status TEXT NOT NULL DEFAULT 'pending'
    CHECK(review_status IN ('pending','approved','rejected','superseded')),
  review_reason TEXT NOT NULL DEFAULT '',
  UNIQUE(payment_request_id, attempt_no),
  FOREIGN KEY(payment_request_id) REFERENCES payment_requests(id)
);

CREATE TABLE IF NOT EXISTS payment_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payment_request_id INTEGER NOT NULL,
  from_status TEXT NOT NULL,
  to_status TEXT NOT NULL,
  actor_kind TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at INTEGER NOT NULL,
  FOREIGN KEY(payment_request_id) REFERENCES payment_requests(id)
);
```

Indexlar:

```sql
CREATE INDEX IF NOT EXISTS idx_payment_requests_owner
  ON payment_requests(user_id,actor_type,business_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payment_requests_status
  ON payment_requests(status,created_at,id);
CREATE INDEX IF NOT EXISTS idx_payment_attempts_request
  ON payment_attempts(payment_request_id,attempt_no DESC);
CREATE INDEX IF NOT EXISTS idx_payment_attempts_receipt_hash
  ON payment_attempts(receipt_sha256);
CREATE INDEX IF NOT EXISTS idx_payment_events_request
  ON payment_events(payment_request_id,id);
```

Joriy kvitansiya — `attempt_no` eng katta bo‘lgan attempt. Bir xil
`receipt_sha256` boshqa `pending` yoki `approved` requestdagi attemptda
bor-yo‘qligi `BEGIN IMMEDIATE` tranzaksiyasida tekshiriladi; topilsa
`PaymentConflict` qaytariladi.

- [ ] **Step 4: Holat o‘tishlarini atomar qilish**

Har review funksiyasi:

```python
conn.execute("BEGIN IMMEDIATE")
row = conn.execute(
    "SELECT * FROM payment_requests WHERE id=?", (payment_id,)
).fetchone()
if not row or row["status"] != expected:
    conn.rollback()
    raise PaymentConflict("To‘lov holati allaqachon o‘zgargan.")
```

`payment_events` append-only yozuvi shu tranzaksiyada yaratiladi. Exceptionda rollback.

- [ ] **Step 5: `database.py::_migrate`ga ulash**

```python
from payments import ensure_payment_schema
ensure_payment_schema(conn)
```

Run:

```bash
.venv/bin/python -m unittest tests.test_payment_domain_v1652 -v
.venv/bin/python -m unittest tests.test_production_foundation -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add payments.py database.py tests/test_payment_domain_v1652.py
git commit -m "feat: add manual payment state machine"
```

---

### Task 2: Private kvitansiya saqlash va bir martalik token

**Files:**
- Create: `receipt_storage.py`
- Modify: `runtime_config.py`
- Modify: `.env.production.example`
- Test: `tests/test_receipt_storage_v1652.py`
- Test: `tests/test_payment_security_v1652.py`

**Interfaces:**
- `store_receipt(root, owner_id, raw, content_type, secret, now=None) -> dict`
- `verify_receipt_token(token, secret, owner_id, now=None) -> dict`
- `claim_receipt(root, token_data, payment_id) -> dict`
- `delete_expired_unclaimed_receipts(root, older_than) -> int`

- [ ] **Step 1: MIME, owner va expiry testlarini yozish**

```python
# tests/test_receipt_storage_v1652.py
import tempfile
import unittest

from receipt_storage import (
    ReceiptValidationError,
    store_receipt,
    verify_receipt_token,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 64


class ReceiptStorageTests(unittest.TestCase):
    def test_png_is_private_and_token_is_owner_bound(self):
        with tempfile.TemporaryDirectory() as root:
            stored = store_receipt(
                root, 10, PNG, "image/png", "s" * 48, now=100
            )
            self.assertNotIn("/uploads/", stored["relative_path"])
            data = verify_receipt_token(
                stored["token"], "s" * 48, owner_id=10, now=101
            )
            self.assertEqual(data["sha256"], stored["sha256"])
            with self.assertRaises(ReceiptValidationError):
                verify_receipt_token(
                    stored["token"], "s" * 48, owner_id=11, now=101
                )

    def test_extension_or_header_cannot_fake_file_type(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ReceiptValidationError):
                store_receipt(
                    root, 10, b"<script>alert(1)</script>", "image/png",
                    "s" * 48, now=100,
                )

    def test_receipt_over_five_megabytes_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ReceiptValidationError):
                store_receipt(
                    root, 10, PNG + b"x" * (5 * 1024 * 1024),
                    "image/png", "s" * 48, now=100,
                )
```

- [ ] **Step 2: Testni import xatosi bilan yiqitish**

Run: `.venv/bin/python -m unittest tests.test_receipt_storage_v1652 -v`

- [ ] **Step 3: Magic sniff va token formatini yozish**

Aniqlash:

- JPEG: `FF D8 FF`;
- PNG: `89 50 4E 47 0D 0A 1A 0A`;
- WEBP: `RIFF....WEBP`.

Token payload:

```json
{
  "owner_id": 10,
  "relative_path": "unclaimed/2026/07/...",
  "mime": "image/png",
  "sha256": "...",
  "expires_at": 3700,
  "nonce": "..."
}
```

Payload base64url qilinadi va `HMAC-SHA256(PAYMENT_TOKEN_SECRET, payload)` bilan imzolanadi. Token bir soat amal qiladi. Fayl nomi foydalanuvchi yuborgan nomdan olinmaydi.

- [ ] **Step 4: Private katalog konfiguratsiyasi**

`.env.production.example`:

```dotenv
PAYMENT_RECEIPT_DIR=/data/private/payment_receipts
PAYMENT_TOKEN_SECRET=replace-with-at-least-48-random-characters
```

`runtime_config.validate_runtime_config` productionda:

- katalog persistent root ichida;
- secret kamida 48 belgi;
- `/uploads` va `static` ichida emasligini tekshiradi.

- [ ] **Step 5: Security testlarini yashil qilish**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_receipt_storage_v1652 \
  tests.test_payment_security_v1652 \
  tests.test_v1616_security_contract -v
```

Expected: `OK`; private receipt uchun public route yo‘q.

- [ ] **Step 6: Commit**

```bash
git add receipt_storage.py runtime_config.py .env.production.example tests/test_receipt_storage_v1652.py tests/test_payment_security_v1652.py
git commit -m "feat: store payment receipts outside public media"
```

---

### Task 3: Platforma narxlari va to‘lov usullari

**Files:**
- Modify: `payments.py`
- Create: `payment_api.py`
- Modify: `admin_api.py`
- Modify: `main.py`
- Test: `tests/test_payment_api_v1652.py`

**Endpoints:**

- User: `GET /api/payments/catalog`
- Admin: `GET /api/admin/prices`
- Admin: `PUT /api/admin/prices/{price_id}`
- Admin: `GET /api/admin/payment-methods`
- Admin: `POST /api/admin/payment-methods`
- Admin: `PUT /api/admin/payment-methods/{method_id}`

- [ ] **Step 1: Narx admin tomonidan boshqarilishini test qilish**

```python
def test_catalog_ignores_client_price_and_returns_active_server_rows(self):
    response = self.client.get(
        "/api/payments/catalog",
        headers=self.user_auth,
    )
    self.assertEqual(response.status_code, 200)
    self.assertTrue(response.json()["services"]["subscription"])
    self.assertNotIn("secret", response.text.lower())

def test_non_admin_cannot_change_price(self):
    response = self.client.put(
        "/api/admin/prices/1",
        headers=self.user_auth,
        json={"amount": 1},
    )
    self.assertEqual(response.status_code, 401)
```

`tests/test_payment_api_v1652.py` setupida `test_subscription_api.py`dagi temp DB + mobile session usuli va `test_admin_auth_v1651.py`dagi HTTPS admin cookie usuli aynan qo‘llanadi.

- [ ] **Step 2: Endpointlar 404 bo‘lishi bilan testni yiqitish**

Run: `.venv/bin/python -m unittest tests.test_payment_api_v1652.PaymentCatalogApiTests -v`

- [ ] **Step 3: Boshlang‘ich narx seedlarini idempotent yozish**

`payments.ensure_default_prices(conn)`:

- `subscription_plus_1m`, `subscription_plus_3m`, `subscription_plus_12m`;
- `subscription_pro_1m`, `subscription_pro_3m`, `subscription_pro_12m`;
- `advertisement_district_day` — mavjud district kunlik tarifiga teng;
- `listing_publish`.

Seed faqat yo‘q `price_code`ni qo‘shadi; admin o‘zgartirgan narxni
keyingi deploy qayta yozmaydi. `service_type`, plan va duration
`payments.PRICE_RULES` server allowlistidan olinadi, DBdagi erkin JSON kod
bajarmaydi.

- [ ] **Step 4: Admin dependency**

`admin_api.py`:

```python
def require_admin(request: Request, conn=Depends(get_db)):
    token = request.cookies.get(ADMIN_COOKIE, "")
    session = admin_session(conn, token)
    if not session or not is_admin_tg_id(session["tg_id"]):
        if session:
            revoke_admin_session(conn, token)
        raise HTTPException(401, "Admin sessiyasi talab qilinadi.")
    return session
```

Barcha `/api/admin/prices*` va `/api/admin/payment-methods*` endpointlari `Depends(require_admin)` ishlatadi. Har o‘zgarish keyingi rejada `admin_audit_log`ga yoziladi; hozir `payment_events`ga `config_change` metadata qo‘shilmaydi.

- [ ] **Step 5: Testlarni yashil qilish**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_payment_api_v1652.PaymentCatalogApiTests \
  tests.test_admin_auth_v1651 -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add payments.py payment_api.py admin_api.py main.py tests/test_payment_api_v1652.py
git commit -m "feat: expose admin controlled payment catalog"
```

---

### Task 4: Foydalanuvchi to‘lov so‘rovi va qayta yuborish API

**Files:**
- Modify: `payment_api.py`
- Modify: `main.py`
- Test: `tests/test_payment_notification_v1652.py`
- Test: `tests/test_payment_security_v1652.py`

**Endpoints:**

- `POST /api/payments/receipts`
- `POST /api/payments/requests`
- `GET /api/payments/my?actor_type=user|business`
- `GET /api/payments/{payment_id}/receipt`
- `POST /api/payments/{payment_id}/resubmit`

- [ ] **Step 1: End-to-end request testini yozish**

```python
def test_user_uploads_receipt_and_creates_pending_subscription(self):
    uploaded = self.client.post(
        "/api/payments/receipts",
        headers={
            **self.business_auth,
            "Content-Type": "image/png",
        },
        content=PNG,
    )
    self.assertEqual(uploaded.status_code, 200)
    created = self.client.post(
        "/api/payments/requests",
        headers=self.business_auth,
        json={
            "actor_type": "business",
            "service_type": "subscription",
            "price_code": "plus_1m",
            "payment_method_id": self.method_id,
            "receipt_token": uploaded.json()["receipt_token"],
            "target": {"plan_code": "plus", "duration_months": 1},
            "amount": 1,
        },
    )
    self.assertEqual(created.status_code, 201)
    self.assertEqual(created.json()["status"], "pending")
    self.assertNotEqual(created.json()["amount"], 1)
```

Qo‘shimcha testlar:

- boshqa user receipt tokenini ishlata olmaydi;
- inactive payment method rad etiladi;
- biznes actor faqat o‘z biznesi uchun so‘rov qiladi;
- token ikkinchi marta ishlatilmaydi;
- listing flag o‘chiq bo‘lsa listing request 404 `feature_disabled`;
- `GET /my` boshqa user so‘rovini qaytarmaydi.
- owner receipt endpoint boshqa user uchun 404, owner uchun `no-store`.

- [ ] **Step 2: Testlarni 404 bilan yiqitish**

Run: `.venv/bin/python -m unittest tests.test_payment_api_v1652.UserPaymentApiTests -v`

- [ ] **Step 3: Request tranzaksiyasini yozish**

`POST /requests` ketma-ketligi:

1. `require_user`;
2. actor ownership;
3. `service_type/price_code` active `platform_prices` row va
   `PRICE_RULES` mosligi;
4. target configni server price `config_json` bilan moslashtirish;
5. payment method active;
6. receipt token owner/expiry/HMAC;
7. `BEGIN IMMEDIATE`;
8. target materialni pending holatda yaratish;
9. receiptni `claimed/<payment_id>/...`ga ko‘chirish;
10. payment row, `payment_attempts`dagi 1-attempt va `pending` event;
11. commit;
12. faqat safe response.

Safe response receipt path yoki SHA’ni qaytarmaydi.

`GET /api/payments/{id}/receipt` faqat requestning aynan user/business
egasiga joriy attempt faylini beradi. Response `Cache-Control: no-store,
private`; private absolute path response body yoki headerda ochilmaydi.

- [ ] **Step 4: Resubmit qoidasi**

`POST /{id}/resubmit`:

- owner aynan mos;
- faqat `rejected`;
- yangi receipt token;
- eski attempt `superseded` bo‘lib audit uchun saqlanadi;
- yangi private receipt bilan keyingi `attempt_no` yaratiladi;
- requestdagi `public_reason` tozalanadi;
- `pending` event qo‘shiladi.

- [ ] **Step 5: Testlarni yashil qilish**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_payment_api_v1652.UserPaymentApiTests \
  tests.test_payment_security_v1652 -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add payment_api.py main.py tests/test_payment_api_v1652.py tests/test_payment_security_v1652.py
git commit -m "feat: accept private manual payment requests"
```

---

### Task 5: Admin qarori va xizmatni faollashtirish

**Files:**
- Modify: `payment_api.py`
- Modify: `payments.py`
- Modify: `subscriptions.py`
- Modify: `api.py`
- Test: `tests/test_payment_api_v1652.py`
- Test: `tests/test_subscription_api.py`

**Endpoints:**

- `GET /api/admin/payments?status=pending&service_type=subscription`
- `GET /api/admin/payments/{payment_id}`
- `GET /api/admin/payments/{payment_id}/receipt`
- `POST /api/admin/payments/{payment_id}/approve`
- `POST /api/admin/payments/{payment_id}/reject`
- `POST /api/admin/payments/{payment_id}/cancel`

- [ ] **Step 1: Approval side-effect testlarini yozish**

```python
def test_approve_subscription_activates_non_demo_plan_once(self):
    response = self.admin_client.post(
        f"/api/admin/payments/{self.subscription_payment_id}/approve",
        json={"reason": ""},
    )
    self.assertEqual(response.status_code, 200)
    conn = db()
    row = conn.execute(
        "SELECT * FROM business_subscriptions "
        "WHERE business_id=? AND status='active'",
        (self.business_id,),
    ).fetchone()
    conn.close()
    self.assertEqual(row["plan_code"], "plus")
    self.assertEqual(row["is_demo"], 0)
    duplicate = self.admin_client.post(
        f"/api/admin/payments/{self.subscription_payment_id}/approve",
        json={"reason": ""},
    )
    self.assertEqual(duplicate.status_code, 409)

def test_pending_ad_is_absent_until_approved(self):
    before = self.client.get("/api/advertisements/active").json()
    self.assertNotIn(self.ad_id, {row["id"] for row in before})
    self.admin_client.post(
        f"/api/admin/payments/{self.ad_payment_id}/approve",
        json={"reason": ""},
    )
    after = self.client.get("/api/advertisements/active").json()
    self.assertIn(self.ad_id, {row["id"] for row in after})
```

- [ ] **Step 2: Testlarni pending material sabab yiqitish**

Run: `.venv/bin/python -m unittest tests.test_payment_api_v1652.AdminPaymentApiTests -v`

- [ ] **Step 3: Pullik obuna funksiyasi**

`subscriptions.py`:

```python
def activate_paid_subscription(
    conn, business_id, plan_code, duration_months, payment_request_id, now=None
):
    # validate plan/duration
    # supersede current active row
    # insert active row with is_demo=0
    # payment_request_id unique link
```

`business_subscriptions`ga idempotency uchun nullable `payment_request_id` va unique partial index qo‘shiladi.

- [ ] **Step 4: Material activator registry**

`payments.py`:

```python
SERVICE_ACTIVATORS = {
    "subscription": activate_subscription_payment,
    "advertisement": activate_advertisement_payment,
    "listing": activate_listing_payment,
}
```

Activator va payment status bir `BEGIN IMMEDIATE` tranzaksiyasida ishlaydi:

- subscription → active paid plan;
- advertisement → `payment_pending`dan `active`ga, real `start_at/end_at`;
- listing → `payment_pending`dan `active`ga, lekin feature flag o‘chiq paytda public ko‘rinmaydi.

- [ ] **Step 5: Receipt download xavfsizligi**

`GET /receipt`:

- faqat admin cookie;
- `FileResponse` private absolute validated path;
- `Cache-Control: no-store, private`;
- `Content-Disposition: inline; filename="receipt-<id>.<ext>"`;
- path traversalda 404.

- [ ] **Step 6: Demo endpointni productionda yopish**

`api.py::activate_subscription_demo`:

```python
if not TEST_MODE:
    raise HTTPException(404, "Demo obuna mavjud emas.")
```

Production test demo endpoint 404, test-mode regression esa mavjud testlarda yashil.

- [ ] **Step 7: Admin testlarini yashil qilish**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_payment_api_v1652.AdminPaymentApiTests \
  tests.test_subscription_api \
  tests.test_payment_security_v1652 -v
```

Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add payment_api.py payments.py subscriptions.py api.py database.py tests
git commit -m "feat: activate paid services after admin approval"
```

---

### Task 6: Sayt va Telegram bildirishnomalari

**Files:**
- Create: `notification_delivery.py`
- Modify: `database.py`
- Modify: `api.py`
- Modify: `payment_api.py`
- Modify: `main.py`
- Test: `tests/test_payment_api_v1652.py`

- [ ] **Step 1: Notification/outbox testini yozish**

```python
# tests/test_payment_notification_v1652.py
def test_reject_commits_even_when_telegram_is_temporarily_down(self):
    with patch(
        "notification_delivery.send_telegram_now",
        side_effect=RuntimeError("down"),
    ):
        response = self.admin_client.post(
            f"/api/admin/payments/{self.payment_id}/reject",
            json={"reason": "Kvitansiya raqami o‘qilmaydi"},
        )
    self.assertEqual(response.status_code, 200)
    conn = db()
    payment = conn.execute(
        "SELECT status FROM payment_requests WHERE id=?", (self.payment_id,)
    ).fetchone()
    outbox = conn.execute(
        "SELECT status FROM telegram_outbox ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    self.assertEqual(payment["status"], "rejected")
    self.assertEqual(outbox["status"], "pending")
```

- [ ] **Step 2: Schema**

```sql
CREATE TABLE IF NOT EXISTS telegram_outbox(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  tg_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at INTEGER NOT NULL,
  sent_at INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL
);
```

- [ ] **Step 3: Bir tranzaksiyadagi ikkita xabar**

Har payment eventda:

1. `notifications`ga `requires_action=0`, `action_type='payment_status'`;
2. `telegram_outbox`ga pending.

`/api/notifications` so‘rovidan `requires_action=1` filtri olib tashlanadi; `/api/notifications/actions` esa faqat action talab qiladigan xabarlarni qaytarishda davom etadi.

- [ ] **Step 4: Retry worker**

`main.py` lifecycle task har 30 soniyada maksimum 25 pending outbox yozuvini oladi. Backoff: 1, 5, 15, 60 daqiqa; beshinchi xatodan keyin `failed`. App shutdown’da task cancel/await.

- [ ] **Step 5: Testlar**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_payment_notification_v1652 \
  tests.test_payment_api_v1652 \
  tests.test_public_access_contract -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add notification_delivery.py database.py api.py payment_api.py main.py tests/test_payment_notification_v1652.py
git commit -m "feat: notify users about payment decisions"
```

---

### Task 7: Reklama/obuna to‘lov UI va “To‘lovlarim”

**Files:**
- Modify: `static/index.html`
- Test: `tests/test_payment_frontend_v1652_contract.py`
- Test: `tests/ad-upload-ui-smoke.cjs`
- Test: `tests/subscription-ui-smoke.cjs`

- [ ] **Step 1: Frontend contract testini yozish**

```python
# tests/test_payment_frontend_v1652_contract.py
import unittest
from tests.frontend_source import frontend_source


class PaymentFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_payment_dialog_uses_server_catalog(self):
        self.assertIn('id="paymentRequestModal"', self.html)
        self.assertIn('"/api/payments/catalog"', self.html)
        self.assertIn('"/api/payments/receipts"', self.html)
        self.assertIn('"/api/payments/requests"', self.html)

    def test_user_can_see_status_and_resubmit_rejected_receipt(self):
        self.assertIn('id="myPaymentsSection"', self.html)
        self.assertIn("paymentStatusLabel", self.html)
        self.assertIn("/resubmit", self.html)

    def test_client_does_not_supply_trusted_amount(self):
        self.assertNotIn("trustedPaymentAmount", self.html)
```

- [ ] **Step 2: Testni markup yo‘qligi bilan yiqitish**

Run: `.venv/bin/python -m unittest tests.test_payment_frontend_v1652_contract -v`

- [ ] **Step 3: To‘lov dialogini yozish**

Dialog:

- tanlangan xizmat/tarif va serverdan kelgan summa;
- active to‘lov usullari;
- instruktsiya va rekvizitlar;
- kvitansiya preview;
- kvitansiya chekkasida `×` o‘chirish tugmasi;
- yuborish progressi;
- pending success holati.

Frontend `amount`ni yubormaydi. Reklama builder oldin reklama materialini pending yaratadi, so‘ng umumiy to‘lov dialogini ochadi. Obuna kartasi ham shu dialogni ishlatadi.

- [ ] **Step 4: “To‘lovlarim” ro‘yxati**

Har karta:

- xizmat turi;
- summa;
- status;
- yuborilgan sana;
- rad sababi;
- rejected bo‘lsa yangi receipt + “Qayta yuborish”.

MVPda listing turi frontenddan chaqirilmaydi.

- [ ] **Step 5: Mobil va desktop smoke**

Run:

```bash
.venv/bin/python -m unittest tests.test_payment_frontend_v1652_contract -v
node tests/ad-upload-ui-smoke.cjs
node tests/subscription-ui-smoke.cjs
```

Expected: `OK`, Node exit 0.

- [ ] **Step 6: Commit**

```bash
git add static/index.html tests/test_payment_frontend_v1652_contract.py tests/ad-upload-ui-smoke.cjs tests/subscription-ui-smoke.cjs
git commit -m "feat: add receipt based payment UI"
```

---

### Task 8: BUILD v1652 va to‘liq regressiya

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Create: `docs/v1652-manual-payments.md`
- Test: all tests

- [ ] **Step 1: Build contract**

`/api/build`:

```json
{
  "build": "v1652",
  "manual_payments_v1652": true,
  "private_receipts_v1652": true,
  "paid_subscription_activation_v1652": true
}
```

- [ ] **Step 2: BUILD markerlarni yangilash**

- `main.py`: `APP_BUILD = "v1652"`;
- `static/index.html`: `<!-- BUILD: v1652 -->`;
- release hujjatida migration, env, rollback va o‘zgargan fayllar.

- [ ] **Step 3: To‘liq tekshiruv**

Run:

```bash
.venv/bin/python -m compileall -q .
.venv/bin/python -m unittest discover -s tests -q
node tests/ad-upload-ui-smoke.cjs
node tests/subscription-ui-smoke.cjs
node tests/district-offers-ui-smoke.cjs
wc -l static/index.html
```

Expected:

- compile xatosiz;
- avvalgi 278 test va yangi testlar `OK`;
- barcha Node smoke exit 0;
- qator soni release hujjatiga aynan yozilgan.

- [ ] **Step 4: Commit**

```bash
git add main.py static/index.html docs/v1652-manual-payments.md
git commit -m "release: prepare Ko‘prik v1652 manual payments"
```

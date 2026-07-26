# Ko‘prik Telegram Auth-Only Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telegram botni ro‘yxatdan o‘tish va yangi qurilmadan kirish kodlari hamda yangi akkaunt login-parolini yuboradigan autentifikatsiya botiga aylantirish.

**Architecture:** Sayt bir martalik maxfiy deep-link challenge yaratadi. Bot `/start <token>` orqali haqiqiy Telegram ID ni challenge bilan bog‘laydi va 6 xonali kodni yuboradi; sayt kodni tekshirgach akkaunt yoki 30 kunlik sessiya yaratadi. Challenge yaratish/tekshirish alohida `telegram_auth.py` modulida, HTTP va webhook integratsiyasi `main.py`da, interfeys `static/index.html`da qoladi.

**Tech Stack:** Python 3.12, FastAPI, SQLite, Telegram Bot API, vanilla JavaScript, `unittest`.

## Global Constraints

- BUILD `v1639` bo‘ladi.
- Bot faqat autentifikatsiya kodi, yangi akkaunt login-paroli va oddiy `/start` yo‘riqnomasini yuboradi.
- Ro‘yxatdan o‘tish va yangi qurilmadan kirishda Telegram kodi talab qilinadi.
- Tasdiqlangan sayt sessiyasi 30 kun amal qiladi.
- Deep-link token va OTP bazada ochiq matnda saqlanmaydi.
- OTP 5 daqiqa amal qiladi, 5 ta urinishga ruxsat beradi va qayta yuborish oralig‘i 60 soniya.
- Doimiy login-parol faqat akkaunt yaratilganda bot va saytda bir marta ko‘rsatiladi.
- Telegram ID si mavjud akkauntni boshqa Telegram akkaunti tasdiqlay olmaydi.
- Eski Telegram ID siz akkaunt to‘g‘ri login-parol va bot kodi orqali birinchi marta bog‘lanadi.
- SMS, QR, parolni tiklash va Mini App ushbu bosqichga kirmaydi.
- Mavjud profil, qidiruv, xarita, istoriyalar, e’lonlar, kabinet va biznes ma’lumotlari o‘zgarmaydi.
- `TEST_MODE` OTPni HTTP javobi, diagnostika yoki logga chiqarmaydi.

---

## Fayl tuzilishi

- Create: `telegram_auth.py`
  - deep-link token, OTP xeshi, challenge yaratish/faollashtirish/tekshirish;
  - vaqt va urinish qoidalari;
  - HTTP yoki Telegramga bog‘liq bo‘lmagan domen funksiyalari.
- Modify: `database.py`
  - `telegram_pending_registrations`;
  - `telegram_auth_challenges`;
  - kerakli indekslar.
- Modify: `main.py`
  - Telegram bot username aniqlash;
  - register/login start va verify endpointlari;
  - 30 kunlik sessiya yaratish;
  - auth-only webhook;
  - bot menyusini Web App’dan oddiy holatga qaytarish.
- Modify: `api.py`
  - buyurtma holati va chat bo‘yicha Telegram `sendMessage` chaqiruvlarini olib tashlash;
  - sayt ichidagi/push xabarlarni saqlash.
- Modify: `static/index.html`
  - Telegram deep-link ro‘yxatdan o‘tish;
  - Telegram kodi bilan yangi qurilmadan kirish;
  - SMS va eski Mini App registratsiya interfeysini olib tashlash.
- Modify: `.env.production.example`
  - ixtiyoriy `BOT_USERNAME` sozlamasi.
- Create: `tests/test_telegram_auth_domain.py`
- Create: `tests/test_telegram_auth_api.py`
- Create: `tests/test_telegram_auth_bot_contract.py`
- Create: `tests/test_telegram_auth_frontend_contract.py`
- Modify: build qiymatini tekshiradigan mavjud testlar.
- Create: `docs/v1639-telegram-auth-only-bot.md`

---

### Task 1: Telegram challenge domeni va baza sxemasi

**Files:**
- Create: `telegram_auth.py`
- Modify: `database.py`
- Create: `tests/test_telegram_auth_domain.py`

**Interfaces:**
- Produces:
  - `create_start_challenge(conn, purpose, user_id=0, pending_registration_id=0, now=None) -> dict`
  - `activate_start_challenge(conn, start_token, tg_id, otp_secret, fixed_code="", now=None) -> dict`
  - `verify_telegram_code(conn, challenge_id, code, otp_secret, now=None) -> sqlite3.Row`
  - `hash_start_token(token) -> str`
  - `hash_telegram_code(challenge_id, tg_id, code, otp_secret) -> str`
  - constants `TELEGRAM_LINK_TTL=600`, `TELEGRAM_CODE_TTL=300`, `TELEGRAM_MAX_ATTEMPTS=5`, `TELEGRAM_RESEND_AFTER=60`.

- [ ] **Step 1: Write failing challenge tests**

```python
class TelegramAuthDomainTests(unittest.TestCase):
    def test_start_token_is_stored_only_as_hash(self):
        created = create_start_challenge(self.conn, "register", pending_registration_id=7, now=1000)
        row = self.conn.execute(
            "SELECT * FROM telegram_auth_challenges WHERE id=?", (created["id"],)
        ).fetchone()
        self.assertNotEqual(row["start_token_hash"], created["start_token"])
        self.assertEqual(row["start_token_hash"], hash_start_token(created["start_token"]))

    def test_activation_binds_telegram_and_hashes_code(self):
        created = create_start_challenge(self.conn, "login", user_id=4, now=1000)
        activated = activate_start_challenge(
            self.conn, created["start_token"], 998877, "secret", fixed_code="123456", now=1001
        )
        self.assertEqual(activated["code"], "123456")
        row = self.conn.execute(
            "SELECT * FROM telegram_auth_challenges WHERE id=?", (created["id"],)
        ).fetchone()
        self.assertEqual(row["tg_id"], 998877)
        self.assertNotEqual(row["code_hash"], "123456")

    def test_code_expires_and_locks_after_five_failures(self):
        created = create_start_challenge(self.conn, "login", user_id=4, now=1000)
        activate_start_challenge(
            self.conn, created["start_token"], 998877, "secret", fixed_code="123456", now=1001
        )
        for _ in range(5):
            with self.assertRaises(TelegramAuthError):
                verify_telegram_code(self.conn, created["id"], "000000", "secret", now=1002)
        with self.assertRaises(TelegramAuthError) as locked:
            verify_telegram_code(self.conn, created["id"], "123456", "secret", now=1003)
        self.assertEqual(locked.exception.code, "attempts_exhausted")
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m unittest tests.test_telegram_auth_domain -v
```

Expected: FAIL because `telegram_auth` and the new tables do not exist.

- [ ] **Step 3: Add exact SQLite schema**

Add to `init_db()` in `database.py`:

```sql
CREATE TABLE IF NOT EXISTS telegram_pending_registrations(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload_json TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    verified_at INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS telegram_auth_challenges(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purpose TEXT NOT NULL,
    user_id INTEGER DEFAULT 0,
    pending_registration_id INTEGER DEFAULT 0,
    start_token_hash TEXT NOT NULL UNIQUE,
    tg_id INTEGER DEFAULT 0,
    code_hash TEXT DEFAULT '',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 5,
    created_at INTEGER NOT NULL,
    start_expires_at INTEGER NOT NULL,
    code_sent_at INTEGER DEFAULT 0,
    code_expires_at INTEGER DEFAULT 0,
    verified_at INTEGER DEFAULT 0,
    invalidated_at INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tg_auth_start
ON telegram_auth_challenges(start_token_hash, start_expires_at);
CREATE INDEX IF NOT EXISTS idx_tg_auth_user
ON telegram_auth_challenges(user_id, purpose, created_at);
```

- [ ] **Step 4: Implement minimal domain module**

`telegram_auth.py` must:

```python
class TelegramAuthError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def hash_start_token(token):
    return hashlib.sha256(str(token).encode()).hexdigest()


def hash_telegram_code(challenge_id, tg_id, code, otp_secret):
    raw = f"{int(challenge_id)}:{int(tg_id)}:{code}:{otp_secret}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

`create_start_challenge()` old active challengelarni `invalidated_at` bilan yopadi,
`secrets.token_urlsafe(24)` yaratadi va faqat xeshini yozadi.

`activate_start_challenge()` tokenni bir marta qabul qiladi, 6 xonali kod
yaratadi, `tg_id`, `code_hash`, `code_sent_at`, `code_expires_at`ni yozadi va
ochiq kodni faqat chaqiruvchiga qaytaradi.

`verify_telegram_code()` `verified_at`, muddat, `attempts` va HMAC-safe
`compare_digest`ni tekshiradi. Muvaffaqiyatda `verified_at`ni yozib, row qaytaradi.

- [ ] **Step 5: Run domain tests and verify GREEN**

Run:

```bash
python -m unittest tests.test_telegram_auth_domain -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit Task 1 if Git is available**

```bash
git add telegram_auth.py database.py tests/test_telegram_auth_domain.py
git commit -m "feat: add telegram authentication challenges"
```

If this extracted source has no `.git`, record the changed-file list instead of
inventing a commit.

---

### Task 2: Ro‘yxatdan o‘tish va yangi qurilma API oqimi

**Files:**
- Modify: `main.py`
- Create: `tests/test_telegram_auth_api.py`

**Interfaces:**
- Consumes Task 1 domain functions.
- Produces:
  - `POST /api/telegram-auth/register/start`
  - `POST /api/telegram-auth/register/verify`
  - `POST /api/telegram-auth/login/start`
  - `POST /api/telegram-auth/login/verify`
  - helper `create_mobile_session(conn, user_id, device_name, now=None) -> dict`
  - helper `resolve_bot_username() -> str`.

- [ ] **Step 1: Write failing registration API tests**

Tests must patch `main.tg_call` and use a temporary database. Essential cases:

```python
def test_register_start_returns_deep_link_without_otp(self):
    response = self.client.post("/api/telegram-auth/register/start", json={
        "role": "user", "name": "Ali Valiyev", "phone": "+998901234567"
    })
    self.assertEqual(response.status_code, 200)
    body = response.json()
    self.assertIn("https://t.me/", body["deep_link"])
    self.assertIn("?start=", body["deep_link"])
    self.assertNotIn("code", body)
    self.assertNotIn("test_code", body)

def test_register_verify_creates_user_session_and_sends_credentials_once(self):
    challenge = self.start_and_activate_registration(tg_id=777001, code="123456")
    response = self.client.post("/api/telegram-auth/register/verify", json={
        "request_id": challenge["id"],
        "code": "123456",
        "device_name": "Chrome Windows"
    })
    self.assertEqual(response.status_code, 200)
    body = response.json()
    self.assertEqual(body["expires_in"], 30 * 24 * 60 * 60)
    self.assertTrue(body["login"])
    self.assertTrue(body["password"])
    self.assertEqual(self.sent_messages[-1]["chat_id"], 777001)
    second = self.client.post("/api/telegram-auth/register/verify", json={
        "request_id": challenge["id"], "code": "123456"
    })
    self.assertEqual(second.status_code, 400)
```

- [ ] **Step 2: Write failing login API tests**

```python
def test_login_start_validates_password_but_does_not_create_session(self):
    response = self.client.post("/api/telegram-auth/login/start", json={
        "login": "user100", "password": "correct-pass"
    })
    self.assertEqual(response.status_code, 200)
    self.assertNotIn("access_token", response.json())
    self.assertIn("?start=", response.json()["deep_link"])

def test_linked_account_rejects_wrong_telegram_id(self):
    challenge = self.start_login_for_user(linked_tg_id=777001)
    result = self.activate_bot_link(challenge, tg_id=888002)
    self.assertEqual(result["bot_error"], "wrong_telegram_account")

def test_login_verify_returns_thirty_day_session(self):
    challenge = self.start_and_activate_login(tg_id=777001, code="123456")
    response = self.client.post("/api/telegram-auth/login/verify", json={
        "request_id": challenge["id"],
        "code": "123456",
        "device_name": "Safari iPhone"
    })
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json()["expires_in"], 30 * 24 * 60 * 60)
```

- [ ] **Step 3: Run API tests and verify RED**

Run:

```bash
python -m unittest tests.test_telegram_auth_api -v
```

Expected: FAIL with 404/new helper missing.

- [ ] **Step 4: Implement register start/verify**

`register/start`:

1. validate `role`, `name`, optional normalized phone, business `yon/address`;
2. reject duplicate phone+role without exposing OTP;
3. insert `telegram_pending_registrations` with JSON payload and 10-minute expiry;
4. call `create_start_challenge(..., purpose="register")`;
5. return `request_id`, `deep_link`, `expires_in=600`, `resend_after=60`.

`register/verify`:

1. call `verify_telegram_code`;
2. load non-used pending registration;
3. create user/business using existing `gen_login`, `gen_biz_login`,
   `gen_pass`, `hash_password`;
4. persist challenge `tg_id` into `users.tg_id`;
5. mark pending registration used;
6. create 30-day `mobile_sessions` row;
7. call `tg_call("sendMessage", credentials_payload)` exactly once;
8. return token and credentials exactly once.

- [ ] **Step 5: Implement login start/verify**

`login/start`:

1. validate user or business login and password using one helper;
2. return the same `401 Login yoki parol noto‘g‘ri` for every mismatch;
3. create `purpose="login"` challenge for the owner user;
4. return deep-link without access token.

`login/verify`:

1. verify challenge and code;
2. if `users.tg_id` exists, require exact match;
3. if it is empty, bind the verified challenge `tg_id`;
4. create a 30-day `mobile_sessions` row;
5. return token and role, never return password.

The old `/api/password-auth/login` route must no longer issue a session directly.
Either remove the route or return HTTP 410 with
`"Telegram orqali yangi kirish tasdig‘idan foydalaning."`; the frontend must not
call it after Task 4.

- [ ] **Step 6: Add auth routes to the public middleware allowlist**

Allow only:

```python
"/api/telegram-auth/register/start",
"/api/telegram-auth/register/verify",
"/api/telegram-auth/login/start",
"/api/telegram-auth/login/verify",
```

Remove old SMS register/login routes from the public unauthenticated allowlist.

- [ ] **Step 7: Run API tests and verify GREEN**

Run:

```bash
python -m unittest tests.test_telegram_auth_api -v
```

Expected: all tests PASS, no OTP appears in response output.

- [ ] **Step 8: Commit Task 2 if Git is available**

```bash
git add main.py tests/test_telegram_auth_api.py
git commit -m "feat: add telegram registration and device verification"
```

---

### Task 3: Botni faqat autentifikatsiya vazifasida qoldirish

**Files:**
- Modify: `main.py`
- Modify: `api.py`
- Create: `tests/test_telegram_auth_bot_contract.py`

**Interfaces:**
- Consumes Task 1 `activate_start_challenge`.
- Produces auth-only `/webhook` behavior and `send_auth_code(tg_id, code, purpose)`.

- [ ] **Step 1: Write failing bot contract tests**

```python
def test_setup_bot_removes_web_app_menu(self):
    source = Path("main.py").read_text(encoding="utf-8")
    self.assertIn('"menu_button": {"type": "default"}', source)
    self.assertNotIn('"type": "web_app", "text": "Platforma"', source)

def test_webhook_does_not_store_photo_or_video(self):
    source = Path("main.py").read_text(encoding="utf-8")
    webhook = source[source.index('@app.post("/webhook")'):]
    self.assertNotIn("INSERT INTO media_inbox", webhook)
    self.assertNotIn("callback_query", webhook)

def test_order_api_does_not_send_telegram_service_messages(self):
    source = Path("api.py").read_text(encoding="utf-8")
    self.assertNotIn('from main import tg_call, BASE_URL', source)
    self.assertNotIn('"Ilovada ko\\'rish"', source)
```

Integration test:

```python
def test_start_token_sends_six_digit_code_to_opening_chat(self):
    challenge = self.create_challenge("register")
    response = self.client.post("/webhook", json={
        "update_id": 1,
        "message": {
            "message_id": 4,
            "chat": {"id": 777001},
            "from": {"id": 777001},
            "text": "/start " + challenge["start_token"]
        }
    }, headers={"X-Telegram-Bot-Api-Secret-Token": self.webhook_secret})
    self.assertEqual(response.status_code, 200)
    self.assertRegex(self.sent_messages[-1]["text"], r"\b\d{6}\b")
```

- [ ] **Step 2: Run bot tests and verify RED**

Run:

```bash
python -m unittest tests.test_telegram_auth_bot_contract -v
```

Expected: FAIL because Web App, media and callback code still exist.

- [ ] **Step 3: Simplify bot setup**

`setup_bot()` and manual `_setup`:

```python
await tg_call("setChatMenuButton", {
    "menu_button": {"type": "default"},
})
```

Resolve bot username from `BOT_USERNAME` or Telegram `getMe`; strip leading `@`.
If neither works, auth start endpoints return HTTP 503 with a safe configuration
message.

- [ ] **Step 4: Replace webhook behavior**

Webhook keeps only:

1. Telegram secret header validation;
2. `/start <token>`:
   - activate challenge;
   - enforce linked Telegram ID;
   - send 6-digit code;
3. plain `/start`:
   - send `Ko‘prik saytida “Telegram orqali kod olish” tugmasini bosing.`;
4. unrelated updates return `{"ok": True}` without DB writes or service messages.

- [ ] **Step 5: Remove service Telegram sends from `api.py`**

Delete the three post-commit `notify_tg` blocks in:

- order status update;
- order text chat send;
- order image chat send.

Do not remove in-app notification rows, realtime polling, push outbox or Firebase
delivery.

- [ ] **Step 6: Run bot tests and verify GREEN**

Run:

```bash
python -m unittest tests.test_telegram_auth_bot_contract -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit Task 3 if Git is available**

```bash
git add main.py api.py tests/test_telegram_auth_bot_contract.py
git commit -m "refactor: limit telegram bot to authentication"
```

---

### Task 4: Sayt ro‘yxatdan o‘tish va login interfeysi

**Files:**
- Modify: `static/index.html`
- Create: `tests/test_telegram_auth_frontend_contract.py`

**Interfaces:**
- Consumes Task 2 endpoints.
- Produces:
  - `openTelegramAuthLink(url)`
  - `startTelegramRegistration(payload)`
  - `verifyTelegramRegistration()`
  - `startTelegramLogin(login, password)`
  - `verifyTelegramLogin()`
  - shared 60-second resend timer.

- [ ] **Step 1: Write failing frontend contract tests**

```python
class TelegramAuthFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_registration_uses_telegram_deep_link_api(self):
        self.assertIn("/api/telegram-auth/register/start", self.html)
        self.assertIn("/api/telegram-auth/register/verify", self.html)
        self.assertIn("Telegram orqali kod olish", self.html)

    def test_password_login_requires_telegram_verification(self):
        self.assertIn("/api/telegram-auth/login/start", self.html)
        self.assertIn("/api/telegram-auth/login/verify", self.html)
        self.assertNotIn('api("POST","/api/password-auth/login"', self.html)

    def test_sms_and_mini_app_registration_paths_are_absent(self):
        self.assertNotIn("/api/mobile-auth/register/request-code", self.html)
        self.assertNotIn("/api/mobile-auth/request-code", self.html)
        self.assertNotIn("SMS kod", self.html)
        self.assertNotIn("Telegram akkauntingiz avtomatik tasdiqlanadi", self.html)
```

- [ ] **Step 2: Run frontend tests and verify RED**

Run:

```bash
python -m unittest tests.test_telegram_auth_frontend_contract -v
```

Expected: FAIL because old SMS/direct-password flows remain.

- [ ] **Step 3: Simplify registration markup**

Remove `regMethodChoice`, phone-vs-Telegram method state and Mini App-only
registration. Keep ordinary/business role choice.

For both roles render:

- profile fields;
- optional phone;
- `Telegram orqali kod olish`;
- code field after deep-link creation;
- `Tasdiqlash va kirish`;
- resend button disabled for 60 seconds.

`openTelegramAuthLink(url)`:

```javascript
function openTelegramAuthLink(url){
  var opened=null;
  try{ opened=window.open(url,"_blank","noopener"); }catch(e){}
  if(!opened) window.location.href=url;
}
```

- [ ] **Step 4: Replace registration JavaScript**

`startTelegramRegistration(payload)` calls `/register/start`, stores
`request_id`, opens `deep_link`, then renders the code step.

`verifyTelegramRegistration()` posts:

```javascript
{
  request_id: TELEGRAM_REGISTER_REQUEST_ID,
  code: sixDigitCode,
  device_name: navigator.userAgent.slice(0,100)
}
```

On success:

1. save `access_token` to `koprik_mobile_token`;
2. show credentials once;
3. allow direct cabinet continuation without requiring a second login.

- [ ] **Step 5: Replace login JavaScript**

`submitPasswordLogin()` calls `/api/telegram-auth/login/start`, never receives a
session immediately, opens Telegram and shows the code step.

`verifyTelegramLogin()` calls `/api/telegram-auth/login/verify`, stores the
returned mobile token and calls existing `afterAuth(login_role)`.

Change texts from phone/SMS wording to:

- `Telegram bot yuborgan 6 xonali kodni kiriting`;
- `Telegramni qayta ochish`;
- `Kodni qayta olish`.

- [ ] **Step 6: Run frontend contract and inline-JS syntax tests**

Run:

```bash
python -m unittest tests.test_telegram_auth_frontend_contract -v
node -e "const fs=require('fs');const s=fs.readFileSync('static/index.html','utf8');const m=s.match(/<script>([\\s\\S]*?)<\\/script>/);new Function(m[1]);console.log('inline JS syntax: OK')"
```

Expected: frontend tests PASS and `inline JS syntax: OK`.

- [ ] **Step 7: Commit Task 4 if Git is available**

```bash
git add static/index.html tests/test_telegram_auth_frontend_contract.py
git commit -m "feat: add telegram code flow to web authentication"
```

---

### Task 5: Build flaglari, konfiguratsiya, regressiya va topshirish

**Files:**
- Modify: `main.py`
- Modify: `.env.production.example`
- Modify: `tests/test_cabinet_dashboard_v1637_contract.py`
- Modify: `tests/test_domain_integration_ready.py`
- Modify: `tests/test_first_visit_district_profile_stories_v1638_contract.py`
- Modify: `tests/test_frontend_assets.py`
- Modify: `tests/test_listing_media_frontend_contract.py`
- Modify: `tests/test_production_foundation.py`
- Modify: `tests/test_story_frontend_contract.py`
- Modify: `tests/test_v1616_security_contract.py`
- Create: `docs/v1639-telegram-auth-only-bot.md`

**Interfaces:**
- Produces build `v1639` and deploy checklist.

- [ ] **Step 1: Write failing v1639 build assertions**

Add assertions:

```python
self.assertIn('APP_BUILD = "v1639"', main_text)
self.assertIn('<!-- BUILD: v1639 -->', html)
self.assertIn('"telegram_auth_only_bot_v1639": True', main_text)
self.assertIn('"telegram_deep_link_otp_v1639": True', main_text)
self.assertIn('"trusted_device_30d_v1639": True', main_text)
```

Old product flags must become truthful:

```python
"mobile_phone_verification": False
"phone_registration_ui": False
"dual_registration": False
"password_only_login": False
```

- [ ] **Step 2: Run affected contract tests and verify RED**

Run:

```bash
python -m unittest \
  tests.test_production_foundation \
  tests.test_v1616_security_contract \
  tests.test_first_visit_district_profile_stories_v1638_contract -v
```

Expected: FAIL on v1638/current flags.

- [ ] **Step 3: Update build and deployment configuration**

- set `APP_BUILD = "v1639"`;
- set `<!-- BUILD: v1639 -->`;
- add the three v1639 feature flags;
- update existing build assertions from v1638 to v1639;
- add to `.env.production.example`:

```dotenv
# Ixtiyoriy. Bo‘sh bo‘lsa server Telegram getMe orqali aniqlaydi.
BOT_USERNAME=YOUR_TELEGRAM_BOT_USERNAME
```

- [ ] **Step 4: Document deploy behavior**

`docs/v1639-telegram-auth-only-bot.md` must include:

- Railway variables: `BOT_TOKEN`, `BOT_USERNAME` optional, `BASE_URL`,
  `WEBHOOK_SECRET`, `MOBILE_OTP_SECRET`;
- bot setup after deploy;
- registration and login acceptance checklist;
- note that QR, SMS and password recovery are deferred;
- database backup requirement before deploying schema changes.

- [ ] **Step 5: Run the complete Python suite**

Run:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Expected: all existing and new tests PASS with zero failures/errors.

- [ ] **Step 6: Run frontend contract and JavaScript checks**

Run:

```bash
node tests/district-offers-ui-smoke.cjs --contract-only
node -e "const fs=require('fs');const s=fs.readFileSync('static/index.html','utf8');const m=s.match(/<script>([\\s\\S]*?)<\\/script>/);new Function(m[1]);console.log('inline JS syntax: OK')"
```

Expected:

```text
District offers UI contract passed
inline JS syntax: OK
```

- [ ] **Step 7: Verify secrets and legacy behavior are absent**

Run:

```bash
rg -n '"test_code": code|/api/_test/last_code|INSERT INTO media_inbox|type": "web_app"|from main import tg_call, BASE_URL' main.py api.py static/index.html
```

Expected: no active OTP leak, media webhook, Web App menu or service Telegram
notification match. Any historical comment match must be removed or rewritten.

- [ ] **Step 8: Record changed files and index line count**

Run:

```bash
wc -l static/index.html
```

Report every changed file, BUILD `v1639`, test count and exact `index.html` line
count.

- [ ] **Step 9: Package a clean ZIP**

Create:

```text
Platforma_v1639_telegram_auth_only_bot.zip
```

Exclude:

- `platforma.db`;
- `uploads/`;
- `__pycache__/`;
- `.pytest_cache/`;
- `*.pyc`;
- real `.env` secrets.

- [ ] **Step 10: Commit Task 5 if Git is available**

```bash
git add main.py .env.production.example tests docs/v1639-telegram-auth-only-bot.md
git commit -m "release: build v1639 telegram authentication bot"
```

If this extracted source has no `.git`, deliver the ZIP and exact changed-file
list without claiming a commit.


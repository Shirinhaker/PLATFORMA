# Ko‘prik biznes obunalari Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biznes kabinetining `Onlaynlashtirish` guruhiga egasi boshqaradigan, serverda saqlanadigan Bepul/Plus/Pro demo obuna bo‘limini qo‘shish.

**Architecture:** Obuna qoidalari va entitlement hisoblash alohida `subscriptions.py` modulida turadi; `database.py` faqat jadval va indeks migratsiyasini yaratadi, `api.py` esa autentifikatsiya va HTTP kontraktini boshqaradi. Mavjud bitta sahifali frontend yangi menyu kartasi, responsive tarif ekrani va API holatlarini oladi; boshqa onlayn/tizimlashtirish kartalari va ularning yo‘nalish bo‘yicha joylashuvi o‘zgarmaydi.

**Tech Stack:** Python 3.12, FastAPI, SQLite, stdlib `unittest`, HTML/CSS/vanilla JavaScript, Node.js syntax check, Playwright smoke test.

## Global Constraints

- Yakuniy build aniq `v1612` bo‘ladi.
- Faqat biznes profil obunasi qo‘shiladi va faqat biznes egasi ko‘radi/o‘zgartiradi.
- Tariflar `free`, `plus`, `pro`; Plus/Pro muddatlari faqat `1`, `3`, `12`, Bepul muddati `0` oy.
- Narxlar kodga yozilmaydi va ushbu versiyada haqiqiy to‘lov/karta/Click/Payme bo‘lmaydi.
- Mahsulot/xizmat joylash tarif bilan cheklanmaydi.
- Istoriya funksiyasi obunadan mustaqil qoladi va entitlement helperga ulanmaydi.
- `Sizga yaqin` va xarita chiqarish uchun entitlement helper yaratiladi.
- `CAB_PLANS`, 20 yo‘nalish, navbat, ta’lim, ovqatlanish, xodim ko‘rinishi va boshqa endpointlar o‘zgarmaydi.
- To‘liq ZIP va faqat o‘zgargan fayllar ZIP’i tayyorlanadi.

---

## File map

- Create `subscriptions.py`: tarif katalogi, oy qo‘shish, joriy tarifni normallashtirish, aktivlashtirish va entitlement javobi.
- Modify `database.py`: `business_subscriptions` jadvali va indekslari.
- Modify `api.py`: egaga yopiq GET va demo POST endpointlari.
- Modify `static/index.html`: yangi karta/ekran, responsive CSS, yuklash/faollashtirish/tarix JavaScript’i va follow nomlari.
- Modify `main.py`: `v1612` va build capability.
- Create `tests/test_subscriptions.py`: domen va migratsiya testlari.
- Create `tests/test_subscription_api.py`: egasi/xodim, validatsiya, izolyatsiya va server persistence integratsiyasi.
- Create `tests/test_subscription_frontend_contract.py`: frontend strukturasi, nomlash va build kontrakti.
- Create `tests/subscription-ui-smoke.cjs`: telefon/planshet/desktop render va interaction tekshiruvi.
- Create `docs/business-subscriptions-v1612.md`: foydalanuvchiga sodda funksional topshirish hujjati.

---

### Task 1: Obuna modeli, migratsiya va domen qoidalari

**Files:**
- Create: `tests/test_subscriptions.py`
- Create: `subscriptions.py`
- Modify: `database.py`

**Interfaces:**
- Produces: `PLAN_FEATURES: dict[str, dict[str, bool]]`.
- Produces: `subscription_entitlements(plan_code: str) -> dict[str, bool]`.
- Produces: `current_business_subscription(conn, business_id: int, now: int | None = None) -> dict`.
- Produces: `activate_demo_subscription(conn, business_id: int, plan_code: str, duration_months: int, now: int | None = None) -> dict`.
- Produces: `subscription_payload(conn, business_id: int, now: int | None = None) -> dict`.

- [ ] **Step 1: Write failing schema/default/entitlement tests**

```python
def test_schema_and_default_free(self):
    init_subscription_schema(self.conn)
    payload = subscription_payload(self.conn, 41, now=1_700_000_000)
    self.assertEqual(payload["current"]["plan_code"], "free")
    self.assertEqual(payload["current"]["expires_at"], 0)
    self.assertTrue(payload["features"]["unlimited_items"])
    self.assertFalse(payload["features"]["home_nearby_eligible"])

def test_plan_entitlements_are_cumulative(self):
    self.assertTrue(subscription_entitlements("plus")["home_nearby_eligible"])
    self.assertFalse(subscription_entitlements("plus")["map_marker_eligible"])
    self.assertTrue(subscription_entitlements("pro")["map_marker_eligible"])
    self.assertNotIn("unlimited_stories", subscription_entitlements("pro"))
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `python -m unittest tests.test_subscriptions -v`

Expected: import or missing-symbol failure because `subscriptions.py` does not exist.

- [ ] **Step 3: Implement schema and pure subscription helpers**

`business_subscriptions` columns must match the spec and use indexes on `(business_id,status,expires_at)` and `(business_id,id)`. Use `calendar.monthrange` to preserve calendar dates when adding 1/3/12 months. Expired Plus/Pro rows are updated to `expired`; if no active paid row remains, return a virtual Free current record without inserting duplicate Free rows. Return features with these exact keys:

```python
{
    "unlimited_items": True,
    "home_nearby_eligible": plan_code in ("plus", "pro"),
    "map_marker_eligible": plan_code == "pro",
}
```

- [ ] **Step 4: Add RED tests for activation, renewal, switch and isolation**

```python
def test_same_paid_plan_extends_from_existing_expiry(self):
    first = activate_demo_subscription(self.conn, 7, "plus", 1, now=self.now)
    second = activate_demo_subscription(self.conn, 7, "plus", 3, now=self.now + 60)
    self.assertEqual(second["current"]["starts_at"], first["current"]["starts_at"])
    self.assertGreater(second["current"]["expires_at"], first["current"]["expires_at"])
    self.assertEqual(second["history"], [])

def test_switch_supersedes_previous_and_keeps_businesses_isolated(self):
    activate_demo_subscription(self.conn, 7, "plus", 1, now=self.now)
    switched = activate_demo_subscription(self.conn, 7, "pro", 3, now=self.now + 60)
    other = subscription_payload(self.conn, 8, now=self.now + 60)
    self.assertEqual(switched["current"]["plan_code"], "pro")
    self.assertEqual(switched["history"][0]["status"], "superseded")
    self.assertEqual(other["current"]["plan_code"], "free")
```

- [ ] **Step 5: Implement minimal activation rules and make tests GREEN**

Validation must raise `SubscriptionValidationError` for invalid plan/duration. Same paid plan updates the active row’s expiry; a different plan marks prior active rows `superseded` and inserts a new row. Free supersedes paid rows and inserts one active, perpetual Free row. Commit only inside the activation helper after all writes succeed.

Run: `python -m unittest tests.test_subscriptions -v`

Expected: all subscription unit tests pass.

---

### Task 2: Egaga yopiq obuna API’lari

**Files:**
- Create: `tests/test_subscription_api.py`
- Modify: `api.py`

**Interfaces:**
- Consumes: `subscription_payload(...)`, `activate_demo_subscription(...)`, `SubscriptionValidationError`.
- Produces: `GET /api/business/subscription` returning `{current, features, history, plans, durations, demo_mode}`.
- Produces: `POST /api/business/subscription/demo-activate` consuming `{plan_code, duration_months}` and returning the same payload plus `ok:true`.

- [ ] **Step 1: Write failing owner GET and POST integration tests**

```python
def test_owner_can_read_default_and_activate_plus(self):
    default = self.client.get("/api/business/subscription", headers=self.auth(self.owner_token))
    self.assertEqual(default.status_code, 200)
    self.assertEqual(default.json()["current"]["plan_code"], "free")
    activated = self.client.post(
        "/api/business/subscription/demo-activate",
        headers=self.auth(self.owner_token),
        json={"plan_code": "plus", "duration_months": 3},
    )
    self.assertEqual(activated.status_code, 200)
    self.assertEqual(activated.json()["current"]["plan_code"], "plus")
```

- [ ] **Step 2: Run test and confirm RED**

Run: `python -m unittest tests.test_subscription_api -v`

Expected: both routes return 404.

- [ ] **Step 3: Implement the two routes**

Both routes must call `deny_staff(conn, init_data, "Obunalarim")` before returning business data, then `require_business`. Translate `SubscriptionValidationError` to HTTP 400 and always close the connection through `try/finally`.

- [ ] **Step 4: Add and pass permission/validation/isolation tests**

Cover invalid plan, Free with non-zero duration, paid plan with invalid duration, personal user 403, staff 403, unauthenticated 401 and two separate business owners seeing only their own history.

Run: `python -m unittest tests.test_subscription_api -v`

Expected: all API tests pass.

---

### Task 3: Responsive “Obunalarim” kabinet ekrani

**Files:**
- Create: `tests/test_subscription_frontend_contract.py`
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `GET /api/business/subscription` and `POST /api/business/subscription/demo-activate`.
- Produces: `data-nav="cab-subscriptions"`, `data-screen="cab-subscriptions"`, `loadBusinessSubscription()`, `activateBusinessSubscription(planCode)`.

- [ ] **Step 1: Write failing frontend contract tests**

```python
def test_subscription_card_is_immediately_after_profile(self):
    profile = self.html.index('data-nav="cab-profil"')
    subscription = self.html.index('data-nav="cab-subscriptions"')
    next_existing = self.html.index('data-nav="cab-items"')
    self.assertLess(profile, subscription)
    self.assertLess(subscription, next_existing)

def test_follow_labels_are_unambiguous(self):
    self.assertIn('"cab-following":"Kuzatayotganlar"', self.html)
    self.assertIn('"ucab-subs":"Kuzatayotganlar"', self.html)
```

- [ ] **Step 2: Run frontend tests and confirm RED**

Run: `python -m unittest tests.test_subscription_frontend_contract -v`

Expected: missing navigation card/screen/functions and old follow names fail.

- [ ] **Step 3: Add menu card, screen and responsive CSS**

Insert the card directly after `cab-profil`. The screen must include current plan summary, `1/3/12` segmented controls, Bepul/Plus/Pro cards, demo buttons, history, loading/error/empty regions, and an explicit “Haqiqiy to‘lov ulanmagan” notice. Use `minmax(0,1fr)`, `min-width:0`, wrapping controls and a mobile breakpoint so the document cannot overflow.

- [ ] **Step 4: Add frontend loading and activation behavior**

`loadBusinessSubscription()` renders API state and disables activation buttons while loading. `activateBusinessSubscription()` sends the selected paid duration (Free always sends 0), shows the API error text without leaving the screen, refreshes state on success, and guards duplicate clicks. Navigation to `cab-subscriptions` triggers the loader.

- [ ] **Step 5: Preserve direction-specific layout and hide from staff**

Add `cab-subscriptions` to the owner-only card set used by existing staff visibility logic without changing `CAB_PLANS`. Change only user-facing follow titles from `Obunalarim` to `Kuzatayotganlar`; retain route ids and follow behavior.

- [ ] **Step 6: Verify frontend tests and JS syntax GREEN**

Run:

```bash
python -m unittest tests.test_subscription_frontend_contract -v
python -c "from pathlib import Path; import re; s=Path('static/index.html').read_text(encoding='utf-8'); Path('/tmp/koprik-v1612-inline.js').write_text('\n'.join(re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>',s)),encoding='utf-8')"
node --check /tmp/koprik-v1612-inline.js
```

Expected: all contract tests pass and Node exits 0.

---

### Task 4: Build metadata, UI smoke test and regression suite

**Files:**
- Create: `tests/subscription-ui-smoke.cjs`
- Modify: `main.py`
- Modify: `tests/test_story_frontend_contract.py`

**Interfaces:**
- Produces: `APP_BUILD = "v1612"`, `<!-- BUILD: v1612 -->`, and `/api/build` key `business_subscriptions_demo: True`.

- [ ] **Step 1: Update failing build contract to v1612**

Change the existing build assertions to require `v1612` and the new capability, then run:

`python -m unittest tests.test_story_frontend_contract.BuildMetadataTests -v`

Expected: fail until production metadata is updated.

- [ ] **Step 2: Update build metadata minimally**

Update only `APP_BUILD`, HTML build comment and `/api/build` capability. Do not change deployment files.

- [ ] **Step 3: Add Playwright smoke flow**

Mock `/api/me`, `/api/business/me` and both subscription endpoints. Exercise:

`Biznes kabineti → Obunalarim → 3 oy → Plus demo faollashtirish → joriy tarif Plus`.

At 390×844, 820×1180 and 1440×1000 assert horizontal overflow is at most 2px, the screen is not blank, the current plan is visible, controls respond, and no relevant page errors occur. Save screenshots only under `/tmp/koprik-v1612-qa/`.

- [ ] **Step 4: Run complete verification**

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python -m py_compile main.py api.py database.py subscriptions.py stories.py
node --check /tmp/koprik-v1612-inline.js
```

Start `uvicorn main:app --host 127.0.0.1 --port 8090`, run `node tests/subscription-ui-smoke.cjs`, then stop the server.

Expected: Python suite has zero failures, compilation and JS syntax exit 0, smoke script reports all three viewports passed.

---

### Task 5: Documentation and delivery archives

**Files:**
- Create: `docs/business-subscriptions-v1612.md`
- Create outside project: `Platforma_v1612_business_subscriptions.zip`
- Create outside project: `Platforma_v1612_business_subscriptions_changed_files.zip`

**Interfaces:**
- Produces: full runnable project archive and focused changed-files archive.

- [ ] **Step 1: Write the handoff document**

Document exact menu path, Bepul/Plus/Pro features, demo limitation, renewal/switch behavior, owner-only rule, persistence, API routes, changed runtime files and note that homepage/map/regional story eligibility will be wired in a later task.

- [ ] **Step 2: Record delivery facts**

Run:

```bash
wc -l static/index.html
rg -n 'APP_BUILD = "v1612"|BUILD: v1612|business_subscriptions_demo' main.py static/index.html
find . -maxdepth 3 -type f | sort
```

- [ ] **Step 3: Build both ZIP files**

The full ZIP must exclude local databases, uploaded media, caches, screenshots and nested ZIPs. The changed-files ZIP contains only `subscriptions.py`, `database.py`, `api.py`, `main.py`, `static/index.html`, the four new subscription tests/smoke file, the v1612 document, the approved spec and this plan.

- [ ] **Step 4: Verify archives**

Run `unzip -t` for both files and inspect `unzip -l` to confirm neither archive contains `platforma.db`, `uploads/*`, `__pycache__`, `.pyc`, screenshots or another ZIP.

- [ ] **Step 5: Save both final ZIPs to Library and report links**

Create both as new Library files, preserve returned local identity metadata, then provide clickable local artifact links plus Library save confirmation.

---

## Self-review result

- Spec coverage: every approved rule maps to Tasks 1–5; actual homepage/map/regional story integration remains intentionally excluded.
- Placeholder scan: barcha qadamlar aniq kod, buyruq va kutilgan natija bilan yozilgan.
- Interface consistency: domain helper names are identical across unit, API and frontend tasks; plan codes and feature keys use one spelling throughout.
- Repository note: the supplied project is an extracted ZIP without Git metadata, so commits/worktree merge steps do not apply; verification and delivery ZIPs are the completion boundary.

## Execution note

- Final automated result: 69 Python tests passed; Python compilation, fresh SQLite migration and inline JavaScript syntax checks passed.
- `tests/subscription-ui-smoke.cjs` covers the agreed mobile/tablet/desktop interaction flow, but the current workspace had no Browser plugin or browser binary. The Playwright Chromium download was blocked by the active sandbox policy, so screenshot-based rendered QA was not claimed.

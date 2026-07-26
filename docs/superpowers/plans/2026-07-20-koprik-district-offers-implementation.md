# Ko‘prik District Offers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bosh sahifada foydalanuvchi tumanidagi faol Plus/Pro bizneslardan bittadan mahsulot, xizmat yoki ommaviy e’lonni 30 daqiqalik adolatli navbat bilan, xaritadan keyingi sarlavhasiz uzluksiz railda ko‘rsatish.

**Architecture:** Yangi `district_offers.py` moduli tumanni normallashtirish, 30 daqiqalik slot va bitta biznesdan bitta kontent tanlashni bazaga yozuvsiz bajaradi. `api.py` yengil endpoint orqali joriy foydalanuvchi ID sini modulga beradi; `static/index.html` natijani bir marta yuklab, klientda takrorlangan rail yordamida o‘ngdan chapga oqizadi.

**Tech Stack:** Python 3, FastAPI, SQLite, vanilla JavaScript, HTML/CSS, `unittest`, Node syntax/smoke checks.

## Global Constraints

- BUILD `v1613` bo‘ladi.
- Faqat foydalanuvchi va biznes egasining `users.district` qiymati solishtiriladi; koordinata, radius yoki kilometr hisoblanmaydi.
- Faqat `active` biznes va muddati tugamagan Plus/Pro obuna qatnashadi; Plus va Pro teng huquqli.
- Bir javobda ko‘pi bilan 6 ta noyob biznes va har biznesdan ko‘pi bilan bitta kontent qaytadi.
- E’lon faqat `status='active'` va `visibility='all'` bo‘lsa chiqadi.
- Bosh sahifadagi rail xaritadan keyin, sarlavhasiz bo‘ladi.
- Rail o‘ngdan chapga uzluksiz oqadi; hover, fokus va touch paytida pauza qiladi; `prefers-reduced-motion` avtomatik harakatni o‘chiradi.
- Tumansiz foydalanuvchiga `Tumanni tanlang` tugmasi ko‘rsatiladi.
- Foydalanuvchi tumani API javobidagi kartochkalarga yoki biznesga berilmaydi.
- Web-sayt uchun yakuniy grid/son bu bosqichda kiritilmaydi.
- Mahsulot/xizmat limitlari o‘zgarmaydi; xarita Pro imkoniyati ulanmaydi.
- Istoriyalar obuna tariflaridan mustaqil va mavjud tartibda qoladi.
- Loyiha arxivida Git metadata yo‘q; commit qadamlari o‘rniga har vazifadan keyin test checkpointi yoziladi.

---

### Task 1: Tuman va navbat domen moduli

**Files:**
- Create: `district_offers.py`
- Create: `tests/test_district_offers.py`

**Interfaces:**
- Consumes: `business_subscriptions` jadvali va `subscriptions.py` dagi tarif kodlari.
- Produces: `normalize_district(value: str | None) -> str`, `offer_time_slot(now: int | None = None) -> int`, `district_offers_payload(conn: sqlite3.Connection, user_id: int | None, now: int | None = None, limit: int = 6) -> dict`.

- [ ] **Step 1: Failing unit test skeletini yozish**

`tests/test_district_offers.py` ichida minimal `users`, `businesses`, `items`, `listings`, `listing_media` jadvallarini yarating va `init_subscription_schema(conn)` ni chaqiring. Quyidagi kontraktlarni yozing:

```python
def test_normalize_district_handles_case_spaces_and_apostrophes(self):
    self.assertEqual(normalize_district("  Sho‘rchi  "), "shorchi")
    self.assertEqual(normalize_district("SHO'RCHI"), "shorchi")

def test_missing_user_or_district_requests_district(self):
    self.assertEqual(
        district_offers_payload(self.conn, None, now=self.now),
        {"needs_district": True, "slot": self.now // 1800, "items": []},
    )

def test_only_same_district_active_paid_businesses_are_returned(self):
    payload = district_offers_payload(self.conn, self.viewer_id, now=self.now)
    ids = {item["business_id"] for item in payload["items"]}
    self.assertIn(self.plus_business_id, ids)
    self.assertIn(self.pro_business_id, ids)
    self.assertNotIn(self.free_business_id, ids)
    self.assertNotIn(self.other_district_business_id, ids)
    self.assertNotIn(self.inactive_business_id, ids)

def test_response_has_at_most_six_unique_businesses(self):
    payload = district_offers_payload(self.conn, self.viewer_id, now=self.now)
    ids = [item["business_id"] for item in payload["items"]]
    self.assertLessEqual(len(ids), 6)
    self.assertEqual(len(ids), len(set(ids)))

def test_private_and_inactive_listings_are_excluded(self):
    payload = district_offers_payload(self.conn, self.viewer_id, now=self.now)
    listing_ids = {x["content_id"] for x in payload["items"] if x["kind"] == "listing"}
    self.assertNotIn(self.private_listing_id, listing_ids)
    self.assertNotIn(self.inactive_listing_id, listing_ids)

def test_same_slot_is_stable_and_next_slot_rotates(self):
    first = district_offers_payload(self.conn, self.viewer_id, now=self.now)
    same = district_offers_payload(self.conn, self.viewer_id, now=self.now + 1799)
    later = district_offers_payload(self.conn, self.viewer_id, now=self.now + 1800)
    self.assertEqual(first, same)
    self.assertNotEqual(
        [x["business_id"] for x in first["items"]],
        [x["business_id"] for x in later["items"]],
    )
```

- [ ] **Step 2: Testlar hozir yiqilishini tasdiqlash**

Run: `python -m unittest tests.test_district_offers -v`

Expected: `ModuleNotFoundError: No module named 'district_offers'`.

- [ ] **Step 3: Minimal domen implementatsiyasini yozish**

`district_offers.py` da quyidagi doimiy interfeyslarni yarating:

```python
import hashlib
import time

SLOT_SECONDS = 30 * 60
MAX_DISTRICT_OFFERS = 6
APOSTROPHES = ("'", "’", "‘", "ʻ", "ʼ", "`", "´")


def normalize_district(value):
    text = " ".join(str(value or "").strip().casefold().split())
    for mark in APOSTROPHES:
        text = text.replace(mark, "")
    return text


def offer_time_slot(now=None):
    return int(time.time() if now is None else now) // SLOT_SECONDS


def _stable_offset(district_key, slot, count):
    if count <= 0:
        return 0
    seed = hashlib.sha256(district_key.encode("utf-8")).digest()
    district_offset = int.from_bytes(seed[:8], "big")
    return (district_offset + slot) % count
```

`district_offers_payload` quyidagi javob shaklini qaytarsin:

```python
{
    "needs_district": False,
    "slot": 946704,
    "items": [{
        "business_id": 12,
        "business_name": "Ko‘prik Market",
        "business_logo": "/uploads/...",
        "logo_x": 50.0,
        "logo_y": 50.0,
        "logo_zoom": 1.0,
        "content_id": 91,
        "kind": "product",  # product | service | listing
        "title": "Divan",
        "price": "2500000",
        "unit": "dona",
        "image": "/uploads/...",
    }],
}
```

Nomzodlarni `businesses`, biznes egasi `users` va faol `business_subscriptions` orqali oling. `ends_at > now`, `active=1`, `plan_code IN ('plus','pro')`, `b.status='active'` shartlarini SQL darajasida qo‘llang; tumanlarni `normalize_district` bilan yakuniy solishtiring. Bizneslarni `b.id` bo‘yicha barqaror tartiblang, `_stable_offset` dan aylana bo‘ylab yuring va kontenti bor birinchi 6 ta noyob biznesni oling.

Har biznes uchun mavjud turlarni `product`, `service`, `listing` tartibida tuzing. Boshlanish turini `(slot + business_id) % len(available_kinds)`, shu tur ichidagi kontentni `(slot // 3 + business_id) % len(rows)` bilan tanlang. Listing media uchun faqat birinchi `mtype='photo'` ni oling; rasm topilmasa `image=''` qaytaring. Umumiy ovqatlanish biznesida `items.stock_type` mavjud bo‘lsa ommaviy sahifadagi kabi faqat `ready_food` qatorlarini oling.

- [ ] **Step 4: Unit testlarni yashil qilish**

Run: `python -m unittest tests.test_district_offers -v`

Expected: barcha district offer unit testlari `OK`.

- [ ] **Step 5: Checkpoint**

Run: `python -m py_compile district_offers.py`

Expected: exit code `0`; Git bo‘lmagani uchun shu natija Task 1 checkpointidir.

---

### Task 2: Bosh sahifa API endpointi

**Files:**
- Modify: `api.py`
- Create: `tests/test_district_offers_api.py`

**Interfaces:**
- Consumes: `district_offers_payload(conn, user_id, now=None, limit=6)`.
- Produces: `GET /api/home/district-offers` JSON endpointi.

- [ ] **Step 1: Failing API testlarini yozish**

`tests/test_district_offers_api.py` da mavjud `TestClient`, vaqtinchalik DB va Bearer session uslubidan foydalaning. Quyidagi testlarni yozing:

```python
def test_unauthenticated_and_user_without_district_need_district(self):
    public = self.client.get("/api/home/district-offers")
    missing = self.client.get(
        "/api/home/district-offers", headers=self.auth(self.no_district_token)
    )
    self.assertEqual(public.status_code, 200)
    self.assertTrue(public.json()["needs_district"])
    self.assertTrue(missing.json()["needs_district"])

def test_authenticated_user_receives_same_district_paid_offers_only(self):
    response = self.client.get(
        "/api/home/district-offers", headers=self.auth(self.viewer_token)
    )
    self.assertEqual(response.status_code, 200)
    body = response.json()
    self.assertFalse(body["needs_district"])
    self.assertLessEqual(len(body["items"]), 6)
    self.assertNotIn("district", str(body["items"]).lower())

def test_endpoint_does_not_require_business_owner_role(self):
    response = self.client.get(
        "/api/home/district-offers", headers=self.auth(self.viewer_token)
    )
    self.assertEqual(response.status_code, 200)
```

- [ ] **Step 2: Endpoint yo‘qligi sabab test yiqilishini tekshirish**

Run: `python -m unittest tests.test_district_offers_api -v`

Expected: `/api/home/district-offers` uchun `404`.

- [ ] **Step 3: Endpointni qo‘shish**

`api.py` importlariga:

```python
from district_offers import district_offers_payload
```

Bosh sahifa endpointlari yoniga:

```python
@router.get("/home/district-offers")
async def home_district_offers(
    x_telegram_init_data: str = Header(default=""),
):
    conn = db()
    try:
        me = optional_user(conn, x_telegram_init_data)
        return district_offers_payload(conn, me["id"] if me else None)
    finally:
        conn.close()
```

Endpoint auth bo‘lmasa `401` bermasin; u `needs_district=true` qaytarsin. Endpoint hech qachon foydalanuvchi `district`, `name`, `phone` yoki ID sini kartochka obyektiga qo‘shmasin.

- [ ] **Step 4: API va domen testlarini ishga tushirish**

Run: `python -m unittest tests.test_district_offers tests.test_district_offers_api -v`

Expected: barcha testlar `OK`.

- [ ] **Step 5: Checkpoint**

Run: `python -m py_compile api.py district_offers.py`

Expected: exit code `0`.

---

### Task 3: Sarlavhasiz uzluksiz frontend rail

**Files:**
- Modify: `static/index.html`
- Create: `tests/test_district_offers_frontend_contract.py`

**Interfaces:**
- Consumes: `GET /api/home/district-offers` payloadi.
- Produces: `loadDistrictOffers(force)`, `renderDistrictOffers(payload)`, `clearDistrictOffersCache()` va `#districtOffersMount`.

- [ ] **Step 1: Failing frontend kontrakt testlarini yozish**

`tests/test_district_offers_frontend_contract.py`:

```python
from pathlib import Path
import unittest


class DistrictOffersFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("static/index.html").read_text(encoding="utf-8")

    def test_mount_is_after_map_and_before_existing_listing_heading(self):
        home = self.html[self.html.index('data-screen="home"'):]
        map_end = home.index('</div>\n\n        <div id="driverCard"')
        mount = home.index('id="districtOffersMount"')
        heading = home.index('id="elonHead"')
        self.assertLess(map_end, mount)
        self.assertLess(mount, heading)

    def test_rail_has_no_visible_section_title(self):
        start = self.html.index('id="districtOffersMount"')
        block = self.html[start:start + 500]
        self.assertNotIn("Sizga yaqin", block)
        self.assertNotIn("Tumandagi takliflar", block)
        self.assertNotIn("<h2", block)

    def test_loader_renderer_cache_and_navigation_contracts_exist(self):
        for value in (
            "function loadDistrictOffers(",
            "function renderDistrictOffers(",
            "function clearDistrictOffersCache(",
            '"/api/home/district-offers"',
            "openBizSrv(",
            "openElonSrv(",
        ):
            self.assertIn(value, self.html)

    def test_continuous_motion_pause_and_accessibility_contracts_exist(self):
        for value in (
            "district-offers-track",
            "animation-play-state:paused",
            "prefers-reduced-motion:reduce",
            "pointerenter",
            "pointerleave",
            "focusin",
            "focusout",
            "Tumanni tanlang",
        ):
            self.assertIn(value, self.html)
```

- [ ] **Step 2: Kontrakt testining yiqilishini tekshirish**

Run: `python -m unittest tests.test_district_offers_frontend_contract -v`

Expected: `districtOffersMount` va frontend funksiyalari topilmagani uchun `FAIL`.

- [ ] **Step 3: HTML mount va CSS yozish**

Xaritaning `.map-wrap` blokidan keyin, `#driverCard` dan oldin:

```html
<div class="district-offers" id="districtOffersMount" hidden aria-label="Hududiy takliflar"></div>
```

CSS kontrakti:

```css
.district-offers{margin:14px -18px 0;overflow:hidden;min-width:0}
.district-offers-viewport{overflow-x:auto;scrollbar-width:none;touch-action:pan-x;padding:0 18px}
.district-offers-viewport::-webkit-scrollbar{display:none}
.district-offers-track{display:flex;width:max-content;gap:10px;will-change:transform;animation:districtOffersFlow 34s linear infinite}
.district-offers.is-paused .district-offers-track,
.district-offers:focus-within .district-offers-track{animation-play-state:paused}
.district-offer-card{width:178px;flex:0 0 178px;min-width:0;border:1px solid var(--line);border-radius:16px;background:var(--card);overflow:hidden;color:var(--ink);box-shadow:var(--shadow);cursor:pointer;text-align:left}
.district-offer-media{height:112px;background:var(--primary-tint);overflow:hidden;display:grid;place-items:center}
.district-offer-media img{width:100%;height:100%;object-fit:cover}
.district-offer-body{padding:10px;min-width:0}
.district-offer-title,.district-offer-business{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@keyframes districtOffersFlow{from{transform:translateX(0)}to{transform:translateX(calc(-50% - 5px))}}
@media(prefers-reduced-motion:reduce){.district-offers-track{animation:none!important}}
```

JS render yakunida kartochkalar ikki marta takrorlansin, lekin `items.length===1` da takrorlanmasin va animatsiya klassi ishlamasin. Tugma/karuselning tashqi konteynerida ko‘rinadigan sarlavha yozmang.

- [ ] **Step 4: Loader, render, cache va navigatsiyani yozish**

Frontend holati:

```javascript
var DISTRICT_OFFERS_CACHE=null;
var DISTRICT_OFFERS_LOADING=null;

function clearDistrictOffersCache(){
  DISTRICT_OFFERS_CACHE=null;
  DISTRICT_OFFERS_LOADING=null;
}
```

`loadDistrictOffers(force)` bir vaqtning o‘zida takroriy so‘rovlarni bir Promise bilan birlashtirsin. Cache ichida `slot` saqlansin; serverdan kelgan payload `renderDistrictOffers` ga berilsin. `needs_district=true` da:

```html
<button type="button" class="district-select-btn" data-district-select>Tumanni tanlang</button>
```

Kartochka uchun `data-district-business`, `data-district-content`, `data-district-kind` atributlarini qo‘ying. `product|service` bosilsa `openBizSrv(businessId, contentId)`, `listing` bosilsa `openElonSrv(contentId)` chaqirilsin. `data-district-select` bosilsa `nav("loc")` chaqirilsin.

`pointerenter`, `pointerleave`, `touchstart`, `touchend`, `focusin`, `focusout` hodisalari `.is-paused` klassini boshqarsin. API xatosida mount yashirilsin; bosh sahifaning boshqa elementlariga xato chiqarilmasin.

`nav("home")` ishlaganda `loadDistrictOffers(false)` chaqirilsin. `afterAuth`, logout va manzilni muvaffaqiyatli saqlash yo‘llarida `clearDistrictOffersCache()` so‘ng `loadDistrictOffers(true)` chaqirilsin.

- [ ] **Step 5: Frontend kontrakt va JS sintaksisini tekshirish**

Run: `python -m unittest tests.test_district_offers_frontend_contract -v`

Expected: barcha kontrakt testlari `OK`.

Run: `python - <<'PY'
from pathlib import Path
html = Path('static/index.html').read_text(encoding='utf-8')
script = html.rsplit('<script>', 1)[1].split('</script>', 1)[0]
Path('/tmp/koprik-v1613-inline.js').write_text(script, encoding='utf-8')
PY
node --check /tmp/koprik-v1613-inline.js`

Expected: exit code `0`.

---

### Task 4: Frontend smoke va xato holatlari

**Files:**
- Create: `tests/district-offers-ui-smoke.cjs`
- Modify: `tests/test_district_offers_frontend_contract.py`

**Interfaces:**
- Consumes: Task 3 DOM va frontend funksiyalari.
- Produces: mocked API bilan mobile/tablet/desktop smoke tekshiruvi.

- [ ] **Step 1: Playwright smoke skriptini yozish**

`tests/district-offers-ui-smoke.cjs` mavjud `subscription-ui-smoke.cjs` uslubida `/api/**` so‘rovlarini mock qilsin. `/api/home/district-offers` uchun 6 ta boshqa `business_id` li product/service/listing payload qaytarsin. 390×844, 820×1180 va 1440×1000 viewportlarda quyidagilarni tekshirsin:

```javascript
const mount = page.locator('#districtOffersMount');
await mount.waitFor({ state: 'visible' });
if (await mount.locator('h1,h2,h3').count()) throw new Error('Rail must not have a title.');
if (await mount.locator('.district-offer-card').count() !== 12) {
  throw new Error('Six cards must be duplicated once for seamless motion.');
}
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
if (overflow > 2) throw new Error(`Page overflow: ${overflow}px`);
```

Pointer hoverdan oldin computed `animationPlayState` `running`, hoverdan keyin `paused` ekanini tekshiring. Product kartochkasi bosilganda `/api/business/{id}` so‘rovi, listing kartochkasi bosilganda `/api/listings/{id}` so‘rovi yuborilganini mock state orqali tasdiqlang.

- [ ] **Step 2: Tumansiz va API xatosi holatini smoke testga qo‘shish**

`needs_district=true` qaytganda `Tumanni tanlang` tugmasi ko‘rinsin va bosilganda `loc` screen ochilsin. Endpoint 500 qaytargan alohida page holatida mount hidden bo‘lsin, ammo `home` screen va xarita konteyneri saqlansin.

- [ ] **Step 3: Browser mavjud bo‘lsa smoke testni bajarish**

Run: `node tests/district-offers-ui-smoke.cjs`

Expected: `District offers UI smoke passed` va exit code `0`. Agar Playwright brauzer binarysi muhitda mavjud bo‘lmasa, binary yuklashga siyosat to‘sqinlik qilsa bu holat yakuniy hisobotda aniq yoziladi; sintaksis va kontrakt testlari baribir majburiy.

- [ ] **Step 4: Checkpoint**

Run: `node --check tests/district-offers-ui-smoke.cjs`

Expected: exit code `0`.

---

### Task 5: BUILD, hujjat va to‘liq regressiya

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Create: `docs/district-offers-v1613.md`
- Modify: `tests/test_story_frontend_contract.py`

**Interfaces:**
- Consumes: Tasks 1–4 yakuniy funksiyalari.
- Produces: BUILD `v1613`, deployable yakuniy arxivlar va o‘zgargan fayllar ro‘yxati.

- [ ] **Step 1: BUILD kontraktini avval qizil qilish**

`tests/test_story_frontend_contract.py` dagi kutilgan BUILD qiymatini `v1613` ga o‘zgartiring va yangi build flagni tekshiradigan assertion qo‘shing:

```python
self.assertIn('APP_BUILD = "v1613"', main_source)
self.assertIn('"district_offers": True', main_source)
```

Run: `python -m unittest tests.test_story_frontend_contract -v`

Expected: `main.py` hali `v1612` bo‘lgani uchun `FAIL`.

- [ ] **Step 2: BUILD va capability flagni yangilash**

`main.py`:

```python
APP_BUILD = "v1613"
```

`/api/build` javobiga:

```python
"district_offers": True
```

`static/index.html` yuqori BUILD kommentini `v1613` ga o‘zgartiring.

- [ ] **Step 3: Foydalanuvchi hujjatini yozish**

`docs/district-offers-v1613.md` quyidagilarni aniq yozsin:

- joylashuv: xaritadan keyin, sarlavhasiz;
- 6 ta noyob Plus/Pro biznes;
- bir biznesdan bir kontent;
- tuman bo‘yicha, masofasiz;
- 30 daqiqalik yozuvsiz rotatsiya;
- sekin uzluksiz oqish va pauza;
- tumansiz holatda `Tumanni tanlang`;
- bu bosqichda web grid, masofa, real to‘lov va Pro xarita ulanmagani;
- istoriyalar obuna tariflaridan mustaqil qolishi.

- [ ] **Step 4: Barcha avtomatik tekshiruvlarni bajarish**

Run: `python -m unittest discover -s tests -p 'test_*.py' -v`

Expected: barcha testlar `OK`.

Run: `python -m py_compile main.py api.py database.py subscriptions.py district_offers.py stories.py`

Expected: exit code `0`.

Run: `node --check /tmp/koprik-v1613-inline.js && node --check tests/district-offers-ui-smoke.cjs`

Expected: exit code `0`.

- [ ] **Step 5: Yetkazib berish arxivlarini yaratish va tekshirish**

To‘liq loyihani `Platforma_v1613_district_offers.zip`, faqat o‘zgargan/yangi fayllarni `Platforma_v1613_district_offers_changed_files.zip` nomida yarating. `.db`, `.pyc`, `__pycache__`, test media va ichki ZIP larni kiritmang.

Run: `unzip -t Platforma_v1613_district_offers.zip && unzip -t Platforma_v1613_district_offers_changed_files.zip`

Expected: ikkala arxiv uchun ham `No errors detected`.

- [ ] **Step 6: Yakuniy hisobot**

Quyidagilarni foydalanuvchiga bering: BUILD, `static/index.html` qator soni, o‘zgargan fayllar ro‘yxati, testlar soni/natijasi, brauzer QA holati, to‘liq ZIP va changed-files ZIP havolalari. Ikkala ZIP ni Library’ga bitta batch sifatida saqlang.

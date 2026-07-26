# Taxi Call Clean Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BUILD v1632 da Taxi chaqiruv rejimini mobil bosh sahifa grididan ajratish, Taxi sahifasida reklama va barcha mahsulot/xizmat/e’lon kartalarini yashirish hamda eski toza Taxi ko‘rinishini qaytarish.

**Architecture:** Mavjud Taxi API va `callPanel` saqlanadi. `enterCall()` va `exitCall()` `.phone` elementida `taxi-call-active` UI holatini boshqaradi; holatga bog‘langan CSS faqat Taxi paneli, istoriyalar va asosiy xaritani ko‘rsatadi. CSS himoyasi kechikkan hududiy taklif API javobi kartalarni qayta ko‘rsatishining oldini oladi.

**Tech Stack:** FastAPI metadata, bitta `static/index.html` frontend, CSS media queries, vanilla JavaScript, Python `unittest`, Node JavaScript syntax checks.

## Global Constraints

- Istoriyalar qatori Taxi rejimida ko‘rinib turadi.
- Qidiruv/katalog kartasi, qidiruv natijalari, reklama va hududiy takliflar Taxi rejimida ko‘rinmaydi.
- Taxi/Dostavka, GPS, xarita tanlovi, narx, buyurtma va yopish oqimlari o‘zgarmaydi.
- Taxi yopilganda odatiy bosh sahifa to‘liq tiklanadi.
- Backend Taxi API va boshqa kabinet bo‘limlari o‘zgarmaydi.
- BUILD qiymati `v1632`.
- Manba katalogi Git repository emas; commit qadamlari o‘rniga test va ZIP nazorat nuqtalari ishlatiladi.

---

### Task 1: Taxi toza sahifa kontraktini test bilan belgilash

**Files:**
- Create: `tests/test_taxi_call_clean_screen_contract.py`

**Interfaces:**
- Consumes: `frontend_source() -> str`
- Produces: Taxi UI klassi, yashiriladigan bloklar va ochish/yopish oqimi uchun regression kontrakti.

- [x] **Step 1: Muvaffaqiyatsiz kontrakt testini yozish**

```python
import unittest

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


class TaxiCallCleanScreenContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_taxi_mode_has_dedicated_state_and_restores_it_on_exit(self):
        self.assertIn('classList.add("taxi-call-active")', self.html)
        self.assertIn('classList.remove("taxi-call-active")', self.html)

    def test_taxi_mode_keeps_stories_panel_and_map_in_vertical_flow(self):
        for value in (
            '.phone.home-active.taxi-call-active .screens{overflow-y:auto;',
            '.phone.home-active.taxi-call-active .screen[data-screen="home"].active{display:flex;',
            '.phone.home-active.taxi-call-active #storyStrip{display:block;',
            '.phone.home-active.taxi-call-active #callPanel{display:block;',
            '.phone.home-active.taxi-call-active .home-map-pane{display:block;',
        ):
            self.assertIn(value, self.html)

    def test_taxi_mode_hides_search_results_ads_and_district_offers(self):
        for value in (
            '.phone.home-active.taxi-call-active .home-search-card',
            '.phone.home-active.taxi-call-active #resWrap',
            '.phone.home-active.taxi-call-active #adBox',
            '.phone.home-active.taxi-call-active #adDots',
            '.phone.home-active.taxi-call-active #districtOffersMount',
            'display:none!important;',
        ):
            self.assertIn(value, self.html)

    def test_home_parts_hide_covers_async_district_offer_mount(self):
        block = self.html[
            self.html.index("function homePartsHide(h){"):
            self.html.index("/* ---------- v1389", self.html.index("function homePartsHide(h){"))
        ]
        self.assertIn('"districtOffersMount"', block)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Testning eski kod bilan to‘g‘ri yiqilishini ko‘rish**

Run:

```bash
python -m unittest tests.test_taxi_call_clean_screen_contract -v
```

Expected: `taxi-call-active` va Taxi holati CSSi hali yo‘qligi sababli `FAIL`.

---

### Task 2: Taxi UI holati va eski toza joylashuvni amalga oshirish

**Files:**
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `enterCall()`, `exitCall()`, `homePartsHide(h)`, `.phone`, `#callPanel`, `.home-discovery`.
- Produces: `.phone.taxi-call-active` holati va boshqa bosh sahifa bloklaridan ajratilgan Taxi oqimi.

- [x] **Step 1: Taxi holati uchun CSS qo‘shish**

Mobil `@media(max-width:620px)` ichiga:

```css
.phone.home-active.taxi-call-active{height:100dvh;max-height:100dvh;overflow:hidden;}
.phone.home-active.taxi-call-active .screens{overflow-y:auto;padding-bottom:10px;}
.phone.home-active.taxi-call-active .screen[data-screen="home"].active{
  display:flex;
  flex-direction:column;
  height:auto;
  min-height:100%;
  gap:8px;
}
.phone.home-active.taxi-call-active #storyStrip{display:block;flex:0 0 58px;}
.phone.home-active.taxi-call-active #callPanel{display:block;flex:none;order:2;}
.phone.home-active.taxi-call-active #driverCard{order:3;flex:none;}
.phone.home-active.taxi-call-active .home-discovery{display:block;order:4;flex:none;}
.phone.home-active.taxi-call-active .home-search-card,
.phone.home-active.taxi-call-active #resWrap,
.phone.home-active.taxi-call-active #adBox,
.phone.home-active.taxi-call-active #adDots,
.phone.home-active.taxi-call-active #districtOffersMount{display:none!important;}
.phone.home-active.taxi-call-active .home-map-pane{display:block;height:280px;min-height:280px;}
.phone.home-active.taxi-call-active .home-map-pane .map-wrap{height:280px;min-height:280px;}
.phone.home-active.taxi-call-active #leafletMap{height:280px!important;min-height:280px;}
```

Desktop/planshet umumiy himoya qoidasi:

```css
.phone.taxi-call-active #adBox,
.phone.taxi-call-active #adDots,
.phone.taxi-call-active #districtOffersMount,
.phone.taxi-call-active #resWrap{display:none!important;}
```

- [x] **Step 2: Yashirish ro‘yxatini yangi hududiy taklif blokiga moslash**

`homePartsHide(h)`:

```javascript
function homePartsHide(h){
  ["adBox","adDots","pinEyebrow","districtOffersMount"].forEach(function(id){
    var x=el(id); if(x) x.style.display = h ? "none" : "";
  });
}
```

- [x] **Step 3: Taxi klassini ochish/yopish oqimiga ulash**

`enterCall()` ichida:

```javascript
var phone=document.querySelector(".phone");
if(phone){
  phone.classList.remove("search-results-active");
  phone.classList.add("taxi-call-active");
}
```

`exitCall()` ichida:

```javascript
var phone=document.querySelector(".phone");
if(phone) phone.classList.remove("taxi-call-active");
```

Xarita o‘lchami Taxi layouti chizilgandan so‘ng qayta hisoblanadi:

```javascript
setTimeout(function(){ try{ if(LMAP) LMAP.invalidateSize(); }catch(e){} },120);
```

- [x] **Step 4: Target testlarni yashil qilish**

Run:

```bash
python -m unittest tests.test_taxi_call_clean_screen_contract tests.test_mobile_home_single_screen_contract tests.test_district_offers_frontend_contract -v
```

Expected: `OK`.

---

### Task 3: BUILD v1632 metadata va hujjat

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Modify: `tests/test_frontend_assets.py`
- Modify: `tests/test_domain_integration_ready.py`
- Modify: `tests/test_listing_media_frontend_contract.py`
- Modify: `tests/test_production_foundation.py`
- Modify: `tests/test_story_frontend_contract.py`
- Modify: `tests/test_v1616_security_contract.py`
- Create: `docs/v1632-taxi-call-clean-screen.md`

**Interfaces:**
- Consumes: `/api/build`
- Produces: `build == "v1632"` va `taxi_call_clean_screen_v1632 == True`.

- [x] **Step 1: BUILD kontraktlarini v1632 ga yangilash**

Mavjud release assertionlarida `v1631`ni `v1632`ga almashtirish va
`tests/test_frontend_assets.py`ga:

```python
self.assertIn('"taxi_call_clean_screen_v1632": True', self.main)
```

- [x] **Step 2: Eski metadata bilan test yiqilishini tasdiqlash**

Run:

```bash
python -m unittest tests.test_frontend_assets tests.test_domain_integration_ready tests.test_production_foundation -v
```

Expected: `v1631 != v1632` va yangi feature flag yo‘qligi sababli `FAIL`.

- [x] **Step 3: Runtime metadata va HTML BUILDni v1632 ga yangilash**

`main.py`:

```python
APP_BUILD = "v1632"
```

`/api/build` javobiga:

```python
"taxi_call_clean_screen_v1632": True
```

`static/index.html`:

```html
<!-- BUILD: v1632 -->
```

- [x] **Step 4: O‘zgarish hujjatini yozish**

`docs/v1632-taxi-call-clean-screen.md` ichida sabab, yechim, o‘zgargan fayllar,
qabul mezonlari va test buyruqlari yoziladi.

- [x] **Step 5: Metadata testlarini yashil qilish**

Run:

```bash
python -m unittest tests.test_frontend_assets tests.test_domain_integration_ready tests.test_listing_media_frontend_contract tests.test_production_foundation tests.test_story_frontend_contract tests.test_v1616_security_contract -v
```

Expected: `OK`.

---

### Task 4: To‘liq tekshiruv va ZIP

**Files:**
- Verify: `static/index.html`
- Verify: `main.py`
- Package: `Platforma_v1632_taxi_call_clean_screen.zip`

**Interfaces:**
- Consumes: v1632 manba holati.
- Produces: testdan o‘tgan, foydalanuvchiga yuklashga tayyor ZIP.

- [x] **Step 1: Inline JavaScript sintaksisini tekshirish**

`static/index.html` ichidagi tashqi `src` skriptlar tashlab ketilib, inline
JavaScript vaqtinchalik `.js` faylga chiqariladi va:

```bash
node --check /tmp/koprik-v1632-inline.js
```

Expected: exit code `0`.

- [x] **Step 2: Barcha Python testlarini ishga tushirish**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: barcha testlar `OK`.

- [x] **Step 3: Mavjud frontend smoke testini ishga tushirish**

Run:

```bash
node tests/district-offers-ui-smoke.cjs
```

Expected: o‘rnatilgan muhitda smoke test `OK`; Chromium mavjud bo‘lmasa bu
cheklov yakuniy hisobotda ochiq aytiladi.

- [x] **Step 4: Toza v1632 papkasini va ZIPni tayyorlash**

v1632 manba nusxasi alohida paket papkasiga ko‘chiriladi va:

```bash
zip -qr Platforma_v1632_taxi_call_clean_screen.zip Platforma_v1632_taxi_call_clean_screen
```

- [x] **Step 5: Paket ichidagi BUILD, fayllar va SHA-256 ni tekshirish**

Run:

```bash
unzip -p Platforma_v1632_taxi_call_clean_screen.zip Platforma_v1632_taxi_call_clean_screen/main.py
unzip -p Platforma_v1632_taxi_call_clean_screen.zip Platforma_v1632_taxi_call_clean_screen/static/index.html
sha256sum Platforma_v1632_taxi_call_clean_screen.zip
```

Expected: ikkala faylda `v1632`; arxiv uchun bitta SHA-256 qiymati.

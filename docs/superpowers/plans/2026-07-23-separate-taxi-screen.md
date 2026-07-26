# Separate Taxi Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BUILD v1633 da Taxi chaqiruv oqimini bosh sahifa ichidan chiqarib, boshqa bo‘limlar kabi alohida `taxi-call` sahifaga o‘tkazish.

**Architecture:** Yangi Taxi screen faqat `callPanel`, `driverCard` va `taxiMapHost`ni saqlaydi. Mavjud yagona `homeMapPane` Taxi ochilganda `taxiMapHost`ga, Taxi yopilganda `homeDiscovery`ga ko‘chiriladi. Bosh sahifa promo bloklari Taxi markupiga kiritilmaydi va Taxi API o‘zgarmaydi.

**Tech Stack:** FastAPI metadata, bitta `static/index.html`, vanilla JavaScript screen router, Leaflet, CSS media queries, Python `unittest`, Node syntax check.

## Global Constraints

- Qidiruv, istoriyalar, reklama va hududiy takliflar faqat `home` screen ichida qoladi.
- Taxi sahifasida faqat buyurtma paneli, haydovchi ma’lumoti va xarita bo‘ladi.
- Bitta mavjud Leaflet xarita ishlatiladi; ikkinchi xarita yaratilmaydi.
- Yuqori orqaga, panel yopish va xaritadagi Taxi tugmasi `exitCall()` orqali qaytadi.
- Login sahifasiga o‘tishda xarita Taxi ekranida qolmaydi.
- Taxi backend API, narx, GPS va buyurtma holatlari o‘zgarmaydi.
- BUILD qiymati `v1633`.
- Manba Git repository emas; commit o‘rniga test va ZIP nazorat nuqtalari ishlatiladi.

---

### Task 1: Alohida Taxi screen kontraktini test bilan belgilash

**Files:**
- Modify: `tests/test_taxi_call_clean_screen_contract.py`

**Interfaces:**
- Consumes: `frontend_source() -> str`
- Produces: ekran chegarasi, xarita ko‘chishi, orqaga va login xavfsizligi uchun regression testlari.

- [x] **Step 1: Eski yashirish kontraktini alohida screen kontraktiga almashtirish**

```python
def screen_markup(self, name):
    start = self.html.index(f'<section class="screen" data-screen="{name}"')
    end = self.html.index('<section class="screen"', start + 20)
    return self.html[start:end]

def test_taxi_is_a_separate_screen_not_a_hidden_home_state(self):
    home = self.screen_markup("home")
    taxi = self.screen_markup("taxi-call")
    self.assertIn('id="storyStrip"', home)
    self.assertIn('id="homeQueryInput"', home)
    self.assertIn('id="adBox"', home)
    self.assertIn('id="districtOffersMount"', home)
    self.assertNotIn('id="callPanel"', home)
    self.assertNotIn('id="driverCard"', home)
    self.assertIn('id="callPanel"', taxi)
    self.assertIn('id="driverCard"', taxi)
    self.assertIn('id="taxiMapHost"', taxi)
    for value in ("storyStrip", "homeQueryInput", "adBox", "districtOffersMount"):
        self.assertNotIn(value, taxi)
    self.assertNotIn("taxi-call-active", self.html)

def test_taxi_moves_the_single_map_between_screen_hosts(self):
    for value in (
        'id="homeDiscovery"',
        'id="homeMapPane"',
        'el("taxiMapHost").appendChild(el("homeMapPane"))',
        'el("homeDiscovery").appendChild(el("homeMapPane"))',
        'nav("taxi-call")',
        'nav("home")',
    ):
        self.assertIn(value, self.html)

def test_taxi_back_and_login_paths_restore_home_map(self):
    self.assertIn('if(current==="taxi-call"){ exitCall(); return; }', self.html)
    self.assertIn('if(!loggedIn){ exitCall(); showLogin("Zakaz qilish"); return; }', self.html)
```

- [x] **Step 2: Eski v1632 kodda testning yiqilishini tasdiqlash**

Run:

```bash
python -m unittest tests.test_taxi_call_clean_screen_contract -v
```

Expected: `data-screen="taxi-call"` va xarita ko‘chirish oqimi yo‘qligi sababli `FAIL`.

---

### Task 2: Taxi markup, navigatsiya va yagona xaritani ko‘chirish

**Files:**
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `enterCall()`, `exitCall()`, `nav(screen)`, `LMAP`, `homeMapPane`.
- Produces: `data-screen="taxi-call"`, `#taxiMapHost`, xaritani ikki host orasida xavfsiz ko‘chirish.

- [x] **Step 1: Home markupdan Taxi elementlarini chiqarish**

Home ichidan:

```html
<div id="callPanel" hidden></div>
<div id="driverCard" hidden></div>
```

olib tashlanadi. Home elementlariga barqaror host IDlari beriladi:

```html
<div class="home-discovery" id="homeDiscovery">
<div class="home-map-pane" id="homeMapPane">
```

- [x] **Step 2: Alohida Taxi screen qo‘shish**

```html
<section class="screen" data-screen="taxi-call">
  <div class="taxi-call-shell">
    <div id="callPanel" hidden></div>
    <div id="driverCard" hidden></div>
    <div id="taxiMapHost"></div>
  </div>
</section>
```

- [x] **Step 3: Eski `taxi-call-active` CSSini alohida screen CSSiga almashtirish**

```css
.screen[data-screen="taxi-call"]{padding-top:10px;padding-bottom:18px;}
.taxi-call-shell{width:min(100%,920px);margin:0 auto;display:flex;flex-direction:column;gap:10px;}
#taxiMapHost{min-width:0;}
#taxiMapHost .home-map-pane{display:block;width:100%;min-height:380px;}
#taxiMapHost .pin-eyebrow{display:none!important;}
#taxiMapHost .map-wrap{height:380px;min-height:380px;}
#taxiMapHost #leafletMap{height:380px!important;min-height:380px;}
@media(max-width:620px){
  .screen[data-screen="taxi-call"]{padding:8px 10px 14px;}
  #taxiMapHost .home-map-pane{min-height:280px;}
  #taxiMapHost .map-wrap{height:280px;min-height:280px;}
  #taxiMapHost #leafletMap{height:280px!important;min-height:280px;}
}
```

- [x] **Step 4: Xarita hostini ko‘chiruvchi yordamchilarni qo‘shish**

```javascript
function moveHomeMapToTaxi(){
  var host=el("taxiMapHost"), pane=el("homeMapPane");
  if(host && pane && pane.parentNode!==host) host.appendChild(pane);
}
function restoreHomeMap(){
  var host=el("homeDiscovery"), pane=el("homeMapPane");
  if(host && pane && pane.parentNode!==host) host.appendChild(pane);
}
function refreshMainMapSize(){
  setTimeout(function(){ try{ if(LMAP) LMAP.invalidateSize(); }catch(e){} },120);
}
```

- [x] **Step 5: `enterCall()` va `exitCall()`ni yangi screenga ulash**

`enterCall()`:

```javascript
moveHomeMapToTaxi();
el("callPanel").hidden=false;
renderCallPanel();
nav("taxi-call");
screensEl.scrollTop=0;
refreshMainMapSize();
```

`exitCall()`:

```javascript
restoreHomeMap();
nav("home");
loadHomeMap();
refreshMainMapSize();
```

Eski `taxi-call-active` klassi va `homePartsHide()` chaqiruvlari olib
tashlanadi.

- [x] **Step 6: Sarlavha, orqaga va login oqimini xavfsiz qilish**

```javascript
titles["taxi-call"]="Taxi chaqirish";
BACKMAP["taxi-call"]="home";

el("backBtn").addEventListener("click", function(){
  if(current==="taxi-call"){ exitCall(); return; }
  nav(/* mavjud qaytish ifodasi */);
});
```

`submitRide()` ichida:

```javascript
if(!loggedIn){ exitCall(); showLogin("Zakaz qilish"); return; }
```

- [x] **Step 7: Target testlarni yashil qilish**

Run:

```bash
python -m unittest tests.test_taxi_call_clean_screen_contract tests.test_mobile_home_single_screen_contract tests.test_web_home_frontend_contract -v
```

Expected: `OK`.

---

### Task 3: BUILD v1633 metadata va hujjat

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Modify: `tests/test_frontend_assets.py`
- Modify: `tests/test_domain_integration_ready.py`
- Modify: `tests/test_listing_media_frontend_contract.py`
- Modify: `tests/test_production_foundation.py`
- Modify: `tests/test_story_frontend_contract.py`
- Modify: `tests/test_v1616_security_contract.py`
- Create: `docs/v1633-separate-taxi-screen.md`

**Interfaces:**
- Consumes: `/api/build`
- Produces: `build == "v1633"` va `separate_taxi_screen_v1633 == True`.

- [x] **Step 1: Test metadata assertionlarini v1633 ga yangilash**

`v1632` release assertionlari `v1633`ga almashtiriladi va:

```python
self.assertIn('"separate_taxi_screen_v1633": True', self.main)
```

- [x] **Step 2: Eski metadata bilan testning yiqilishini tasdiqlash**

Run:

```bash
python -m unittest tests.test_frontend_assets tests.test_domain_integration_ready tests.test_production_foundation -v
```

Expected: eski `v1632` sababli `FAIL`.

- [x] **Step 3: Runtime BUILD va feature flagni yangilash**

```python
APP_BUILD = "v1633"
```

`/api/build`ga:

```python
"separate_taxi_screen_v1633": True
```

HTML:

```html
<!-- BUILD: v1633 -->
```

- [x] **Step 4: Release hujjatini yozish va metadata testlarini yashil qilish**

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
- Package: `Platforma_v1633_separate_taxi_screen.zip`

**Interfaces:**
- Consumes: v1633 manba.
- Produces: keshsiz, testdan o‘tgan v1633 ZIP.

- [x] **Step 1: Inline JavaScript sintaksisini tekshirish**

Run:

```bash
node --check /tmp/koprik-v1633-inline.js
```

Expected: exit code `0`.

- [x] **Step 2: Barcha testlarni ishga tushirish**

Run:

```bash
python -m unittest discover -s tests -q
```

Expected: barcha testlar `OK`.

- [x] **Step 3: Browser-free UI contractni ishga tushirish**

Run:

```bash
node tests/district-offers-ui-smoke.cjs --contract-only
```

Expected: `District offers UI contract passed`.

- [x] **Step 4: Keshsiz paket va ZIP tayyorlash**

`rsync` orqali `__pycache__`, `.pyc`, `.venv` va `.pytest_cache` chiqarib
tashlangan `Platforma_v1633_separate_taxi_screen` papkasi yaratiladi va ZIPga
olinadi.

- [x] **Step 5: ZIP BUILD, yaxlitlik, qator va SHA-256 nazorati**

Expected:

- arxiv xatosiz;
- `main.py` va `static/index.html` ichida `v1633`;
- `static/index.html` qator soni qayd etilgan;
- kesh fayllari yo‘q;
- SHA-256 qayd etilgan.

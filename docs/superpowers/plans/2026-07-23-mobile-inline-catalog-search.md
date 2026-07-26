# Mobile Inline Catalog Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BUILD v1634 da telefon bosh sahifasining katalog tugmasini qidiruv qatoriga joylashtirish, fokus paytida yig‘ish, reklamani 100 px qilish va mobil bosh xaritadagi Leaflet `+`/`−` tugmalarini yashirish.

**Architecture:** Mavjud `#homeCatalogOpen` elementi `.home-search-row` ichiga ko‘chiriladi va CSS grid area orqali desktopda eski ikki qator, telefonda yangi bir qator ko‘rinishida ishlaydi. Mobil input fokus holati `mobile-search-focused` klassi bilan boshqariladi; qidiruv va katalog ochish funksiyalari o‘zgarmaydi. Leaflet zoom control faqat aktiv home screenning 620 px dan kichik ko‘rinishida CSS orqali yashiriladi.

**Tech Stack:** Bitta `static/index.html`, vanilla JavaScript, CSS Grid, Leaflet, FastAPI build metadata, Python `unittest`, Node syntax check.

## Global Constraints

- O‘zgarish faqat telefon kengligida (`max-width: 620px`) ko‘rinadi.
- Desktop, planshet, Taxi va boshqa screenlar o‘zgarmaydi.
- Katalog tugmasi mavjud katalog ekranini ochishda davom etadi.
- Input fokus olganda katalog yashirinadi; qidiruv blokidan fokus chiqqanda qaytadi.
- Mobil reklama balandligi va rasmi 100 px bo‘ladi.
- Mobil home xaritasida faqat Leaflet `+` va `−` tugmalari yashiriladi.
- Pinch-to-zoom, xaritani surish va dasturiy markazlash saqlanadi.
- BUILD qiymati `v1634`.
- Manba Git repository emas; commit o‘rniga test va ZIP nazorat nuqtalari ishlatiladi.

---

### Task 1: Mobil inline katalog va xarita control kontrakti

**Files:**
- Modify: `tests/test_mobile_home_single_screen_contract.py`

**Interfaces:**
- Consumes: `frontend_source() -> str`
- Produces: markup, mobil grid, fokus, reklama balandligi va zoom control uchun regression kontrakti.

- [x] **Step 1: Yangi talablar uchun failing testlarni yozish**

```python
def test_mobile_catalog_is_inside_the_search_row_and_collapses_on_focus(self):
    row_start = self.html.index('<div class="home-search-row">')
    row_end = self.html.index("</div>", row_start)
    row = self.html[row_start:row_end]
    self.assertIn('id="homeQueryInput"', row)
    self.assertIn('id="homeCatalogOpen"', row)
    self.assertIn('id="homeSearchSubmit"', row)
    for value in (
        'grid-template-areas:"query catalog submit";',
        '.home-search-card.mobile-search-focused #homeCatalogOpen{display:none;',
        'grid-template-areas:"query submit";',
        'classList.add("mobile-search-focused")',
        'classList.remove("mobile-search-focused")',
    ):
        self.assertIn(value, self.html)

def test_mobile_ad_uses_the_freed_catalog_height(self):
    self.assertIn(
        "grid-template-rows:58px minmax(0,1fr) 100px 4px 92px;",
        self.html,
    )
    self.assertIn("#adBox{height:100px;min-height:100px;", self.html)
    self.assertIn("#adBox .ad-photo{height:100px;", self.html)

def test_mobile_home_hides_only_leaflet_zoom_buttons(self):
    self.assertIn(
        '.screen[data-screen="home"] #leafletMap .leaflet-control-zoom{display:none!important;}',
        self.html,
    )
    self.assertIn('L.map("leafletMap",{zoomControl:true', self.html)
    self.assertNotIn('L.map("leafletMap",{zoomControl:false', self.html)
```

- [x] **Step 2: Eski v1633 kodda testlarning yiqilishini tasdiqlash**

Run:

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_mobile_home_single_screen_contract -v
```

Expected: katalog hali `.home-search-row` tashqarisida, reklama 72 px va zoom control yashirilmaganligi uchun `FAIL`.

---

### Task 2: Markup va mobil responsive CSSni joriy etish

**Files:**
- Modify: `static/index.html`
- Test: `tests/test_mobile_home_single_screen_contract.py`
- Test: `tests/test_web_home_frontend_contract.py`
- Test: `tests/test_taxi_call_clean_screen_contract.py`

**Interfaces:**
- Consumes: `#homeQueryInput`, `#homeCatalogOpen`, `#homeSearchSubmit`, `.home-search-card`, `#adBox`, `#leafletMap`.
- Produces: desktopda ikki qator va telefonda fokusga javob beradigan bitta qatorli search grid.

- [x] **Step 1: Katalog tugmasini qidiruv qatori ichiga ko‘chirish**

```html
<div class="home-search-row">
  <label class="home-query-shell" for="homeQueryInput">...</label>
  <button class="home-catalog-open" id="homeCatalogOpen" type="button">...</button>
  <button class="home-search-submit" id="homeSearchSubmit" type="button">Qidirish</button>
</div>
```

`#homeCatalogOpen`ning eski alohida sibling nusxasi o‘chiriladi; ID takrorlanmaydi.

- [x] **Step 2: Katta ekran eski ko‘rinishini CSS grid area bilan saqlash**

```css
.home-search-row{
  display:grid;
  grid-template-columns:minmax(0,1fr) auto;
  grid-template-areas:"query submit" "catalog catalog";
  column-gap:8px;
  row-gap:10px;
  margin-top:22px;
}
.home-query-shell{grid-area:query;}
.home-search-submit{grid-area:submit;}
.home-catalog-open{grid-area:catalog;margin-top:0;}
```

- [x] **Step 3: Telefon uchun bitta qator va fokus holatini qo‘shish**

`@media(max-width:620px)` ichida:

```css
.screen[data-screen="home"] .home-search-row{
  grid-template-columns:minmax(0,1fr) 94px 64px;
  grid-template-areas:"query catalog submit";
  column-gap:4px;
  row-gap:0;
}
.screen[data-screen="home"] .home-search-card.mobile-search-focused .home-search-row{
  grid-template-columns:minmax(0,1fr) 64px;
  grid-template-areas:"query submit";
}
.screen[data-screen="home"] .home-search-card.mobile-search-focused #homeCatalogOpen{display:none;}
.screen[data-screen="home"] .home-catalog-open{
  min-height:36px;
  height:36px;
  margin:0;
  padding:0 6px;
}
.screen[data-screen="home"] .home-catalog-copy small{display:none;}
```

Input hodisalari:

```javascript
el("homeQueryInput").addEventListener("focus",function(){
  var card=this.closest(".home-search-card");
  if(card) card.classList.add("mobile-search-focused");
});
el("homeQueryInput").addEventListener("blur",function(){
  var input=this;
  setTimeout(function(){
    var card=input.closest(".home-search-card");
    if(card && document.activeElement!==input) card.classList.remove("mobile-search-focused");
  },0);
});
```

- [x] **Step 4: Reklama qatorini 100 px qilish**

```css
.screen[data-screen="home"].active{
  grid-template-rows:58px minmax(0,1fr) 100px 4px 92px;
}
.screen[data-screen="home"]>#adBox{
  height:100px;
  min-height:100px;
}
.screen[data-screen="home"]>#adBox .ad-photo{height:100px;}
```

- [x] **Step 5: Mobil home xarita zoom controlini yashirish**

`@media(max-width:620px)` ichida:

```css
.screen[data-screen="home"] #leafletMap .leaflet-control-zoom{display:none!important;}
```

Selector map Taxi screen hostiga ko‘chirilganda mos kelmaydi, shuning uchun Taxi xaritasining zoom boshqaruvi saqlanadi.

- [x] **Step 6: Target testlarni yashil qilish**

Run:

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_mobile_home_single_screen_contract tests.test_web_home_frontend_contract tests.test_taxi_call_clean_screen_contract -v
```

Expected: `OK`.

---

### Task 3: BUILD v1634 metadata va release hujjati

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Modify: `tests/test_frontend_assets.py`
- Modify: `tests/test_domain_integration_ready.py`
- Modify: `tests/test_listing_media_frontend_contract.py`
- Modify: `tests/test_production_foundation.py`
- Modify: `tests/test_story_frontend_contract.py`
- Modify: `tests/test_v1616_security_contract.py`
- Create: `docs/v1634-mobile-inline-catalog-search.md`

**Interfaces:**
- Consumes: `/api/build`
- Produces: `build == "v1634"`, `mobile_inline_catalog_search_v1634 == True` va `mobile_home_zoom_controls_hidden_v1634 == True`.

- [x] **Step 1: BUILD kontrakt testlarini v1634 ga yangilash**

Mavjud release assertionlarida `v1633`ni `v1634`ga almashtiring va
`tests/test_frontend_assets.py`ga:

```python
self.assertIn('"mobile_inline_catalog_search_v1634": True', self.main)
self.assertIn('"mobile_home_zoom_controls_hidden_v1634": True', self.main)
```

- [x] **Step 2: Eski metadata bilan testning yiqilishini tasdiqlash**

Run:

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_frontend_assets tests.test_domain_integration_ready tests.test_production_foundation -v
```

Expected: eski `v1633` va yangi feature flaglar yo‘qligi sababli `FAIL`.

- [x] **Step 3: Runtime BUILD va feature flaglarni yangilash**

`main.py`:

```python
APP_BUILD = "v1634"
```

`/api/build`:

```python
"mobile_inline_catalog_search_v1634": True,
"mobile_home_zoom_controls_hidden_v1634": True
```

`static/index.html`:

```html
<!-- BUILD: v1634 -->
```

- [x] **Step 4: Release hujjatini yozish va metadata testlarini yashil qilish**

Run:

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_frontend_assets tests.test_domain_integration_ready tests.test_listing_media_frontend_contract tests.test_production_foundation tests.test_story_frontend_contract tests.test_v1616_security_contract -v
```

Expected: `OK`.

---

### Task 4: To‘liq tekshiruv va toza ZIP

**Files:**
- Verify: `static/index.html`
- Verify: `main.py`
- Package: `Platforma_v1634_mobile_inline_catalog_search.zip`

**Interfaces:**
- Consumes: v1634 manba holati.
- Produces: keshsiz, testdan o‘tgan v1634 ZIP.

- [x] **Step 1: Inline JavaScript sintaksisini tekshirish**

Run:

```bash
sed -n '/<script>/{:a;n;/<\/script>/q;p;ba}' static/index.html | node --check -
```

Expected: exit code `0`.

- [x] **Step 2: Barcha testlarni ishga tushirish**

Run:

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest discover -s tests -q
```

Expected: barcha testlar `OK`.

- [x] **Step 3: Browser-free UI contractni ishga tushirish**

Run:

```bash
node tests/district-offers-ui-smoke.cjs --contract-only
```

Expected: `District offers UI contract passed`.

- [x] **Step 4: Keshsiz paket va ZIP tayyorlash**

`rsync` bilan `__pycache__`, `.pyc`, `.venv` va `.pytest_cache` chiqarilgan
`Platforma_v1634_mobile_inline_catalog_search` papkasi yaratiladi va ZIPga
olinadi.

- [x] **Step 5: ZIP BUILD, yaxlitlik, qator va SHA-256 nazorati**

Expected:

- arxiv xatosiz;
- `main.py` va `static/index.html` ichida `v1634`;
- `static/index.html` qator soni qayd etilgan;
- kesh fayllari yo‘q;
- SHA-256 qayd etilgan.

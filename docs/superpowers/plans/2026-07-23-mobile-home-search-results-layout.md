# Mobile Home Search Results Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BUILD v1631 da mobil xaritani ixchamlashtirish, qidiruv natijalarini xarita ostida chiqarish, bosh sahifa tezkor filtrlarini olib tashlash va bo‘shagan joyni qolgan bosh sahifa qismlariga taqsimlash.

**Architecture:** Oddiy mobil bosh sahifa v1630 gridini saqlaydi. Qidiruv ochilganda `.phone.search-results-active` klassi mobil sahifani vertikal oqimga o‘tkazadi, `#resWrap`ni xaritadan keyin vizual joylashtiradi va sahifa aylantirilishini yoqadi. Qidiruv API va natija kartalari o‘zgartirilmaydi.

**Tech Stack:** FastAPI metadata, bitta `static/index.html` frontend, CSS media queries, vanilla JavaScript, Python `unittest`, Node syntax/contract checks.

## Global Constraints

- Joylashuv va o‘lcham o‘zgarishlari faqat `620px` va undan kichik ekranlar uchun.
- Mahsulot/Xizmat/Biznes/Mutaxassis bosh sahifa filtrlari barcha ekranlarda olib tashlanadi.
- Qidiruv API, xarita metkalari, profil rollari va saralash mantiqi o‘zgarmaydi.
- Oddiy mobil bosh sahifa bitta ekranga sig‘adi.
- Qidiruv natijalari holatida vertikal aylantirishga ruxsat beriladi.
- Reklama va hududiy takliflar natijalardan keyin saqlanadi.
- BUILD qiymati `v1631`.
- Manba katalogi Git repository emas; commit qadamlari o‘rniga test va ZIP nazorat nuqtalari ishlatiladi.

---

### Task 1: v1631 frontend kontraktlarini yozish

**Files:**
- Modify: `tests/test_mobile_home_single_screen_contract.py`
- Modify: `tests/test_approved_home_catalog_contract.py`

**Interfaces:**
- Consumes: `frontend_source() -> str`
- Produces: filtrlarning yo‘qligi, mobil qidiruv klassi, vizual tartib va kattalashtirilgan bo‘limlar uchun regression kontraktlari.

- [ ] **Step 1: Eski tezkor filtrlar olib tashlanishini tekshiruvchi test yozish**

`tests/test_approved_home_catalog_contract.py` ichida eski shortcut testini quyidagicha almashtirish:

```python
def test_home_shortcuts_are_removed_but_search_controls_stay_interactive(self):
    for value in (
        'data-web-search-type="product"',
        'data-web-search-type="service"',
        'data-web-search-type="business"',
        'data-web-search-type="specialist"',
        'document.querySelectorAll("[data-web-search-type]")',
    ):
        self.assertNotIn(value, self.html)
    for value in (
        'el("homeCatalogOpen")',
        'el("homeSearchSubmit")',
        'el("homeQueryClear")',
    ):
        self.assertIn(value, self.html)
```

- [ ] **Step 2: Mobil natijalar joylashuvi kontraktini yozish**

`tests/test_mobile_home_single_screen_contract.py`ga quyidagi tekshiruvlarni qo‘shish:

```python
def test_mobile_results_flow_below_map_before_advertisement(self):
    for value in (
        "search-results-active",
        '.phone.home-active.search-results-active .screens{overflow-y:auto;',
        '.phone.home-active.search-results-active .screen[data-screen="home"].active{display:flex;',
        '.phone.home-active.search-results-active .home-discovery{order:2;',
        '.phone.home-active.search-results-active #resWrap{order:3;',
        '.phone.home-active.search-results-active #adBox{order:4;',
        '.phone.home-active.search-results-active #districtOffersMount{order:6;',
        'classList.add("search-results-active")',
        'classList.remove("search-results-active")',
    ):
        self.assertIn(value, self.html)

def test_mobile_sections_grow_while_map_becomes_shorter(self):
    for value in (
        "grid-template-rows:58px minmax(0,1fr) 72px 4px 92px;",
        ".story-rail{height:58px;",
        "#adBox{height:72px;",
        "#districtOffersMount{height:92px;",
        ".search-results-active .home-map-pane{height:150px;",
    ):
        self.assertIn(value, self.html)
```

- [ ] **Step 3: Yangi testlarning avval muvaffaqiyatsizligini tasdiqlash**

Run:

```bash
python -m unittest tests.test_mobile_home_single_screen_contract tests.test_approved_home_catalog_contract -v
```

Expected: yangi v1631 kontraktlari filtr markup va `search-results-active` CSS/JS hali mavjudligi sababli `FAIL`.

---

### Task 2: Mobil joylashuv va qidiruv natijalari holatini amalga oshirish

**Files:**
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `enterResults(list_html, pins, count)` va `exitResults()`.
- Produces: `.phone.search-results-active` UI holati.

- [ ] **Step 1: Tezkor filtr markup, CSS va listenerini olib tashlash**

Quyidagilarni o‘chirish:

```html
<div class="desktop-hero-tags">
  <button type="button" data-web-search-type="product">Mahsulot</button>
  <button type="button" data-web-search-type="service">Xizmat</button>
  <button type="button" data-web-search-type="business">Biznes</button>
  <button type="button" data-web-search-type="specialist">Mutaxassis</button>
</div>
```

```javascript
document.querySelectorAll("[data-web-search-type]").forEach(function(button){
  button.addEventListener("click",function(){
    openWebSearchType(button.getAttribute("data-web-search-type")||"all");
  });
});
```

Shuningdek `.desktop-hero-tags` va `.desktop-hero-tags button` selectorlarining barcha CSS qoidalarini olib tashlash.

- [ ] **Step 2: Mobil bosh sahifa o‘lchamlarini qayta taqsimlash**

v1630 mobil media query ichida:

```css
.screen[data-screen="home"].active{
  grid-template-rows:58px minmax(0,1fr) 72px 4px 92px;
}
.screen[data-screen="home"]>.story-strip{height:58px;}
.screen[data-screen="home"] .story-rail{height:58px;}
.screen[data-screen="home"]>#adBox{height:72px;min-height:72px;}
.screen[data-screen="home"]>#adBox .ad-photo{height:72px;}
.screen[data-screen="home"]>#districtOffersMount{height:92px;}
.screen[data-screen="home"] .district-offers-viewport,
.screen[data-screen="home"] .district-offers-track{height:92px;}
.screen[data-screen="home"] .district-offer-card{height:90px;}
.screen[data-screen="home"] .district-offer-media{height:90px;}
```

Qidiruv satri va katalog tugmasi filtrdan bo‘shagan joyga mos ravishda `36px` va `32px` balandlikka, sarlavha `15px`ga oshiriladi.

- [ ] **Step 3: Mobil natijalar holati CSSini qo‘shish**

```css
.phone.home-active.search-results-active .screens{overflow-y:auto;}
.phone.home-active.search-results-active .screen[data-screen="home"].active{
  display:flex;
  flex-direction:column;
  height:auto;
  min-height:100%;
}
.phone.home-active.search-results-active .story-strip{order:1;flex:0 0 58px;}
.phone.home-active.search-results-active .home-discovery{
  order:2;
  flex:none;
  grid-template-rows:auto 150px;
}
.phone.home-active.search-results-active .home-map-pane{height:150px;}
.phone.home-active.search-results-active #resWrap{order:3;margin-top:6px;}
.phone.home-active.search-results-active #adBox{order:4;margin-top:8px!important;}
.phone.home-active.search-results-active #adDots{order:5;}
.phone.home-active.search-results-active #districtOffersMount{order:6;}
```

- [ ] **Step 4: Qidiruv klassini JS oqimiga ulash**

`enterResults()` boshida:

```javascript
var phone=document.querySelector(".phone");
if(phone) phone.classList.add("search-results-active");
```

`exitResults()` boshida:

```javascript
var phone=document.querySelector(".phone");
if(phone) phone.classList.remove("search-results-active");
```

- [ ] **Step 5: Target testlarni yashil qilish**

Run:

```bash
python -m unittest tests.test_mobile_home_single_screen_contract tests.test_approved_home_catalog_contract tests.test_web_home_frontend_contract -v
```

Expected: `OK`.

---

### Task 3: BUILD v1631 va test metadata

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Modify: `tests/test_frontend_assets.py`
- Modify: `tests/test_domain_integration_ready.py`
- Modify: `tests/test_listing_media_frontend_contract.py`
- Modify: `tests/test_production_foundation.py`
- Modify: `tests/test_story_frontend_contract.py`
- Modify: `tests/test_v1616_security_contract.py`
- Create: `docs/v1631-mobile-home-search-results.md`

**Interfaces:**
- Consumes: `/api/build`
- Produces: `build == "v1631"` va `mobile_home_search_results_v1631 == True`.

- [ ] **Step 1: BUILD kontraktlarini avval v1631ga yangilash**

Mavjud BUILD assertionlarida `v1630`ni `v1631`ga almashtirish va
`tests/test_frontend_assets.py`ga quyidagini qo‘shish:

```python
self.assertTrue(payload["mobile_home_search_results_v1631"])
```

- [ ] **Step 2: Testning eski metadata bilan yiqilishini tasdiqlash**

Run:

```bash
python -m unittest tests.test_frontend_assets tests.test_domain_integration_ready tests.test_production_foundation -v
```

Expected: `v1630 != v1631` sababli `FAIL`.

- [ ] **Step 3: Runtime metadata va HTML BUILDni yangilash**

`main.py`:

```python
APP_BUILD = "v1631"
```

`/api/build` payload:

```python
"mobile_home_search_results_v1631": True
```

`static/index.html`:

```html
<!-- BUILD: v1631 -->
```

- [ ] **Step 4: Release hujjatini yozish**

`docs/v1631-mobile-home-search-results.md`da o‘zgarishlar, o‘zgarmagan
qidiruv/xarita mantiqlari va bajarilgan testlar yoziladi.

---

### Task 4: Regression va paket

**Files:**
- Modify: `tests/district-offers-ui-smoke.cjs`
- Create: `Platforma_v1631_mobile_search_results.zip`

**Interfaces:**
- Consumes: tayyor v1631 manba daraxti.
- Produces: tekshirilgan ZIP va foydalanuvchiga aniq fayllar ro‘yxati.

- [ ] **Step 1: Viewport kontraktiga yangi mobil holatlarni qo‘shish**

`tests/district-offers-ui-smoke.cjs` mobil tekshiruviga:

- bosh sahifa shortcutlari soni `0`;
- odatiy home vertikal overflow qilmasligi;
- qidiruv holatida `resWrap` xarita bilan reklama orasida bo‘lishi;
- xarita qidiruv holatida `150px` bo‘lishi

shartlarini qo‘shish.

- [ ] **Step 2: To‘liq Python testlarini bajarish**

Run:

```bash
python -m unittest discover -s tests -p 'test_*.py' -q
```

Expected: barcha testlar `OK`.

- [ ] **Step 3: JavaScript va UI kontraktlarini tekshirish**

Run:

```bash
node --check < extracted-inline-script.js
node tests/district-offers-ui-smoke.cjs --contract-only
```

Expected: exit code `0` va `District offers UI contract passed`.

- [ ] **Step 4: ZIP yaratish va yaxlitligini tekshirish**

`__pycache__`, `*.pyc` va `.pytest_cache`ni chiqarib tashlab
`Platforma_v1631_mobile_search_results.zip` yaratish.

Run:

```bash
unzip -t Platforma_v1631_mobile_search_results.zip
sha256sum Platforma_v1631_mobile_search_results.zip
wc -l static/index.html
```

Expected: ZIP xatosiz, checksum mavjud va yakuniy `index.html` qator soni
hisobotga kiritilgan.


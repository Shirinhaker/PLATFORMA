# Ko‘prik Mobile Home Single-Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ko‘prik telefon bosh sahifasidagi barcha asosiy bo‘limlarni `320×568` va undan katta telefon ekranlarida pastga yoki yon tomonga chiqarmasdan bitta ekranga sig‘dirish hamda “20 ta demo taklif qo‘shish” tugmasini olib tashlash.

**Architecture:** Mavjud bir faylli frontend tuzilmasi saqlanadi. `static/index.html` ichiga faqat telefon bosh sahifasiga tegishli, viewport balandligiga mos CSS qoidalari qo‘shiladi; mavjud HTML tuzilmasi va event handlerlar saqlanadi, faqat demo tugmasi va uning frontend handleri olib tashlanadi. Backend demo endpointi va desktop/planshet dizayniga tegilmaydi.

**Tech Stack:** HTML5, CSS Grid/Flexbox, vanilla JavaScript, Python `unittest`, Playwright smoke test.

## Global Constraints

- O‘zgarish faqat telefon bosh sahifasiga qo‘llanadi.
- Asosiy viewportlar: `320×568`, `360×640`, `390×844`.
- Desktop va planshet dizayni o‘zgarmaydi.
- Boshqa sahifalarning vertikal aylantirilishi saqlanadi.
- Qidiruv API, xarita API, marker tanlash, profil, obuna va istoriya algoritmlari o‘zgarmaydi.
- “20 ta demo taklif qo‘shish” tugmasi frontenddan olib tashlanadi; backend endpoint va mavjud ma’lumotlar o‘chirilmaydi.
- Mavjud kod arxitekturasi bir faylli frontend bo‘lib qoladi.
- Release BUILD `v1630` bo‘ladi.
- Ushbu arxiv papkasi Git worktree emas. Commit qadamlari faqat o‘zgarishlar haqiqiy Git checkoutga ko‘chirilganda bajariladi.

---

## File Map

- Modify: `static/index.html` — telefon bosh sahifa CSS’i, demo tugma HTML’i va demo tugma event handleri.
- Create: `tests/test_mobile_home_single_screen_contract.py` — yangi mobil layout va demo tugma yo‘qligi kontrakti.
- Modify: `tests/test_web_home_frontend_contract.py` — desktop kontraktidan demo tugma talabini olib tashlash.
- Modify: `tests/district-offers-ui-smoke.cjs` — uchta telefon viewportida gorizontal/vertikal sig‘ish va bo‘lim chegaralarini tekshirish.
- Modify: `main.py` — BUILD va yangi feature flag.
- Modify: `tests/test_story_frontend_contract.py` — BUILD kontrakti.
- Modify: `tests/test_frontend_assets.py` — BUILD va feature flag kontrakti.
- Modify: `tests/test_production_foundation.py` — BUILD kontrakti.
- Modify: `tests/test_domain_integration_ready.py` — BUILD kontrakti.
- Modify: `tests/test_listing_media_frontend_contract.py` — BUILD kontrakti.
- Modify: `tests/test_v1616_security_contract.py` — BUILD kontrakti.
- Create: `docs/v1630-mobile-home-single-screen.md` — release tavsifi va tekshiruv natijalari.

---

### Task 1: Mobil bosh sahifa kontraktini test bilan qulflash

**Files:**
- Create: `tests/test_mobile_home_single_screen_contract.py`
- Modify: `tests/test_web_home_frontend_contract.py`

**Interfaces:**
- Consumes: `tests.frontend_source.frontend_source() -> str`
- Produces: Mobil CSS markerlari va demo tugma yo‘qligini tekshiradigan testlar.

- [ ] **Step 1: Yangi failing contract test yozish**

```python
import unittest

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


class MobileHomeSingleScreenContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_phone_home_uses_single_screen_layout(self):
        for value in (
            "/* v1630 — telefon bosh sahifasi bitta ekranda */",
            "@media(max-width:620px)",
            ".screen[data-screen=\"home\"].active{display:grid;",
            "height:100%;",
            "grid-template-rows:",
            ".home-discovery{display:grid;",
            "grid-template-rows:auto minmax(0,1fr);",
            "#leafletMap{height:100%!important;min-height:0;}",
        ):
            self.assertIn(value, self.html)

    def test_phone_home_keeps_horizontal_rails_but_no_page_overflow(self):
        for value in (
            ".story-rail{",
            "overflow-x:auto;",
            ".district-offers-viewport{",
            "overflow-x:auto;",
            "min-width:0;",
            "max-width:100%;",
        ):
            self.assertIn(value, self.html)

    def test_demo_seed_button_and_frontend_handler_are_removed(self):
        self.assertNotIn('id="seedDistrictOffers"', self.html)
        self.assertNotIn('if(el("seedDistrictOffers"))', self.html)
        self.assertNotIn("Demo takliflar yaratilmoqda...", self.html)

    def test_phone_header_keeps_all_required_actions_inside_compact_row(self):
        for value in (
            'id="webBrandBtn"',
            'id="webListingsBtn"',
            'id="locBtn"',
            'id="cartBtn"',
            'id="taxiCabBtn"',
            'id="cabBtn"',
            ".tb-home{min-width:0;",
        ):
            self.assertIn(value, self.html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Desktop kontraktini yangi talabga moslashtirish**

`tests/test_web_home_frontend_contract.py` ichidagi `test_current_product_constraints_remain_present` testini quyidagiga almashtirish:

```python
    def test_current_product_constraints_remain_present(self):
        for value in (
            'data-screen="cab-subscriptions"',
            'id="storyAddCard"',
            'id="mapChip"',
        ):
            self.assertIn(value, self.html)
        self.assertNotIn('id="seedDistrictOffers"', self.html)
```

- [ ] **Step 3: Testlar hozirgi kodda xato berishini tekshirish**

Run:

```bash
python -m unittest tests.test_mobile_home_single_screen_contract tests.test_web_home_frontend_contract -v
```

Expected: yangi mobil CSS markerlari yo‘qligi va `seedDistrictOffers` hali mavjudligi sababli `FAIL`.

- [ ] **Step 4: Git checkout mavjud bo‘lsa test commitini qilish**

```bash
git add tests/test_mobile_home_single_screen_contract.py tests/test_web_home_frontend_contract.py
git commit -m "test: define mobile home single-screen contract"
```

---

### Task 2: Telefon bosh sahifasini bitta viewportga sig‘dirish

**Files:**
- Modify: `static/index.html`

**Interfaces:**
- Consumes: Mavjud `tbHome`, `storyStrip`, `home-discovery`, `adBox`, `adDots`, `districtOffersMount` DOM elementlari.
- Produces: Telefon viewportida barcha bo‘limlar bir vaqtda sig‘adigan CSS; mavjud element ID va JavaScript interfeyslari o‘zgarmaydi.

- [ ] **Step 1: Mobil single-screen CSS blokini yozish**

`static/index.html` ichidagi v1629 responsive qoidalaridan keyin, desktop `@media(min-width:1080px)` blokidan oldin quyidagi scoped blokni qo‘shish:

```css
  /* v1630 — telefon bosh sahifasi bitta ekranda */
  @media(max-width:620px){
    .phone{height:100dvh;max-height:100dvh;overflow:hidden;}
    .topbar{height:42px;padding:4px 6px;overflow:hidden;}
    .tb-home{min-width:0;height:34px;gap:3px;overflow:hidden;}
    .web-brand{flex:0 0 auto;max-width:56px;margin-right:auto;font-size:17px;overflow:hidden;text-overflow:ellipsis;}
    .web-nav{flex:0 0 auto;min-width:0;}
    .web-nav button{height:32px;max-width:52px;padding:0 6px;border-radius:9px;font-size:10px;overflow:hidden;text-overflow:ellipsis;}
    .tb-home>.icon-btn{width:30px;height:30px;min-width:30px;border-radius:9px;}
    .tb-home>.icon-btn svg{width:17px;height:17px;}
    .tb-home>#taxiCabBtn{display:grid;font-size:15px!important;}
    .screens{min-height:0;padding-bottom:0;}
    .screen[data-screen="home"].active{display:grid;height:100%;min-height:0;padding:4px 8px;grid-template-rows:52px minmax(0,1fr) 58px 4px 72px;gap:4px;align-content:stretch;}
    .screen[data-screen="home"]>.story-strip{height:52px;margin:0;min-width:0;}
    .screen[data-screen="home"] .story-rail{height:52px;gap:6px;padding:0 1px 2px;overflow-x:auto;overflow-y:hidden;}
    .screen[data-screen="home"] .story-card{width:44px;flex-basis:44px;}
    .screen[data-screen="home"] .story-thumb{width:42px;height:42px;border-radius:12px;}
    .screen[data-screen="home"] .story-plus{width:23px;height:23px;border-radius:8px;font-size:18px;}
    .screen[data-screen="home"] .story-name{margin-top:2px;font-size:8px;line-height:1;}
    .screen[data-screen="home"] .home-discovery{display:grid;min-width:0;min-height:0;grid-template-rows:auto minmax(0,1fr);gap:4px;}
    .screen[data-screen="home"] .home-search-card{min-height:0;padding:4px 7px;border-radius:12px;}
    .screen[data-screen="home"] .home-search-card h1{font-size:14px;line-height:1.05;letter-spacing:-.02em;}
    .screen[data-screen="home"] .home-search-row{height:32px;margin-top:4px;gap:4px;}
    .screen[data-screen="home"] .home-query-shell{min-height:32px;height:32px;padding:0 6px;border-radius:8px;}
    .screen[data-screen="home"] .home-query-shell svg{width:14px;height:14px;}
    .screen[data-screen="home"] .home-query-shell input{font-size:10px;}
    .screen[data-screen="home"] .home-query-clear{width:22px;height:22px;font-size:14px;}
    .screen[data-screen="home"] .home-search-submit{min-width:60px;height:32px;padding:0 7px;border-radius:8px;font-size:10px;}
    .screen[data-screen="home"] .home-catalog-open{min-height:28px;height:28px;margin-top:3px;padding:2px 7px;border-radius:8px;gap:6px;}
    .screen[data-screen="home"] .home-catalog-open svg{width:14px;height:14px;}
    .screen[data-screen="home"] .home-catalog-copy strong{font-size:9px;}
    .screen[data-screen="home"] .home-catalog-copy small{font-size:7px;line-height:1;}
    .screen[data-screen="home"] .home-catalog-chevron{font-size:14px;}
    .screen[data-screen="home"] .desktop-hero-tags{grid-template-columns:repeat(4,minmax(0,1fr));gap:3px;margin-top:3px;}
    .screen[data-screen="home"] .desktop-hero-tags button{min-height:24px;height:24px;padding:1px 2px;border-radius:7px;font-size:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
    .screen[data-screen="home"] .home-location-note{display:none;}
    .screen[data-screen="home"] .home-map-pane{min-width:0;min-height:0;height:100%;}
    .screen[data-screen="home"] .home-map-pane .map-wrap{height:100%;min-height:0;border-radius:12px;}
    .screen[data-screen="home"] #leafletMap{height:100%!important;min-height:0;}
    .screen[data-screen="home"] .map-chip{top:5px;left:5px;max-width:calc(100% - 44px);padding:4px 6px;border-radius:7px;font-size:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
    .screen[data-screen="home"] #taxiBtn{top:5px!important;right:5px!important;width:28px;height:28px;font-size:14px!important;}
    .screen[data-screen="home"]>#adBox{height:58px;min-height:58px;margin-top:0!important;padding:6px 8px;border-radius:11px;}
    .screen[data-screen="home"]>#adBox .tag{left:8px;top:5px;padding:2px 5px;font-size:7px;}
    .screen[data-screen="home"]>#adBox .ad-copy{padding:5px 8px;}
    .screen[data-screen="home"]>#adBox .ad-copy h3{margin:10px 0 1px;font-size:11px;line-height:1.05;}
    .screen[data-screen="home"]>#adBox .ad-copy p{max-width:72%;font-size:8px;line-height:1.1;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
    .screen[data-screen="home"]>#adBox .ad-cta{display:none;}
    .screen[data-screen="home"]>#adBox .ad-photo{height:58px;}
    .screen[data-screen="home"]>#adDots{height:4px;margin:0;gap:3px;}
    .screen[data-screen="home"]>#adDots span{height:3px;width:3px;}
    .screen[data-screen="home"]>#adDots span.on{width:10px;}
    .screen[data-screen="home"]>#districtOffersMount{height:72px;margin:0 -8px;min-width:0;overflow:hidden;}
    .screen[data-screen="home"] .district-offers-viewport{height:72px;padding:0 8px;overflow-x:auto;overflow-y:hidden;min-width:0;max-width:100%;}
    .screen[data-screen="home"] .district-offers-track{height:72px;gap:5px;}
    .screen[data-screen="home"] .district-offer-card{width:145px;flex-basis:145px;height:70px;display:grid;grid-template-columns:50px minmax(0,1fr);border-radius:10px;}
    .screen[data-screen="home"] .district-offer-media{height:70px;font-size:19px;}
    .screen[data-screen="home"] .district-offer-body{padding:5px 6px;align-self:center;}
    .screen[data-screen="home"] .district-offer-title{font-size:9px;}
    .screen[data-screen="home"] .district-offer-business{margin-top:1px;font-size:7px;}
    .screen[data-screen="home"] .district-kind-badge{margin-top:3px;padding:2px 4px;font-size:6px;}
    .screen[data-screen="home"] .district-offer-price{margin-top:3px;font-size:8px;}
  }
```

- [ ] **Step 2: Demo tugma markupini olib tashlash**

`static/index.html` ichidan quyidagi elementni olib tashlash:

```html
<button type="button" class="btn btn-soft btn-block" id="seedDistrictOffers" data-privileged-only style="margin-top:10px">20 ta demo taklif qo‘shish</button>
```

- [ ] **Step 3: Demo tugma frontend handlerini olib tashlash**

`static/index.html` ichidan `if(el("seedDistrictOffers")) ...` bilan boshlanib tugaydigan event listener blokini butunlay olib tashlash. `/api/home/district-offers/demo-seed` backend endpointiga tegmaslik.

- [ ] **Step 4: Target contract testlarni qayta ishga tushirish**

Run:

```bash
python -m unittest tests.test_mobile_home_single_screen_contract tests.test_web_home_frontend_contract tests.test_mobile_home_listings_contract tests.test_approved_home_catalog_contract -v
```

Expected: barcha testlar `PASS`.

- [ ] **Step 5: Git checkout mavjud bo‘lsa frontend commitini qilish**

```bash
git add static/index.html
git commit -m "feat: fit mobile home into one viewport"
```

---

### Task 3: Real browser viewport va tugmalar regressiya testi

**Files:**
- Modify: `tests/district-offers-ui-smoke.cjs`

**Interfaces:**
- Consumes: Playwright `Page`, `verifyViewport(browser, viewport)`.
- Produces: `320×568`, `360×640`, `390×844` viewportlarida aniq layout o‘lchovlari.

- [ ] **Step 1: Mobil sig‘ishni o‘lchaydigan helper qo‘shish**

`verifyViewport()` ichida district-offers kartalari yuklangandan keyin quyidagi tekshiruvni qo‘shish:

```javascript
  const layout = await page.evaluate(() => {
    const screens = document.querySelector('#screens');
    const home = document.querySelector('.screen[data-screen="home"].active');
    const selectors = ['#storyStrip', '.home-search-card', '.home-map-pane', '#adBox', '#districtOffersMount'];
    return {
      pageOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      homeOverflowY: screens.scrollHeight - screens.clientHeight,
      sections: selectors.map(selector => {
        const node = home.querySelector(selector);
        const rect = node && node.getBoundingClientRect();
        return {
          selector,
          visible: !!node && !node.hidden && !!rect && rect.width > 0 && rect.height > 0,
          left: rect ? rect.left : null,
          right: rect ? rect.right : null,
          top: rect ? rect.top : null,
          bottom: rect ? rect.bottom : null,
        };
      }),
      demoButton: !!document.querySelector('#seedDistrictOffers'),
    };
  });
  if (layout.pageOverflowX > 2) throw new Error(`Page overflow: ${layout.pageOverflowX}px`);
  if (viewport.width <= 620 && layout.homeOverflowY > 2) {
    throw new Error(`Home vertical overflow: ${layout.homeOverflowY}px at ${viewport.width}x${viewport.height}`);
  }
  if (layout.demoButton) throw new Error('Demo seed button must not be rendered.');
  if (viewport.width <= 620) {
    for (const section of layout.sections) {
      if (!section.visible) throw new Error(`Missing mobile home section: ${section.selector}`);
      if (section.left < -2 || section.right > viewport.width + 2) {
        throw new Error(`Horizontal clipping in ${section.selector}: ${JSON.stringify(section)}`);
      }
      if (section.top < -2 || section.bottom > viewport.height + 2) {
        throw new Error(`Vertical clipping in ${section.selector}: ${JSON.stringify(section)}`);
      }
    }
  }
```

- [ ] **Step 2: Telefon viewportlar ro‘yxatini kengaytirish**

`runBrowserSmoke()` ichidagi viewportlar ro‘yxatini quyidagiga almashtirish:

```javascript
    results.push(await verifyViewport(browser, { width: 320, height: 568 }));
    results.push(await verifyViewport(browser, { width: 360, height: 640 }));
    results.push(await verifyViewport(browser, { width: 390, height: 844 }));
    results.push(await verifyViewport(browser, { width: 820, height: 1180 }));
    results.push(await verifyViewport(browser, { width: 1440, height: 1000 }));
```

- [ ] **Step 3: Browser testni ishga tushirish**

Run:

```bash
node tests/district-offers-ui-smoke.cjs
```

Expected: `District offers UI smoke passed` va barcha besh viewport natijasi chiqadi.

- [ ] **Step 4: Interaktiv funksiyalar saqlanganini tekshirish**

Mavjud smoke test quyidagilarni allaqachon bosib tekshiradi va ular `PASS` bo‘lishi kerak:

- mahsulot kartasi → biznes sahifasi;
- e’lon kartasi → e’lon so‘rovi va biznes sahifasi;
- karusel hover/focus/touch holatlari;
- gorizontal qo‘lda aylantirish.

- [ ] **Step 5: Git checkout mavjud bo‘lsa smoke-test commitini qilish**

```bash
git add tests/district-offers-ui-smoke.cjs
git commit -m "test: verify mobile home viewport fit"
```

---

### Task 4: BUILD v1630 va release hujjati

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Modify: `tests/test_story_frontend_contract.py`
- Modify: `tests/test_frontend_assets.py`
- Modify: `tests/test_production_foundation.py`
- Modify: `tests/test_domain_integration_ready.py`
- Modify: `tests/test_listing_media_frontend_contract.py`
- Modify: `tests/test_v1616_security_contract.py`
- Create: `docs/v1630-mobile-home-single-screen.md`

**Interfaces:**
- Consumes: `APP_BUILD`, health/feature response, HTML BUILD comment.
- Produces: `v1630` release identifikatori va `mobile_home_single_screen_v1630` feature flag.

- [ ] **Step 1: BUILD metadata testlarini avval v1630 ga o‘zgartirish**

Yuqoridagi test fayllarida:

```python
self.assertIn('APP_BUILD = "v1630"', main_text)
self.assertIn('<!-- BUILD: v1630 -->', html_text)
```

`tests/test_frontend_assets.py` ichiga qo‘shimcha assertion:

```python
self.assertIn('"mobile_home_single_screen_v1630": True', self.main)
```

- [ ] **Step 2: BUILD testlari hozirgi v1629 kodda xato berishini tekshirish**

Run:

```bash
python -m unittest \
  tests.test_story_frontend_contract \
  tests.test_frontend_assets \
  tests.test_production_foundation \
  tests.test_domain_integration_ready \
  tests.test_listing_media_frontend_contract \
  tests.test_v1616_security_contract -v
```

Expected: `v1630` hali yozilmagani sababli `FAIL`.

- [ ] **Step 3: main.py va HTML BUILD ni yangilash**

`main.py`:

```python
APP_BUILD = "v1630"
```

Health feature dictionary oxiriga:

```python
"mobile_home_single_screen_v1630": True
```

`static/index.html`:

```html
<title>Koprik</title><!-- BUILD: v1630 --><!-- UI: approved-home-catalog -->
```

- [ ] **Step 4: Release hujjatini yozish**

`docs/v1630-mobile-home-single-screen.md`:

```markdown
# BUILD v1630 — telefon bosh sahifasi bitta ekranda

## O‘zgarishlar

- Telefon bosh sahifasi `320×568`, `360×640` va `390×844` ekranlarga moslandi.
- Yuqori menyu, istoriyalar, qidiruv, xarita, reklama va takliflar bir vaqtda ko‘rinadi.
- Sahifaning gorizontal va vertikal chiqib ketishi bloklandi.
- “20 ta demo taklif qo‘shish” tugmasi frontenddan olib tashlandi.
- Desktop, planshet, backend demo endpointi, qidiruv va xarita algoritmlari o‘zgartirilmadi.

## Tekshiruv

- Python contract testlari.
- Playwright: `320×568`, `360×640`, `390×844`, `820×1180`, `1440×1000`.
```

- [ ] **Step 5: BUILD testlarini qayta ishga tushirish**

Run: Step 2 dagi ayni command.

Expected: barcha testlar `PASS`.

- [ ] **Step 6: Git checkout mavjud bo‘lsa release commitini qilish**

```bash
git add main.py static/index.html tests docs/v1630-mobile-home-single-screen.md
git commit -m "chore: release build v1630"
```

---

### Task 5: To‘liq regressiya va ZIP handoff

**Files:**
- Verify: barcha o‘zgargan fayllar.
- Create artifact: `Platforma_v1630_mobile_home_single_screen.zip`

**Interfaces:**
- Consumes: v1630 source tree.
- Produces: tekshirilgan ZIP va foydalanuvchiga o‘zgargan fayllar ro‘yxati.

- [ ] **Step 1: Barcha Python testlarini ishga tushirish**

Run:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: mavjud va yangi testlarning barchasi `PASS`.

- [ ] **Step 2: Frontend contract smoke testlarini ishga tushirish**

Run:

```bash
node tests/district-offers-ui-smoke.cjs --contract-only
node tests/story-ui-smoke.cjs --contract-only
node tests/subscription-ui-smoke.cjs --contract-only
```

Expected: uchalasi ham exit code `0`.

- [ ] **Step 3: Real browser smoke testini qayta ishga tushirish**

Run:

```bash
node tests/district-offers-ui-smoke.cjs
```

Expected: beshta viewport `PASS`.

- [ ] **Step 4: BUILD va index qator sonini olish**

Run:

```bash
python -c "from pathlib import Path; print(sum(1 for _ in Path('static/index.html').open(encoding='utf-8')))"
python -c "import main; print(main.APP_BUILD)"
```

Expected: qator soni chop etiladi va BUILD `v1630`.

- [ ] **Step 5: ZIP tayyorlash**

Source papkaning ota papkasidan:

```bash
zip -r Platforma_v1630_mobile_home_single_screen.zip v1629-source \
  -x "v1629-source/__pycache__/*" "v1629-source/tests/__pycache__/*" "v1629-source/.pytest_cache/*"
```

Expected: `Platforma_v1630_mobile_home_single_screen.zip` yaratiladi.

- [ ] **Step 6: Foydalanuvchiga handoff berish**

Handoff quyidagilarni aniq ko‘rsatadi:

- BUILD: `v1630`;
- o‘zgargan fayllar;
- `static/index.html` qator soni;
- test natijalari va mavjud muhit cheklovlari;
- ZIP faylga yuklab olish havolasi.

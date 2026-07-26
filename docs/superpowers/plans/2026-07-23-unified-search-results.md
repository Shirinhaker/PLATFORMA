# Unified Search Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BUILD v1635 da qidiruv natijalarini barcha ekranlarda xarita osti va reklama ustiga birlashtirish, katta oq natijalar kartasini ixcham sarlavhaga almashtirish va reklamadagi ko‘rinadigan `Reklama` belgisini olib tashlash.

**Architecture:** `#resWrap` DOM ichida `#homeDiscovery` va `#adBox` orasiga ko‘chiriladi, shuning uchun barcha breakpointlar bir xil tabiiy tartibdan foydalanadi. `#resBar.menu-card` o‘rniga faqat `#resCount.search-results-summary` qoladi; natijalar ro‘yxati yig‘ilmaydi va darhol ko‘rinadi. Qidiruv API, natija HTML generatori, xarita metkalari va reklama aylanishi o‘zgarmaydi.

**Tech Stack:** Bitta `static/index.html`, vanilla JavaScript, CSS, FastAPI BUILD metama’lumoti, Python `unittest`, Node syntax check.

## Global Constraints

- Ko‘k `«so‘rov» bo‘yicha natijalar ko‘rsatilmoqda` izohi saqlanadi.
- Natija guruhlari sarlavhalari saqlanadi.
- Qidiruv API, xarita metkalari, saralash, profil turlari va Taxi o‘zgarmaydi.
- Reklama rasmi, aylanishi va click funksiyasi saqlanadi.
- `alt="Reklama"` saqlanadi; faqat ko‘rinadigan tag olib tashlanadi.
- BUILD qiymati `v1635`.
- Manba Git repository emas; commit o‘rniga test va ZIP nazorat nuqtalari ishlatiladi.

---

### Task 1: Unified natijalar frontend kontrakti

**Files:**
- Create: `tests/test_unified_search_results_contract.py`
- Test: `static/index.html`

**Interfaces:**
- Consumes: `frontend_source() -> str`
- Produces: DOM tartibi, ixcham sarlavha, saqlanadigan izoh va reklama tagi uchun regressiya kontrakti.

- [x] **Step 1: Failing contract testini yozish**

```python
import unittest
from frontend_source import frontend_source


class UnifiedSearchResultsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()
        start = cls.html.index('<section class="screen active" data-screen="home">')
        end = cls.html.index("<!-- TAXI CHAQIRUV", start)
        cls.home = cls.html[start:end]

    def test_results_follow_map_and_precede_ad_on_every_viewport(self):
        discovery = self.home.index('id="homeDiscovery"')
        results = self.home.index('id="resWrap"')
        advertisement = self.home.index('id="adBox"')
        offers = self.home.index('id="districtOffersMount"')
        self.assertLess(discovery, results)
        self.assertLess(results, advertisement)
        self.assertLess(advertisement, offers)

    def test_large_collapsible_result_bar_is_replaced_by_compact_count(self):
        self.assertNotIn('id="resBar"', self.html)
        self.assertNotIn('el("resBar").addEventListener', self.html)
        self.assertIn(
            '<div class="search-results-summary" id="resCount" aria-live="polite">Natijalar — 0 ta</div>',
            self.home,
        )
        self.assertIn(".search-results-summary{", self.html)

    def test_visible_ad_tag_is_removed_but_search_context_is_preserved(self):
        self.assertNotIn('<span class="tag">Reklama</span>', self.home)
        self.assertIn('alt="Reklama"', self.home)
        self.assertIn("bo\\'yicha natijalar ko\\'rsatilmoqda", self.html)
        self.assertIn("Mahsulot va xizmatlar", self.html)
```

- [x] **Step 2: Eski v1634 kodda testning kutilgan sabab bilan yiqilishini tasdiqlash**

Run:

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_unified_search_results_contract -v
```

Expected: `#resWrap` reklamadan keyin turgani, `#resBar` mavjudligi va ko‘rinadigan reklama tagi sabab `FAIL`.

---

### Task 2: DOM, CSS va JavaScriptni ixchamlashtirish

**Files:**
- Modify: `static/index.html`
- Test: `tests/test_unified_search_results_contract.py`
- Test: `tests/test_mobile_home_single_screen_contract.py`
- Test: `tests/test_web_home_frontend_contract.py`
- Test: `tests/test_taxi_call_clean_screen_contract.py`

**Interfaces:**
- Consumes: `#homeDiscovery`, `#resWrap`, `#resCount`, `#resList`, `#adBox`, `#districtOffersMount`.
- Produces: barcha ekranlarda yagona natijalar oqimi.

- [x] **Step 1: Natijalar markupini xarita va reklama orasiga ko‘chirish**

```html
</div><!-- #homeDiscovery -->

<div id="resWrap" hidden>
  <div class="search-results-summary" id="resCount" aria-live="polite">Natijalar — 0 ta</div>
  <div id="resList" hidden></div>
</div>

<div class="ad" id="adBox">
```

Eski `#resBar.menu-card` va `#districtOffersMount`dan keyingi `#resWrap` nusxasi o‘chiriladi.

- [x] **Step 2: Ixcham sarlavha CSSini qo‘shish**

```css
.search-results-summary{
  margin:8px 0 6px;
  color:var(--ink);
  font-size:13px;
  font-weight:800;
  line-height:1.25;
}
```

Mobil natija holatidagi `#resWrap` order qoidasi saqlanadi; desktop va planshet yangi DOM tartibidan foydalanadi.

- [x] **Step 3: Visible reklama tagi va eski yig‘ish handlerini olib tashlash**

Quyidagilar o‘chiriladi:

```html
<span class="tag">Reklama</span>
```

```javascript
el("resBar").addEventListener("click", function(){ var r=el("resList"); r.hidden=!r.hidden; });
```

`enterResults()` ichidagi `#resCount` yangilanishi va `#resList.hidden = false` saqlanadi.

- [x] **Step 4: Target testlarni yashil qilish**

Run:

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_unified_search_results_contract tests.test_mobile_home_single_screen_contract tests.test_web_home_frontend_contract tests.test_taxi_call_clean_screen_contract -v
```

Expected: `OK`.

---

### Task 3: BUILD v1635

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Modify: `tests/test_frontend_assets.py`
- Modify: `tests/test_domain_integration_ready.py`
- Modify: `tests/test_listing_media_frontend_contract.py`
- Modify: `tests/test_production_foundation.py`
- Modify: `tests/test_story_frontend_contract.py`
- Modify: `tests/test_v1616_security_contract.py`
- Create: `docs/v1635-unified-search-results.md`

**Interfaces:**
- Consumes: `/api/build`
- Produces: `build == "v1635"`, `unified_search_results_v1635 == True`, `home_ad_tag_hidden_v1635 == True`.

- [x] **Step 1: BUILD testlarini v1635 ga o‘tkazish**

Mavjud BUILD assertionlarida `v1634`ni `v1635`ga almashtiring.
`tests/test_frontend_assets.py`ga qo‘shing:

```python
self.assertIn('"unified_search_results_v1635": True', self.main)
self.assertIn('"home_ad_tag_hidden_v1635": True', self.main)
```

- [x] **Step 2: Eski metadata bilan testning yiqilishini ko‘rish**

Run:

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_frontend_assets.FrontendAssetContractTests.test_release_metadata_declares_single_file_frontend -v
```

Expected: eski `v1634` va yangi flaglar yo‘qligi sabab `FAIL`.

- [x] **Step 3: Runtime metadata va release hujjatini yangilash**

```python
APP_BUILD = "v1635"
```

`/api/build`ga:

```python
"unified_search_results_v1635": True,
"home_ad_tag_hidden_v1635": True
```

`static/index.html`ga:

```html
<!-- BUILD: v1635 -->
```

Release hujjati o‘zgarishlar, o‘zgarmagan funksiyalar va test buyruqlarini qayd etadi.

- [x] **Step 4: Metadata testlarini yashil qilish**

Run:

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_frontend_assets tests.test_domain_integration_ready tests.test_listing_media_frontend_contract tests.test_production_foundation tests.test_story_frontend_contract tests.test_v1616_security_contract -v
```

Expected: `OK`.

---

### Task 4: To‘liq tekshiruv va ZIP

**Files:**
- Verify: `static/index.html`
- Verify: `main.py`
- Package: `Platforma_v1635_unified_search_results.zip`

**Interfaces:**
- Consumes: testdan o‘tgan v1635 manba.
- Produces: keshsiz, yaxlitligi tekshirilgan ZIP.

- [x] **Step 1: Inline JavaScript sintaksisini tekshirish**

```bash
sed -n '/^<script>$/,/^<\/script>$/p' static/index.html | sed '1d;$d' | node --check -
```

Expected: exit code `0`.

- [x] **Step 2: Barcha testlarni ishga tushirish**

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest discover -s tests -q
```

Expected: barcha testlar `OK`.

- [x] **Step 3: Browser-free UI smoke test**

```bash
node tests/district-offers-ui-smoke.cjs --contract-only
```

Expected: `District offers UI contract passed`.

- [x] **Step 4: Toza paket va ZIP yaratish**

`rsync` bilan `__pycache__`, `.pytest_cache`, `.venv` va `*.pyc` chiqarilgan
`Platforma_v1635_unified_search_results` papkasi yaratiladi va ZIP qilinadi.

- [x] **Step 5: ZIP yaxlitligi, BUILD, kesh, qator va SHA-256 nazorati**

Expected:

- arxiv xatosiz;
- BUILD va ikki v1635 flag mavjud;
- kesh fayllari yo‘q;
- `static/index.html` qator soni qayd etilgan;
- SHA-256 qayd etilgan.

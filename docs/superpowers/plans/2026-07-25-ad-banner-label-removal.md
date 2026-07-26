# Reklama banneri xizmat yozuvlarini olib tashlash Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Bosh sahifa reklama banneridan ko‘rinadigan `Tavsiya etamiz` va alohida `Reklama` xizmat yozuvlarini olib tashlash, bannerning qolgan ishlash tartibini o‘zgartirmaslik.

**Architecture:** O‘zgarish faqat `static/index.html` ichidagi bosh sahifa `#adBox` komponenti va uning `renderHomeAd()` funksiyasiga cheklanadi. HTML holati parser bilan, dinamik zaxira sarlavha esa haqiqiy JavaScript funksiyasini Node.js’da bajarish orqali test qilinadi.

**Tech Stack:** HTML, CSS, vanilla JavaScript, Python `unittest`, Node.js, FastAPI loyiha BUILD metama’lumoti.

## Global Constraints

- `Tavsiya etamiz` va alohida `Reklama` xizmat yozuvlari bannerda ko‘rinmasin.
- Reklama sarlavhasi, tavsifi, rasmi va `Ko‘rish` tugmasi saqlansin.
- `alt="Reklama"` accessibility matni saqlansin.
- Reklama karuseli, ko‘rish/bosish hisobi, mobil/desktop rasmlar, API va ma’lumotlar bazasi o‘zgarmasin.
- Qidiruv, xarita, istoriyalar, takliflar va kabinetlarga tegilmasin.
- Yangi BUILD `v1650` bo‘lsin.

---

### Task 1: Banner yozuvlari va regressiya himoyasi

**Files:**
- Create: `tests/test_ad_banner_labels_v1650_frontend.py`
- Modify: `static/index.html:1519-1538`
- Modify: `static/index.html:12780-12820`
- Modify: `main.py:70`
- Modify: `main.py:679`
- Modify: BUILD raqamini tekshiradigan mavjud `tests/test_*.py` fayllari

**Interfaces:**
- Consumes: `#adBox`, `#adTitle`, `#adText`, `#adPhoto`, `#adMobileSource`, `renderHomeAd()`.
- Produces: `adTitleText(ad: object) -> string`; bo‘sh sarlavha uchun `Taklif bilan tanishing`, mavjud sarlavha uchun uning o‘zi.

- [x] **Step 1: Mavjud to‘liq test holatini tekshirish**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
```

Expected: `Ran 275 tests`, `OK`.

- [x] **Step 2: Failing frontend test yozish**

`tests/test_ad_banner_labels_v1650_frontend.py`:

```python
import json
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path


class AdBoxParser(HTMLParser):
    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self):
        super().__init__()
        self.in_ad = False
        self.depth = 0
        self.ids = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if not self.in_ad and attrs.get("id") == "adBox":
            self.in_ad = True
            self.depth = 1
        elif self.in_ad and tag not in self.VOID_TAGS:
            self.depth += 1
        if self.in_ad and attrs.get("id"):
            self.ids.append(attrs["id"])

    def handle_endtag(self, tag):
        if self.in_ad:
            self.depth -= 1
            if self.depth == 0:
                self.in_ad = False

    def handle_data(self, data):
        if self.in_ad and data.strip():
            self.text.append(data.strip())


class AdBannerLabelRemovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("static/index.html").read_text(encoding="utf-8")

    def test_initial_banner_has_no_service_labels(self):
        parser = AdBoxParser()
        parser.feed(self.html)
        self.assertNotIn("adEyebrow", parser.ids)
        self.assertNotIn("Tavsiya etamiz", parser.text)
        self.assertNotIn("Reklama", parser.text)
        self.assertIn("adTitle", parser.ids)
        self.assertIn("adText", parser.ids)
        self.assertIn("Ko‘rish", parser.text)

    def test_runtime_title_fallback_is_neutral(self):
        start = self.html.index("function adTitleText(")
        end = self.html.index("\n  function ", start + 10)
        function_source = self.html[start:end]
        script = (
            function_source
            + "\nconsole.log(JSON.stringify(["
            + "adTitleText({title:'Mahalla Market'}),"
            + "adTitleText({title:''})]));"
        )
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(result.stdout),
            ["Mahalla Market", "Taklif bilan tanishing"],
        )

    def test_build_endpoint_reports_the_change(self):
        import asyncio
        import main

        payload = asyncio.run(main.app_build())
        self.assertEqual(payload["build"], "v1650")
        self.assertIs(payload["ad_banner_labels_hidden_v1650"], True)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 3: Testni RED holatda ishga tushirish**

Run:

```bash
./.venv/bin/python -m unittest tests.test_ad_banner_labels_v1650_frontend -v
```

Expected: FAIL, chunki `adEyebrow` va `Tavsiya etamiz` hali mavjud hamda `adTitleText()` yo‘q.

- [x] **Step 4: Minimal frontend o‘zgarishini kiritish**

`static/index.html`:

```html
<div class="ad-copy">
  <h3 id="adTitle">Taklif bilan tanishing</h3>
  <p id="adText">Hududingizdagi foydali takliflarni ko‘ring.</p>
  <span class="ad-cta">Ko‘rish</span>
</div>
```

`renderHomeAd()` dan barcha `el("adEyebrow")` murojaatlarini olib tashlash va sarlavha yordamchisini qo‘shish:

```javascript
function adTitleText(a){
  var title=a&&a.title!=null?String(a.title).trim():"";
  return title||"Taklif bilan tanishing";
}
```

Bo‘sh reklama holati:

```javascript
el("adTitle").textContent="Taklif bilan tanishing";
el("adText").textContent="Hududingizdagi foydali takliflarni ko‘ring.";
```

Aktiv reklama holati:

```javascript
el("adTitle").textContent=adTitleText(a);
el("adText").textContent=a.caption||"Batafsil ko'rish uchun bosing.";
```

- [x] **Step 5: BUILD va capability ni yangilash**

`main.py`:

```python
APP_BUILD = "v1650"
```

`/api/capabilities` javobiga:

```python
"ad_banner_labels_hidden_v1650": True
```

Mavjud frontend testlaridagi aynan joriy BUILD talablarini `v1649` dan `v1650` ga yangilash.

- [x] **Step 6: Yangi testni GREEN holatda tekshirish**

Run:

```bash
./.venv/bin/python -m unittest tests.test_ad_banner_labels_v1650_frontend -v
```

Expected: `Ran 3 tests`, `OK`.

- [x] **Step 7: Tegishli regressiya testlarini tekshirish**

Run:

```bash
./.venv/bin/python -m unittest \
  tests.test_ad_banner_labels_v1650_frontend \
  tests.test_unified_search_results_contract \
  tests.test_responsive_ad_images_v1649_frontend -v
```

Expected: barcha testlar `OK`.

- [x] **Step 8: To‘liq test va sintaksis tekshiruvi**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
./.venv/bin/python -m py_compile main.py api.py database.py
```

Inline JavaScriptni `node --check` bilan tekshirish uchun HTML ichidagi asosiy inline script vaqtinchalik faylga ajratiladi.

Expected: `Ran 278 tests`, `OK`; Python va JavaScript sintaksis xatosiz.

- [x] **Step 9: Tarqatish ZIP faylini yaratish va tekshirish**

Create:

```text
/workspace/scratch/ce2e01c62c86/Platforma_v1650_ad_banner_labels_hidden.zip
```

ZIP tarkibiga loyiha manbasi kiritiladi; `.venv`, `__pycache__`, `.pytest_cache` va `platforma.db` kiritilmaydi.

Run:

```bash
zip -T /workspace/scratch/ce2e01c62c86/Platforma_v1650_ad_banner_labels_hidden.zip
```

Expected: `test of ... OK`.

## Yakuniy qabul

- Bannerda `Tavsiya etamiz` va alohida `Reklama` xizmat yozuvlari yo‘q.
- Reklama kontenti va barcha ishlash jarayonlari saqlangan.
- BUILD `v1650`.
- `static/index.html` yakuniy qator soni qayd etilgan.
- To‘liq testlar yashil.

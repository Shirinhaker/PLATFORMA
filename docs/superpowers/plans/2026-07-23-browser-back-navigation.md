# Browser Back Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BUILD v1636 da kompyuter va telefon Back/Forward tugmalarini Ko‘prikning ichki ekranlari, qidiruv natijasi va Taxi holati bilan sinxronlashtirish.

**Architecture:** `nav()` History API bilan ishlaydigan optsionli routerga kengaytiriladi. Har bir tarix holatida `screen` va `results` saqlanadi; `popstate` oddiy ekran, qidiruv natijasi yoki Taxi holatini yangi tarix yozmasdan tiklaydi. Mavjud `BACKMAP` faqat history mavjud bo‘lmagan fallback sifatida qoladi.

**Tech Stack:** Bitta `static/index.html`, vanilla JavaScript History API, FastAPI BUILD metama’lumoti, Python `unittest`, Node syntax check.

## Global Constraints

- Ichki ekrandagi Back sayt tashqarisiga chiqarmaydi.
- Boshlang‘ich `home` holatida Back brauzerning odatiy chiqish xatti-harakatini saqlaydi.
- Qidiruv loading va yakuniy natija ikki tarix yozuvi yaratmaydi.
- Forward ichki ekran va `RES` keshidagi qidiruv natijasini tiklaydi.
- Taxi Back/Forward xaritani ko‘chirish va cleanupni ham bajaradi.
- `BACKMAP`, qidiruv API, xarita metkalari va kabinet ruxsatlari o‘zgarmaydi.
- BUILD qiymati `v1636`.
- Manba Git repository emas; commit o‘rniga test va ZIP nazorat nuqtalari ishlatiladi.

---

### Task 1: Browser history regression kontrakti

**Files:**
- Create: `tests/test_browser_history_navigation_contract.py`
- Test: `static/index.html`

**Interfaces:**
- Consumes: `frontend_source() -> str`
- Produces: History API, qidiruv result state, Taxi replay va Back fallback kontrakti.

- [x] **Step 1: Failing testlarni yozish**

```python
import unittest

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


class BrowserHistoryNavigationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_navigation_registers_and_replays_browser_history(self):
        for value in (
            'var APP_HISTORY_READY=false;',
            'history.replaceState(appHistoryState(screen,extra)',
            'history.pushState(appHistoryState(screen,extra)',
            'window.addEventListener("popstate",function(event){',
            'nav(target,{fromHistory:true});',
        ):
            self.assertIn(value, self.html)

    def test_search_results_have_one_replayable_history_state(self):
        for value in (
            'function enterResults(list_html, pins, count, options){',
            'results:true',
            'var resultHistoryActive=',
            'enterResults(RES.html,RES.pins,RES.count,{fromHistory:true});',
            'exitResults({fromHistory:true});',
        ):
            self.assertIn(value, self.html)

    def test_taxi_and_header_back_use_the_same_history(self):
        for value in (
            'function enterCall(options){',
            'function exitCall(options){',
            'exitCall({fromHistory:true,targetScreen:target});',
            'enterCall({fromHistory:true});',
            'function appBack(){',
            'history.back();',
        ):
            self.assertIn(value, self.html)
```

- [x] **Step 2: v1635 kodda testlarning History API yo‘qligi sabab yiqilishini tasdiqlash**

Run:

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_browser_history_navigation_contract -v
```

Expected: `replaceState`, `pushState`, `popstate` va history-aware result/Taxi funksiyalari yo‘qligi uchun `FAIL`.

---

### Task 2: History API router

**Files:**
- Modify: `static/index.html`
- Test: `tests/test_browser_history_navigation_contract.py`
- Test: `tests/test_taxi_call_clean_screen_contract.py`

**Interfaces:**
- Produces:
  - `appHistoryState(screen: string, extra?: object) -> object`
  - `writeAppHistory(screen: string, extra?: object, replace?: boolean) -> void`
  - `nav(screen: string, options?: object) -> void`
  - `appBack() -> void`

- [x] **Step 1: History helperlarini `nav()` oldiga qo‘shish**

```javascript
var APP_HISTORY_READY=false;
function appHistoryState(screen,extra){
  extra=extra||{};
  return {koprikApp:true,screen:screen||"home",results:!!extra.results};
}
function writeAppHistory(screen,extra,replace){
  if(!window.history||!history.pushState)return;
  try{
    if(replace||!APP_HISTORY_READY){
      history.replaceState(appHistoryState(screen,extra),"",window.location.href);
      APP_HISTORY_READY=true;
    }else{
      history.pushState(appHistoryState(screen,extra),"",window.location.href);
    }
  }catch(e){}
}
```

- [x] **Step 2: `nav()`ni options va history sync bilan kengaytirish**

```javascript
function nav(screen,options){
  options=options||{};
  var previousScreen=current;
  // mavjud UI navigatsiya...
  if(options.fromHistory){
    APP_HISTORY_READY=true;
  }else if(!APP_HISTORY_READY){
    writeAppHistory(screen,options.historyExtra,true);
  }else if(previousScreen!==screen||options.forceHistory){
    writeAppHistory(screen,options.historyExtra,false);
  }
}
```

UI qismi o‘z joyida saqlanadi; history yozuvi `nav()` oxiriga qo‘shiladi.

- [x] **Step 3: Header Back uchun history-first helper qo‘shish**

```javascript
function fallbackBackScreen(){
  return current==="person" ? personBack :
    current==="list" ? listBack :
    current==="pickloc" ? pickReturnScreen() :
    (BACKMAP[current]||"home");
}
function appBack(){
  var state=window.history&&history.state;
  if(state&&state.koprikApp&&history.length>1){
    history.back();
    return;
  }
  if(current==="taxi-call"){exitCall();return;}
  nav(fallbackBackScreen());
}
```

`#backBtn` click handleri faqat `appBack()`ni chaqiradi.

---

### Task 3: Result va Taxi holatlarini tarixdan tiklash

**Files:**
- Modify: `static/index.html`
- Test: `tests/test_browser_history_navigation_contract.py`
- Test: `tests/test_mobile_home_single_screen_contract.py`
- Test: `tests/test_taxi_call_clean_screen_contract.py`

**Interfaces:**
- Extends:
  - `enterResults(list_html, pins, count, options?)`
  - `exitResults(options?)`
  - `enterCall(options?)`
  - `exitCall(options?)`

- [x] **Step 1: Qidiruv natijasini bir marta historyga yozish**

`enterResults()` options qabul qiladi. Joriy history allaqachon
`results:true` bo‘lsa loading/yakuniy update yangi yozuv yaratmaydi:

```javascript
var historyState=window.history&&history.state;
var resultHistoryActive=!!(
  historyState&&historyState.koprikApp&&historyState.screen==="home"&&
  historyState.results
);
nav("home",{
  fromHistory:!!options.fromHistory,
  forceHistory:!options.fromHistory&&!resultHistoryActive,
  historyExtra:{results:true}
});
```

`exitResults({fromHistory:true})` popstate vaqtida history yozuvini
almashtirmaydi. Oddiy tozalashda stale `results:true` yozuvi
`replaceState()` bilan `results:false`ga o‘tkaziladi.

- [x] **Step 2: Taxi funksiyalarini history replayga moslash**

```javascript
function enterCall(options){
  options=options||{};
  // mavjud setup...
  nav("taxi-call",{fromHistory:!!options.fromHistory});
}
function exitCall(options){
  options=options||{};
  // mavjud cleanup...
  nav(options.targetScreen||"home",{fromHistory:!!options.fromHistory});
}
```

- [x] **Step 3: `popstate` holat tiklovchisini qo‘shish**

```javascript
window.addEventListener("popstate",function(event){
  var state=event.state;
  if(!state||!state.koprikApp)return;
  APP_HISTORY_READY=true;
  var target=state.screen||"home";
  var wantsResults=target==="home"&&!!state.results;

  if(current==="taxi-call"&&target!=="taxi-call"){
    exitCall({fromHistory:true,targetScreen:target});
    return;
  }
  if(target==="taxi-call"&&current!=="taxi-call"){
    enterCall({fromHistory:true});
    return;
  }
  if(!wantsResults&&!el("resWrap").hidden){
    exitResults({fromHistory:true});
  }
  if(wantsResults&&RES&&RES.html){
    enterResults(RES.html,RES.pins,RES.count,{fromHistory:true});
    return;
  }
  nav(target,{fromHistory:true});
});
```

- [x] **Step 4: Target testlarni yashil qilish**

Run:

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_browser_history_navigation_contract tests.test_taxi_call_clean_screen_contract tests.test_mobile_home_single_screen_contract tests.test_unified_search_results_contract -v
```

Expected: `OK`.

---

### Task 4: BUILD v1636

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Modify: `tests/test_frontend_assets.py`
- Modify: `tests/test_domain_integration_ready.py`
- Modify: `tests/test_listing_media_frontend_contract.py`
- Modify: `tests/test_production_foundation.py`
- Modify: `tests/test_story_frontend_contract.py`
- Modify: `tests/test_v1616_security_contract.py`
- Create: `docs/v1636-browser-back-navigation.md`

**Interfaces:**
- Consumes: `/api/build`
- Produces: `build == "v1636"`, `browser_history_navigation_v1636 == True`, `search_result_history_v1636 == True`.

- [x] **Step 1: BUILD testlarini v1636 ga o‘tkazish va yangi flaglarni talab qilish**

Mavjud `v1635` BUILD assertionlari `v1636`ga o‘zgartiriladi.
`tests/test_frontend_assets.py`ga:

```python
self.assertIn('"browser_history_navigation_v1636": True', self.main)
self.assertIn('"search_result_history_v1636": True', self.main)
```

- [x] **Step 2: Eski metadata bilan testning yiqilishini tasdiqlash**

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_frontend_assets.FrontendAssetContractTests.test_release_metadata_declares_single_file_frontend -v
```

Expected: eski `v1635` va yangi flaglar yo‘qligi sabab `FAIL`.

- [x] **Step 3: Runtime BUILD, flaglar va release hujjatini yangilash**

```python
APP_BUILD = "v1636"
```

`/api/build`:

```python
"browser_history_navigation_v1636": True,
"search_result_history_v1636": True
```

HTML comment:

```html
<!-- BUILD: v1636 -->
```

- [x] **Step 4: Metadata testlarini yashil qilish**

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest tests.test_frontend_assets tests.test_domain_integration_ready tests.test_listing_media_frontend_contract tests.test_production_foundation tests.test_story_frontend_contract tests.test_v1616_security_contract -v
```

Expected: `OK`.

---

### Task 5: To‘liq tekshiruv va ZIP

**Files:**
- Verify: `static/index.html`
- Verify: `main.py`
- Package: `Platforma_v1636_browser_back_navigation.zip`

**Interfaces:**
- Consumes: testdan o‘tgan v1636 manba.
- Produces: keshsiz, tekshirilgan ZIP.

- [x] **Step 1: Inline JavaScript sintaksisini tekshirish**

```bash
sed -n '/^<script>$/,/^<\/script>$/p' static/index.html | sed '1d;$d' | node --check -
```

- [x] **Step 2: To‘liq testlarni bajarish**

```bash
/tmp/koprik-v1630-venv/bin/python -m unittest discover -s tests -q
```

- [x] **Step 3: Browser-free UI smoke test**

```bash
node tests/district-offers-ui-smoke.cjs --contract-only
```

- [x] **Step 4: Keshsiz ZIP yaratish**

`rsync` bilan `__pycache__`, `.pytest_cache`, `.venv`, `*.pyc` chiqariladi.

- [x] **Step 5: ZIP yaxlitligi, BUILD, qator soni va SHA-256ni tekshirish**

Expected: arxiv xatosiz, manba bilan bir xil, keshsiz va BUILD v1636.

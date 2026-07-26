# Reklama rasmi o‘chirish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Oddiy va biznes reklama formasida tanlangan rasmni yuqori o‘ng burchakdagi `×` tugmasi va tasdiqlash oynasi orqali xavfsiz olib tashlash.

**Architecture:** Mavjud `AD_FORM` holatiga vaqtinchalik preview URL qo‘shiladi. `clearAdImage(prefix)` faqat media holatini tozalaydi, `requestAdImageRemoval(prefix)` esa mavjud `askConfirm` yordamida foydalanuvchi tasdig‘ini oladi; qolgan reklama forma maydonlari o‘zgarmaydi.

**Tech Stack:** Bitta faylli HTML/CSS/vanilla JavaScript frontend, Python `unittest` kontrakt testlari, FastAPI build metama’lumoti.

## Global Constraints

- Faqat reklama rasm tanlash/o‘chirish oqimi o‘zgaradi.
- Oddiy foydalanuvchi (`ua`) va biznes (`ba`) formasi bir xil umumiy funksiyadan foydalanadi.
- Backend reklama API’si, narx, hudud, vaqt va e’lon media oqimi o‘zgarmaydi.
- `data-ui-release="v1647"` o‘zgarmaydi, chunki v1647 dizayn CSS selektorlari shu atributga bog‘langan.
- Ilova BUILD qiymati `v1648` bo‘ladi.
- Loyiha papkasi Git repozitoriy emas; yangi Git yaratmasdan yakunda ZIP nazorat nusxasi tayyorlanadi.

---

### Task 1: Reklama rasmi o‘chirish kontrakt testi

**Files:**
- Create: `tests/test_ad_image_removal_v1648_contract.py`
- Read: `static/index.html`

**Interfaces:**
- Consumes: `baPreview`, `uaPreview`, `bindAdForm(prefix)`, `askConfirm(options)`.
- Produces: HTML tugma identifikatorlari va JavaScript funksiyalariga qo‘yilgan bajariladigan kontrakt.

- [ ] **Step 1: Failing test yozish**

```python
import unittest
from pathlib import Path


class AdImageRemovalV1648ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("static/index.html").read_text(encoding="utf-8")

    def test_business_and_user_preview_have_remove_button(self):
        for value in (
            'id="baImageRemove"',
            'id="uaImageRemove"',
            'class="ad-preview-remove"',
            'aria-label="Tanlangan reklama rasmini o‘chirish"',
        ):
            self.assertIn(value, self.html)

    def test_remove_flow_requires_confirmation_and_clears_media_state(self):
        for value in (
            "function clearAdImage(prefix)",
            "function requestAdImageRemoval(prefix)",
            'text:"Tanlangan reklama rasmi o‘chirilsinmi?"',
            "st.file=null",
            'st.image_file=""',
            "URL.revokeObjectURL(st.preview_url)",
            'el(prefix+"ImageRemove").addEventListener("click"',
        ):
            self.assertIn(value, self.html)

    def test_v1647_design_release_attribute_is_preserved(self):
        self.assertIn('data-ui-release="v1647"', self.html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Testni RED holatda ishga tushirish**

Run:

```bash
python -m unittest tests.test_ad_image_removal_v1648_contract -v
```

Expected: `baImageRemove` topilmagani sabab test `FAIL` bo‘ladi.

---

### Task 2: Preview ustidagi `×` va media holatini tozalash

**Files:**
- Modify: `static/index.html` — reklama CSS, `baPreview`, `uaPreview`, `AD_FORM`, `resetAdForm`, `bindAdForm`.
- Test: `tests/test_ad_image_removal_v1648_contract.py`

**Interfaces:**
- Consumes: `askConfirm({text, okText, danger})`, `resetAdCrop(prefix)`, `el(id)`.
- Produces:
  - `clearAdImage(prefix): void`
  - `requestAdImageRemoval(prefix): Promise<void>`

- [ ] **Step 1: `×` tugmasi CSS’ini qo‘shish**

```css
.ad-preview-remove{
  position:absolute;
  top:8px;
  right:8px;
  z-index:3;
  width:36px;
  height:36px;
  border:2px solid #fff;
  border-radius:50%;
  background:#dc2626;
  color:#fff;
  font:900 22px/1 Arial,sans-serif;
  display:grid;
  place-items:center;
  cursor:pointer;
  box-shadow:0 4px 12px rgba(0,0,0,.28);
}
.ad-preview-remove:active{transform:scale(.94);}
.ad-preview-remove:focus-visible{outline:3px solid var(--amber);outline-offset:2px;}
```

- [ ] **Step 2: Ikkala previewga tugma qo‘shish**

```html
<div class="ad-preview" id="baPreview">
  <img alt="Reklama rasmi">
  <button type="button" class="ad-preview-remove" id="baImageRemove"
    aria-label="Tanlangan reklama rasmini o‘chirish">×</button>
</div>
```

`uaPreview` uchun ham aynan shu tuzilma `uaImageRemove` identifikatori bilan qo‘shiladi.

- [ ] **Step 3: Preview URL holatini saqlash**

```javascript
var AD_FORM = {
  ba:{actor:"business",targets:[],file:null,image_file:"",preview_url:"",crop_x:50,crop_y:50,crop_zoom:1},
  ua:{actor:"user",targets:[],file:null,image_file:"",preview_url:"",crop_x:50,crop_y:50,crop_zoom:1}
};
```

- [ ] **Step 4: Faqat rasm holatini tozalovchi funksiya yozish**

```javascript
function clearAdImage(prefix){
  var st=AD_FORM[prefix];
  st.file=null;
  st.image_file="";
  if(st.preview_url){
    try{URL.revokeObjectURL(st.preview_url);}catch(e){}
    st.preview_url="";
  }
  el(prefix+"ImageInput").value="";
  el(prefix+"Preview").classList.remove("on");
  el(prefix+"Preview").querySelector("img").removeAttribute("src");
  el(prefix+"CropBox").classList.remove("on");
  el(prefix+"CropStage").querySelector("img").removeAttribute("src");
  el(prefix+"ImageInfo").textContent="";
  resetAdCrop(prefix);
}
```

- [ ] **Step 5: Tasdiqlash oqimini yozish**

```javascript
function requestAdImageRemoval(prefix){
  return askConfirm({
    text:"Tanlangan reklama rasmi o‘chirilsinmi?",
    okText:"O‘chirish",
    danger:true
  }).then(function(ok){
    if(ok) clearAdImage(prefix);
  });
}
```

- [ ] **Step 6: Reset va yangi fayl tanlashni xavfsiz ulash**

`resetAdForm(prefix)` media qismini takroran qo‘lda tozalamasdan
`clearAdImage(prefix)`ni chaqiradi. Yangi fayl uchun `URL.createObjectURL(f)`
yaratilishidan oldin eski `st.preview_url` bekor qilinadi, yangi URL
`st.preview_url`ga yoziladi.

- [ ] **Step 7: Tugma hodisasini ulash**

```javascript
el(prefix+"ImageRemove").addEventListener("click",function(){
  requestAdImageRemoval(prefix);
});
```

- [ ] **Step 8: GREEN testni ishga tushirish**

Run:

```bash
python -m unittest tests.test_ad_image_removal_v1648_contract -v
```

Expected: barcha yangi testlar `OK`.

---

### Task 3: BUILD v1648 metama’lumoti

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Modify: BUILD qiymatini aniq tekshiradigan mavjud `tests/test_*.py` fayllari.

**Interfaces:**
- Consumes: `APP_BUILD`, `/api/capabilities`, HTML `BUILD` izohi.
- Produces: backend va frontendda bir xil `v1648` build identifikatori.

- [ ] **Step 1: Backend build va imkoniyat bayrog‘ini yangilash**

```python
APP_BUILD = "v1648"
```

`capabilities()` javobiga:

```python
"ad_image_remove_v1648": True
```

qo‘shiladi.

- [ ] **Step 2: Frontend BUILD izohini yangilash**

```html
<title>Koprik</title><!-- BUILD: v1648 --><!-- UI: approved-home-catalog -->
```

`data-ui-release="v1647"` saqlanadi.

- [ ] **Step 3: Mavjud build kontraktlarini v1648 ga moslash**

Faqat `APP_BUILD = "v1647"` va `<!-- BUILD: v1647 -->` qiymatini tekshirayotgan
assertlar `v1648` ga o‘zgartiriladi. `auth_profile_design_v1647` bayrog‘i va
`data-ui-release="v1647"` testi o‘zgartirilmaydi.

- [ ] **Step 4: Build kontraktlarini tekshirish**

Run:

```bash
python -m unittest discover -s tests -p "test*.py" -v
```

Expected: barcha Python testlari `OK`.

---

### Task 4: Yakuniy tekshiruv va paket

**Files:**
- Verify: `static/index.html`
- Verify: `main.py`
- Create: `/workspace/scratch/ce2e01c62c86/Platforma_v1648_ad_image_remove.zip`

**Interfaces:**
- Consumes: Task 1–3 natijalari.
- Produces: tekshirilgan v1648 ZIP paket va o‘zgarishlar ro‘yxati.

- [ ] **Step 1: Python sintaksisini tekshirish**

Run:

```bash
python -m py_compile main.py api.py
```

Expected: chiqishsiz `0` kodi.

- [ ] **Step 2: To‘liq test to‘plamini ishga tushirish**

Run:

```bash
python -m unittest discover -s tests -p "test*.py"
```

Expected: barcha testlar `OK`.

- [ ] **Step 3: BUILD va dizayn release’ini tekshirish**

Run:

```bash
rg -n 'APP_BUILD = "v1648"|BUILD: v1648|data-ui-release="v1647"|ad_image_remove_v1648' main.py static/index.html
```

Expected: backend/frontend BUILD `v1648`, dizayn release `v1647`, yangi imkoniyat
bayrog‘i mavjud.

- [ ] **Step 4: `index.html` qatorini hisoblash**

Run:

```bash
wc -l static/index.html
```

- [ ] **Step 5: ZIP paket yaratish**

Loyiha papkasining barcha manba va test fayllari
`Platforma_v1648_ad_image_remove.zip` ichiga joylanadi; vaqtinchalik
`__pycache__`, `.pyc` va render artefaktlari kiritilmaydi.

- [ ] **Step 6: ZIP yaxlitligini tekshirish**

Run:

```bash
unzip -t /workspace/scratch/ce2e01c62c86/Platforma_v1648_ad_image_remove.zip
```

Expected: `No errors detected`.

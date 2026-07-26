# Responsive Advertisement Images Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ko‘prik reklamasiga hozirgi banner balandliklarini o‘zgartirmasdan kompyuter va telefon uchun alohida rasm yuklash hamda mos rasmni avtomatik ko‘rsatish imkonini qo‘shish.

**Architecture:** Mavjud `advertisements.image_file` kompyuter rasmi bo‘lib qoladi, yangi `mobile_image_file` ustuni telefon rasmini saqlaydi. Bitta mavjud upload endpointi har ikki faylni yuklaydi, reklama yaratish endpointi ikkala yo‘lni saqlaydi. Frontend ikkita mustaqil upload/preview holatini boshqaradi va bosh sahifada `<picture>` orqali `1080px` chegarada mos rasmni tanlaydi.

**Tech Stack:** Python 3, FastAPI, SQLite, yagona `static/index.html` ichidagi HTML/CSS/JavaScript, `unittest`/`pytest`.

## Global Constraints

- Kompyuter bannerining hozirgi maksimal `1372 × 184 px` ko‘rinishi o‘zgarmaydi.
- Mobil bannerning hozirgi `122 px` balandligi o‘zgarmaydi.
- Kompyuter rasmi uchun tavsiya `2744 × 368 px`, nisbat `7.46:1`.
- Mobil rasm uchun tavsiya `800 × 250 px`, nisbat `3.2:1`.
- `image_file` majburiy, `mobile_image_file` ixtiyoriy.
- Mobil rasm bo‘lmasa kompyuter rasmi fallback bo‘ladi.
- Eski reklamalarning crop oqimi buzilmaydi.
- `data-ui-release="v1647"` o‘zgarmaydi.
- Yangi BUILD `v1649`.
- Ishlamaydigan boshqa bo‘limlar o‘zgartirilmaydi.

---

### Task 1: Ma’lumotlar bazasi va API kontrakti

**Files:**
- Modify: `database.py`
- Modify: `api.py`
- Create: `tests/test_responsive_ad_images_v1649_api.py`

**Interfaces:**
- Consumes: mavjud `advertisements` jadvali, `_ad_dict(row)`, `POST /api/advertisements`.
- Produces: `advertisements.mobile_image_file: str`, API javobidagi `mobile_image_file`, xavfsiz `/uploads/ads/` mobil rasm yo‘li.

- [ ] **Step 1: Failing kontrakt testlarini yozish**

```python
class ResponsiveAdApiContractTests(unittest.TestCase):
    def test_database_adds_mobile_image_column(self):
        self.assertIn("mobile_image_file TEXT NOT NULL DEFAULT ''", self.database)

    def test_ad_dict_returns_mobile_image(self):
        self.assertIn('"mobile_image_file": row["mobile_image_file"]', self.api)

    def test_create_advertisement_validates_and_inserts_mobile_image(self):
        self.assertIn('mobile_image_file = str(b.get("mobile_image_file") or "").strip()', self.api)
        self.assertIn('mobile_image_file and not mobile_image_file.startswith("/uploads/ads/")', self.api)
        self.assertIn("caption,image_file,mobile_image_file,crop_x", self.api)
```

- [ ] **Step 2: Testni ishga tushirib qizil holatni tasdiqlash**

Run: `./.venv/bin/python -m pytest tests/test_responsive_ad_images_v1649_api.py -q`

Expected: `mobile_image_file` hali mavjud bo‘lmagani sabab FAIL.

- [ ] **Step 3: Bazaga orqaga mos ustun qo‘shish**

`database.py` jadval ta’rifiga:

```python
"mobile_image_file TEXT NOT NULL DEFAULT '', "
```

Migratsiyaga:

```python
if "mobile_image_file" not in adcols:
    conn.execute(
        "ALTER TABLE advertisements "
        "ADD COLUMN mobile_image_file TEXT NOT NULL DEFAULT ''"
    )
```

- [ ] **Step 4: API serializatsiya, validatsiya va INSERTni yangilash**

`_ad_dict()` javobiga:

```python
"mobile_image_file": row["mobile_image_file"] or "",
```

`create_advertisement()` ichiga:

```python
mobile_image_file = str(b.get("mobile_image_file") or "").strip()
if mobile_image_file and not mobile_image_file.startswith("/uploads/ads/"):
    raise HTTPException(400, "Telefon rasmi manzili noto‘g‘ri")
```

INSERT ustunlari va qiymatlariga `mobile_image_file`ni `image_file`dan keyin qo‘shish.

- [ ] **Step 5: API testini yashil holatga keltirish**

Run: `./.venv/bin/python -m pytest tests/test_responsive_ad_images_v1649_api.py -q`

Expected: PASS.

---

### Task 2: Ikki rasmli reklama formasi

**Files:**
- Modify: `static/index.html`
- Create: `tests/test_responsive_ad_images_v1649_frontend.py`
- Preserve: `tests/test_ad_image_removal_v1648_contract.py`

**Interfaces:**
- Consumes: mavjud `AD_FORM`, `bindAdForm(prefix)`, `clearAdImage(prefix)`, `/api/advertisements/image`.
- Produces: har forma uchun `mobile_file`, `mobile_image_file`, `mobile_preview_url`; `clearAdImage(prefix, variant)`; ikkala rasmni ketma-ket yuklaydigan submit oqimi.

- [ ] **Step 1: Failing frontend kontrakt testini yozish**

```python
class ResponsiveAdFrontendContractTests(unittest.TestCase):
    def test_both_forms_offer_desktop_and_mobile_images(self):
        for prefix in ("ba", "ua"):
            self.assertIn(f'id="{prefix}Image"', self.html)
            self.assertIn(f'id="{prefix}MobileImage"', self.html)
            self.assertIn(f'id="{prefix}MobilePreview"', self.html)

    def test_form_state_keeps_two_images(self):
        self.assertIn('mobile_file:null', self.html)
        self.assertIn('mobile_image_file:""', self.html)

    def test_submit_sends_mobile_image(self):
        self.assertIn("mobile_image_file:st.mobile_image_file", self.html)
```

- [ ] **Step 2: Testni ishga tushirib qizil holatni tasdiqlash**

Run: `./.venv/bin/python -m pytest tests/test_responsive_ad_images_v1649_frontend.py -q`

Expected: mobil input va holat hali yo‘qligi sabab FAIL.

- [ ] **Step 3: Oddiy va biznes formaga ikkinchi upload/preview qo‘shish**

Har formadagi mavjud kompyuter rasm inputini saqlab, uning ostiga quyidagi
strukturani prefiksga mos IDlar bilan qo‘shish:

```html
<label class="list-sub">Telefon uchun rasm — tavsiya 800 × 250 px</label>
<input type="file" id="baMobileImage" accept="image/jpeg,image/png,image/webp">
<div class="ad-crop-stage" id="baMobilePreview">
  <img id="baMobilePreviewImg" alt="Telefon banneri">
  <button type="button" class="ad-image-remove"
          id="baMobileImageRemove" aria-label="Telefon rasmini o‘chirish">×</button>
</div>
```

`ua` formasi uchun ayni struktura `ua...` IDlari bilan qo‘shiladi.

- [ ] **Step 4: Holat va o‘chirish funksiyasini ikki variantga moslash**

```javascript
ba:{
  actor:"business",targets:[],
  file:null,image_file:"",preview_url:"",
  mobile_file:null,mobile_image_file:"",mobile_preview_url:"",
  crop_x:50,crop_y:50,crop_zoom:1
}
```

```javascript
function clearAdImage(prefix, variant){
  var st=AD_FORM[prefix], mobile=variant==="mobile";
  var fileKey=mobile?"mobile_file":"file";
  var imageKey=mobile?"mobile_image_file":"image_file";
  var previewKey=mobile?"mobile_preview_url":"preview_url";
  if(st[previewKey]) URL.revokeObjectURL(st[previewKey]);
  st[fileKey]=null;
  st[imageKey]="";
  st[previewKey]="";
  renderAdCrop(prefix);
}
```

Mavjud desktop `×` tugmasi `clearAdImage(prefix, "desktop")`, yangi mobil
`×` tugmasi `clearAdImage(prefix, "mobile")` chaqiradi.

- [ ] **Step 5: Submit oqimida ikkala rasmni yuklash**

```javascript
var desktopUpload=st.image_file
  ? Promise.resolve({image_file:st.image_file})
  : uploadRaw("POST","/api/advertisements/image?actor_type="+st.actor,st.file);

desktopUpload.then(function(desktop){
  st.image_file=desktop.image_file;
  if(st.mobile_image_file) return {image_file:st.mobile_image_file};
  if(!st.mobile_file) return {image_file:""};
  return uploadRaw(
    "POST",
    "/api/advertisements/image?actor_type="+st.actor,
    st.mobile_file
  );
}).then(function(mobile){
  st.mobile_image_file=mobile.image_file||"";
  return api("POST","/api/advertisements",{
    actor_type:st.actor,
    title:title,
    caption:caption,
    image_file:st.image_file,
    mobile_image_file:st.mobile_image_file,
    crop_x:st.crop_x,
    crop_y:st.crop_y,
    crop_zoom:st.crop_zoom,
    daily_all_day:allDay,
    daily_start:dailyStart,
    daily_end:dailyEnd,
    targets:st.targets,
    start_at:startAt,
    duration_days:durationDays
  });
});
```

- [ ] **Step 6: Frontend va eski o‘chirish testlarini yashil qilish**

Run:

```bash
./.venv/bin/python -m pytest \
  tests/test_responsive_ad_images_v1649_frontend.py \
  tests/test_ad_image_removal_v1648_contract.py -q
```

Expected: PASS.

---

### Task 3: Responsive banner ko‘rsatish

**Files:**
- Modify: `static/index.html`
- Modify: `tests/test_responsive_ad_images_v1649_frontend.py`

**Interfaces:**
- Consumes: API reklama obyektidagi `image_file`, `mobile_image_file`, crop qiymatlari.
- Produces: `#adMobileSource`, `<picture>`, `renderHomeAd()`dagi mobil source va eski reklama fallbacki.

- [ ] **Step 1: Failing `<picture>` va fallback testlarini qo‘shish**

```python
def test_home_ad_uses_picture_source(self):
    self.assertIn("<picture", self.html)
    self.assertIn('id="adMobileSource"', self.html)
    self.assertIn('media="(max-width: 1079px)"', self.html)

def test_mobile_source_falls_back_to_desktop(self):
    self.assertIn("a.mobile_image_file||a.image_file", self.html)

def test_current_banner_heights_are_preserved(self):
    self.assertIn(".ad.has-image .ad-photo{height:184px;}", self.html)
    self.assertIn("#adBox .ad-photo{height:122px;}", self.html)
```

- [ ] **Step 2: Testni ishga tushirib qizil holatni tasdiqlash**

Run: `./.venv/bin/python -m pytest tests/test_responsive_ad_images_v1649_frontend.py -q`

Expected: `<picture>` va mobil source yo‘qligi sabab FAIL.

- [ ] **Step 3: Banner DOMini `<picture>`ga o‘tkazish**

```html
<picture class="ad-picture">
  <source id="adMobileSource" media="(max-width: 1079px)">
  <img class="ad-photo" id="adPhoto" alt="Reklama">
</picture>
```

CSS:

```css
.ad-picture{display:block;width:100%;height:100%}
.ad-picture .ad-photo{width:100%;height:100%;object-fit:cover}
```

Mavjud `184px` desktop va `122px` mobil qoidalari saqlanadi.

- [ ] **Step 4: `renderHomeAd()`ni responsive manbaga moslash**

```javascript
var mobileImage=a.mobile_image_file||a.image_file;
el("adMobileSource").srcset=mobileImage;
el("adPhoto").src=a.image_file;
```

`mobile_image_file` bor yangi reklamada crop transformini tozalash:

```javascript
if(a.mobile_image_file){
  el("adPhoto").removeAttribute("style");
}else{
  el("adPhoto").setAttribute("style", adCropStyle(a));
}
```

- [ ] **Step 5: Frontend testlarini yashil qilish**

Run: `./.venv/bin/python -m pytest tests/test_responsive_ad_images_v1649_frontend.py -q`

Expected: PASS.

---

### Task 4: BUILD, regressiya va paket

**Files:**
- Modify: `main.py`
- Modify: BUILD qiymatini tekshiradigan `tests/test_*.py` fayllari
- Create: `Platforma_v1649_responsive_ad_images.zip`

**Interfaces:**
- Consumes: Tasks 1–3 natijalari.
- Produces: `APP_BUILD = "v1649"`, capability `responsive_ad_images_v1649`, foydalanuvchiga yuklanadigan ZIP.

- [ ] **Step 1: BUILD kontraktlarini v1649ga yangilash**

`main.py`:

```python
APP_BUILD = "v1649"
```

Capability javobiga:

```python
"responsive_ad_images_v1649": True
```

Testlardagi aniq `APP_BUILD = "v1648"` kutuvlarini `v1649`ga almashtirish.

- [ ] **Step 2: Yangi testlar va bog‘liq regressiyani ishga tushirish**

Run:

```bash
./.venv/bin/python -m pytest \
  tests/test_responsive_ad_images_v1649_api.py \
  tests/test_responsive_ad_images_v1649_frontend.py \
  tests/test_ad_image_removal_v1648_contract.py \
  tests/test_web_home_frontend_contract.py -q
```

Expected: PASS.

- [ ] **Step 3: To‘liq test to‘plamini ishga tushirish**

Run: `./.venv/bin/python -m pytest -q`

Expected: barcha testlar PASS.

- [ ] **Step 4: Statik tekshiruvlar**

Run:

```bash
python -m py_compile main.py api.py database.py
wc -l static/index.html
rg -n 'APP_BUILD|responsive_ad_images_v1649|mobile_image_file|adMobileSource' \
  main.py api.py database.py static/index.html
```

Expected: Python syntax xatosiz; BUILD va yangi maydonlar topiladi.

- [ ] **Step 5: ZIP tayyorlash va tarkibini tekshirish**

Paketdan `.venv`, `__pycache__`, `.pytest_cache`, mavjud `.zip`lar chiqarib
tashlanadi. ZIP ichida `static/index.html`, `main.py`, `api.py`,
`database.py` va testlar bo‘lishi shart.

Run:

```bash
zipinfo -1 Platforma_v1649_responsive_ad_images.zip | \
  rg '^(static/index.html|main.py|api.py|database.py|tests/)'
```

Expected: kerakli fayllar ro‘yxatda bor, virtual muhit yo‘q.


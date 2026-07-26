# Ko‘prik kirish, manzil va profil dizaynini yangilash

## Maqsad

Berilgan qoramtir Ko‘prik dizaynini amaldagi `v1646` loyihasining quyidagi
ekranlariga moslashtirish:

1. manzilni belgilash;
2. kabinetga kirish;
3. ro‘yxatdan o‘tish;
4. xodimlar kirishi;
5. oddiy foydalanuvchi, mutaxassis va biznes profil/kabinet ekranlari.

## Tasdiqlangan yondashuv

Foydalanuvchi `1`-variantni tasdiqladi: faqat ko‘rinish va responsive joylashuv
yangilanadi. Mavjud API, ma’lumotlar bazasi, autentifikatsiya jarayoni,
Telegram tasdiqlashi, ruxsatlar, ekran yo‘nalishlari va element IDlari
o‘zgartirilmaydi.

## Vizual manba

- `upload/design-comparison.png`
- `upload/design-comparison-mobile.png`
- `upload/preview.html`
- `upload/index-C9IKZUn_.js`
- `upload/index-wHB27tS_.css`
- `upload/AGENTS.md`

Asosiy vizual til:

- chuqur yashil-qora fon;
- turkuaz asosiy tugmalar;
- yumaloqlangan 16–24 px kartalar;
- oq va xira-yashil matnlar;
- amber rang faqat ogohlantirish va yordamchi belgilar uchun;
- kompyuterda markazlangan keng panel, telefonda to‘liq kenglik;
- ishlatilayotgan `Inter` va `Plus Jakarta Sans` shriftlari saqlanadi.

## Ekranlar

### Manzilim

- Sarlavha, maxfiylik izohi va majburiy tanlash xabari bitta tartibli panelga
  yig‘iladi.
- Avtomatik aniqlash tugmasi asosiy amal bo‘lib qoladi.
- Viloyat, tuman va mahalla maydonlari bir xil yangi input uslubida chiqadi.
- Xaritadagi markaziy belgi va mavjud Leaflet mantiqi saqlanadi.
- `locAuto`, `locViloyat`, `locTuman`, `locMahalla`, `userLocMap` va
  `locSave` IDlari saqlanadi.

### Kabinetga kirish

- Kabinet turi vizual jihatdan aniq ko‘rsatiladi.
- Login va parol maydonlari yangi panel uslubiga o‘tadi.
- Telegram tasdiqlashning ikki bosqichi va qayta yuborish taymeri saqlanadi.
- Ro‘yxatdan o‘tish va xodimlar kirishi ikkilamchi amallar sifatida qoladi.
- `passwordLogin`, `passwordPass`, `passwordLoginGo`, `loginCode`,
  `loginVerify`, `loginOpenTelegram`, `loginResend` IDlari saqlanadi.

### Ro‘yxatdan o‘tish

- Biznes va oddiy foydalanuvchi tanlovi yangi katta tanlov kartalari bilan
  ko‘rsatiladi.
- Dinamik `regBody` formasining amaldagi maydonlari va Telegram kodi jarayoni
  saqlanadi.
- Yangi dizayn forma holatlari: tanlash, kiritish, kod kutish va tasdiqlashni
  vizual ajratadi.

### Xodim kirishi

- Markazlangan, alohida `Xodim kirishi` paneli ishlatiladi.
- Firma logini, xodim logini va xodim paroli o‘zgarmaydi.
- Oddiy kirishga qaytish tugmasi saqlanadi.
- `slFirm`, `slLogin`, `slPass`, `slEnter`, `slErr`, `slBack` IDlari saqlanadi.

### Profil va kabinetlar

- Oddiy va biznes kabinetning mavjud KPI kartalari, menyu yo‘nalishlari va
  so‘nggi faoliyat qismi saqlanadi.
- Oddiy, mutaxassis va biznes profil kartalari yangi qoramtir dizayn tokenlari
  asosida bir xil vizual tizimga o‘tadi.
- Biznes va oddiy kabinet o‘rtasidagi almashtirish tugmalari saqlanadi.
- Onlaynlashtirish va Tizimlashtirish guruhlari saqlanadi.
- Istoriyalar, obunalar, xarita, qidiruv va buyurtma mantiqlariga tegilmaydi.

## Responsive talablar

- Telefon (`<720px`): bitta ustun, to‘liq kenglik, kamida 44 px bosish zonasi.
- Planshet (`720–1079px`): ikki ustunli tanlov va KPI kartalari.
- Kompyuter (`>=1080px`): keng kabinet paneli, asosiy menyu va so‘nggi faoliyat
  yonma-yon.
- Hech bir ekran gorizontal scroll chiqarmaydi.

## O‘zgarmas cheklovlar

- `main.py` API endpointlari o‘zgarmaydi.
- Telegram tasdiqlashi va 30 kunlik sessiya mantiqi o‘zgarmaydi.
- Oddiy va biznes kabinet ma’lumotlari aralashmaydi.
- Xodim ruxsatlari o‘zgarmaydi.
- Foydalanuvchi tumani boshqa foydalanuvchilarga oshkor qilinmaydi.
- Istoriya va tariflar mustaqilligi saqlanadi.
- Pro uchun alohida maxsus xarita belgisi qo‘shilmaydi.

## Qabul mezonlari

1. Besh ekran guruhi yangi dizaynda ko‘rinadi.
2. Mavjud ID, API va tugma hodisalari ishlaydi.
3. Telefon, planshet va kompyuterda joylashuv buzilmaydi.
4. Qidiruv, xarita, obuna, istoriya va kabinet ruxsatlari regressiya qilmaydi.
5. Barcha avvalgi avtomatik testlar va yangi dizayn kontrakt testlari yashil.
6. `design-qa.md` manba va amalga oshirilgan ko‘rinishni solishtirib
   `final result: passed` bilan tugaydi.


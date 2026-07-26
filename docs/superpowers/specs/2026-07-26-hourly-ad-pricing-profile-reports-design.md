# Ko‘prik: soatlik reklama narxi va profil shikoyatlari dizayni

Sana: 2026-07-26  
Holat: foydalanuvchi tomonidan tasdiqlangan

## 1. Maqsad

Ushbu o‘zgarish ikkita aniq vazifani bajaradi:

1. reklama narxini bitta tuman uchun bir soatga bog‘lab, viloyat va
   respublika narxini tumanlar sonidan avtomatik hisoblash;
2. oddiy va biznes profillariga yagona, tushunarli shikoyat yuborish
   oqimini qo‘shish.

O‘zgarishlar MVPda ochiq qolgan reklama, qo‘lda to‘lov tasdig‘i va admin
moderatsiyasi bilan ishlaydi. Istoriya, e’lon, suhbat va tizimlashtirish
qismlarining yoqilgan/o‘chirilgan holatiga tegilmaydi.

## 2. Tasdiqlangan biznes qoidalari

### 2.1 Asosiy reklama birligi

- Bitta tuman uchun bir soat: **20 000 so‘m**.
- Admin faqat shu bazaviy narxni o‘zgartiradi.
- Yangi narx kodi: `advertisement_district_hour`.
- Eski `advertisement_district_day` kodi yangi reklama yaratishda
  ishlatilmaydi, lekin eski to‘lov va reklama yozuvlari buzilmasligi uchun
  legacy yozuv sifatida saqlanadi.

### 2.2 Hudud narxi

Backend tanlangan hududni yagona tumanlar to‘plamiga yoyadi:

- bitta tuman — 1 birlik;
- viloyat — katalogdagi shu viloyatga tegishli tumanlar soni;
- respublika — katalogdagi barcha viloyatlardagi barcha tumanlar soni.

Bir tuman bir nechta tanlov orqali qamrab olingan bo‘lsa, faqat bir marta
hisoblanadi. Masalan, Surxondaryo viloyati va uning ichidagi alohida tuman
birgalikda tanlansa, o‘sha tuman ikki marta narxga qo‘shilmaydi.

Respublika tanlanganda boshqa hudud qo‘shilmaydi.

Surxondaryo katalogida 13 tuman bo‘lsa:

```text
13 × 1 soat × 20 000 = 260 000 so‘m
```

### 2.3 Vaqt va kunlar

- Foydalanuvchi boshlanish sanasini tanlaydi.
- Reklama necha kun takrorlanishini `1`, `3`, `7`, `14` yoki `30`
  variantidan belgilaydi.
- Har kunlik boshlanish va tugash vaqtlarida faqat to‘liq soatlar
  tanlanadi: `00:00`, `01:00`, ... `23:00`.
- Daqiqali vaqtlar (`11:02`, `11:29`, `13:30`) qabul qilinmaydi.
- Boshlanish va tugash vaqti teng bo‘lishi mumkin emas.
- Tun oralig‘i qo‘llab-quvvatlanadi: `22:00–02:00` — 4 soat.
- Tun oralig‘ida tugash vaqti keyingi kalendar kuniga tegishli bo‘ladi.
  Masalan, dushanba `22:00–02:00` ko‘rsatilishi seshanba `02:00`da
  tugaydi.
- “Kun bo‘yi” tanlovi mavjud bo‘lsa, u 24 hisoblanadigan soatga teng.
- Chegirmalar qo‘llanmaydi.

Narx formulasi:

```text
unique_district_count × hours_per_day × duration_days × district_hour_rate
```

Misol:

```text
13 tuman × 2 soat × 3 kun × 20 000 = 1 560 000 so‘m
```

### 2.4 Narx xavfsizligi

- Frontend faqat taxminiy/yakuniy narxni ko‘rsatadi.
- Yakuniy hisob backendda o‘sha paytdagi faol bazaviy narx va server
  katalogi asosida qayta bajariladi.
- Foydalanuvchidan yuborilgan tayyor summa qabul qilinmaydi.
- To‘lov so‘rovi yaratilganda bazaviy narx, tumanlar soni, kunlik soatlar,
  kunlar va yakuniy summa snapshot sifatida saqlanadi.
- Admin keyinchalik bazaviy narxni o‘zgartirsa, avval yuborilgan to‘lov
  so‘rovi summasi o‘zgarmaydi.

## 3. Reklama oqimi

### 3.1 Foydalanuvchi interfeysi

Reklama yaratish oynasida quyidagilar bo‘ladi:

1. kompyuter va telefon banner rasmlari;
2. sarlavha va qisqa matn;
3. hudud tanlash;
4. boshlanish sanasi;
5. necha kun takrorlanishi;
6. har kunlik boshlanish va tugash soati;
7. hisob tafsiloti:
   - qamrab olingan tumanlar soni;
   - kunlik soatlar soni;
   - kunlar soni;
   - bir tuman/soat narxi;
   - yakuniy summa.

Masalan:

```text
13 tuman × 2 soat × 3 kun × 20 000 so‘m
Jami: 1 560 000 so‘m
```

### 3.2 To‘lov

Reklama saqlangach:

1. reklama `payment_pending` holatida yaratiladi;
2. yangi `advertisement_district_hour` narxi asosida to‘lov so‘rovi
   yaratiladi;
3. miqdor `unique_district_count × hours_per_day × duration_days`
   ko‘rinishidagi tuman-soat soniga teng bo‘ladi;
4. foydalanuvchi kvitansiya yuboradi;
5. admin to‘lovni tasdiqlaydi yoki rad etadi;
6. tasdiqlangach reklama belgilangan jadval asosida faol bo‘ladi.

### 3.3 Kech tasdiqlangan reklama

To‘lov reklamaning tanlangan birinchi boshlanish vaqtidan oldin
tasdiqlansa, jadval o‘zgarmaydi.

To‘lov tanlangan boshlanish vaqtidan keyin tasdiqlansa, foydalanuvchi
to‘lagan vaqt yo‘qolmasligi uchun birinchi ko‘rsatish avtomatik ravishda
keyingi mos to‘liq soatli jadvalga suriladi. Kunlar va kunlik soatlar soni
saqlanadi. Admin tasdig‘i reklama vaqtini kamaytirmaydi.

### 3.4 Eski yozuvlar

- Eski kunlik reklamalar mavjud `duration_days`, `start_at`, `end_at`,
  `daily_start` va `daily_end` qiymatlari bilan ishlashda davom etadi.
- Eski `advertisement_district_day` to‘lovlari avvalgi snapshot bo‘yicha
  ko‘riladi va tasdiqlanadi.
- Yangi UI faqat soatlik narx kodini ishlatadi.
- Migratsiya mavjud reklama yoki to‘lovni qayta narxlamaydi.

## 4. Profil shikoyati

### 4.1 Tugma joylashuvi

Shikoyat tugmasi faqat profil ichida bo‘ladi:

- oddiy foydalanuvchi profili;
- biznes profili.

Profil egasi o‘z profilini ko‘rayotganda shikoyat bandi ko‘rsatilmaydi.
Boshqa foydalanuvchi profilda `⋮` menyuni bosib, `Shikoyat qilish` bandini
tanlaydi.

### 4.2 Shikoyat sabablari

UI matni mavjud backend kodlariga quyidagicha bog‘lanadi:

| Foydalanuvchiga ko‘rinadigan sabab | Backend kodi |
|---|---|
| Yolg‘on yoki noto‘g‘ri ma’lumot / firibgarlik | `fraud` |
| Keraksiz yoki takroriy reklama | `spam` |
| Noqonuniy yoki taqiqlangan faoliyat | `illegal` |
| Haqorat, bezovta qilish yoki nomaqbul xatti-harakat | `abuse` |
| Boshqa sabab | `other` |

Izoh ixtiyoriy va 500 belgidan oshmaydi.

### 4.3 Yuborish oqimi

1. Foydalanuvchi `Shikoyat qilish`ni tanlaydi.
2. Sababni tanlaydi.
3. Ixtiyoriy izoh yozadi.
4. Tasdiqlash oynasida `Yuborish`ni bosadi.
5. Frontend `POST /api/reports` so‘rovini yuboradi.
6. Oddiy profil uchun `content_kind=profile`, biznes uchun
   `content_kind=business` ishlatiladi.
7. Shikoyat `open` holatida admin navbatiga tushadi.
8. Muvaffaqiyatli yuborilganda foydalanuvchiga
   `Shikoyatingiz yuborildi` xabari chiqadi.

Ro‘yxatdan o‘tmagan mehmon tugmani bossa, kirish oynasi ochiladi. Kirish
tugagach foydalanuvchi ko‘rib turgan profiliga qaytariladi.

### 4.4 Cheklovlar va maxfiylik

- O‘z profiliga yoki o‘z biznesiga shikoyat yuborib bo‘lmaydi.
- Bir reporter ayni profilga `open` yoki `reviewing` shikoyati mavjud
  bo‘lsa, yana yubora olmaydi.
- Bitta foydalanuvchi 24 soatda ko‘pi bilan 10 ta shikoyat yuboradi.
- Profil egasiga reporterning shaxsi ko‘rsatilmaydi.
- Oddiy foydalanuvchilar boshqa shikoyatlarni ko‘ra olmaydi.
- Admin shikoyatning reporterini faqat moderatsiya vazifasi doirasida
  ko‘radi.

### 4.5 Admin oqimi

Admin panelning `Shikoyatlar` bo‘limida:

1. `open` shikoyat ko‘rinadi;
2. admin uni o‘ziga biriktirib `reviewing` holatiga o‘tkazadi;
3. profil va sababni tekshiradi;
4. shikoyatni:
   - `resolved` — chora ko‘rildi;
   - `dismissed` — asos topilmadi
     holatiga o‘tkazadi;
5. zarurat bo‘lsa profil kontentini yashiradi yoki hisobni bloklaydi;
6. qaror, sabab va admin Telegram ID audit tarixiga yoziladi.

## 5. Ma’lumotlar va interfeys chegaralari

### 5.1 Reklama

Mavjud reklamalar jadvalidagi quyidagi maydonlar saqlanadi:

- `duration_days`;
- `daily_all_day`;
- `daily_start`;
- `daily_end`;
- `start_at`;
- `end_at`;
- `price`.

Hisob tafsilotlari to‘lov so‘rovining target/config snapshotida saqlanadi:

- `district_count`;
- `hours_per_day`;
- `duration_days`;
- `district_hour_rate`;
- `billable_district_hours`;
- `schedule_start`;
- `daily_start`;
- `daily_end`.

Backend region/district katalogi narx hisobining yagona ishonchli manbasi
bo‘ladi. Frontend katalogi faqat tanlash interfeysi uchun ishlatiladi.

### 5.2 Shikoyat

Mavjud `moderation_reports` jadvali va `/api/reports` endpointi ishlatiladi.
Yangi alohida shikoyat jadvali yoki admin endpointi yaratilmaydi.

## 6. Xatolarni boshqarish

Reklama yuborilmaydi, agar:

- hudud tanlanmagan bo‘lsa;
- boshlanish sanasi/soati noto‘g‘ri bo‘lsa;
- daqiqa `00` bo‘lmasa;
- boshlanish va tugash soati teng bo‘lsa;
- kunlar soni ruxsat etilgan chegaradan tashqarida bo‘lsa;
- backend hududni tumanlar katalogiga yoya olmasa;
- faol soatlik narx topilmasa.

Shikoyat yuborilmaydi, agar:

- foydalanuvchi tizimga kirmagan bo‘lsa;
- profil topilmasa yoki ochiq bo‘lmasa;
- foydalanuvchi o‘z profiliga shikoyat qilsa;
- ayni profilga ochiq shikoyat mavjud bo‘lsa;
- sutkalik limit tugagan bo‘lsa;
- sabab kodi noto‘g‘ri bo‘lsa;
- izoh 500 belgidan uzun bo‘lsa.

## 7. Qabul mezonlari

### 7.1 Reklama

- Admin `advertisement_district_hour` qiymatini 20 000 so‘m qilib ko‘radi
  va o‘zgartira oladi.
- Surxondaryo 13 tuman bo‘lganda 1 soat narxi 260 000 so‘m chiqadi.
- `11:00–13:00` 2 soat hisoblanadi.
- `22:00–02:00` 4 soat hisoblanadi.
- Daqiqali vaqt yuborilsa backend 400 qaytaradi.
- Bir-birini qamrab olgan hududlar tumanlarni ikki marta hisoblamaydi.
- Respublika narxi barcha yagona tumanlar sonidan hisoblanadi.
- 7, 14 yoki 30 kun uchun chegirma qo‘llanmaydi.
- Frontend summasini o‘zgartirish backend hisobiga ta’sir qilmaydi.
- Admin narxni o‘zgartirgandan keyin oldingi to‘lov snapshoti o‘zgarmaydi.
- Eski kunlik to‘lovlar va reklamalar ishlashda davom etadi.

### 7.2 Shikoyat

- Boshqa oddiy yoki biznes profilining `⋮` menyusida
  `Shikoyat qilish` ko‘rinadi.
- O‘z profilida bu band ko‘rinmaydi.
- Sabab va izoh yuborilganda shikoyat admin panelga `open` bo‘lib tushadi.
- Takroriy ochiq shikoyat 409 bilan rad etiladi.
- O‘z profiliga so‘rov 400 bilan rad etiladi.
- 24 soatdagi o‘n birinchi shikoyat 429 bilan rad etiladi.
- Admin qarori audit jurnaliga yoziladi.

## 8. Sinovlar

### 8.1 Unit sinovlar

- to‘liq soatlar farqi;
- tun oralig‘i;
- teng vaqtni rad etish;
- hududni yagona tumanlar to‘plamiga yoyish;
- takroriy hududlarni bitta hisoblash;
- narx formulasi;
- snapshot narxining o‘zgarmasligi.

### 8.2 API sinovlar

- reklama narxini hisoblash;
- reklama yaratish va to‘lov so‘rovi;
- to‘lov tasdig‘idan keyingi jadval;
- kech tasdiqda pulli vaqtni saqlash;
- profil va biznes shikoyati;
- self-report, duplicate va rate-limit radlari.

### 8.3 Frontend kontrakt sinovlari

- kunlik boshlanish va tugash selectlarida faqat `HH:00`;
- hisob tafsiloti va jami summa;
- yangi soatlik narx kodi;
- oddiy va biznes profilidagi shikoyat menyusi;
- o‘z profilida shikoyat tugmasining yo‘qligi;
- kirishdan keyin profilga qaytish.

### 8.4 Regressiya

- mavjud admin, to‘lov, obuna va reklama sinovlari;
- MVP feature-guard sinovlari;
- eski reklama/to‘lov moslik sinovlari;
- to‘liq Python test to‘plami;
- frontend JavaScript sintaksis tekshiruvi.

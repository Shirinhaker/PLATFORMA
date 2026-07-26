# Ko‘prik admin sayti, qo‘lda to‘lov va MVP rejimi dizayni

## 1. Maqsad

Ko‘prik loyihasining birinchi ommaviy MVP versiyasini faqat
onlaynlashtirish imkoniyatlari bilan ishga tushirish:

- alohida va himoyalangan admin sayt yaratish;
- reklama, obuna va kelajakdagi e’lon joylashtirish uchun qo‘lda
  tasdiqlanadigan to‘lov tizimi yaratish;
- admin orqali narxlar, to‘lov usullari, profillar, kontent, bloklash,
  statistika, shikoyatlar va audit tarixini boshqarish;
- MVPga kirmaydigan funksiyalarni o‘chirmasdan frontend va backend
  darajasida bloklash;
- bosh sahifada obuna bo‘lingan profillarni istoriyalardan mustaqil
  ko‘rsatish.

## 2. Hozirgi holat

- Obuna domen modeli va Bepul/Plus/Pro tariflari mavjud.
- Plus va Pro hozir demo endpoint orqali faollashadi.
- Reklama yaratish va narx hisoblash mavjud.
- E’lon, istoriya, suhbat va Tizimlashtirish funksiyalari kodda mavjud.
- Alohida platforma admin kabineti mavjud emas.
- Ayrim ichki `admin` endpointlar platforma admin kabinetini tashkil
  qilmaydi.

## 3. Ishni mustaqil bosqichlarga ajratish

Bu dizayn to‘rtta mustaqil, ketma-ket va testlanadigan ishga bo‘linadi:

1. **MVP funksiyalarini boshqarish va admin autentifikatsiyasi.**
2. **Qo‘lda tasdiqlanadigan to‘lov tizimi.**
3. **Alohida to‘liq admin sayt.**
4. **MVP regressiya tekshiruvi va tarqatish paketi.**

Har bir bosqich o‘z testlariga ega bo‘ladi. Keyingi bosqich oldingi
bosqichning tasdiqlangan API interfeyslaridan foydalanadi.

## 4. Admin sayt arxitekturasi

### 4.1 Manzil va joylashtirish

- Admin sayt manzili: `https://admin.koprik.uz`.
- Asosiy `https://koprik.uz` saytida admin tugmasi bo‘lmaydi.
- Admin uchun alohida frontend fayllari bo‘ladi:
  - `admin/index.html`;
  - `admin/styles.css`;
  - `admin/app.js`.
- Admin va asosiy sayt bitta FastAPI backend va bitta ma’lumotlar
  bazasidan foydalanadi.
- Birinchi bosqichda bitta Railway servis yetarli.
- Backend `Host: admin.koprik.uz` bo‘yicha admin frontendni beradi.
- Mahalliy test uchun `/admin/` manzili ham ishlaydi.
- Admin API’lari faqat `/api/admin/...` ostida bo‘ladi.
- Kelajakda admin frontendni alohida serverga ko‘chirish mumkin, ammo API
  kontrakti o‘zgarmaydi.

### 4.2 Admin autentifikatsiyasi

- Admin Telegram orqali tasdiqlanadi.
- Ruxsat berilgan Telegram ID’lar Railway Variables’dagi
  `ADMIN_TG_IDS` qiymatidan olinadi.
- `ADMIN_TG_IDS` va `PRIVILEGED_TG_IDS` alohida tushunchalar.
- Ochiq admin ro‘yxatdan o‘tishi bo‘lmaydi.
- Telegram tasdiqlashdan keyin backend alohida admin sessiya yaratadi.
- Admin sessiyasi `HttpOnly`, `Secure`, `SameSite=Strict` cookie orqali
  saqlanadi.
- Oddiy foydalanuvchi mobil tokeni admin huquqini bermaydi.
- Har bir `/api/admin/...` so‘rovda:
  1. sessiya tekshiriladi;
  2. Telegram ID `ADMIN_TG_IDS` ichida ekanligi qayta tekshiriladi;
  3. bloklangan yoki muddati tugagan sessiya rad etiladi.
- Faolsiz admin sessiyasi belgilangan muddatdan keyin tugaydi.
- Frontendga admin ID, bot tokeni yoki boshqa sir yozilmaydi.

## 5. Admin sayt bo‘limlari

### 5.1 Boshqaruv paneli

Quyidagi ko‘rsatkichlar chiqadi:

- jami foydalanuvchilar;
- jami va faol biznes profillar;
- mahsulotlar va xizmatlar soni;
- faol reklamalar;
- kutilayotgan, tasdiqlangan, rad etilgan va bekor qilingan to‘lovlar;
- bugungi va joriy oydagi tasdiqlangan tushum;
- bloklangan hisoblar;
- yashirilgan kontentlar;
- ochiq shikoyatlar.

### 5.2 To‘lovlar

To‘rtta ro‘yxat:

- `Kutilmoqda`;
- `Tasdiqlangan`;
- `Rad etilgan`;
- `Bekor qilingan`.

Har bir yozuvda:

- foydalanuvchi yoki biznes;
- xizmat turi;
- tarif/muddat yoki reklama ma’lumoti;
- server hisoblagan summa;
- tanlangan to‘lov usuli;
- chek rasmi;
- yaratilgan va yangilangan vaqt;
- oldingi urinishlar;
- amaldagi holat ko‘rinadi.

Admin:

- chekni himoyalangan oynada kattalashtirib ko‘radi;
- tasdiqlaydi;
- majburiy sabab bilan rad etadi;
- tasdiqlangan to‘lovni majburiy sabab bilan bekor qiladi.

### 5.3 Narxlar va to‘lov usullari

Admin quyidagi narxlarni boshqaradi:

- reklama uchun bir tuman/bir kun birlik narxi;
- e’lon joylashtirish narxi;
- Plus 1, 3 va 12 oylik narxlari;
- Pro 1, 3 va 12 oylik narxlari.

To‘lov usullari:

- Uzcard;
- Humo;
- bank hisobi;
- boshqa qo‘lda kiritilgan usul.

Har bir usulda:

- nom;
- turi;
- rekvizitlar;
- oluvchi;
- foydalanuvchiga ko‘rsatma;
- tartib raqami;
- faol/nofaol holat bo‘ladi.

### 5.4 Foydalanuvchilar va bizneslar

- ism, telefon, username, biznes nomi yoki Telegram ID orqali qidirish;
- profil va ommaviy kontentni ko‘rish;
- `Kontentni yashirish`;
- `Hisobni to‘liq bloklash`;
- blokni ochish;
- foydalanuvchiga ko‘rinadigan sabab;
- faqat adminlarga ko‘rinadigan ichki izoh.

### 5.5 Kontent nazorati

MVPda:

- mahsulotlar;
- xizmatlar;
- reklamalar.

Kodda saqlanib, keyingi bosqichga tayyor:

- e’lonlar;
- istoriyalar.

Admin kontentni:

- yashiradi;
- qayta ko‘rsatadi;
- sabab bilan o‘chiradi.

Kontent dastlab avtomatik chiqadi. Oldindan admin tasdig‘i talab
qilinmaydi. Admin shikoyat yoki shubhali holatdan keyin chora ko‘radi.

### 5.6 Shikoyatlar

- `Yangi`;
- `Tekshirilmoqda`;
- `Chora ko‘rildi`;
- `Yopildi`.

Shikoyat profil yoki kontent bilan bog‘lanadi. Admin qarori va ichki izoh
saqlanadi.

### 5.7 Harakatlar tarixi

Quyidagilar audit tarixiga yoziladi:

- to‘lovni tasdiqlash, rad etish, bekor qilish;
- narx o‘zgartirish;
- to‘lov usulini yaratish/tahrirlash/yoqish/o‘chirish;
- kontentni yashirish, qayta ochish, o‘chirish;
- hisobni bloklash yoki ochish;
- shikoyat holatini o‘zgartirish.

Audit yozuvi admin interfeysidan tahrirlanmaydi va o‘chirilmaydi.

## 6. Qo‘lda tasdiqlanadigan to‘lov oqimi

### 6.1 Umumiy jarayon

1. Foydalanuvchi reklama, obuna yoki e’lon xizmatini tanlaydi.
2. Narx backenddagi faol narxdan hisoblanadi.
3. Frontend yuborgan summa ishonchli manba hisoblanmaydi.
4. Foydalanuvchi faol to‘lov usulini tanlaydi.
5. Chek rasmini majburiy yuklaydi.
6. Material va to‘lov so‘rovi `pending` holatida saqlanadi.
7. Admin tekshiradi.

### 6.2 Tasdiqlash

- **Reklama:** reklama avtomatik `active` bo‘ladi va belgilangan
  muddatdan ko‘rina boshlaydi.
- **Obuna:** Plus yoki Pro obuna tasdiqlangan vaqtdan boshlanadi.
- **E’lon:** to‘langan e’lon tayyor holatga o‘tadi, lekin MVPda
  `MVP_LISTINGS_ENABLED=0` sabab ommaga chiqmaydi.
- Tasdiq foydalanuvchiga sayt bildirishnomasi va Telegram bot orqali
  yuboriladi.

### 6.3 Rad etish va qayta yuborish

- Rad etish sababi majburiy.
- Material ommaga chiqmaydi.
- Foydalanuvchiga sayt va Telegram orqali sabab yuboriladi.
- Foydalanuvchi yangi chek yuklab qayta yuboradi.
- Eski chek va urinish o‘chirilmaydi.

### 6.4 Bekor qilish

- Faqat tasdiqlangan to‘lov bekor qilinadi.
- Sabab majburiy.
- Reklama faolsizlantiriladi yoki obuna bekor qilinadi.
- Operatsiya audit tarixiga yoziladi.
- Foydalanuvchiga sayt va Telegram orqali xabar yuboriladi.
- Pulni amalda qaytarish tashqi bank/karta orqali qo‘lda bajariladi;
  platforma avtomatik refund qilmaydi.

### 6.5 Holatlar

- `draft`;
- `pending`;
- `approved`;
- `rejected`;
- `cancelled`.

Tasdiqlash, rad etish va bekor qilish atomar tranzaksiyada ishlaydi.
Bir so‘rovni ikki admin yoki ikki marta tasdiqlash mumkin emas.

## 7. To‘lov ma’lumotlari modeli

### 7.1 `platform_prices`

- `id`;
- `price_code` — unikal kalit;
- `amount_uzs`;
- `active`;
- `updated_by_tg_id`;
- `created_at`;
- `updated_at`.

Asosiy kalitlar:

- `advertisement_district_day`;
- `listing_publish`;
- `subscription_plus_1m`;
- `subscription_plus_3m`;
- `subscription_plus_12m`;
- `subscription_pro_1m`;
- `subscription_pro_3m`;
- `subscription_pro_12m`.

### 7.2 `payment_methods`

- `id`;
- `method_type`;
- `name`;
- `details_json`;
- `recipient_name`;
- `instructions`;
- `sort_order`;
- `active`;
- `created_at`;
- `updated_at`.

### 7.3 `payment_requests`

- `id`;
- `request_code`;
- `actor_type`;
- `user_id`;
- `business_id`;
- `service_type` — `advertisement`, `subscription`, `listing`;
- `target_id`;
- `plan_code`;
- `duration_months`;
- `quantity`;
- `unit_price_snapshot`;
- `amount_snapshot`;
- `payment_method_id`;
- `status`;
- `approved_by_tg_id`;
- `approved_at`;
- `rejected_at`;
- `cancelled_at`;
- `public_reason`;
- `internal_note`;
- `created_at`;
- `updated_at`.

Narx `snapshot` maydonlarida saqlanadi. Keyingi narx o‘zgarishi eski
to‘lovni o‘zgartirmaydi.

### 7.4 `payment_attempts`

- `id`;
- `payment_request_id`;
- `attempt_no`;
- `receipt_filename`;
- `receipt_sha256`;
- `submitted_at`;
- `reviewed_at`;
- `review_status`;
- `review_reason`.

Bir xil chek xeshi boshqa faol yoki tasdiqlangan to‘lovda qayta
ishlatilmaydi.

### 7.5 `admin_sessions`

- admin Telegram ID;
- faqat xeshlangan sessiya tokeni;
- yaratilgan, oxirgi ishlatilgan va tugash vaqti;
- bekor qilingan holat.

### 7.6 `admin_audit_log`

- admin Telegram ID;
- harakat turi;
- obyekt turi va ID;
- o‘zgarishdan oldingi va keyingi xavfsiz qiymatlar;
- sabab;
- vaqt;
- so‘rov identifikatori.

### 7.7 `account_restrictions`

Ikki alohida cheklov:

- `content_hidden`;
- `account_blocked`.

Cheklovda sabab, ichki izoh, admin va vaqt saqlanadi.

### 7.8 `content_moderation`

- kontent turi va ID;
- `visible`, `hidden`, `deleted` holati;
- sabab;
- admin;
- yaratilgan va bekor qilingan vaqt.

### 7.9 `moderation_reports`

- yuboruvchi;
- nishon turi va ID;
- sabab/matn;
- holat;
- admin izohi;
- ko‘rib chiqilgan vaqt.

### 7.10 `platform_feature_flags`

Ma’lumotlar bazasidagi audit qilinadigan holat bilan Railway’dagi
boshlang‘ich qiymatlar birga ishlaydi. MVP ishlab chiqarish qiymatlari:

- `MVP_LISTINGS_ENABLED=0`;
- `MVP_STORIES_ENABLED=0`;
- `MVP_CHAT_ENABLED=0`;
- `MVP_SYSTEMIZATION_ENABLED=0`.

Backend yakuniy ruxsat manbai bo‘ladi. Frontend faqat backend qaytargan
ochiq funksiyalarni ko‘rsatadi.

## 8. MVP tarkibi

### 8.1 Ishlaydigan qismlar

- oddiy va biznes profillar;
- biznes profil/Mening sahifam;
- mahsulot va xizmatlarni joylashtirish;
- qidiruv;
- xarita va tarif qoidalariga mos biznes metkalari;
- Bepul/Plus/Pro obunalar;
- reklama joylashtirish;
- onlayn mahsulot buyurtmalari;
- xizmat buyurtmalari;
- mijoz fikrlari;
- bildirishnomalar;
- profil sozlamalari va chiqish;
- admin sayt va qo‘lda to‘lov boshqaruvi.

### 8.2 Bloklanadigan qismlar

- e’lon yaratish;
- bosh sahifa va menyudagi e’lonlar;
- e’lonlarni ommaviy olish API’lari;
- istoriya yaratish, ko‘rish, arxiv va tomoshabinlar;
- `Istoriyalarim`;
- umumiy `Suhbatlarim` bo‘limi va `/api/messages/*` yozishmalari;
- butun Tizimlashtirish guruhi;
- xodim kirishi;
- Kassa, Xarajatlar, Qarz daftari, Ombor va ichki statistika;
- ta’limning ichki boshqaruvi;
- AI yordamchi, ichki hisobot va Ma’muriyat.

Faqat tugmalar yashirilmaydi. Tegishli backend endpointlari ham feature
guard orqali bloklanadi. Admin arxiv/tekshiruv maqsadida saqlangan
ma’lumotlarni ko‘ra oladi.

### 8.3 Onlayn buyurtmalar

`Buyurtmalar` va `Xizmat buyurtmalari` Tizimlashtirish deb
hisoblanmaydi. Ular sayt orqali kelgan buyurtmalarni qabul qilish uchun
MVPda ishlaydi. Buyurtmaning o‘ziga bog‘langan `/api/orders/{id}/chat`
yozishmalari ham buyurtma jarayonining bir qismi sifatida saqlanadi; bu
umumiy `Suhbatlarim` bo‘limi hisoblanmaydi.

### 8.4 Reklama va e’lon oynasi

Hozirgi birlashgan `E’lonlarim va reklamalarim` oynasi MVPda
`Reklamalarim` sifatida ko‘rsatiladi. E’lon tablari, tugmalari va
so‘rovlari yashiriladi/bloklanadi. E’lon to‘lov oqimi kodda tayyor
turadi.

## 9. Obuna bo‘lingan profillar qatori

Bosh sahifadagi yuqori gorizontal qator saqlanadi, ammo istoriyalardan
butunlay ajratiladi:

- faqat tizimga kirgan foydalanuvchining obuna bo‘lgan biznes va oddiy
  profillari chiqadi;
- profil rasmi va nomi ko‘rinadi;
- profil bosilganda bevosita profil sahifasi ochiladi;
- qator gorizontal suriladi;
- obuna bo‘lmagan profil qo‘shilmaydi;
- obunalar bo‘lmasa qator yashiriladi.

Quyidagilar bo‘lmaydi:

- `Istoriya qo‘shish`;
- istoriya halqasi/yangi istoriya belgisi;
- rasm/video viewer;
- avtomatik istoriya almashishi;
- ko‘rilgan/ko‘rilmagan holati;
- istoriya feed API’ga bog‘liqlik.

Obuna munosabatlari o‘chirilmaydi. Istoriya funksiyasi keyin yoqilganda
alohida tizim sifatida qaytariladi.

## 10. Demo obunalarni yopish

- Plus/Pro demo faollashtirish tugmalari production frontenddan olib
  tashlanadi.
- Demo activation endpoint productionda rad etiladi.
- Demo faollashtirish faqat `TEST_MODE=1` test muhitida ishlaydi.
- Foydalanuvchi Plus/Pro’ni faqat to‘lov so‘rovi orqali oladi.

## 11. Chek fayllari xavfsizligi

- Ruxsat etilgan formatlar: JPG, PNG, WEBP.
- Maksimal fayl hajmi serverda cheklanadi.
- Fayl nomi server tomonidan yaratiladi.
- Fayl tarkibi va MIME turi tekshiriladi.
- Cheklar ommaviy `/uploads` ichida saqlanmaydi.
- Production manzil:
  `PAYMENT_RECEIPT_DIR=/data/private/payment_receipts`.
- Chekni faqat so‘rov egasi yoki admin himoyalangan endpoint orqali
  oladi.
- Receipt endpoint `Cache-Control: private, no-store` qaytaradi.
- To‘lov xeshi duplicate foydalanishni aniqlash uchun saqlanadi.

## 12. Bildirishnomalar

Quyidagi holatlarda sayt va Telegram bot orqali xabar yuboriladi:

- to‘lov qabul qilindi va tekshiruvga yuborildi;
- to‘lov tasdiqlandi;
- to‘lov sabab bilan rad etildi;
- qayta chek yuborildi;
- tasdiqlangan to‘lov bekor qilindi;
- kontent yashirildi/qayta ochildi;
- hisob bloklandi/ochildi.

Telegram yuborilishi vaqtincha ishlamasa, asosiy ma’lumotlar bazasi
tranzaksiyasi bekor qilinmaydi. Xabar qayta yuborish navbatiga yoziladi.

## 13. Xatolik va parallel so‘rovlar

- To‘lov summasi faqat serverda hisoblanadi.
- Admin amallari `BEGIN IMMEDIATE` tranzaksiya va joriy holat sharti
  bilan bajariladi.
- `pending` bo‘lmagan so‘rovni tasdiqlash/rad etish rad etiladi.
- Tasdiqlangan yozuvni faqat `cancelled` holatiga o‘tkazish mumkin.
- Admin frontend takroriy tugma bosilishini bloklaydi, lekin asosiy
  himoya backendda bo‘ladi.
- Har bir admin mutation so‘rovi audit yozuvisiz yakunlanmaydi.
- To‘lov usuli yoki narx o‘zgarganda oldingi request snapshot’i
  saqlanadi.
- Bloklangan hisob yangi yozuv, to‘lov yoki buyurtma yarata olmaydi.
- `content_hidden` foydalanuvchiga kabinetiga kirishga ruxsat beradi,
  lekin ommaviy kontentini yashiradi.

## 14. Migratsiya va orqaga moslik

- Yangi jadvallar `CREATE TABLE IF NOT EXISTS` orqali yaratiladi.
- Mavjud `business_subscriptions`, `advertisements`, `listings`,
  `users`, `businesses` va media ma’lumotlari o‘chirilmaydi.
- Mavjud demo obunalar tarix sifatida saqlanadi, ammo productionda yangi
  demo aktivatsiya qilinmaydi.
- Mavjud e’lon, istoriya va suhbat ma’lumotlari o‘chirilmaydi.
- Feature flag yoqilganda ular keyinchalik qayta ishlaydi.
- Eski DB nusxasida migratsiya testi bajariladi.

## 15. Qabul mezonlari

1. `admin.koprik.uz` asosiy saytdan alohida admin frontendni ochadi.
2. `ADMIN_TG_IDS`da bo‘lmagan foydalanuvchi admin API’dan 403 oladi.
3. Admin bo‘lmagan foydalanuvchi chek faylini ocholmaydi.
4. Admin narx va bir nechta to‘lov usulini boshqara oladi.
5. Reklama va obuna to‘lovi chek bilan `pending` holatga tushadi.
6. Tasdiqlangan reklama/obuna avtomatik faollashadi.
7. Rad etish sababi majburiy va qayta chek yuborish ishlaydi.
8. Tasdiqlangan to‘lovni sabab bilan bekor qilish ishlaydi.
9. Bir to‘lov ikki marta tasdiqlanmaydi.
10. Adminning barcha muhim amali auditda saqlanadi.
11. Ikki tur bloklash mustaqil ishlaydi.
12. MVPda e’lon, istoriya, umumiy `Suhbatlarim` va Tizimlashtirish
    UI/API’lari bloklangan.
13. Buyurtmalar va Xizmat buyurtmalari MVPda ishlaydi.
14. Bosh sahifada obuna bo‘lingan profillar ko‘rinadi va profilga
    ochiladi.
15. Obuna qatori istoriya API’lariga murojaat qilmaydi.
16. Qidiruv, xarita, profil, mahsulot va xizmat regressiya testlari
    yashil.
17. Admin sayt telefon, planshet va kompyuterda moslashuvchan.

## 16. Test strategiyasi

### 16.1 Unit testlar

- admin ID parsing va ruxsat;
- sessiya muddati va bekor qilish;
- narx hisoblash;
- to‘lov holatlari;
- bir xil chek xeshi;
- feature flag qoidalari;
- bloklash qoidalari;
- audit yozuvi.

### 16.2 API integration testlar

- admin login va 401/403 holatlari;
- to‘lov usuli CRUD;
- narx CRUD;
- receipt upload va himoyalangan download;
- reklama/obuna/e’lon payment request;
- approve/reject/resubmit/cancel;
- ikki parallel approve;
- profil/kontent bloklash;
- statistika va audit ro‘yxati;
- shikoyat holatlari;
- MVP bloklangan endpointlar;
- productionda demo activation bloklanishi.

### 16.3 Frontend testlar

- admin dashboard va barcha menyular;
- chek preview;
- narx va rekvizit formasi;
- bloklash confirmation oynalari;
- MVPda olib tashlangan tugmalar;
- `Reklamalarim` oynasida e’lon elementlari yo‘qligi;
- obuna bo‘lingan profillar qatori;
- telefon, planshet va desktop smoke test.

### 16.4 Regressiya

- qidiruv;
- xarita;
- profil;
- mahsulot/xizmat;
- obuna bo‘lgan profil metkalari;
- buyurtmalar;
- xizmat buyurtmalari;
- reklama responsive rasmlari;
- Telegram va sayt bildirishnomalari.

## 17. Tarqatish

- Yangi BUILD raqami beriladi.
- Railway Variables:
  - `ADMIN_TG_IDS`;
  - `PAYMENT_RECEIPT_DIR`;
  - to‘rtta MVP feature flag;
  - mavjud production sirlari.
- Cloudflare’da `admin.koprik.uz` yozuvi Railway domainiga ulanadi.
- Admin domain Railway Custom Domain sifatida qo‘shiladi.
- Avval staging/test ma’lumotlarida sinov qilinadi.
- To‘liq testlar yashil bo‘lgach productionga chiqariladi.
- Yakunda foydalanuvchiga tekshirilgan ZIP va aniq o‘zgargan fayllar
  ro‘yxati beriladi.

## 18. Scope tashqarisida

Ushbu MVP bosqichida quyidagilar bajarilmaydi:

- Click/Payme avtomatik webhook integratsiyasi;
- avtomatik pul qaytarish;
- e’lonlarni ommaga yoqish;
- istoriyalarni yoqish;
- suhbatlarni yoqish;
- Tizimlashtirish funksiyalarini yoqish;
- admin uchun alohida backend/server deploy;
- bir nechta darajali admin/moderator rollari.

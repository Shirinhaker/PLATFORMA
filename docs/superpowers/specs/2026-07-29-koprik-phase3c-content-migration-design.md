# Koprik Phase 3C — kontent va media migratsiyasi dizayni

Sana: 2026-07-29  
Holat: foydalanuvchi tasdiqlagan dizaynning yozma nusxasi  
Repository: `Shirinhaker/PLATFORMA`  
Branch: `codex/phase3c-content-migration`  
Asos commit: `10b27f5b5ae0d63409c561a77b0f19e773106f64`

## 1. Maqsad

Ishlab turgan BUILD v1656 monolitidagi haqiqiy akkauntlar, bizneslar, mahsulotlar, xizmatlar, e’lonlar, reklamalar va ularga tegishli media fayllarni yangi PostgreSQL/R2 arxitekturasiga ma’lumot yo‘qotmasdan ko‘chirish.

Phase 3C yakunida:

- yangi katalog haqiqiy mahsulot va xizmatlarni PostgreSQL’dan oladi;
- yangi qidiruv profil natijalari bilan birga mahsulot va xizmatlarni ham topadi;
- reklama bannerlari eski jadvaldan ajratilgan yangi reklama modelidan ko‘rsatiladi;
- e’lonlar ma’lumoti ko‘chiriladi, ammo `E’lonlar` funksiyasi foydalanuvchilarga yopiq qoladi;
- egasi bog‘langan yozuvlar avvalgi egasiga avtomatik tegishli bo‘ladi;
- egasi aniqlanmagan mahsulot va xizmatlar yo‘qolmaydi;
- barcha rasmlar va videolar yangi R2 media xotirasiga ko‘chiriladi;
- ishlab turgan monolit staging tekshiruvlari va yakuniy production o‘tishigacha o‘zgarmaydi.

Bu bosqichning asosiy tamoyili: avval nusxa, keyin staging migratsiyasi, keyin tekshiruv, eng oxirida nazoratli production o‘tish.

## 2. Joriy holat

### 2.1. Eski monolit

`database.py` ichidagi SQLite sxemada quyidagi asosiy jadvallar mavjud:

- `users`;
- `businesses`;
- `item_groups`;
- `items`;
- `listings`;
- `listing_media`;
- `advertisements`;
- `staff`.

Muhim eski bog‘lanishlar:

- `businesses.user_id -> users.id`;
- `items.business_id -> businesses.id`;
- `listings.user_id -> users.id`;
- `listings.business_id -> businesses.id` ixtiyoriy;
- `listing_media.listing_id -> listings.id`;
- `advertisements.user_id -> users.id`;
- `advertisements.business_id -> businesses.id` ixtiyoriy.

Eski `items.kind` maydoni `product` yoki `service` qiymatini saqlaydi. Narx `TEXT` ko‘rinishida saqlangan, shu sabab migratsiya narxni o‘zidan son qiymatiga aylantirmaydi.

Eski media manbalari bir xil emas:

- profil va mahsulot rasmlarida lokal fayl yo‘li yoki Telegram fayl identifikatori bo‘lishi mumkin;
- e’lon media yozuvlarida `tg_file_id` saqlangan;
- reklamada kompyuter va mobil banner uchun alohida fayl maydonlari bor;
- kesish holati `crop_x`, `crop_y`, `crop_zoom` orqali saqlanadi.

### 2.2. Yangi tizim

Asos commitda yangi backend:

- Python 3.12;
- FastAPI;
- SQLAlchemy asyncio;
- PostgreSQL;
- Alembic;
- Redis;
- Cloudflare R2/S3-compatible storage;
- Argon2 parol xeshlash

asosida qurilgan.

PostgreSQL’da hozir:

- `accounts`;
- `user_profiles`;
- `business_profiles`;
- yangi auth va session jadvallari

mavjud.

Mahsulot, xizmat, e’lon va reklama uchun yangi PostgreSQL modellari hali yo‘q. Joriy public discovery API faqat faol oddiy foydalanuvchi va biznes profillarini qidiradi. Joriy R2 moduli faqat avatar va biznes logosi uchun private upload grant yaratadi; migratsiya media importi uchun alohida server-side yozish adapteri kerak.

## 3. Tasdiqlangan biznes qoidalari

### 3.1. Ko‘chiriladigan ma’lumotlar

Hozir quyidagilarning hammasi ko‘chiriladi:

1. Eski foydalanuvchi akkauntlari.
2. Eski biznes akkauntlari va biznes profillari.
3. Mahsulot guruhlari.
4. Mahsulotlar.
5. Xizmatlar.
6. E’lonlar va e’lon media yozuvlari.
7. Reklamalar, jadvali, hududiy nishonlari, narx snapshoti va statistikasi.
8. Yuqoridagi yozuvlarga tegishli rasm va videolar.

Bloklangan, o‘chirilgan, muddati tugagan va nofaol yozuvlar ham asl statusi bilan ko‘chiriladi. Public API faqat foydalanuvchiga ko‘rsatish mumkin bo‘lgan faol yozuvlarni chiqaradi.

### 3.2. E’lon va reklama alohida tushuncha

- `E’lon` — foydalanuvchi yoki biznes joylashtirgan listing.
- `Reklama` — bosh sahifa yoki boshqa placement’da ko‘rsatiladigan pullik banner.

Ular alohida jadval, model, API va frontend holatiga ega bo‘ladi. Migratsiya yoki qidiruv ularni bitta turga birlashtirmaydi.

E’lonlar ko‘chiriladi, lekin `listings_enabled=false` holati saqlanadi. Yangi foydalanuvchi interfeysi `E’lonlar` sahifasiga kirishni bermaydi. Reklamalar esa o‘z jadvali va ko‘rsatish qoidalari bo‘yicha ishlaydi.

### 3.3. Egani avtomatik bog‘lash

Eski yozuvning egasi tasdiqlashsiz avtomatik bog‘lanadi:

- SMS so‘ralmaydi;
- administrator tasdig‘i so‘ralmaydi;
- “Bu biznes meniki” tugmasi yaratilmaydi;
- mahsulot va xizmat biznes bilan birga bog‘lanadi.

Avtomatik bog‘lash faqat deterministik identifikatorlar orqali bajariladi:

1. Avval mavjud eski ID → yangi ID xaritasi ishlatiladi.
2. Xarita bo‘lmasa, akkaunt turi bilan birga aniq login, Telegram ID yoki oldingi Phase 2 import identifikatori tekshiriladi.
3. Biznes `businesses.user_id` va mavjud biznes xaritasi orqali avvalgi egasiga bog‘lanadi.
4. Telefon raqami bo‘yicha taxminiy yoki o‘xshashlikka asoslangan bog‘lash qilinmaydi.
5. Bir nechta ehtimoliy egasi topilsa, yozuv hech kimga berilmaydi va ziddiyatga chiqariladi.

### 3.4. Egasi aniqlanmagan mahsulot va xizmat

Egasi aniq bog‘lanmagan mahsulot yoki xizmat:

- yangi bazaga ko‘chiriladi;
- katalogda ko‘rinadi;
- `owner_state=unlinked` holatini oladi;
- “Egasi hali akkauntini bog‘lamagan” yozuvi bilan ko‘rsatiladi;
- buyurtma va chat tugmalari ishlamaydi;
- soxta foydalanuvchi yoki soxta biznes profili yaratilmaydi;
- boshqa odamga tasodifan biriktirilmaydi.

Bu maxsus istisno faqat egasi bog‘lanmagani uchun ishlaydi. Nomi, turi yoki boshqa xavfsiz public ko‘rsatish uchun majburiy ma’lumoti yetishmasa, yozuv `review_required` holatida yashiriladi.

### 3.5. Reklamaning egasi

Reklama biznes profilsiz mustaqil qolishi mumkin. Masalan, “Turon Savdo” banneridan avtomatik biznes profili yaratilmaydi.

Reklamada:

- mavjud foydalanuvchi egasi topilsa ichki owner ID saqlanadi;
- mavjud biznes egasi topilsa biznes owner ID saqlanadi;
- biznes profili yo‘q bo‘lsa banner nomi va mazmuni reklama snapshoti sifatida saqlanadi;
- profilga havola faqat haqiqiy bog‘langan profil bo‘lsa chiqadi;
- bog‘lanmagan reklama ham faol jadvali va hudud shartlariga mos bo‘lsa ko‘rsatilishi mumkin.

### 3.6. Majburiy ma’lumoti yetishmagan yozuv

Yangi tizim uchun zarur maydon yetishmasa:

- yozuv baribir ko‘chiriladi;
- `review_required` holatini oladi;
- katalog va public qidiruvdan yashiriladi;
- qaysi maydon yetishmagani migratsiya muammolari hisobotida yoziladi;
- egasi yoki administrator ma’lumotni to‘ldirgach `ready` holatiga o‘tadi.

Tizim avtomatik yolg‘on narx, hudud, kategoriya yoki ega yaratmaydi.

### 3.7. Takrorlangan identifikatorlar

Bir xil telefon raqami yoki Telegram ID bir nechta akkauntda uchrasa:

- akkauntlar avtomatik birlashtirilmaydi;
- hech qanday profil yoki kontent o‘chirilmaydi;
- barcha manba yozuvlar audit nusxasida saqlanadi;
- ziddiyat migratsiya hisobotida alohida ko‘rsatiladi;
- administrator production ochilishidan oldin to‘g‘ri akkauntni aniqlaydi;
- ziddiyat hal qilinmaguncha ushbu identifikator bo‘yicha avtomatik owner mapping yakunlanmaydi.

Hal qilinmagan identity ziddiyati production ochilish gate’ini bloklaydi.

## 4. Yangi PostgreSQL modeli

### 4.1. Katalog

`catalog_groups`:

- `id`;
- `business_account_id` — nullable FK;
- `owner_name_snapshot`;
- `name`;
- `kind` — `product | service`;
- `status`;
- `review_state`;
- `created_at`;
- `updated_at`.

`catalog_items`:

- `id`;
- `business_account_id` — nullable FK;
- `catalog_group_id` — nullable FK;
- `owner_name_snapshot`;
- `name`;
- `price_text`;
- `note`;
- `kind` — `product | service`;
- `queue_enabled`;
- `image_object_key`;
- `status`;
- `owner_state` — `linked | unlinked`;
- `review_state` — `ready | review_required`;
- `created_at`;
- `updated_at`.

`price_text` eski qiymatni aynan saqlaydi. Keyinchalik sonli narx kerak bo‘lsa, u alohida validatsiyalangan maydon sifatida qo‘shiladi; Phase 3C eski matnni taxminiy konvertatsiya qilmaydi.

### 4.2. E’lonlar

`listings`:

- `id`;
- `owner_user_account_id` — nullable FK;
- `owner_business_account_id` — nullable FK;
- `category`;
- `title`;
- `price_text`;
- `description`;
- `address`;
- `latitude`;
- `longitude`;
- `visibility`;
- `status`;
- `review_state`;
- `created_at`;
- `updated_at`.

`listing_media`:

- `id`;
- `listing_id`;
- `media_type` — `photo | video`;
- `object_key`;
- `position`;
- `migration_state`.

Aniq koordinatalar bazada saqlanishi mumkin, lekin public API faqat allowlist qilingan xavfsiz joylashuv ma’lumotini qaytaradi. Ichki R2 object key public javobga chiqmaydi.

### 4.3. Reklamalar

`advertisements`:

- `id`;
- `owner_user_account_id` — nullable FK;
- `owner_business_account_id` — nullable FK;
- `actor_type`;
- `title`;
- `caption`;
- `desktop_image_object_key`;
- `mobile_image_object_key`;
- `crop_x`;
- `crop_y`;
- `crop_zoom`;
- `daily_all_day`;
- `daily_start`;
- `daily_end`;
- `targets_json`;
- `start_at`;
- `end_at`;
- `duration_days`;
- `price`;
- `district_count`;
- `hours_per_day`;
- `district_hour_rate`;
- `billable_district_hours`;
- `price_code`;
- `status`;
- `views`;
- `clicks`;
- `review_state`;
- `created_at`;
- `updated_at`.

Eski narx snapshoti qayta hisoblanmaydi. U tarixiy qiymat sifatida aynan ko‘chiriladi.

### 4.4. Migratsiya nazorat jadvallari

`migration_runs`:

- migratsiya run identifikatori;
- manba SQLite SHA-256 fingerprinti;
- media manifest fingerprinti;
- environment — faqat `staging | production`;
- boshlangan va tugagan vaqt;
- joriy stage;
- umumiy holat;
- stage counterlari;
- xatolar soni.

`legacy_id_map`:

- entity turi;
- eski ID;
- yangi ID;
- source row hash;
- mapping holati;
- review sababi;
- `UNIQUE(entity_type, legacy_id)`.

`migration_issues`:

- run ID;
- entity turi;
- eski ID;
- xavfsiz issue code;
- maxfiy ma’lumotsiz tafsilot;
- resolved holati va vaqti.

`media_migration`:

- entity turi va eski ID;
- source reference fingerprinti;
- destination object key;
- SHA-256 checksum;
- MIME turi;
- fayl hajmi;
- `pending | copied | missing | invalid | failed` holati;
- urinishlar soni;
- maxfiy ma’lumotsiz oxirgi error code.

Parol, Telegram kodi, `pass_plain`, session tokeni, R2 secret yoki to‘liq shaxsiy ma’lumot migratsiya logiga yozilmaydi.

## 5. Migratsiya dasturi

Migratsiya bitta katta tranzaksiya emas. U bosqichma-bosqich, idempotent va qayta ishga tushiriladigan CLI dastur bo‘ladi.

Bosqichlar:

1. `snapshot` — SQLite backup, media manifest va fingerprint.
2. `inventory` — manba jadvallar soni va status kesimlari.
3. `accounts` — mavjud PostgreSQL akkauntlarini reconcile qilish, yetishmaganlarini xavfsiz import qilish.
4. `businesses` — biznes profillarini reconcile qilish va owner mapping.
5. `catalog` — guruhlar, mahsulotlar va xizmatlar.
6. `listings` — e’lonlar va e’lon media metadata.
7. `advertisements` — reklama metadata, schedule, target va statistika.
8. `media` — rasm/video baytlarini R2 ga ko‘chirish.
9. `verify` — son, bog‘lanish, checksum, status, qidiruv va xavfsizlik gate’lari.

Har bir stage:

- alohida ishga tushiriladi;
- oldingi muvaffaqiyatli stage holatini o‘qiydi;
- `legacy_id_map` orqali mavjud target yozuvni topadi;
- source row hash o‘zgarmagan bo‘lsa takroran yozmaydi;
- xato chiqqan yozuvni qayd etib, stage siyosatiga ko‘ra davom etadi yoki gate’ni to‘xtatadi;
- qayta ishlatilganda takroriy target yozuv yaratmaydi.

Bir xil immutable snapshotga migratsiya ikkinchi marta ishlatilganda yangi target yozuvlar soni `0` bo‘lishi shart.

## 6. Xavfsiz manba nusxasi

Live SQLite fayl migratsiya manbasi sifatida bevosita ishlatilmaydi.

Jarayon:

1. Monolitning mavjud backup mexanizmi yoki SQLite Backup API orqali consistent nusxa olinadi.
2. Nusxaga `PRAGMA quick_check` va `PRAGMA integrity_check` bajariladi.
3. SHA-256 fingerprint hisoblanadi.
4. Media papka va Telegram media reference’lari uchun manifest yaratiladi.
5. Migrator SQLite nusxani read-only immutable rejimda ochadi.
6. Manba fingerprinti run tugaguncha o‘zgarmasligi tekshiriladi.
7. Eski baza va media hech qachon o‘chirilmaydi.

Backup yoki integrity tekshiruvi muvaffaqiyatsiz bo‘lsa migratsiya boshlanmaydi.

## 7. Akkaunt va parollar

### 7.1. Foydalanuvchi va biznes akkauntlari

- Mavjud PostgreSQL akkaunti aniq topilsa qayta yaratilmaydi.
- Mavjud mapping topilmasa va ziddiyat bo‘lmasa eski akkaunt import qilinadi.
- Mos eski parol xeshi formatini yangi auth tekshira olsa xesh aynan saqlanadi.
- Mos kelmagan xeshli foydalanuvchi SMS yoki Telegram orqali yangi parol o‘rnatadi.
- Eski sessionlar ko‘chirilmaydi.
- Yangi tizim ochilganda hamma bir marta qayta kiradi.
- Hech kim qayta ro‘yxatdan o‘tmaydi.

### 7.2. Xodim parollari bo‘yicha muzlatilgan qoida

Xodimlar va xodim kabineti Phase 3C public kontent scope’iga kirmaydi. Ular keyingi xodimlar modulida ko‘chiriladi. Ammo tasdiqlangan xavfsizlik qoidasi hozirdan majburiy:

- `staff.pass_plain` faqat migratsiya jarayonida xotirada o‘qiladi;
- u Argon2id xeshga aylantiriladi;
- ochiq qiymat PostgreSQL, log, report yoki artifactga yozilmaydi;
- yangi sxemada `pass_plain` ustuni bo‘lmaydi;
- bo‘sh yoki buzilgan parolli xodim kira olmaydi;
- yangi parolni biznes egasi belgilaydi;
- vaqtinchalik ochiq parol yaratilmaydi.

## 8. Media ko‘chirish

Media migrator manbaga qarab adapter ishlatadi:

- lokal monolit upload fayli;
- Telegram `file_id`;
- eski absolute yoki relative media reference.

Har fayl uchun:

1. Manba reference validatsiya qilinadi.
2. Fayl oqim tarzida o‘qiladi; to‘liq fayl logga yoki bazaga yozilmaydi.
3. MIME turi fayl mazmunidan tekshiriladi.
4. SHA-256 checksum hisoblanadi.
5. Yangi R2 kalit migratsiya namespace’ida yaratiladi.
6. Fayl R2 ga yoziladi.
7. R2 metadata, hajm va checksum qayta tekshiriladi.
8. Target yozuvga faqat object key saqlanadi.

Public API object key’ni qaytarmaydi; faqat backend yaratgan public-safe yoki vaqtinchalik URL beradi.

Fayl topilmasa yoki buzilgan bo‘lsa:

- asosiy yozuv yo‘qolmaydi;
- `media_migration` holati `missing` yoki `invalid` bo‘ladi;
- frontend standart rasm yoki video belgisini chiqaradi;
- muammo hisobotga yoziladi;
- media keyinchalik tiklanganda shu mapping qayta ishlanib placeholder almashtiriladi.

Eski media production to‘liq tasdiqlanmaguncha va alohida retention qarori berilmaguncha o‘chirilmaydi.

## 9. Public API va frontend

### 9.1. Public API

Joriy `GET /api/v1/public/search` endpointi backward-compatible tarzda kengaytiriladi:

- mavjud `all | user | business` qiymatlari o‘zgarmaydi;
- `product | service` result type’lari qo‘shiladi;
- `all` profillar, mahsulotlar va xizmatlarni qamrab oladi;
- profil kartalarining mavjud maydonlari va public ID’lari o‘zgarmaydi;
- mahsulot/xizmat natijasi alohida typed card bo‘lib, `kind`, opaque `public_id`, nom, `price_text`, qisqa izoh, owner holati, capability va media URL qaytaradi.

Qo‘shimcha endpointlar:

- `GET /api/v1/public/catalog/items`;
- `GET /api/v1/public/catalog/items/{public_id}`;
- `GET /api/v1/public/advertisements`.

Katalog endpointlari quyidagilarni ta’minlaydi:

- `product | service` filtri;
- yo‘nalish va faoliyat turi filtri;
- region/tuman/mahalla filtri;
- qidiruv matni;
- pagination;
- barqaror ordering;
- `owner_state`;
- buyurtma/chat mavjudligini ifodalovchi capability maydonlari;
- backend yaratgan media URL.

Public natijaga:

- password hash;
- telefon;
- Telegram ID;
- session ma’lumoti;
- to‘lov ma’lumoti;
- STIR;
- aniq private koordinata;
- R2 object key;
- legacy ID

kirmaydi.

`review_required`, bloklangan, o‘chirilgan yoki nofaol yozuv public natijaga kirmaydi. `owner_state=unlinked` bo‘lgan, boshqa majburiy maydonlari to‘liq mahsulot/xizmat public natijaga kirishi mumkin, ammo action capability’lari `false` bo‘ladi.

`GET /api/v1/public/advertisements`:

- joriy vaqt;
- kunlik vaqt oralig‘i;
- start/end;
- status;
- hudud targeti;
- placement

bo‘yicha mos bannerlarni qaytaradi.

E’lon endpointlari ichki model va testlarda tayyor bo‘lishi mumkin, ammo `listings_enabled=false` bo‘lganda public so‘rov `404 feature_not_available` qaytaradi. Frontend bu route’ni chaqirmaydi va `E’lonlar` navigatsiyasini ko‘rsatmaydi.

### 9.2. Yangi frontend

Yangi React frontend:

- katalogda mahsulot va xizmat kartalarini ko‘rsatadi;
- qidiruvda profil, mahsulot va xizmat turini aniq ajratadi;
- bog‘langan owner bo‘lsa profilga o‘tadi;
- owner bog‘lanmagan bo‘lsa ogohlantirish chiqaradi;
- owner bog‘lanmagan yozuvda buyurtma va chatni disabled qiladi;
- media topilmasa standart tasvir ko‘rsatadi;
- reklama bannerining desktop va mobil variantini mos ravishda ishlatadi;
- telefon, planshet va kompyuterda responsive ishlaydi;
- `E’lonlar` navigatsiyasini feature flag o‘chiq paytda ko‘rsatmaydi.

Frontend eski SQLite endpointiga to‘g‘ridan-to‘g‘ri murojaat qilmaydi.

## 10. Staging tekshiruvlari

Production o‘tishidan oldin staging’da quyidagi gate’lar to‘liq o‘tishi shart.

### 10.1. Ma’lumot gate’i

- Har bir source jadvalning umumiy soni yoziladi.
- Faol, bloklangan, o‘chirilgan va muddati tugagan statuslar alohida solishtiriladi.
- Har bir source ID uchun bitta `legacy_id_map` bo‘lishi tekshiriladi.
- Bir target yozuvga tasodifan bir nechta source yozuv bog‘lanmaganligi tekshiriladi.
- Item → business, listing → owner va media → listing foreign keylari tekshiriladi.
- Mahsulot va xizmat soni `kind` kesimida teng bo‘lishi kerak.
- E’lon va reklama sonlari bir-biridan mustaqil solishtiriladi.
- Ikkinchi idempotency run’da yangi yozuv yaratilmasligi tekshiriladi.

### 10.2. Media gate’i

- `copied`, `missing`, `invalid`, `failed` sonlari hisobotda bo‘ladi.
- `copied` fayllar uchun R2 object mavjudligi tekshiriladi.
- Fayl hajmi va checksum mosligi tekshiriladi.
- Desktop va mobil reklama bannerlari alohida tekshiriladi.
- Missing media yozuvlari placeholder bilan ochilishi tekshiriladi.
- Hech qanday eski fayl o‘chirilmaganligi tasdiqlanadi.
- `failed` media soni `0` bo‘lishi shart.
- `copied + missing + invalid` soni source media reference’lar umumiy soniga teng bo‘lishi shart.
- `missing` va `invalid` holatlari production’ni o‘z-o‘zidan bloklamaydi; ularning har biri reportda bo‘lishi va placeholder bilan xavfsiz ochilishi shart.

### 10.3. Xavfsizlik gate’i

- `pass_plain` target bazada, logda va reportda uchramaydi.
- Auth sessionlar ko‘chirilmaydi.
- Public API maxfiy maydonlarni qaytarmaydi.
- R2 secret va object key frontendga chiqmaydi.
- Identity ziddiyatlar hal qilingan bo‘ladi.
- Migrator production URL bilan faqat explicit production tasdig‘i va maintenance gate’dan keyin ishlaydi.

### 10.4. Funksional gate

- Mahsulot qidiruvi.
- Xizmat qidiruvi.
- Katalog filtrlari.
- Hudud bo‘yicha ko‘rsatish.
- Bog‘langan profilga o‘tish.
- Bog‘lanmagan owner ogohlantirishi.
- Bog‘lanmagan owner uchun buyurtma/chat bloklanishi.
- Reklama jadvali va hudud targeting.
- E’lonlar funksiyasi yopiq qolishi.
- Telefon, planshet va desktop ko‘rinishi.
- Redis ishlamasa PostgreSQL fallback.

### 10.5. Regressiya gate

- Barcha backend testlari.
- Barcha frontend testlari.
- Frontend production build.
- Phase 1, Phase 2 va Phase 3 verifierlari.
- Legacy `static/index.html` BUILD v1656 va line-count contract.
- Ishlab turgan `koprik.uz` staging tasdiqlanmaguncha o‘zgarmaganligi.

## 11. Production o‘tish

Production migratsiya faqat staging hisobotlari tasdiqlangach bajariladi.

Jarayon:

1. Oldindan maintenance oynasi belgilanadi.
2. Sayt o‘rniga “Texnik ishlar olib borilmoqda” sahifasi chiqariladi.
3. Monolitga barcha yozish amallari to‘xtatiladi.
4. Oxirgi consistent SQLite va media manifest snapshot olinadi.
5. Snapshot integrity va fingerprint tekshiriladi.
6. Production migrator barcha stage’larni bajaradi.
7. Verification gate ishlaydi.
8. Identity ziddiyatlari `0` ekanligi tekshiriladi.
9. Yangi backend va frontend smoke testdan o‘tadi.
10. Yangi tizim ochiladi.
11. Foydalanuvchilar bir marta qayta kiradi.

Maintenance vaqtida hech kim ma’lumot qo‘sha, tahrirlay yoki buyurtma bera olmaydi.

## 12. Rollback

Quyidagi holatlardan bittasi yuz bersa yangi tizim ochilmaydi yoki yana yopiladi:

- source/target sonlari mos emas;
- foreign key yoki owner mapping buzilgan;
- hal qilinmagan identity ziddiyati bor;
- public maxfiylik testi yiqilgan;
- operatsion media `failed` soni `0` dan katta yoki media reconciliation sonlari mos emas;
- yangi API yoki frontend smoke testdan o‘tmagan.

Rollback:

1. Yangi frontend routing o‘chiriladi.
2. Eski monolit qayta aktiv qilinadi.
3. “Texnik ishlar” sahifasi olib tashlanadi.
4. Monolit yozish amallari qayta ochiladi.
5. Eski SQLite va media o‘zgartirilmaydi.
6. Qisman import qilingan yangi yozuvlar `migration_run_id` orqali izolyatsiyada qoladi va public feature flag orqali ko‘rsatilmaydi.
7. Xato tuzatilgach aynan o‘sha snapshot yoki yangi final snapshot bilan idempotent run qayta bajariladi.

Rollback ma’lumotni o‘chirishga tayanmaydi.

## 13. Kuzatuv va hisobot

Har run yakunida maxfiy ma’lumotsiz JSON va Markdown hisobot yaratiladi:

- source fingerprint;
- stage holatlari;
- entity bo‘yicha source/target sonlari;
- yaratilgan, qayta ishlatilgan, yangilangan va quarantine qilingan yozuvlar;
- owner mapping natijalari;
- identity conflict soni;
- review-required soni;
- media copied/missing/invalid/failed sonlari;
- idempotency natijasi;
- barcha gate natijalari;
- run boshlandi/tugadi va davomiyligi.

Hisobotda ism, telefon, login, Telegram ID, parol yoki to‘liq media URL bo‘lmaydi. Muammo yozuvlari entity turi, eski ID va xavfsiz issue code orqali aniqlanadi.

## 14. Muvaffaqiyat mezonlari

Phase 3C tayyor hisoblanadi, agar:

1. Immutable backup va media manifest yaratilgan bo‘lsa.
2. Akkaunt va biznes mappingi deterministik bo‘lsa.
3. Barcha mahsulot, xizmat, e’lon va reklama statusi bilan ko‘chgan bo‘lsa.
4. Barcha topilgan media R2 ga checksum bilan ko‘chgan bo‘lsa.
5. Missing media yozuvlari placeholder bilan ishlasa.
6. Egasi bog‘lanmagan mahsulot/xizmat ko‘rinsa, ammo order/chat ishlamasa.
7. Majburiy ma’lumoti yetishmagan yozuv yashirin `review_required` holatida bo‘lsa.
8. E’lonlar ma’lumoti saqlangan, ammo funksiyasi yopiq qolsa.
9. Reklama va e’lon modeli aralashmasa.
10. Takroriy run duplicate yaratmasa.
11. Staging data, media, security, functional va regression gate’lari o‘tsa.
12. Production rollback sinovi hujjatlashtirilgan va tekshirilgan bo‘lsa.
13. Legacy BUILD v1656 production o‘tishigacha o‘zgarmagan bo‘lsa.

## 15. Phase 3C ga kirmaydigan ishlar

Quyidagilar bu bosqichda ko‘chirilmaydi yoki faollashtirilmaydi:

- buyurtmalar va to‘lovlarning yangi oqimi;
- umumiy chat va xabarnomalar;
- istoriyalar va obunalar;
- taxi va yetkazib berish;
- navbat va bron qilish;
- ombor, kassa va qarzlar;
- xodimlar kabineti va xodim ma’lumotlarining to‘liq migratsiyasi;
- hujjatlar va tizimlashtirish modullari;
- admin/moderatsiyaning to‘liq yangi interfeysi;
- `E’lonlar` funksiyasini foydalanuvchiga ochish;
- eski monolit yoki mediani o‘chirish.

Bu modullar Phase 3C tayyor va production’da barqaror ishlagach alohida spec va rollout bilan ko‘chiriladi.

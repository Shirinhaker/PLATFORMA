# Ko‘prik v1654 — onlinelashtirish MVP release

## Release maqsadi

Bu build loyihani birdan to‘liq tizimlashtirish uchun emas, birinchi
**onlinelashtirish bosqichi** uchun tayyorlaydi. Yopiq funksiyalar kod va
ma’lumotlari o‘chirilmagan; barqaror server feature guard orqali
foydalanuvchiga ko‘rsatilmaydi.

## Faol funksiyalar

- oddiy va biznes profillar;
- birinchi hududni tanlash;
- guest va login qilingan foydalanuvchi qidiruvi;
- xarita va qidiruv markerlari;
- oddiy/biznes follow’larining alohida yuritilishi;
- bosh sahifada follow qilingan pullik profillar stripi, historiasiz;
- mahsulot va xizmat yaratish/ko‘rish;
- reklama joylash va moderatsiyadan keyin ko‘rsatish;
- Plus/Pro obuna sotib olish;
- qo‘lda kvitansiya asosidagi to‘lov;
- Orders va Service Orders;
- faqat order ichidagi chat;
- sharhlar va bildirishnomalar;
- alohida `admin.koprik.uz` admin paneli;
- to‘lov, akkaunt, kontent, shikoyat va append-only audit boshqaruvi.

## MVPda yopiq funksiyalar

| Funksiya | Holat | Guard |
|---|---:|---|
| E’lon yaratish va e’lon bo‘limi | yopiq | `MVP_LISTINGS_ENABLED=0` |
| Istoriya joylash va feed | yopiq | `MVP_STORIES_ENABLED=0` |
| Umumiy suhbatlar | yopiq | `MVP_CHAT_ENABLED=0` |
| Kassa, ombor, qarz, xodim va boshqa tizimlashtirish | yopiq | `MVP_SYSTEMIZATION_ENABLED=0` |
| Order ichidagi chat | faol | umumiy chat guardidan mustaqil |
| Follow qilingan profillar stripi | faol | istoriya API’siga bog‘liq emas |

## Migratsiya va ma’lumot xavfsizligi

- `migration_check.py` migratsiyadan **oldin** SQLite online backup yaratadi.
- Backup uchun SHA-256, `integrity_check` va `0600` manifest yaratiladi.
- Migratsiya idempotent; `schema_migrations`da `v1654` bir marta yoziladi.
- Eski foydalanuvchi yozuvlari saqlanadi.
- Migratsiyadan keyin target DB integrity yana tekshiriladi.
- Rollback yangi jadvallarni o‘chirmaydi.

## Production env nomlari

Sir qiymatlar bu hujjatda ataylab berilmagan:

- `APP_ENV`, `BASE_URL`, `PRIMARY_DOMAIN`, `ALLOWED_HOSTS`;
- `BOT_TOKEN`, `BOT_USERNAME`, `WEBHOOK_SECRET`, `MOBILE_OTP_SECRET`;
- `ADMIN_TG_IDS`, `ADMIN_AUDIT_IP_SECRET`;
- `PAYMENT_TOKEN_SECRET`, `PAYMENT_RECEIPT_DIR`;
- `PERSISTENT_ROOT`, `DB_PATH`, `UPLOAD_DIR`, `BACKUP_DIR`;
- `MVP_LISTINGS_ENABLED`, `MVP_STORIES_ENABLED`, `MVP_CHAT_ENABLED`,
  `MVP_SYSTEMIZATION_ENABLED`;
- `TEST_MODE`, `PROJECT_ACCESS_RESTRICTED`;
- `SMS_PROVIDER`, `PAYMENT_PROVIDER`, `OBJECT_STORAGE_PROVIDER`.

To‘liq namuna: `.env.production.example`.

## Readiness kontrakti

`/readyz` HTTP 200 faqat quyidagilarda qaytaradi:

- DB ulanishi ishlaydi;
- 60 soniya cache’li `PRAGMA quick_check = ok`;
- upload katalogi yoziladigan;
- payment receipt katalogi private va yoziladigan;
- admin panelning uchta asseti mavjud;
- to‘rtta MVP feature flag o‘chiq.

Response hech qanday absolute server path yoki sirni oshkor qilmaydi.

## Test dalillari

- Python regressiya: **358 test**, barchasi `OK`.
- Parallel to‘lov: **20 ta bir vaqtdagi approve** ichidan 1 ta success,
  19 ta conflict; bitta approved event.
- Admin UI source smoke: `OK`.
- Reklama upload/remove source smoke: `OK`.
- Subscription UI source contract: `OK`.
- District offers source contract: `OK`.
- `admin/app.js` syntax check: `OK`.
- Load probe CLI help: `OK`.

Live staging load probe bu lokal handoffda bajarilmadi, chunki staging URL va
auth token berilmagan. Production release’dan oldin read-only probe majburiy:
server error `0`, p95 `< 1000 ms`.

## Asosiy o‘zgargan fayllar

Backend:

- `feature_flags.py`, `admin_auth.py`, `admin_audit.py`, `moderation.py`;
- `payments.py`, `payment_api.py`, `receipt_storage.py`;
- `admin_queries.py`, `admin_api.py`;
- `backup_database.py`, `migration_check.py`;
- `runtime_config.py`, `database.py`, `main.py`, `api.py`,
  `district_offers.py`.

Frontend:

- `static/index.html`;
- `admin/index.html`, `admin/styles.css`, `admin/app.js`.

Deploy va QA:

- `.env.production.example`, `railpack.json`;
- `scripts/mvp_load_probe.py`;
- `tests/test_*_v1651.py` – `tests/test_*_v1654.py`;
- `tests/admin-ui-smoke.cjs`, `tests/ad-upload-ui-smoke.cjs`;
- `docs/deploy-admin-koprik.md`.

## Frontend line count

- `static/index.html`: 13 900
- `admin/index.html`: 148
- `admin/styles.css`: 136
- `admin/app.js`: 171
- jami: 14 355

## Ma’lum MVP chegarasi

SQLite faqat **bitta Railway replica + persistent volume** bilan qo‘llanadi.
Staging read probe p95 1000 ms dan oshsa, server error yoki
`database is locked` paydo bo‘lsa release to‘xtatiladi va PostgreSQLga ko‘chish
alohida blocker bo‘ladi.

## Rollback

`docs/deploy-admin-koprik.md`dagi tartib bajariladi: old deployment, backupni
alohida pathda tekshirish, joriy DBni timestamp bilan saqlash, explicit restore,
`/readyz`. Yangi jadvallar qo‘lda drop qilinmaydi.

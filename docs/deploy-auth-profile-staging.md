# Koprik Phase 2 staging deploy va rollback

Bu qo‘llanma faqat yangi `api-staging`, `worker-staging` va
`frontend-staging` servislariga tegishli. Mavjud `web` servisi va
`koprik.uz` production domeniga hech qachon o‘zgartirish kiritilmaydi.

## 1. Railway o‘zgaruvchilari

Haqiqiy maxfiy qiymatlarni faqat Railway Variables ichida saqlang. Ularni
GitHub, log, skrinshot yoki `.env` fayliga yozmang.

### api-staging

```env
KOPRIK_SERVICE_NAME=koprik-api-staging
KOPRIK_ENVIRONMENT=staging
KOPRIK_DATABASE_URL=${{Postgres.DATABASE_URL transformed to asyncpg}}
KOPRIK_REDIS_URL=${{Redis.REDIS_URL}}
KOPRIK_CORS_ORIGINS=https://frontend-staging-production-6c41.up.railway.app
KOPRIK_R2_ENDPOINT_URL=${{"koprik media".ENDPOINT}}
KOPRIK_R2_BUCKET=${{"koprik media".BUCKET}}
KOPRIK_R2_ACCESS_KEY_ID=${{"koprik media".ACCESS_KEY_ID}}
KOPRIK_R2_SECRET_ACCESS_KEY=${{"koprik media".SECRET_ACCESS_KEY}}
KOPRIK_TELEGRAM_BOT_TOKEN=Railway Variables ichidagi yashirin bot tokeni
KOPRIK_TELEGRAM_BOT_USERNAME=Koprik staging botining usernamesi
KOPRIK_TELEGRAM_WEBHOOK_SECRET=openssl rand -hex 32 natijasi
KOPRIK_OTP_SECRET=alohida openssl rand -hex 32 natijasi
KOPRIK_CSRF_SECRET=alohida openssl rand -hex 32 natijasi
KOPRIK_OUTBOX_ENCRYPTION_KEY=Fernet.generate_key natijasi
KOPRIK_AUTH_COOKIE_NAME=koprik_session
KOPRIK_SESSION_TTL_SECONDS=2592000
KOPRIK_SESSION_CACHE_TTL_SECONDS=30
KOPRIK_PROFILE_SUMMARY_CACHE_TTL_SECONDS=30
```

Fernet kalitini lokal terminalda yarating:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`KOPRIK_DATABASE_URL` qiymati `postgresql+asyncpg://` bilan boshlanishi
kerak. Railway reference oddiy `postgresql://` qaytarsa, faqat protokol
qismini `postgresql+asyncpg://` ga almashtiring.

`KOPRIK_SESSION_CACHE_TTL_SECONDS` majburiy emas; koddagi standart qiymat
`30`. API sessiya tokenining o‘zini Redisga yozmaydi: SHA-256 kalit va CSRF
qiymatisiz qisqa muddatli akkaunt identifikatori saqlanadi. Logout PostgreSQL
sessiyasini bekor qiladi va Redis keshini atomik ravishda o‘chiradi.

`KOPRIK_PROFILE_SUMMARY_CACHE_TTL_SECONDS` majburiy emas; standart `30`.
`/api/v1/me` javobining ixcham xulosasi
`profile:me:v1:{account_type}:{account_id}` kalitida saqlanadi. Profil,
avatar yoki logo muvaffaqiyatli saqlangach tegishli kalit o‘chiriladi.
Redis ishlamasa API PostgreSQL fallback orqali ishlashda davom etadi.

### worker-staging

`worker-staging` uchun `api-staging` dagi quyidagi qiymatlar aynan bir xil
Railway reference yoki secretga bog‘lanadi:

```env
KOPRIK_SERVICE_NAME=koprik-worker-staging
KOPRIK_ENVIRONMENT=staging
KOPRIK_DATABASE_URL=api-staging bilan bir xil
KOPRIK_REDIS_URL=api-staging bilan bir xil
KOPRIK_TELEGRAM_BOT_TOKEN=api-staging bilan bir xil
KOPRIK_TELEGRAM_BOT_USERNAME=api-staging bilan bir xil
KOPRIK_TELEGRAM_WEBHOOK_SECRET=api-staging bilan bir xil
KOPRIK_OTP_SECRET=api-staging bilan bir xil
KOPRIK_CSRF_SECRET=api-staging bilan bir xil
KOPRIK_OUTBOX_ENCRYPTION_KEY=api-staging bilan bir xil
KOPRIK_R2_ENDPOINT_URL=${{"koprik media".ENDPOINT}}
KOPRIK_R2_BUCKET=${{"koprik media".BUCKET}}
KOPRIK_R2_ACCESS_KEY_ID=${{"koprik media".ACCESS_KEY_ID}}
KOPRIK_R2_SECRET_ACCESS_KEY=${{"koprik media".SECRET_ACCESS_KEY}}
```

Start command:

```bash
python -m app.outbox.worker
```

Worker public domain va healthcheck talab qilmaydi.

### frontend-staging

```env
VITE_API_BASE_URL=https://platforma-production-f753.up.railway.app
```

Bu qiymat build vaqtida frontendga joylanadi. API domeni o‘zgarsa frontend
qayta build qilinadi.

## 2. Deploydan oldingi gate

1. Railway Postgres backup/snapshot yarating va tiklash nuqtasining vaqtini
   yozib oling.
2. GitHub CI yashil ekanini tasdiqlang.
3. Lokal yoki CI muhitida `python scripts/verify_phase2.py` ni o‘tkazing.
4. `api-staging`, `worker-staging` va `frontend-staging` avvalgi muvaffaqiyatli
   deployment IDlarini rollback uchun yozib oling.
5. `web` va `koprik.uz` ga tegilmaganini qayta tekshiring.

## 3. Ketma-ket deploy

1. `backend` root directory bilan bir martalik migration ishga tushiring:

   ```bash
   python -m alembic upgrade head
   ```

2. `api-staging` ni deploy qiling. Start command:

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

3. `/healthz`, `/readyz` va `/api/v1/build` 200 qaytarishini tekshiring.
4. `worker-staging` ni deploy qiling va logda doimiy restart yoki xato
   yo‘qligini tekshiring.
5. Telegram webhook ni `api-staging` callback manziliga, secret token bilan
   o‘rnating. Bot token yoki webhook secretni terminal historyga yozmang.
   Quyidagi buyruqning o‘zida qiymatlar emas, faqat oldindan xavfsiz
   environmentga olingan o‘zgaruvchi nomlari qoladi:

   ```bash
   curl --fail --silent --show-error \
     "https://api.telegram.org/bot${KOPRIK_TELEGRAM_BOT_TOKEN}/setWebhook" \
     --data-urlencode \
     "url=https://platforma-production-f753.up.railway.app/api/v1/auth/telegram/webhook" \
     --data-urlencode \
     "secret_token=${KOPRIK_TELEGRAM_WEBHOOK_SECRET}"
   ```

   Telegram javobidagi `ok: true` ni tekshiring.
6. `frontend-staging` ni deploy qiling va sahifada aynan `Koprik` brendi
   ko‘rinishini tekshiring.

## 4. Funksional staging gate

Bir Telegram akkaunti bilan:

1. oddiy user akkauntini yarating va qayta login qiling;
2. alohida business akkauntini yarating va qayta login qiling;
3. login rol tanlashni so‘ramasligini tekshiring;
4. user faqat oddiy kabinetni, business faqat biznes kabinetni ko‘rishini
   tekshiring;
5. user profil maydonlarini saqlang va avatar yuklang;
6. business profil maydonlarini saqlang va logotip yuklang;
7. sahifani yangilab session, profil va media R2 dan qayta yuklanishini
   tekshiring;
8. logout sessionni bekor qilishini tekshiring.

## 5. Xavfsiz yuklama o‘lchovi

### Windows — tavsiya etilgan usul

PowerShell oynasini loyiha papkasida ochib quyidagi buyruqni bajaring:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\koprik-phase2-load.ps1
```

Skript loginni so‘ragach, Telegram bot yuborgan parolning faqat qiymatini
clipboard’ga nusxalang va PowerShell ko‘rsatmasida Enter bosing. Skript
clipboard’ni darhol tozalaydi; parol ekranga, faylga va buyruqlar tarixiga
chiqarilmaydi. Telegram kodi hamda sessiya diska yozilmaydi va ekranga
chiqarilmaydi. Sinov faqat kabinet ma’lumotini o‘qiydigan
`GET /api/v1/me` so‘rovlarini 100 → 500 → 1000 parallel bosqichlarda
yuboradi va oxirida test sessiyasidan chiqadi.

Runner Windows ulanish limitini eng katta bosqichga moslab avtomatik
`1000` ga o‘rnatadi. `phase2-load-result.json` ichidagi
`max_connections_per_server` ham `1000` bo‘lishi kerak. Har bosqich
uchun `duration_ms`, `status_counts` va `error_types` yoziladi. Bu
diagnostika gate o‘tmasa muammoni klient transporti, HTTP statusi yoki
API javob vaqtiga ajratishga yordam beradi.

Maxfiy bo‘lmagan natija shu papkada `phase2-load-result.json` nomi bilan
yaratiladi. Gate o‘tishi uchun fayldagi `gate.passed` qiymati `true`,
`error_rate` 0.01 dan past va `p95_ms` 500 dan past bo‘lishi kerak.
Hisobot login, parol, Telegram kodi, cookie, session token yoki CSRF
qiymatini saqlamaydi.

### p95 sekin bo‘lsa — qatlamlar bo‘yicha diagnostika

Asosiy yuklama sinovida xatolar 1% dan kam, lekin p95 500 ms dan yuqori
bo‘lsa, Railway sozlamalarini darhol o‘zgartirmang. Avval Windows
PowerShell’da quyidagi skriptni ishga tushiring:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\koprik-phase2-latency-diagnostic.ps1
```

Skript bitta autentifikatsiyalangan `HttpClient` bilan har bir bosqichni
avval bir marta qizdiradi, keyin alohida-alohida 1000 parallel `GET`
so‘rovi yuboradi:

- `healthz_cold` — API va tarmoq, yangi HTTPS ulanishlari bilan;
- `healthz_reused` — ayni `/healthz`, ochilgan ulanishlarni qayta ishlatib;
- `/api/v1/auth/session` — sessiya autentifikatsiyasi va uning DB so‘rovi;
- `/api/v1/me` — sessiya autentifikatsiyasi hamda profil DB so‘rovi.

Natija `phase2-latency-diagnostic-v2-result.json` fayliga yoziladi. Har
endpoint uchun `p50_ms`, `p95_ms`, `p99_ms`, `duration_ms`,
`status_counts` va `error_types` ko‘rsatiladi. Hisobotda login, parol,
Telegram kodi, cookie, session token yoki CSRF qiymati bo‘lmaydi.

Natijani quyidagicha talqin qiling:

- faqat `healthz_cold` sekin bo‘lsa — yangi HTTPS ulanishlarini ochish
  va internet/Railway yo‘li asosiy gumon;
- `healthz_reused` ham sekin bo‘lsa — API konteyneri yoki Railway proxy
  navbati asosiy gumon;
- `healthz_reused` tez, `/api/v1/auth/session` sekin bo‘lsa — autentifikatsiya
  DB so‘rovi yoki ulanish navbati asosiy gumon;
- dastlabki ikkitasi tez, faqat `/api/v1/me` sekin bo‘lsa — profilni
  yuklash so‘rovi yoki qo‘shimcha DB sessiyasi asosiy gumon;
- barcha endpointlarda HTTP xatosi bo‘lmasa-yu p95 yuqori bo‘lsa,
  Railway API va Postgres metrikalarini sinov vaqt oralig‘i bilan
  solishtiring.

Bu diagnostika kuzatuv rejimida ishlaydi: production `web`, Railway
replica, DB pool, Redis, Postgres va R2 sozlamalarini o‘zgartirmaydi.

Phase 2 profil cache gate’i `/api/v1/me` uchun 1000 parallel so‘rovda
0 xato, barcha javoblar HTTP 200 va p95 500 ms dan past bo‘lganda o‘tadi.

### k6 — muqobil usul

Faqat staging uchun alohida test session yarating. Uni shell historyga
yozmasdan environment orqali uzating:

```bash
KOPRIK_API_BASE_URL=https://platforma-production-f753.up.railway.app \
KOPRIK_LOAD_SESSION=STAGING_TEST_SESSION \
k6 run scripts/phase2_load.js
```

Gate: HTTP xatolar 1% dan kam va p95 500 ms dan past. Bu 100 → 500 → 1000
authenticated read o‘lchovi, butun tizim 10 000 concurrent userni ko‘taradi
degan da’vo emas. 10 000 uchun alohida capacity test, Railway replica
masshtablash va DB/Redis/R2 metrikalari talab qilinadi.

## 6. Rollback

Quyidagilardan biri bajarilmasa rollback qiling: migration, healthcheck,
Telegram, user/business ajratilishi, profil/media, error rate yoki latency
gate.

1. Trafikni yangi frontenddan olib tashlang.
2. `frontend-staging`, `worker-staging`, so‘ng `api-staging` ni oldingi
   muvaffaqiyatli deployment IDga qaytaring.
3. Forward-compatible migration bo‘lsa DBni o‘zgartirmang. Aks holda faqat
   tasdiqlangan rollback migration yoki oldingi Postgres backupdan staging
   bazani tiklang.
4. Telegram webhook ni oldingi staging endpointiga qaytaring.
5. Hodisa va deployment IDlarini yozib qo‘ying.
6. `web`, uning volume’i, custom domaini va `koprik.uz` ga hech qachon
   tegmang.

Rollbackdan keyin `/healthz`, `/readyz`, `/api/v1/build` va eski staging
loginini qayta tekshiring.

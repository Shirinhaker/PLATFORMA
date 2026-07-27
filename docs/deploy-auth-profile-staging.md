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
```

Fernet kalitini lokal terminalda yarating:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`KOPRIK_DATABASE_URL` qiymati `postgresql+asyncpg://` bilan boshlanishi
kerak. Railway reference oddiy `postgresql://` qaytarsa, faqat protokol
qismini `postgresql+asyncpg://` ga almashtiring.

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

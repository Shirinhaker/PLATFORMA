# Phase 3C V9 — Telegram webhook va monolitni yakuniy uzish

Bu bosqich yangi modular frontend/API productionda ishlayotganidan keyin eski v1656
`web` servisni xavfsiz chiqarish uchun ishlatiladi. Maqsad — eski servisni birdan
o‘chirish emas, avval uning barcha yozuvlarini muzlatish, Telegram webhookni yangi
API'ga o‘tkazish va real login smoke-testlaridan keyingina auto-deploy/service'ni
to‘xtatish.

## Muhim xavf

Eski v1656 `main.py` ishga tushganda Telegram webhookni `BASE_URL + /webhook` ga
qayta o‘rnatadi. Shuning uchun yangi webhookni avval almashtirib, eski `web`ni
keyin freeze qilish mumkin emas.

Majburiy tartib:

`legacy freeze -> freeze verify -> Telegram webhook cutover -> real auth smoke -> legacy auto-deploy/service off`

## 0. Old shartlar

Quyidagilar allaqachon ishlayotgan bo‘lishi kerak:

- `koprik.uz` yangi React frontendga xizmat qilmoqda;
- yangi modular API productionda deploy bo‘lmoqda;
- production PostgreSQL/R2/Redis ishlamoqda;
- final SQLite va PostgreSQL backup/migratsiya dalillari saqlangan.

Haqiqiy Telegram token yoki webhook secretni repo, log yoki chatga yozmang.
Production avtomatik cutover bu qiymatlarni API servisining mavjud environment
secretlaridan o‘qiydi.

## 1. Eski `web` servisni write-freeze holatiga o‘tkazish

Root `Procfile` eski Railway `web` servisni maintenance wrapper orqali ishga
tushirishga pin qilinadi:

```text
web: env KOPRIK_MIGRATION_MAINTENANCE=1 uvicorn cutover_app:app --host 0.0.0.0 --port $PORT
```

Bu commit `main`ga merge bo‘lib eski `web` qayta deploy qilingach freeze production
holatiga kiradi. `cutover_app.py` maintenance rejimida eski `main.py`ni import
qilmaydi. Natijada legacy Telegram webhook, outbox/push background workerlar va
SQLite mutation endpointlari ishga tushmaydi.

Freeze aktiv paytda `Procfile`ni `main:app`ga qaytarmang.

## 2. Freeze holatini majburiy tekshirish

Manual tekshiruv uchun:

```powershell
.\scripts\Koprik-Phase3C-Legacy-Freeze-Verify-V9.ps1 `
  -LegacyBaseUrl https://web-production-302eb.up.railway.app
```

Skript quyidagilarni tekshiradi:

- `GET /readyz` -> 200 va `maintenance=true`, `writes_frozen=true`;
- `GET /maintenance.html` -> 200;
- `GET /` -> 503;
- `POST /api/_setup` -> 503;
- `POST /webhook` -> 503.

Muvaffaqiyat belgisi:

```text
LEGACY_WRITE_FREEZE_VERIFIED=1
```

## 3. Production uchun avtomatik, fail-closed Telegram cutover

`backend/app/auth/telegram_cutover_once.py` production API startidan oldin
`backend/Dockerfile` orqali ishga tushadi.

U faqat aynan cutover uchun tasdiqlangan Railway service ID va environment ID mos
kelganda ishlaydi. Boshqa PR/staging servislarida:

```text
TELEGRAM_WEBHOOK_CUTOVER_SKIPPED=1
```

va API odatdagidek start bo‘ladi.

Production targetda modul quyidagi tartibni majburiy bajaradi:

1. eski `web` `/readyz` javobida `maintenance=true` va `writes_frozen=true` ni tekshiradi;
2. Railway bergan `RAILWAY_PUBLIC_DOMAIN`dan target webhook URL tuzadi;
3. API servisidagi `KOPRIK_TELEGRAM_BOT_TOKEN`, `KOPRIK_TELEGRAM_BOT_USERNAME` va
   `KOPRIK_TELEGRAM_WEBHOOK_SECRET` secretlarini o‘qiydi, lekin logga chiqarmaydi;
4. Telegram `getMe` orqali aynan kutilgan bot ekanini tekshiradi;
5. `getWebhookInfo` bilan joriy URLni ko‘radi;
6. URL targetga teng bo‘lmasa legacy freeze'ni ikkinchi marta tekshiradi;
7. `setWebhook` bilan yangi modular endpointga o‘tkazadi;
8. `getWebhookInfo` bilan target URLni qayta tasdiqlaydi.

Target URL Railway tomonidan avtomatik berilgan API public domain asosida:

```text
https://$RAILWAY_PUBLIC_DOMAIN/api/v1/auth/telegram/webhook
```

Docker command `&&` bilan fail-closed. Cutover modul xato bilan tugasa yangi API
process start qilinmaydi va Railway deploy muvaffaqiyatli deb belgilanmasligi kerak.
Token/secret qiymatlari xato matniga kiritilmaydi.

Muvaffaqiyat belgisi:

```text
TELEGRAM_WEBHOOK_CUTOVER_COMPLETE=1
```

yoki webhook avvaldan to‘g‘ri bo‘lsa:

```text
TELEGRAM_WEBHOOK_ALREADY_TARGET=1
```

Bu one-shot pre-start gate cutover tasdiqlangach alohida cleanup PR bilan Docker
start komandadan olib tashlanadi. Webhook endpointning o‘zi modular auth ichida
qoladi.

## 4. Manual PowerShell fallback

Avtomatik production gate ishlatilmaydigan operator muhitida avval dry-run:

```powershell
.\scripts\Koprik-Phase3C-Telegram-Webhook-Cutover-V9.ps1 `
  -ApiBaseUrl https://NEW-API.up.railway.app `
  -LegacyBaseUrl https://OLD-WEB.up.railway.app `
  -ExpectedBotUsername YOUR_BOT_USERNAME
```

Keyin freeze verify yashil bo‘lgandagina `-Execute` bilan ishlatiladi. Manual skript
ham `getMe`, ikki bosqichli freeze guard, `setWebhook` va post-verify bajaradi.

## 5. Real auth smoke-test

Eski `web`ni freeze holatida qoldiring va kamida quyidagilarni tekshiring:

1. Avvaldan mavjud haqiqiy oddiy foydalanuvchi login + Telegram kodi bilan kira oladi.
2. Avvaldan mavjud haqiqiy biznes kabinet login + Telegram kodi bilan kira oladi.
3. Telegram deep-link `/start <token>` modular auth challenge'ni faollashtiradi.
4. Kod resend oqimi ishlaydi.
5. Login tugagach `koprik.uz` kabinetga qaytadi va mavjud profil ochiladi; qayta
   ro‘yxatdan o‘tishni talab qilmaydi.

Demo akkaunt yaratish shart emas.

## 6. Eski Railway `web`ni chiqarish

Faqat freeze, Telegram cutover va real auth smoke yashil bo‘lgandan keyin:

- eski `web` servisning auto-deployini o‘chiring;
- undan public domain/routing qolmaganini tasdiqlang;
- servisni stop/suspend qiling;
- **SQLite volume, backup, source archive va migratsiya dalillarini o‘chirmang**.

Repo ichidagi v1656 kodini ham shu zahoti o‘chirmang. Avval production faqat
modular tizimda barqaror ishlashi tasdiqlansin; source cleanup alohida PR bo‘ladi.

## Rollback

Public modular tizimga yangi yozuvlar tushayotgan bo‘lsa eski SQLite monolitga
ko‘r-ko‘rona qaytish mumkin emas. Auth/webhook muammosida avval legacy freeze'ni
saqlang, yangi API muammosini tuzating va ma’lumotlar reconciliation holatini
tekshiring. To‘liq rollback tartibi `docs/deploy-phase3c-production.md` dagi
"Rollback — public trafik ochilgandan keyin" bo‘limiga amal qiladi.

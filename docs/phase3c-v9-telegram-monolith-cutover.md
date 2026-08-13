# Phase 3C V9 — Telegram webhook va monolitni yakuniy uzish

Bu bosqich yangi modular frontend/API productionda ishlayotganidan keyin eski v1656
`web` servisni xavfsiz chiqarish uchun ishlatiladi. Maqsad — eski servisni birdan
o‘chirish emas, avval uning barcha yozuvlarini muzlatish, Telegram webhookni yangi
API'ga o‘tkazish va real login smoke-testlaridan keyingina auto-deploy/service'ni
to‘xtatish.

## Muhim xavf

Eski v1656 `main.py` ishga tushganda Telegram webhookni `BASE_URL + /webhook` ga
qayta o‘rnatadi. Shuning uchun yangi webhookni avval almashtirib, eski `web`ni
keyin freeze qilish xavfli: legacy servis redeploy/restart bo‘lsa webhook yana eski
manzilga qaytishi mumkin.

Majburiy tartib:

`legacy freeze -> freeze verify -> Telegram webhook cutover -> real auth smoke -> legacy auto-deploy/service off`

## 0. Old shartlar

Quyidagilar allaqachon ishlayotgan bo‘lishi kerak:

- `koprik.uz` yangi React frontendga xizmat qilmoqda;
- yangi modular API `/readyz` `status=ready` qaytarmoqda;
- production PostgreSQL/R2/Redis ishlamoqda;
- asosiy kabinet, katalog, navbat/buyurtma, chat/media smoke-testlari o‘tgan;
- final SQLite va PostgreSQL backup/migratsiya dalillari saqlangan.

Haqiqiy Telegram token yoki webhook secretni repo, log yoki terminal tarixiga
qo‘ymang. Ularni faqat vaqtinchalik environment variable orqali bering:

```powershell
$env:KOPRIK_TELEGRAM_BOT_TOKEN = "..."
$env:KOPRIK_TELEGRAM_WEBHOOK_SECRET = "..."
```

## 1. Eski `web` servisni write-freeze holatiga o‘tkazish

Railway eski v1656 `web` servisida:

```text
KOPRIK_MIGRATION_MAINTENANCE=1
```

qiymatini qo‘ying va aynan eski `web` servisni redeploy qiling.

Bu rejimda `cutover_app.py` eski `main.py`ni umuman import qilmaydi. Natijada
legacy Telegram webhook, outbox/push background workerlar va SQLite mutation
endpointlari ishga tushmaydi.

## 2. Freeze holatini majburiy tekshirish

```powershell
.\scripts\Koprik-Phase3C-Legacy-Freeze-Verify-V9.ps1 `
  -LegacyBaseUrl https://OLD-WEB.up.railway.app
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

Bu natija chiqmasa webhook cutover bajarilmaydi.

## 3. Telegram webhook dry-run

Avval yozuvsiz dry-run qiling:

```powershell
.\scripts\Koprik-Phase3C-Telegram-Webhook-Cutover-V9.ps1 `
  -ApiBaseUrl https://NEW-API.up.railway.app `
  -LegacyBaseUrl https://OLD-WEB.up.railway.app `
  -ExpectedBotUsername YOUR_BOT_USERNAME
```

Dry-run:

- yangi API `/readyz` holatini tekshiradi;
- legacy `writes_frozen` holatini ko‘radi;
- Telegram `getMe` orqali aynan kutilgan bot ekanini tasdiqlaydi;
- `getWebhookInfo` bilan joriy webhookni ko‘rsatadi;
- hech qanday Telegram sozlamasini o‘zgartirmaydi.

Muvaffaqiyat belgisi:

```text
TELEGRAM_WEBHOOK_CUTOVER_DRY_RUN_OK=1
TELEGRAM_WEBHOOK_NOT_CHANGED=1
```

## 4. Webhookni yangi modular API'ga o‘tkazish

Freeze verify yashil bo‘lgandan keyingina:

```powershell
.\scripts\Koprik-Phase3C-Telegram-Webhook-Cutover-V9.ps1 `
  -ApiBaseUrl https://NEW-API.up.railway.app `
  -LegacyBaseUrl https://OLD-WEB.up.railway.app `
  -ExpectedBotUsername YOUR_BOT_USERNAME `
  -Execute
```

Target manzil qat’iy:

```text
https://NEW-API.up.railway.app/api/v1/auth/telegram/webhook
```

`-Execute` rejimi legacy servis `maintenance=true` va `writes_frozen=true` bo‘lmasa
`TELEGRAM_CUTOVER_LEGACY_NOT_FROZEN` bilan to‘xtaydi. Skript `setWebhook`dan keyin
`getWebhookInfo`ni qayta chaqiradi va URL aynan targetga teng bo‘lmasa xato beradi.

Muvaffaqiyat belgisi:

```text
TELEGRAM_WEBHOOK_CUTOVER_COMPLETE=1
LEGACY_WEB_MUST_REMAIN_FROZEN=1
```

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

Faqat 2–5-bosqichlar yashil bo‘lgandan keyin:

- eski `web` servisning auto-deployini o‘chiring;
- undan public domain/routing qolmaganini tasdiqlang;
- servisni stop/suspend qiling;
- **SQLite volume, backup, source archive va migratsiya dalillarini o‘chirmang**.

Repo ichidagi v1656 kodini ham shu zahoti o‘chirmang. Avval production bir muddat
faqat modular tizimda barqaror ishlashi va rollback/reconciliation ehtiyoji
yo‘qligi tasdiqlansin; source cleanup alohida PR bo‘ladi.

## Rollback

Public modular tizimga yangi yozuvlar tushayotgan bo‘lsa eski SQLite monolitga
ko‘r-ko‘rona qaytish mumkin emas. Auth/webhook muammosida avval legacy freeze'ni
saqlang, yangi API muammosini tuzating va ma’lumotlar reconciliation holatini
tekshiring. To‘liq rollback tartibi `docs/deploy-phase3c-production.md` dagi
"Rollback — public trafik ochilgandan keyin" bo‘limiga amal qiladi.

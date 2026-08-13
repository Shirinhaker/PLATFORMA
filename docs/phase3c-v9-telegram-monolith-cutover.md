# Phase 3C V9 — Telegram webhook va monolitni yakuniy uzish

Bu bosqich yangi modular frontend/API productionda ishlayotganidan keyin eski v1656
`web` servisni xavfsiz chiqarish uchun ishlatiladi.

## Hozirgi holat — 2026-08-13

- legacy `web` write-freeze holatiga o‘tkazildi;
- Telegram webhook modular API targetiga cutover qilindi;
- production API deployi cutover gate bilan muvaffaqiyatli tugadi;
- real oddiy foydalanuvchi login smoke-testidan o‘tdi;
- real biznes kabinet login smoke-testidan o‘tdi;
- one-shot cutover gate endi default holatda avtomatik ishlamaydi.

Keyingi operatsion bosqich: eski `web` auto-deploy/public routingni chiqarish va servisni
stop/suspend qilish. SQLite volume, backup, source archive va migratsiya dalillarini
o‘chirmang.

## Muhim xavf

Eski v1656 `main.py` ishga tushganda Telegram webhookni `BASE_URL + /webhook` ga
qayta o‘rnatadi. Shuning uchun freeze holatini saqlamasdan eski monolitni qayta
ishga tushirmang.

Majburiy tartib:

`legacy freeze -> freeze verify -> Telegram webhook cutover -> real auth smoke -> legacy auto-deploy/service off`

## 1. Legacy freeze

Root `Procfile` eski Railway `web` servisni maintenance wrapper orqali ishga
tushirishga pin qilingan:

```text
web: env KOPRIK_MIGRATION_MAINTENANCE=1 uvicorn cutover_app:app --host 0.0.0.0 --port $PORT
```

Bu holatda `cutover_app.py` eski `main.py`ni import qilmaydi. Legacy Telegram webhook,
outbox/push background workerlar va SQLite mutation endpointlari ishga tushmaydi.

Freeze aktiv paytda `Procfile`ni `main:app`ga qaytarmang.

## 2. Freeze verify

Manual tekshiruv uchun:

```powershell
.\scripts\Koprik-Phase3C-Legacy-Freeze-Verify-V9.ps1 `
  -LegacyBaseUrl https://web-production-302eb.up.railway.app
```

Muvaffaqiyat belgisi:

```text
LEGACY_WRITE_FREEZE_VERIFIED=1
```

## 3. Telegram cutover — yakunlangan

Cutover paytida `backend/app/auth/telegram_cutover_once.py` production API startidan
oldin ishladi. U legacy freeze, bot identity va webhook target URLni tekshirdi;
`setWebhook`dan keyin `getWebhookInfo` bilan post-verify qildi.

Target endpoint:

```text
https://platforma-production-f753.up.railway.app/api/v1/auth/telegram/webhook
```

Cutoverdan keyingi production API deployi muvaffaqiyatli tugadi va real ordinary +
business login smoke-testlari o‘tdi.

### One-shot gate cleanup

Oddiy API restartlar endi cutover’ni qayta bajarmaydi. Docker startupda gate faqat
quyidagi maxsus flag aniq yoqilgandagina ishlaydi:

```text
KOPRIK_TELEGRAM_CUTOVER_ONCE=1
```

Default qiymat `0`; shu sabab oddiy deploy/restart legacy `web`ning mavjudligiga
bog‘liq emas. Bu flagni odatiy production deploylarda yoqmang.

## 4. Manual PowerShell fallback

Favqulodda operator muhitida manual skript mavjud:

```powershell
.\scripts\Koprik-Phase3C-Telegram-Webhook-Cutover-V9.ps1 `
  -ApiBaseUrl https://platforma-production-f753.up.railway.app `
  -LegacyBaseUrl https://web-production-302eb.up.railway.app `
  -ExpectedBotUsername YOUR_BOT_USERNAME
```

`-Execute` faqat freeze verify yashil bo‘lgandagina ishlatiladi. Haqiqiy bot token yoki
webhook secretni repo, log yoki chatga yozmang.

## 5. Real auth smoke — yakunlangan

Quyidagilar 2026-08-13 kuni real profillar bilan tekshirildi:

1. mavjud oddiy foydalanuvchi Telegram orqali kabinetga kirdi;
2. mavjud biznes profil Telegram orqali kabinetga kirdi.

Demo akkaunt ishlatilmadi. Demo akkaunt yaratish shart emas.

## 6. Eski Railway `web`ni chiqarish

Faqat freeze, Telegram cutover va real auth smoke yashil bo‘lgandan keyin:

- eski `web` servisning auto-deployini o‘chiring;
- undan public domain/routingni olib tashlang;
- servisni stop/suspend qiling;
- **SQLite volume, backup, source archive va migratsiya dalillarini o‘chirmang**.

Repo ichidagi v1656 source kodini ham shu zahoti o‘chirmang. Avval production faqat
modular tizimda barqaror ishlashi tasdiqlansin; source cleanup alohida PR bo‘ladi.

## Rollback

Public modular tizimga yangi yozuvlar tushayotgan bo‘lsa eski SQLite monolitga
ko‘r-ko‘rona qaytish mumkin emas. Auth/webhook muammosida modular API muammosini
tuzating va reconciliation holatini tekshiring. Eski monolitni `main.py` bilan qayta
ishga tushirish Telegram webhookni eski endpointga qaytarishi mumkin.

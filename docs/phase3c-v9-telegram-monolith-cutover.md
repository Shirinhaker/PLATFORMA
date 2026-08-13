# Phase 3C V9 — Telegram webhook va monolitni yakuniy uzish

Bu bosqich yangi modular frontend/API productionda ishlayotganidan keyin eski v1656
`web` servisni xavfsiz chiqarish uchun ishlatiladi.

## Hozirgi holat — 2026-08-13

- legacy `web` write-freeze holatiga o‘tkazildi;
- Telegram webhook modular API targetiga cutover qilindi;
- production API deployi cutover gate bilan muvaffaqiyatli tugadi;
- real oddiy foydalanuvchi login smoke-testidan o‘tdi;
- real biznes kabinet login smoke-testidan o‘tdi;
- one-shot cutover gate endi default holatda avtomatik ishlamaydi;
- eski Railway `web` servisi operator tomonidan productiondan chiqarilib `offline` holatiga o‘tkazildi;
- eski `web-volume` saqlab qolindi;
- `melodious-emotion` modular frontend va API deploy statuslari retirementdan keyin ham `success` bo‘lib qoldi.

**Production cutover yakunlandi.** Endi yangi trafik va login oqimi modular frontend/API orqali ishlaydi. Legacy source, SQLite volume, backup va migratsiya dalillari hozircha rollback/evidence uchun saqlanadi.

## Muhim xavf

Eski v1656 `main.py` ishga tushganda Telegram webhookni `BASE_URL + /webhook` ga
qayta o‘rnatadi. Shuning uchun eski monolit servisni `main.py` bilan qayta ishga
tushirmang.

Majburiy tartib:

`legacy freeze -> freeze verify -> Telegram webhook cutover -> real auth smoke -> legacy auto-deploy/service off`

## 1. Legacy freeze — yakunlangan

Root `Procfile` eski Railway `web` servisni maintenance wrapper orqali ishga
tushirishga pin qilingan:

```text
web: env KOPRIK_MIGRATION_MAINTENANCE=1 uvicorn cutover_app:app --host 0.0.0.0 --port $PORT
```

Freeze paytida `cutover_app.py` eski `main.py`ni import qilmagan. Legacy Telegram webhook,
outbox/push background workerlar va SQLite mutation endpointlari ishga tushmagan.

## 2. Freeze verify — yakunlangan

Manual tekshiruv uchun mavjud skript:

```powershell
.\scripts\Koprik-Phase3C-Legacy-Freeze-Verify-V9.ps1 `
  -LegacyBaseUrl https://OLD-LEGACY-WEB.up.railway.app
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

### One-shot gate cleanup — yakunlangan

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
  -LegacyBaseUrl https://OLD-LEGACY-WEB.up.railway.app `
  -ExpectedBotUsername YOUR_BOT_USERNAME
```

`-Execute` faqat freeze verify yashil bo‘lgandagina ishlatiladi. Haqiqiy bot token yoki
webhook secretni repo, log yoki chatga yozmang.

## 5. Real auth smoke — yakunlangan

Quyidagilar 2026-08-13 kuni real profillar bilan tekshirildi:

1. mavjud oddiy foydalanuvchi Telegram orqali kabinetga kirdi;
2. mavjud biznes profil Telegram orqali kabinetga kirdi.

Demo akkaunt ishlatilmadi. Demo akkaunt yaratish shart emas.

## 6. Eski Railway `web`ni chiqarish — yakunlangan

2026-08-13 kuni operator eski root `web` servisni productiondan chiqardi:

- servis `offline` holatiga o‘tkazildi;
- GitHub source bog‘lanishi retirement jarayonida uzildi;
- eski `web-volume` o‘chirilmay saqlandi;
- modular frontend/API retirementdan keyin ham yashil deploy holatida qoldi.

**SQLite volume, backup, source archive va migratsiya dalillarini o‘chirmang.**

Repo ichidagi v1656 source kodini ham shu zahoti o‘chirmang. Avval production faqat
modular tizimda barqaror ishlashi tasdiqlansin; source cleanup alohida PR bo‘ladi.

## Keyingi cleanup — production migratsiyaning majburiy qismi emas

Legacy source kodni, vaqtinchalik cutover skriptlarini va eski migration evidence fayllarini
birdan o‘chirmang. Bir muddat modular production barqaror ishlagach, alohida source-cleanup
PR bilan faqat endi kerak bo‘lmaydigan runtime qismlar tozalanadi. Backup va audit dalillari
saqlanadi.

## Rollback

Public modular tizimga yangi yozuvlar tushayotgan bo‘lsa eski SQLite monolitga
ko‘r-ko‘rona qaytish mumkin emas. Auth/webhook muammosida modular API muammosini
tuzating va reconciliation holatini tekshiring. Eski monolitni `main.py` bilan qayta
ishga tushirish Telegram webhookni eski endpointga qaytarishi mumkin.

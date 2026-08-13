# Phase 3C V9 — Telegram webhook va monolitni yakuniy uzish

Bu bosqich yangi modular frontend/API productionda ishlayotganidan keyin eski v1656
`web` servisni xavfsiz chiqarish va uni qayta tirilishdan himoyalash uchun ishlatiladi.

Majburiy tartib yakunlandi:

`legacy freeze -> freeze verify -> Telegram webhook cutover -> real auth smoke -> legacy auto-deploy/service off`

## Hozirgi holat — 2026-08-13

- eski v1656 yozuvlari freeze qilindi;
- Telegram webhook modular API targetiga ko‘chirildi;
- production modular API deployi muvaffaqiyatli tugadi;
- real oddiy foydalanuvchi Telegram orqali kabinetga kirdi;
- real biznes profil Telegram orqali kabinetga kirdi;
- one-shot cutover gate default holatda o‘chirilgan;
- `melodious-emotion` ichidagi eski `web` Railway UI orqali offline qilindi;
- `web-volume` saqlab qolindi;
- yangi `frontend-staging` va `api-staging` oxirgi tekshiruvda success holatda qoldi;
- v1656 cutover paytidagi to‘liq source snapshot `archive/legacy-v1656-production-cutover`
  branchida saqlandi;
- root `cutover_app.py` endi permanent retired shell: u hech qanday env yoki fallback
  orqali eski monolit runtime’ni import qilib ishga tushira olmaydi.

BUILD v1656 va `static/index.html` (14 091 qator) bu bosqichda o‘zgartirilmaydi.

## 1. Legacy freeze

Root `Procfile` eski Railway `web` servisni wrapper orqali ishga tushirishga pin qilingan:

```text
web: env KOPRIK_MIGRATION_MAINTENANCE=1 uvicorn cutover_app:app --host 0.0.0.0 --port $PORT
```

`KOPRIK_MIGRATION_MAINTENANCE=1` tarixiy freeze flagi sifatida Procfile’da qoladi,
lekin `cutover_app.py` endi bu flagga qarab eski runtime’ga qaytmaydi. Wrapper doim
retired holatda ishlaydi: health probe 200, public sahifalar/API/webhook esa servis
qayta yoqilib qolsa ham yozuv bajarmaydi.

`Procfile`ni `main:app`ga qaytarmang.

## 2. Freeze verify

Tarixiy/manual tekshiruv vositasi saqlanadi:

```powershell
.\scripts\Koprik-Phase3C-Legacy-Freeze-Verify-V9.ps1 `
  -LegacyBaseUrl https://web-production-302eb.up.railway.app
```

Muvaffaqiyat belgisi:

```text
LEGACY_WRITE_FREEZE_VERIFIED=1
```

Bu skript `/readyz`, `/maintenance.html`, `/`, `/api/_setup` va `/webhook`
chegaralarini tekshiradi. Retired wrapper ham shu write-freeze kontraktini saqlaydi.

## 3. Telegram cutover — yakunlangan

Cutover paytida `backend/app/auth/telegram_cutover_once.py` production API startidan
oldin legacy freeze, bot identity va target URLni tekshirdi; `setWebhook`dan keyin
`getWebhookInfo` bilan post-verify bajarildi.

Target endpoint:

```text
https://platforma-production-f753.up.railway.app/api/v1/auth/telegram/webhook
```

Oddiy API restartlar endi cutover’ni avtomatik bajarmaydi. Fallback faqat quyidagi
maxsus flag aniq yoqilgandagina ishlaydi:

```text
KOPRIK_TELEGRAM_CUTOVER_ONCE=1
```

Odatiy production deploylarda bu flagni yoqmang.

Favqulodda operator fallback skripti ham arxiv/evidence sifatida saqlanadi:

```powershell
.\scripts\Koprik-Phase3C-Telegram-Webhook-Cutover-V9.ps1 `
  -ApiBaseUrl https://platforma-production-f753.up.railway.app `
  -LegacyBaseUrl https://web-production-302eb.up.railway.app `
  -ExpectedBotUsername YOUR_BOT_USERNAME
```

Haqiqiy bot token yoki webhook secretni repo, log yoki chatga yozmang.

## 4. Real auth smoke — yakunlangan

2026-08-13 kuni real profillar bilan tekshirildi:

1. mavjud oddiy foydalanuvchi Telegram orqali kabinetga kirdi;
2. mavjud biznes profil Telegram orqali kabinetga kirdi.

Demo akkaunt ishlatilmadi. Demo akkaunt yaratish shart emas.

## 5. Legacy Railway servis — retired

`melodious-emotion` Railway projectidagi eski `web` servis UI orqali offline qilindi.
Unga biriktirilgan `web-volume` o‘chirilmagan.

**SQLite volume, backup, source archive va migratsiya dalillarini o‘chirmang.**
`archive/legacy-v1656-production-cutover` branchini ham saqlang.

GitHub status tarixida uchrashi mumkin bo‘lgan eski Railway deployment/domain yozuvlarini
faol servis deb qabul qilib ko‘r-ko‘rona restart qilmang. Agar eski servis topilsa,
uni yangi modular API o‘rniga ishga tushirmang; permanent `cutover_app:app` wrapperi
eski runtime’ni qayta faollashtirishga yo‘l qo‘ymasligi kerak.

## 6. Source cleanup — bosqichma-bosqich

Production cutover tugagan bo‘lsa ham v1656 source fayllarini birdan o‘chirmang.
Avval:

1. permanent retired wrapperni merge va CI bilan mustahkamlang;
2. CI’dagi legacy parity/inventory testlarini archive snapshot strategiyasiga o‘tkazing;
3. yangi modular testlar mustaqil yashil qolishini tasdiqlang;
4. shundan keyin root legacy runtime fayllarini alohida cleanup PRlarda olib tashlang.

Bu tartib ishlayotgan modular kodni eski test dependencylari bilan birga tasodifan
buzib yubormaslik uchun kerak.

## Rollback

Public modular tizimga yangi yozuvlar tushayotgan bo‘lsa eski SQLite monolitga
ko‘r-ko‘rona qaytish mumkin emas. Auth/webhook muammosida modular API muammosini
tuzating va reconciliation holatini tekshiring. Retired wrapperni chetlab o‘tib eski
runtime’ni qayta ishga tushirish Telegram webhook va eski writerlarni qayta faollashtirishi
mumkin; bunday rollback alohida data-reconciliation rejasisiz bajarilmasin.

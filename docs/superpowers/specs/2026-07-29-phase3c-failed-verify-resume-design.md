# Phase 3C Failed Verify Resume Design

Sana: 2026-07-29
Holat: foydalanuvchi tasdiqlagan
Repository: `Shirinhaker/PLATFORMA`

## Maqsad

Phase 3C staging migratsiyasi `verify` bosqichida muvaffaqiyatsiz
tugaganidan keyin shu snapshot va shu `migration_run_id` bilan
xavfsiz davom etishi kerak. Oldingi akkaunt, biznes, katalog, e’lon va
reklama importlari qayta bajarilmasligi kerak.

## Root sabab

`MigrationRunner` muvaffaqiyatsiz verify natijasini
`stage=verify, status=failed` sifatida saqlaydi. Keyingi `run` chaqiruvida
`_remaining_stages()` verify bosqichidan keyingi bosqichlarni qidiradi va
bo‘sh ro‘yxat qaytaradi. Runner statusni `running`ga o‘zgartiradi, ammo
hech qanday handler ishlamaydi.

## Tasdiqlangan xatti-harakat

- Mavjud `migration_run_id` saqlanadi.
- `stage=verify, status=failed` run qayta ishga tushirilganda faqat
  `media` va `verify` handlerlari ishlaydi.
- `accounts`, `businesses`, `catalog`, `listings` va `advertisements`
  handlerlari qayta ishlamaydi.
- Oldingi birinchi-pass counterlari saqlanadi; qayta ishlangan `media`
  va `verify` counterlari yangi natija bilan almashtiriladi.
- Resume boshlanganda eski terminal `finished_at` qiymati tozalanadi.
- Resume muvaffaqiyatli verify bilan tugasa run `completed` bo‘ladi.
- Haqiqatan yo‘q lokal media `missing` terminal holatiga o‘tadi.
- R2 yoki Telegram kabi haqiqiy tashqi xatolar `failed` bo‘lib gate’ni
  bloklashda davom etadi.
- Completed running mavjud to‘liq idempotency qayta tekshiruvi
  o‘zgarmaydi. Idempotency verify muvaffaqiyatsiz bo‘lsa
  `idempotency_in_progress` marker saqlanadi va keyingi
  `media → verify` resume natijalari faqat `counters_json.idempotency`
  ichiga yoziladi. Birinchi-pass counterlari o‘zgarmaydi.
- Production tasdiqlash gate’lari o‘zgarmaydi.

## Minimal kod o‘zgarishi

`MigrationRunner.run()` qolgan bosqichlarni running oldingi statusi
`running`ga almashtirilishidan avval hisoblaydi.

`MigrationRunner._remaining_stages()` quyidagi maxsus holatni taniydi:

```python
if (
    run.status is MigrationStatus.FAILED
    and run.stage is MigrationStage.VERIFY
):
    return STAGES[-2:]
```

Boshqa stage va statuslar mavjud oqimdan foydalanadi.

Idempotency marker faqat `verify` natijasi muvaffaqiyatli bo‘lganda
o‘chiriladi. Failed resume `running` holatiga o‘tishidan avval
`finished_at=None` qilinadi.

## Testlash

Regression test oldindan `stage=verify, status=failed` bo‘lgan runni
yaratadi, faqat chaqirilgan handlerlarni va yakuniy holatni tekshiradi.
Test production kod o‘zgarishidan oldin `calls == []` sabab yiqilishi,
minimal tuzatishdan keyin esa `calls == ["media", "verify"]` bilan
o‘tishi kerak.

Qo‘shimcha regressionlar:

- failed resume media bosqichida saqlanganda `finished_at=None`;
- completed run idempotency verify’da yiqilib, keyin resume bo‘lganda
  first-pass counterlari o‘zgarmaydi.

To‘liq tekshiruv:

1. Runner regression testi.
2. Barcha backend testlari.
3. Phase 3C static contract, backend, frontend test va frontend build
   gate’i.
4. GitHub CI.
5. `api-staging` deploy.
6. O‘sha snapshot bilan migratsiya resume va verify report.

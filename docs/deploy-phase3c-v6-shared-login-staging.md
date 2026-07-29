# Phase 3C V6 shared-login staging rollout

## Maqsad

V5 `run_id=4`da karantinda qolgan 20 ta haqiqiy oddiy profil va ularga tegishli 20 ta haqiqiy biznes kabinetini yangi shared-login modeliga xavfsiz ko‘chirish.

Read-only diagnostika dalili:

- explicit demo/test juftliklar: `0`;
- real-evidence juftliklar: `20`;
- noaniq juftliklar: `0`;
- source `tg_id` yo‘q: `20`;
- alohida `biz_login` yo‘q: `20`;
- audit yozuvlari: `0`.

## Qat’iy taqiqlar

- V3, V4 yoki V5 rollout skriptini qayta ishlatmang.
- `run_id=4`ni qayta ochmang yoki davom ettirmang.
- Production bazasiga ushbu staging runbook orqali ulanmaydi.
- `BUILD v1656` va `static/index.html` o‘zgartirilmaydi.
- CI yashil bo‘lmasdan migratsiyani ishga tushirmang.
- Noaniq identity yozuvlarini avtomatik birlashtirmang.
- V6 yozuvlari yaratilgach `alembic downgrade`ni rollback sifatida ishlatmang.

## Old shartlar

1. PR #18 CI to‘liq yashil.
2. PR #18 foydalanuvchi tasdig‘i bilan merge qilingan.
3. `api-staging` PR #18 kodi bilan muvaffaqiyatli deploy qilingan.
4. Staging PostgreSQL snapshot/backup V6 yozuvchi run’dan oldin olingan.
5. Alembic head: `0004_shared_login_cabinets`.
6. Immutable snapshot va `media-manifest.json` V5 bilan bir xil fingerprintga ega.
7. `KOPRIK_ENVIRONMENT=staging`.
8. Database URL staging PostgreSQL’ga tegishli ekanligi tekshirilgan.

## Rasmiy Windows skripti

Skript default holatda faqat dry-run qiladi:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\Koprik-Phase3C-Shared-Login-Staging-V6.ps1
```

Dry-run quyidagilarni tasdiqlaydi va bazaga yozmaydi:

- staging muhiti;
- public Phase 3C flag o‘chiq;
- V6 kod va CLI deploy qilingan;
- V5 `run_id=4` statusi `failed`, stage `verify`;
- V5 schema `0003_phase3c_dual_accounts_v4`;
- aynan 20 ta `identity.account_type_mismatch`;
- aynan 20 ta `identity.business_owner_unresolved`;
- lokal backup SHA-256 mosligi.

Dry-run yakuni:

```text
DRY_RUN_COMPLETE DATABASE_WRITES=0 FILE_UPLOADS=0
```

Faqat old shartlar to‘liq bajarilgach yozuvchi run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\Koprik-Phase3C-Shared-Login-Staging-V6.ps1 -Execute
```

## Staging migratsiyasi

V6 alohida CLI orqali ishga tushiriladi:

```bash
koprik-migrate-legacy-v6 run \
  --snapshot /app/migration/platforma.snapshot.db \
  --environment staging
```

Kutiladigan natija:

- yangi `migration_runs` yozuvi yaratiladi;
- schema version: `0004_phase3c_shared_login_v1`;
- V5 `run_id=4` o‘zgarmaydi;
- `accounts` bosqichida 20 ta oddiy akkaunt yaratiladi yoki xavfsiz qayta ishlatiladi;
- mavjud 20 ta biznes akkaunt/profil saqlanadi;
- bir login `user` va `business` turida alohida mavjud bo‘ladi;
- login/parol qiymati manba legacy yozuvidan olinadi;
- soxta Telegram ID, login yoki parol yaratilmaydi.

## Verify gate

Quyidagilarning barchasi PASS bo‘lishi shart:

- `mapping_coverage`;
- `catalog_kind_count`;
- `listing_count`;
- `advertisement_count`;
- `broken_foreign_keys=0`;
- `identity_conflicts=0`;
- `media_failed=0`;
- `media_terminal_count`;
- `copied_media_verification=0`;
- `public_schema_leak=0`.

Birinchi run yakunida status `completed`, stage `verify` bo‘lishi kerak.

## Idempotency gate

Xuddi shu V6 CLI yana bir marta ishga tushiriladi. Ikkinchi run/replay natijasida:

- o‘sha V6 run ID qayta ishlatiladi;
- `idempotency_created=0`;
- yangi akkaunt, profil, katalog, e’lon, reklama yoki media yozuvi yaratilmaydi;
- mavjud mappinglar V6 run’ga bog‘langan holda saqlanadi.

## Login smoke test

Bitta tasdiqlangan shared-login juftlikda:

1. login va parol kiritiladi;
2. `Oddiy kabinet` tanlanadi;
3. user session va user profil ochiladi;
4. logout qilinadi;
5. o‘sha login/parol bilan `Biznes kabinet` tanlanadi;
6. business session va business profil ochiladi;
7. har ikkala kabinetdagi haqiqiy ma’lumotlar o‘z joyida ekanligi tekshiriladi.

## Rollback

### V6 yozuvchi run boshlanmasidan oldin

- deployni avvalgi staging revisionga qaytarish mumkin;
- Alembic `0004` hali shared-login yozuvlar yaratmagan bo‘lsa, schema rollback alohida tekshiruv bilan ko‘rib chiqilishi mumkin.

### V6 yozuvchi run boshlanganidan keyin

`user` va `business` uchun bir xil loginlar paydo bo‘ladi. Eski global `accounts.login` UNIQUE chekloviga oddiy downgrade qilish mumkin emas. Shu sabab:

1. `api-staging` trafik va workerlar to‘xtatiladi;
2. V6 run’dan oldin olingan staging PostgreSQL snapshot/backup tiklanadi;
3. avvalgi staging deploy revision qaytariladi;
4. R2’da V6 run yaratgan yangi obyektlar bo‘lsa, V6 report/manifest bo‘yicha alohida tozalanadi;
5. V5 `run_id=4` va immutable source snapshotga tegilmaydi;
6. sabab read-only diagnostika bilan tekshiriladi;
7. production migratsiyasi boshlanmaydi.

V6 run muvaffaqiyatsiz bo‘lsa uni production approval sifatida ishlatish qat’iyan taqiqlanadi.

## Production gate

Production migratsiyasi alohida yozma tasdiq, maintenance rejimi, snapshot fingerprint tasdig‘i va muvaffaqiyatli V6 staging run ID’siz bajarilmaydi.

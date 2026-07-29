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

## Old shartlar

1. PR #18 CI to‘liq yashil.
2. `api-staging` PR #18 kodi bilan muvaffaqiyatli deploy qilingan.
3. Alembic head: `0004_shared_login_cabinets`.
4. Immutable snapshot va `media-manifest.json` V5 bilan bir xil fingerprintga ega.
5. `KOPRIK_ENVIRONMENT=staging`.
6. Database URL staging PostgreSQL’ga tegishli ekanligi tekshirilgan.

## Dry-run tekshiruvlari

Quyidagi narsalar yozmasdan tekshiriladi:

- V5 `run_id=4` statusi `failed` va stage `verify`;
- V6 schema version `0004_phase3c_shared_login_v1`;
- source snapshotda 20 ta shared-login nomzod;
- nomzodlarning har birida bitta owner va bitta business;
- mavjud target business account va business profile mavjud;
- explicit demo/test marker `0`;
- noaniq nomzod `0`.

Bitta shart mos kelmasa rollout to‘xtaydi.

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

Verify yoki smoke test muvaffaqiyatsiz bo‘lsa:

- feature/deploy V6 branchdan oldingi staging revisionga qaytariladi;
- V6 run production approval sifatida ishlatilmaydi;
- V5 `run_id=4`ga tegilmaydi;
- snapshot o‘zgartirilmaydi;
- sabab read-only diagnostika bilan tekshiriladi;
- production migratsiyasi boshlanmaydi.

## Production gate

Production migratsiyasi alohida yozma tasdiq, maintenance rejimi, snapshot fingerprint tasdig‘i va muvaffaqiyatli V6 staging run ID’siz bajarilmaydi.

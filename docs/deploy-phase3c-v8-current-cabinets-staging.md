# Phase 3C V8 — joriy typed kabinetlarni yangi staging bazasiga ko‘chirish

## Nega V8 kerak

Eski V7 skripti `0005_profile_cabinet_parity` davrida yozilgan. Hozirgi
modulli backend `0041_taxi_driver_domain`gacha yetgan va complete-cabinet
algoritmi `0008_phase3c_taxi_v1` versiyasida. Eski V5/V7 run yoki staging
bazasi qayta ishlatilmaydi.

V8 alohida, backup olingan staging PostgreSQL bazasida quyidagi tartibni
majburiy qiladi:

```text
v1656 immutable snapshot
        ↓
0005 bazaviy user/business kabinet payload importi
        ↓
0006…0041 typed Alembic backfilllari
        ↓
qolgan katalog/listing/media bosqichlarini davom ettirish
        ↓
AI va Taxi late-domain importi
        ↓
ikkinchi idempotent complete-cabinet run
        ↓
cabinet JSON → relational normalization va verify
```

Bu tartib muhim: `0006…0039` migratsiyalari kabinet payloadidan typed
jadvallarni to‘ldiradi. Ularni legacy importdan oldin ishlatish real kabinet
ma’lumotlarini typed jadvallarga ko‘chirmay qo‘yadi.

## Qat’iy chegaralar

- Faqat yangi, alohida **staging** PostgreSQL bazasi ishlatiladi.
- Boshlang‘ich Alembic revision aynan `0005_profile_cabinet_parity` bo‘ladi.
- Mavjud staging, eski V5/V7 run va production bazaga yozilmaydi.
- `KOPRIK_PHASE3C_PUBLIC_ENABLED=false` bo‘ladi.
- Demo/test va maxfiy credential maydonlari ko‘chirilmaydi.
- `static/index.html` va BUILD v1656 o‘zgarmaydi.
- `-Execute` faqat staging backup tasdiqlanganda ishlaydi.

## Yozuvsiz dry-run

Windows PowerShell’da repository ildizidan:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File ".\scripts\Koprik-Phase3C-Complete-Cabinet-Staging-V8.ps1" `
  -Archive "C:\xavfsiz-joy\koprik-phase3c-source-final.tar.gz" `
  -ExpectedArchiveSha256 "TASDIQLANGAN_SHA256" `
  -SshTarget "koprik-api-migration-staging"
```

Kutiladigan yakun:

```text
DRY_RUN_COMPLETE DATABASE_WRITES=0 FILE_UPLOADS=0
```

Dry-run remote muhit staging ekanini, public flag o‘chiqligini, V8 kodi va
CLIlar deploy qilinganini, yangi baza `0005`da turganini hamda kodning final
head’i `0041` ekanini tekshiradi.

## Yozuvchi staging run

PostgreSQL backup/snapshot alohida tasdiqlangandan keyin yuqoridagi buyruqqa
quyidagilar qo‘shiladi:

```powershell
  -Execute -BackupConfirmed
```

Kutiladigan yakun:

```text
PHASE3C_V8_STAGING_COMPLETE RUN_ID=<id> WORK=<remote-path>
```

## Majburiy PASS gate’lar

- `mapping_coverage`;
- `identity_conflicts=0`;
- `cabinet_demo_rows=0`;
- `cabinet_sensitive_fields=0`;
- `media_failed=0`;
- `idempotency_created=0`;
- `public_schema_leak=0`;
- late AI/Taxi `quarantined=0`;
- cabinet normalization `VERIFY_OK=1`;
- kamida 20 ta oddiy ↔ biznes profil bog‘lanishi.

Bitta gate yiqilsa run production approval hisoblanmaydi. Snapshot, media va
partial staging yozuvlari diagnostika uchun saqlanadi; production ochilmaydi.

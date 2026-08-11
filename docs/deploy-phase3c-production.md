# Phase 3C V8 production cutover va rollback

Production migratsiyasi PR merge bilan avtomatik bajarilmaydi. V8 production
cutover **yangi production bazaga oddiy import qilish emas**. Avval final,
yozuvlari muzlatilgan v1656 snapshot aynan production candidate PostgreSQL
bazasida V8 staging tartibi bilan to‘liq tekshiriladi; keyin o‘sha candidate DB,
o‘sha snapshot va o‘sha staging run ID production sifatida promote qilinadi.

Bu tartib `approved_staging_run_id` himoyasiga mos: production approval aynan bir
xil snapshot SHA-256, media manifest SHA-256 va shu target DB ichidagi muvaffaqiyatli
V8 staging runni talab qiladi. Eski V5/V7 run ID yoki avvalgi, final bo‘lmagan
snapshot production approval sifatida ishlatilmaydi.

## Nega ikki bosqich majburiy

V8 current typed cabinet migratsiyasi quyidagi tartibga tayanadi:

`0005 base import -> 0006..0041 Alembic backfill -> import resume -> late AI/Taxi -> idempotent rerun -> cabinet normalization`

Shuning uchun `0041` dagi bo‘sh production bazaga to‘g‘ridan-to‘g‘ri
`koprik-migrate-legacy run --environment production` ishlatish V8 stagingda
tekshirilgan ketma-ketlikni takrorlamaydi. Productionga faqat V8 stagingdan
o‘tgan candidate DB promote qilinadi.

## 1-bosqich — final snapshot va V8 candidate rehearsal

1. Maintenance oynasini `/maintenance.html` orqali boshlang va v1656 monolith write endpointlari hamda
   worker yozuvlarini to‘xtating.
2. Yangi yozuv kelmayotganini tekshiring.
3. Yakuniy SQLite backup va source archive oling; archive SHA-256 ni yozib qo‘ying.
4. Production candidate PostgreSQL **fresh `0005_profile_cabinet_parity`** holatida,
   `KOPRIK_ENVIRONMENT=staging` va `KOPRIK_PHASE3C_PUBLIC_ENABLED=false` bo‘lsin.
5. Final archive bilan V8 staging skriptini ishga tushiring:

   ```powershell
   .\scripts\Koprik-Phase3C-Complete-Cabinet-Staging-V8.ps1 `
     -Archive .\koprik-final.tar.gz `
     -ExpectedArchiveSha256 ARCHIVE_SHA256 `
     -SshTarget RAILWAY_SSH_TARGET `
     -Execute `
     -BackupConfirmed
   ```

6. Faqat `PHASE3C_V8_STAGING_COMPLETE` bilan tugagan run qabul qilinadi.
   Chiqishdan quyidagilarni saqlang:
   - `RUN_ID` — production uchun approved staging run ID;
   - `WORK` — masofadagi aynan shu V8 ish katalogi;
   - snapshot natijasidagi `database_sha256`;
   - snapshot natijasidagi `manifest_sha256`.
7. Final snapshotdan keyin v1656 ga yana write yoqilmaydi. Agar write qayta
   yoqilsa, oldingi RUN_ID production approval uchun bekor hisoblanadi va yangi
   final snapshot + V8 rehearsal kerak.

## 2-bosqich — aynan o‘sha candidate DB’ni productionga promote qilish

Avval dry-run qiling. `SnapshotPath` qiymati 1-bosqichdagi
`WORK/snapshot/platforma.snapshot.db` bo‘ladi:

```powershell
.\scripts\Koprik-Phase3C-Promote-Cabinet-Production-V8.ps1 `
  -SshTarget RAILWAY_SSH_TARGET `
  -ApprovedStagingRunId STAGING_RUN_ID `
  -SnapshotPath /tmp/koprik-phase3c-v8-YYYYMMDD-HHMMSS/snapshot/platforma.snapshot.db `
  -ExpectedSnapshotSha256 SNAPSHOT_SHA256 `
  -ExpectedManifestSha256 MANIFEST_SHA256
```

Dry-run quyidagilarni yozuvsiz tekshiradi:

- candidate DB `0041_taxi_driver_domain` da;
- candidate hali public emas;
- approved run `0008_phase3c_taxi_v1`, staging, completed va verify PASS;
- snapshot va manifest SHA aynan mos;
- account/business/late-domain quarantine = 0;
- idempotent rerunda created = 0;
- profil linklari bizneslar bilan mos;
- media `pending = 0`, `missing = 0`, `invalid = 0`, `failed = 0`;
- barcha manba media yozuvlari `copied` holatda.

Dry-run yashil bo‘lgach, final SQLite backup va candidate PostgreSQL backup
mavjudligini tasdiqlab write bosqichini bajaring:

```powershell
.\scripts\Koprik-Phase3C-Promote-Cabinet-Production-V8.ps1 `
  -SshTarget RAILWAY_SSH_TARGET `
  -ApprovedStagingRunId STAGING_RUN_ID `
  -SnapshotPath /tmp/koprik-phase3c-v8-YYYYMMDD-HHMMSS/snapshot/platforma.snapshot.db `
  -ExpectedSnapshotSha256 SNAPSHOT_SHA256 `
  -ExpectedManifestSha256 MANIFEST_SHA256 `
  -Execute `
  -BackupConfirmed `
  -MaintenanceConfirmed `
  -SourceWritesStoppedConfirmed
```

Skript production runni shu candidate DB ichida yaratadi va quyidagilarni
majburiy tekshiradi:

- production verification gate’lari barchasi PASS;
- production run `approved_staging_run_id` bilan bog‘langan;
- production pass yangi core/late qator yaratmaydi (`created = 0`);
- media production runida ham `pending/missing/invalid/failed = 0`;
- snapshot va manifest o‘zgarmagan.

Muvaffaqiyat belgisi:

```text
PHASE3C_V8_PRODUCTION_PROMOTION_COMPLETE ...
TRAFFIC_NOT_CHANGED=1
NEXT_STEP=manual_smoke_then_explicit_route_cutover
```

**Skript trafikni o‘zi almashtirmaydi va public flagni yoqmaydi.**

## 3-bosqich — smoke va routing

1. Maintenance routing faol holda candidate API `/readyz` va frontendni tekshiring.
2. Eski haqiqiy oddiy foydalanuvchi loginini tekshiring — qayta ro‘yxatdan
   o‘tmasligi kerak; mavjud akkaunt bilan qayta kir ishlashi shart.
3. Haqiqiy biznes kabinet, katalog, navbat/buyurtma, chat, media va asosiy
   onlaynlashtirish ekranlarini smoke-test qiling.
4. Katalogda demo profil/mahsulot/xizmat yo‘qligini va duplicate yo‘qligini
   tekshiring.
5. Candidate backend/frontend routingini production routingga o‘tkazing, lekin
   maintenance’ni darhol olib tashlamang.
6. Production routing orqali yana qisqa smoke-test bajaring.
7. Faqat shundan keyin public Phase 3C flag/maintenance blokini kelishilgan
   tartibda oching.

## Rollback — trafik hali ochilmagan bo‘lsa

Agar production promotion yoki smoke-test trafik ochilishidan oldin yiqilsa:

1. Maintenance’ni saqlang.
2. `KOPRIK_PHASE3C_PUBLIC_ENABLED=false` qolsin.
3. Routingni v1656 monolith’da qoldiring.
4. Candidate PostgreSQL partial/production runlarini o‘chirmang.
5. SQLite, source archive, V8 snapshot, manifest va R2 media obyektlarini
   o‘chirmang — ular dalil va idempotent retry uchun kerak. **do not delete**.
6. Muammoni tuzating. Agar v1656 write qayta yoqilsa, keyingi urinish uchun
   **yangi final snapshot va yangi V8 staging rehearsal** oling.

## Rollback — public trafik ochilgandan keyin

Yangi modular tizim public bo‘lgach, eski monolithga ko‘r-ko‘rona qaytish mumkin
emas: modular bazaga yangi foydalanuvchi yozuvlari tushgan bo‘lishi mumkin.

1. Avval yangi modular write’larni ham maintenance bilan to‘xtating.
2. Cutoverdan keyin yaratilgan/o‘zgargan yozuvlarni aniqlang va reconciliation
   rejasini bajaring.
3. Faqat yangi yozuvlar yo‘qolmasligi isbotlangandan keyin routingni v1656 ga
   qaytaring yoki candidate backupdan tiklang.

Hech bir rollback bosqichida foydalanuvchi ma’lumoti, SQLite source, R2 media yoki
migration dalillari avtomatik o‘chirilmaydi.

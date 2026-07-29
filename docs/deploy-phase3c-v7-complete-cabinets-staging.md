# Phase 3C V7 — v1656 oddiy va biznes kabinetlarini stagingga ko‘chirish

## Maqsad

v1656 immutable snapshotidagi haqiqiy oddiy va biznes kabinetlarini yangi modulli tizimga to‘liq bog‘lash. Profilga tegishli mavjud ma’lumotlar kabinet bo‘limlarida saqlanadi; aniq demo/test belgili yozuvlar va maxfiy credential maydonlari chiqarib tashlanadi.

Logical migration schema:

```text
0006_phase3c_complete_cabinet_v1
```

Alembic head:

```text
0005_profile_cabinet_parity
```

## Ko‘chiriladigan oddiy kabinet ma’lumotlari

- profil va avatar kesimi;
- mutaxassislik/xizmat ma’lumotlari;
- buyurtmalar, order itemlari va order xabarlari;
- xizmat buyurtmalari;
- e’lonlar va media;
- istoriyalar;
- obunalar va obunachilar;
- saqlanganlar;
- bildirishnomalar va filtrlar;
- suhbatlar;
- to‘lov so‘rovlari, urinishlari va voqealari;
- haydovchilik profili;
- taxi/dostavka buyurtmalari;
- biznes kabinet bilan bog‘lanish.

## Ko‘chiriladigan biznes kabinet ma’lumotlari

- profil, logotip, xarita va ish vaqti;
- tovar/xizmat guruhlari va katalog;
- mahsulot va xizmat buyurtmalari, itemlar va xabarlar;
- e’lonlar va media;
- obunalar, to‘lovlar va tarix;
- reklama, istoriya, fikrlar va bildirishnomalar;
- suhbatlar, obunachilar va biznes obunalari;
- qarzdorlar va qarz tranzaksiyalari;
- ombor va ombor harakatlari;
- kassa, savdo va xarajatlar;
- xodimlar;
- biznes, kiruvchi, chiquvchi va ichki hujjatlar;
- kontragentlar;
- umumiy ovqatlanish stollari/xonalari va buyurtmalari;
- ta’lim guruhlari, o‘quvchilar va o‘qituvchilar;
- tibbiy navbat va qabullar.

## Qat’iy xavfsizlik qoidalari

- production va BUILD v1656 o‘zgartirilmaydi;
- `static/index.html` o‘zgartirilmaydi;
- explicit `is_demo`, `demo`, `is_test`, `test_mode` yoki `demo_mode` belgili yozuvlar kabinet payloadiga kiritilmaydi;
- parol hash, token hash, OTP/code hash, secret va private key maydonlari kabinet API javobiga kiritilmaydi;
- eski migration run qayta ishlatilmaydi;
- CI to‘liq yashil bo‘lmasdan staging yozuvchi run boshlanmaydi;
- staging PostgreSQL backup/snapshot olinmasdan `-Execute` ishlatilmaydi;
- production migratsiyasi alohida approval gatesiz bajarilmaydi.

## Dry-run

Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\Koprik-Phase3C-Complete-Cabinet-Staging-V7.ps1"
```

Dry-run faqat quyidagilarni tekshiradi:

- local arxiv SHA-256;
- remote muhit `staging` ekanligi;
- V7 kodi deploy qilinganligi;
- CLI mavjudligi;
- Alembic head `0005_profile_cabinet_parity` ekanligi;
- kabinet modullari va demo guard kodi mavjudligi.

Kutiladigan yakun:

```text
DRY_RUN_COMPLETE DATABASE_WRITES=0 FILE_UPLOADS=0
```

## Yozuvchi staging run

Backup tasdiqlangandan keyin:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\Koprik-Phase3C-Complete-Cabinet-Staging-V7.ps1" -Execute
```

Skript:

1. arxivni stagingga yuklaydi;
2. Alembic migrationni `head`gacha olib boradi;
3. immutable SQLite snapshot va media manifest yaratadi;
4. yangi V7 run ochadi;
5. barcha migratsiya bosqichlarini bajaradi;
6. verify gate’larni tekshiradi;
7. aynan shu snapshotni ikkinchi marta ishga tushirib idempotency’ni tekshiradi;
8. kamida 20 ta oddiy↔biznes profil linki mavjudligini tekshiradi.

## Majburiy verify gate’lar

- `mapping_coverage`;
- `catalog_kind_count`;
- `listing_count`;
- `advertisement_count`;
- `broken_foreign_keys=0`;
- `identity_conflicts=0`;
- `cabinet_demo_rows=0`;
- `cabinet_sensitive_fields=0`;
- `media_failed=0`;
- `media_terminal_count`;
- `copied_media_verification=0`;
- `idempotency=0`;
- `public_schema_leak=0`.

Kutiladigan yakuniy satr:

```text
PHASE3C_V7_STAGING_COMPLETE RUN_ID=<id>
```

## Smoke test

Bitta tasdiqlangan haqiqiy profil juftligida:

1. oddiy kabinetga kiriladi;
2. profil, e’lon, buyurtma, saqlangan, to‘lov, bildirishnoma va boshqa mavjud bo‘limlar tekshiriladi;
3. `Biznes kabinetga o‘tish` bosiladi;
4. qayta login qilmasdan biznes kabinet ochilishi tekshiriladi;
5. biznes profil, katalog, buyurtma, kassa, qarz, ombor, xodim va hujjat bo‘limlari tekshiriladi;
6. `Oddiy kabinet` bosilib ortga qaytish tekshiriladi;
7. demo/test yozuvlar yo‘qligi tasdiqlanadi.

## Rollback

Verify yoki smoke test muvaffaqiyatsiz bo‘lsa:

- production migratsiyasi boshlanmaydi;
- staging deploy oldingi revisionga qaytariladi;
- V7 run production approval sifatida ishlatilmaydi;
- PostgreSQL migratsiyadan oldingi backupdan tiklanadi;
- immutable source snapshot o‘zgartirilmaydi;
- sabab read-only diagnostika bilan tekshiriladi.

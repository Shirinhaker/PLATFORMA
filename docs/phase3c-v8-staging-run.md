# Phase 3C V8 — birinchi haqiqiy staging runi

**Sana:** 2026-08-11
**Natija:** `PHASE3C_V8_STAGING_COMPLETE RUN_ID=1` — 16 tadan 16 ta gate yashil.

## Nega bu hujjat kerak

PR #122 V8 yo'lini yozgan, lekin tavsifida ochiq aytilgan: *«No staging or
production database migration was executed»*. Ya'ni yo'l **yozilgan, lekin
yurilmagan**. 762 ta test o'tgan, chunki ularning birortasi ham haqiqiy
0005 importini ishlatmagan.

Birinchi marta yurganda **yettita to'siq** chiqdi. Hech biri testlar bilan
ushlanmagan edi, chunki hech biri kodning o'zida emas — kod bilan muhit
orasidagi mosligida.

## Muhit

Ish yangi, ajratilgan qum qutida bajarildi:

| Nima | Qiymat |
|---|---|
| Baza | `Postgres-v8-migration` (yangi, bo'sh) |
| Servis | `api-v8-migration` |
| SSH aliasi | `koprik-api-migration-staging` |
| Alembic boshlanish | `0005_profile_cabinet_parity` |
| Alembic yakun | `0041_taxi_driver_domain` |

Jonli `koprik.uz` va mavjud staging bazasiga **tegilmadi**.

Sirlar (OTP, CSRF, outbox kaliti) qum quti uchun **yangi tasodifiy**
qiymatlar bilan berildi — real tizimga sessiya ochib bo'lmaydi. R2 va
Telegram kalitlari `${{api-staging.…}}` havolasi orqali, ya'ni qiymatlari
hech qayerga yozilmadi.

## Topilgan va tuzatilgan to'siqlar

### 1. CRLF — skript masofada umuman ishlamas edi

`Invoke-RemoteBash` bash matnini Windows qatr tugatuvchisi bilan uzatardi.
Masofaviy bash `pipefail\r` ni ko'rib to'xtardi:

```
bash: line 1: set: pipefail: invalid option name
```

Tuzatildi: matn uzatishdan oldin LF ga keltiriladi.

### 2. Ustun shimi chala edi

Bazaviy import 0005 sxemasida bajariladi, lekin uni bajaradigan kod
bugungi modellarga tayanadi. SQLAlchemy INSERT'ga mapperdagi **barcha**
ustunlarni nomlaydi, shuning uchun 0005 da mavjud bo'lmagan har bir ustun
importni yiqitadi.

Skriptda bu naqsh allaqachon bor edi (`specialist_rating_*`, 0032 dan),
lekin `public_id` (0010) va `business_profiles` hisobga olinmagan edi.

Qo'shildi. Xavfsiz, chunki `public_id` — `blake2s(kind:account_id)` xeshi:
0010 migratsiyasi uni **aynan o'sha qiymat bilan** qayta yaratadi.

### 3. Modellar to'liq yuklanmasdi

Migratsiya CLI'si 94 ta jadvaldan atigi 26 tasini yuklardi, natijada
domenlararo tashqi kalitlar yechilmasdi:

```
NoReferencedTableError: Foreign key associated with column
'stories.created_by_staff_id' could not find table 'staff_members'
```

Ilovada ko'rinmaydi, chunki `app.main` hammasini import qiladi.

Yechim: `app/db/all_models.py` — barcha model modullari bitta joyda.

### 4. `migrations/env.py` da uchta model yetishmasdi

`cabinet_records`, `outbox`, `taxi` — alembic autogenerate ularni
"o'chirilgan jadval" deb hisoblab, o'chirish migratsiyasini yozib qo'yishi
mumkin edi. Qo'shildi.

### 5. Demo yozuvlar chetlanmagan edi

Batafsil quyida.

### 6. `__main__` bloki yo'q edi

`demo_prune` moduli `main()` ni e'lon qilardi, lekin uni chaqiradigan blok
yo'q edi. `python -m` buyrug'i **muvaffaqiyatli tugab, hech narsa
qilmasdi** — eng yomon turdagi xato. Modulni buyruq sifatida ishga
tushiradigan testlar qo'shildi.

### 7. `assert links >= 20` eskirgan chegara

Bu raqam demo yozuvlar ham ko'chirilgan davrga moslangan edi. Demo
chiqarilgach real biznes 3 ta bo'lib qoldi.

O'rniga aniq moslik tekshiriladi:

```python
assert links == businesses
assert 0 < linked_users <= businesses
```

Bu **kuchliroq**: eski shart 25 ta biznesdan 5 tasi bog'lanmagan bo'lsa
ham o'tib ketardi.

## Demo yozuvlarni chetlash — egasining qarori

v1656 bazasida namoyish uchun yaratilgan yozuvlar bor edi. Ular yangi
platformaga ko'chirilmaydi.

**Qoida:** login prefiksi `demo_v1616_`. U 4 ta real foydalanuvchini
(`user905189`, `user354463`, `user546054`, `user402728`) 20 ta demodan
toza ajratadi.

**Qayerda bajariladi:** arxivdan chiqarilgan **vaqtinchalik nusxada**,
snapshot olinishidan oldin. Jonli v1656 bazasiga tegilmaydi. Snapshot
tozalangan ma'lumotdan olingani uchun barmoq izi va barcha gate sanoqlari
o'z-o'zidan mos bo'ladi.

**Qo'riqchi:** Telegram raqami bog'langan akkaunt hech qachon demo deb
hisoblanmaydi. Prefiks xato bo'lsa amal to'xtaydi va **hech narsa
o'chmaydi** (`PruneAbort`). Bu oqimdagi yagona o'chiruvchi qadam bo'lgani
uchun testlar avvalo "nima o'chmasligi kerak" ni tekshiradi.

**Chetlangan:** 20 foydalanuvchi, 20 biznes, 20 obuna, 10 e'lon,
10 mahsulot.

## Yakuniy solishtirish

| Nima | Manba | Yangi |
|---|---|---|
| Foydalanuvchi | 4 | 4 |
| Biznes | 3 | 3 |
| E'lon | 6 | 6 |
| Reklama | 6 | 6 |
| Istoriya | 2 | 2 |
| Xodim | 2 | 2 |
| AI xabari | 24 | 24 |
| Haydovchi | 1 | 1 |
| Kassa | 66 savdo | 35 chek + 66 qator |

## Ochiq muammo: katalog ikkilanmoqda

Run yashil tugadi, lekin gate'lar sezmagan nuqson bor:

```
ingliz tili    service  biz=5  run=1      ← eski import
ingliz tili    service  biz=5  run=None   ← 0007 backfill
```

3 ta xizmat → 6 ta yozuv. Bir xil ma'lumotni ikki yo'l yaratadi:
`0007_catalog_live_sync` migratsiyasi (`cabinet_payload` dan) va eski
import CATALOG bosqichi (snapshot'dan).

**Nega gate sezmadi:** `catalog_kind_count` faqat
`migration_run_id == run.id` bo'lgan qatorlarni sanaydi, backfill
yaratganlari (`run=None`) uning ko'zidan yashirin.

Bildirishnomalarda ham shu naqsh shubhasi bor: manbada 84, yangi bazada
132.

**Bu tuzatilmaguncha produksiyaga o'tilmaydi.** Gate ham tuzatilishi
kerak — jami sanashi shart, aks holda nuqson yana yashirinadi.

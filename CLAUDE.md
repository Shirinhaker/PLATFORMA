# PLATFORMA — loyiha qoidalari

## Faol arxitektura

Production kod faqat modular arxitekturada saqlanadi:

- **Backend**: FastAPI, `backend/app/`
- **Database**: PostgreSQL + Alembic, `backend/migrations/`
- **Worker**: `backend/app/outbox/`
- **Frontend**: React + TypeScript + Vite, `frontend/`
- **Infra**: `compose.yaml` va `infra/`

Eski v1656 monolit source/UI active branchdan olib tashlangan.
Cutover paytidagi to'liq nusxa:
`archive/legacy-v1656-production-cutover`.

## Qat'iy qoida

Rootga `main.py`, `api.py`, `database.py`, `static/`, `admin/` yoki boshqa
v1656 runtime fayllarini qayta qo'shmang. Zarur tarixiy tekshiruv archive
branch yoki `docs/` dagi migratsiya dalillari orqali qilinadi.

## Kod tuzilishi qoidalari

Bu qoidalar avtomatik tekshiriladi — eslab qolish shart emas, CI aytadi.

### 1. Bitta fayl 500 qatordan oshmasin

Oshsa, uni papkaga bo'ling va eski fayl faqat qayta-eksport qilsin:

```ts
// api/types.ts
export * from "./types/orders";
export * from "./types/education";
```

Shunda chaqiruv joylari umuman o'zgarmaydi.

```
python scripts/check_file_length.py            # tekshirish
python scripts/check_file_length.py --report   # hozirgi holat
python scripts/check_file_length.py --update   # fayl bo'lingandan keyin
```

Hozirgi qarz `scripts/file_length_baseline.py` da. U **faqat kamayadi**:
yangi katta fayl qo'shib bo'lmaydi, ro'yxatdagi fayl o'sa olmaydi.

### 2. `router.py` da biznes-mantiq bo'lmasin

`router.py` — faqat HTTP: yo'l, sxema, huquq tekshiruvi, `service` chaqiruvi.
Hisob-kitob, shart va tranzaksiya — `service.py` da. SQL — `repository.py` da.

### 3. Nomga versiya qo'shimchasi yozilmasin

`V2`, `V3`, `_new`, `_old`, `Final` — taqiqlanadi. Ular oy o'tib ma'nosini
yo'qotadi va "qaysi biri ishlaydi?" degan savol tug'diradi. Nom nima
qilishini aytsin: `BusinessProfileEditor`, `BusinessProfileEditorV2` emas.

> **Istisno:** CSS klass nomlaridagi `v1656`. Ular eski tizim bilan
> ko'rinish mosligini ta'minlaydi — o'zgartirilsa sayt buziladi
> (bir marta buzilgan, PR #182 da orqaga qaytarilgan).

### 4. `app/legacy_migration/` dan import qilmang

Bu paket — v1656 dan bir martalik ko'chirish. Jonli kod unga bog'lanmasin.
Umumiy narsa kerak bo'lsa `app/core/` ga chiqaring.
`tests/test_legacy_migration_boundary.py` buni tekshiradi.

## Testlar

PR yuborishdan oldin:

- `cd backend && python -m pytest tests -q`
- `cd frontend && npm test`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `python scripts/check_file_length.py`

Testni shunchaki yashil qilish uchun `skip`/`todo` ishlatilmaydi.
Faol modular funksiyaning qoplamasi olib tashlanmaydi.

## Ish uslubi

- Har bir ish alohida branchda.
- `main` ga faqat PR orqali.
- Ishlayotgan modular funksiyalarga aloqasiz o'zgarish kiritmang.
- API kalit, token, parol va boshqa maxfiy qiymatlarni repoga yozmang.
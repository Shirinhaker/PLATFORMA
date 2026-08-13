# PLATFORMA вЂ” loyiha qoidalari

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

## Testlar

PR yuborishdan oldin:

- `cd backend && python -m pytest tests -q`
- `cd frontend && npm test`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`

Testni shunchaki yashil qilish uchun `skip`/`todo` ishlatilmaydi.
Faol modular funksiyaning qoplamasi olib tashlanmaydi.

## Ish uslubi

- Har bir ish alohida branchda.
- `main` ga faqat PR orqali.
- Ishlayotgan modular funksiyalarga aloqasiz o'zgarish kiritmang.
- API kalit, token, parol va boshqa maxfiy qiymatlarni repoga yozmang.
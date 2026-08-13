# PLATFORMA / Koprik

Active production repository modular arxitekturaga o'tgan.

## Tuzilma

- `backend/` вЂ” FastAPI modular API, worker va PostgreSQL migratsiyalari
- `frontend/` вЂ” React + TypeScript + Vite
- `infra/` вЂ” deployment/infra konfiguratsiyasi
- `docs/` вЂ” migratsiya va production cutover dalillari
- `compose.yaml` вЂ” local PostgreSQL + Redis + API + worker

## Legacy v1656

Eski monolit productiondan chiqarilgan va active branchdan olib tashlangan.
Cutover paytidagi to'liq etalon nusxa Git tarixida
`archive/legacy-v1656-production-cutover` branchida saqlanadi.

Active branchga v1656 root runtime/UI fayllarini qayta qo'shmang.
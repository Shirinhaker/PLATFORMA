# PLATFORMA / Koprik

Active production repository modular arxitekturaga o'tgan.

> **Loyihaga yangi kelgan bo'lsangiz — [`ARCHITECTURE.md`](./ARCHITECTURE.md) ni o'qing.**
> U yerda so'rov oqimi, 38 ta backend moduli, frontend xaritasi va tuzoqlar bor.

## Tuzilma

- `backend/` — FastAPI modular API, worker va PostgreSQL migratsiyalari
- `frontend/` — React + TypeScript + Vite
- `infra/` — deployment/infra konfiguratsiyasi
- `docs/` — migratsiya va production cutover dalillari
- `compose.yaml` — local PostgreSQL + Redis + API + worker

## Legacy v1656

Eski monolit productiondan chiqarilgan va active branchdan olib tashlangan.
Cutover paytidagi to'liq etalon nusxa Git tarixida
`archive/legacy-v1656-production-cutover` branchida saqlanadi.

Active branchga v1656 root runtime/UI fayllarini qayta qo'shmang.
# Frontend Staging Deploy

## O‘zgarmaydigan production

- `web` va `koprik.uz`ga tegmang.
- `worker-staging`ga public domain yaratmang.
- `api-staging`ning mavjud domenini o‘chirmang.

## Frontend service

1. GitHub repo: `Shirinhaker/PLATFORMA`
2. Branch: `main`
3. Root Directory: `/frontend`
4. Build Command: `npm ci && npm run build`
5. Start Command:
   `/bin/sh -c "exec npm run preview -- --host 0.0.0.0 --port $PORT"`
6. Variable:
   `VITE_API_BASE_URL=https://platforma-production-f753.up.railway.app`
7. Healthcheck Path: `/`
8. Public domain target port: `8080`

## CORS

Frontend domeni yaratilgach, uning to‘liq `https://...` origin qiymatini
`api-staging` servisidagi `KOPRIK_CORS_ORIGINS`ga yozing va faqat
`api-staging`ni qayta deploy qiling.

## Acceptance

- frontend deployment `ACTIVE`;
- foundation sahifasi ochiladi;
- `API v1`, `Phase 1`, `Eski faol BUILD: v1656` ko‘rinadi;
- browser console’da CORS xatosi yo‘q;
- `/healthz` status `ok`;
- `/readyz` status `ready`, database/redis/r2 qiymatlari `true`;
- `web`, `worker-staging`, PostgreSQL va Redis Online.

## Rollback

1. `api-staging`ni oldingi muvaffaqiyatli deploymentga rollback qiling.
2. `frontend-staging`ni vaqtincha o‘chiring yoki oldingi deploymentga qaytaring.
3. `web` va `koprik.uz`ni o‘zgartirmang.

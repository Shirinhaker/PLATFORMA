# Phase 1 Foundation Verification

Tekshiruv sanasi: 2026-07-26  
Branch: `codex/koprik-phase1-foundation`

## Tasdiqlangan natijalar

- Legacy BUILD: `v1656`
- Legacy frontend qatorlar soni: `14091`
- Legacy inventory contract: **PASS**
- Legacy Python testlari: **415 PASS**
- Brauzersiz legacy UI smoke-testlar: **3 PASS**
- Backend unit testlari: **6 PASS**
- Frontend testlari: **2 PASS**
- Frontend TypeScript va Vite production build: **PASS**
- Alembic PostgreSQL offline SQL generatsiyasi: **PASS**
- Redis atomik distributed rate-limit testi: **PASS**
- R2 presigned upload validatsiyasi: **PASS**
- Railway API va worker konfiguratsiyasi: **CREATED**
- Production trafik yangi backendga o‘tkazildi: **NO**
- Legacy SQLite runtime kodi o‘zgartirildi: **NO**
- Legacy upload runtime kodi o‘zgartirildi: **NO**
- `static/index.html` o‘zgartirildi: **NO**

## Railway yoki Docker muhitida bajarilishi shart

Joriy ish muhitida Docker, PostgreSQL, Redis va tizim Chromium’i mavjud emas.
Cloud browser esa lokal preview manzilini blokladi. Shu sabab quyidagi bandlar
o‘tgan deb belgilanmadi:

- PostgreSQL migration `up/down/up`: **PENDING**
- PostgreSQL pool va `/readyz` real ulanish testi: **PENDING**
- Outbox `FOR UPDATE SKIP LOCKED` eksklyuzivlik testi: **PENDING**
- API va worker alohida process/container testi: **PENDING**
- Redis real service readiness testi: **PENDING**
- React desktop va mobile screenshot taqqoslash: **PENDING**
- Story va subscription Chromium smoke-testlari: **PENDING**
- Phase 1 GitHub Actions yakuniy holati: **PENDING**

Bu bandlar muvaffaqiyatli tugamaguncha Phase 1 production acceptance yakunlangan
hisoblanmaydi va production trafik o‘zgartirilmaydi.

## Railway acceptance ketma-ketligi

1. PostgreSQL, Redis va R2 staging servislarini sozlash.
2. `backend/` ichida `python -m alembic upgrade head` bajarish.
3. Phase 1 CI workflow’ni ishga tushirish.
4. `/healthz`, `/readyz` va `/api/v1/build` endpointlarini tekshirish.
5. API va worker’ni alohida Railway servislarida ishga tushirish.
6. Outbox eksklyuzivlik testini real PostgreSQL’da bajarish.
7. React preview’ni desktop va mobile o‘lchamlarda tekshirish.
8. Barcha bandlar o‘tgandan keyingina Phase 1’ni production uchun qabul qilish.

## Phase 2 uchun shartlar

- PostgreSQL va Redis staging private URL’lari sozlangan.
- R2 staging bucket va cheklangan API credential’lari sozlangan.
- v1656 inventory snapshot commit qilingan.
- Phase 1 CI yashil.
- Yuqoridagi barcha `PENDING` acceptance bandlari `PASS`.
- Shundan keyin production trafikni o‘zgartirmasdan SQLite schema mapping va
  migratsiya harnessini yaratish boshlanadi.

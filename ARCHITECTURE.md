# PLATFORMA / Koprik — arxitektura xaritasi

> Bu hujjat loyihaga birinchi marta kirgan dasturchi uchun. Bir marta o'qib chiqsangiz,
> istalgan faylni qayerdan izlashni bilasiz.
> Holat: `main` branch, 2026-08-15 (commit `4b508fb`).

---

## 1. 30 soniyalik xulosa

Koprik — mahalliy biznes-platforma: e'lonlar, katalog, buyurtmalar, navbatlar, taksi,
ta'lim markazlari, ombor/kassa, to'lovlar va admin panel bitta tizimda.

| | |
|---|---|
| **Backend** | Python 3.12, FastAPI, to'liq async |
| **DB** | PostgreSQL + SQLAlchemy 2.0 (asyncio) + Alembic (44 migratsiya) |
| **Cache / navbat** | Redis |
| **Fayl saqlash** | Cloudflare R2 (S3-mos, `boto3`) |
| **Frontend** | React 19 + TypeScript + Vite |
| **Deploy** | Docker, `compose.yaml`, Railway (`infra/railway`) |
| **Hajm** | backend ~102k qator (454 fayl), frontend ~60k qator (219 fayl) |
| **API** | 271 ta endpoint, hammasi `/api/v1/...` ostida |
| **Testlar** | backend 136 test fayli (pytest), frontend vitest |

---

## 2. Repozitoriya xaritasi

```
PLATFORMA/
├── backend/
│   ├── app/                  ← BUTUN BACKEND KODI SHU YERDA
│   │   ├── main.py           ← kirish nuqtasi: barcha service'lar shu yerda ulanadi
│   │   ├── core/             ← config, xatolar, logging, middleware
│   │   ├── db/               ← DB sessiya, Base, all_models
│   │   ├── cache/            ← Redis client, rate limit
│   │   ├── outbox/           ← fon worker (outbox pattern)
│   │   └── <domen>/          ← 38 ta biznes-domen moduli (pastda ro'yxat)
│   ├── migrations/versions/  ← 44 ta Alembic migratsiyasi (0001…0044)
│   ├── tests/                ← 136 test fayli
│   └── pyproject.toml        ← bog'liqliklar, pytest sozlamalari
├── frontend/
│   └── src/                  ← BUTUN FRONTEND KODI
│       ├── main.tsx          ← kirish nuqtasi
│       ├── app/              ← App.tsx, AppShell, routing, design-tokens.css
│       ├── api/              ← client.ts + types.ts (backend bilan yagona aloqa nuqtasi)
│       └── <domen>/          ← ekranlar, domen bo'yicha
├── infra/railway/            ← deploy konfiguratsiyasi
├── docs/superpowers/plans/   ← har bir feature bo'yicha reja hujjatlari
├── scripts/
├── compose.yaml              ← lokal: PostgreSQL + Redis + API + worker
└── CLAUDE.md                 ← loyiha qoidalari (o'qing!)
```

---

## 3. So'rov qanday oqadi (eng muhim qism)

```
Brauzer
   │
   │  HTTP  /api/v1/orders/...
   ▼
┌──────────────────────────────────────────────────────────┐
│ main.py                                                  │
│  · CORSMiddleware                                        │
│  · RequestIdMiddleware        (core/middleware.py)        │
│  · lifespan → app.state.* ga barcha service'ni yaratadi   │
└──────────────────────────────────────────────────────────┘
   ▼
router.py      ← HTTP qatlami. Faqat: validatsiya + service chaqirish.
   │             Biznes-mantiq YO'Q. Kirish/chiqish — Pydantic schemas.
   ▼
service.py     ← BIZNES-MANTIQ. Qoidalar, huquqlar, hisob-kitob, tranzaksiya.
   │             Bu yerda SQL yozilmaydi.
   ▼
repository.py  ← FAQAT DB. SQLAlchemy so'rovlari, boshqa hech narsa.
   ▼
PostgreSQL     ← jadval ta'riflari: model.py (SQLAlchemy), app/db/all_models.py da yig'iladi
```

Yon oqim — fon vazifalari:

```
service.py → outbox jadvaliga yozadi → outbox/worker.py o'qiydi
                                          → notifications/push_worker.py
                                          → Firebase push / Telegram
```

**Xotirada tuting:** service obyektlari `main.py`ning `lifespan` funksiyasida bir marta
yaratilib, `app.state.<nom>_service` ga qo'yiladi. Router ularni `request.app.state`
orqali oladi. Shuning uchun `main.py` uzun (359 qator) — bu tizimning "elektr shchiti".

---

## 4. Bitta modul qanday tuzilgan

Har bir domen moduli bir xil 5 ta fayldan iborat. Bittasini tushunsangiz — 38 tasini tushunasiz:

| Fayl | Vazifasi | Nima YOZILMAYDI |
|---|---|---|
| `router.py` | HTTP endpointlar, URL prefiksi | biznes-mantiq, SQL |
| `schemas.py` | Pydantic — so'rov/javob shakllari | mantiq |
| `service.py` | biznes qoidalari, huquqlar, oqim | to'g'ridan-to'g'ri SQL |
| `repository.py` | SQLAlchemy so'rovlari | biznes qoidalari |
| `model.py` | jadval ta'riflari (SQLAlchemy) | mantiq |

Namuna sifatida `app/catalog/` ni o'qing — eng toza modul (955 qator, 8 fayl).

---

## 5. Backend modullari ro'yxati

Chapdagi jadval — "menga X kerak bo'lsa qaysi papkani ochaman" savoliga javob.

<!-- STATS:boshlanish backend/app -->

### Ommaviy qism (login talab qilinmaydi)

| Modul | URL prefiksi | Qator | Nima qiladi |
|---|---|---|---|
| `platform` | `/` | 55 | healthcheck, versiya, umumiy ma'lumot |
| `public_discovery` | `/api/v1/public` | 2 325 | ommaviy qidiruv va kashfiyot |
| `catalog` | `/api/v1/public/catalog` | 938 | mahsulot/xizmatlar katalogi |
| `advertisements` | `/api/v1/public`, `/advertisements` | 1 545 | reklama e'lonlari + narxlash |
| `listings` | `/api/v1` | 1 353 | e'lonlar, aktivatsiya |
| `stories` | `/api/v1/stories` | 1 633 | stories (video/rasm), processor |
| `media` | `/api/v1/media` | 450 | R2 ga yuklash, download URL |

### Foydalanuvchi va profil

| Modul | URL prefiksi | Qator | Nima qiladi |
|---|---|---|---|
| `auth` | `/api/v1/auth` | 2 367 | Telegram auth, sessiya, xavfsizlik, shared login |
| `accounts` | — | 128 | account modeli (router yo'q) |
| `profiles` | `/api/v1` | 1 205 | foydalanuvchi/biznes profillari |
| `account_settings` | `/api/v1/account-settings` | 266 | sozlamalar |
| `follows` | `/api/v1/follows` | 599 | obuna, kuzatuvchilar |
| `messages` | `/api/v1/messages` | 1 143 | xabarlar |
| `reviews` | `/api/v1/reviews` | 833 | sharhlar, reyting |
| `notifications` | `/api/v1/notifications` | 2 227 | bildirishnomalar + push worker |

### Biznes kabineti

| Modul | URL prefiksi | Qator | Nima qiladi |
|---|---|---|---|
| `business_opening` | `/api/v1/business-opening` | 278 | biznes ochish oqimi |
| `business_online` | `/api/v1/business-online` | 3 764 | biznes onlayn vitrinasi ⚠️ |
| `orders` | `/api/v1/orders` | 2 656 | buyurtmalar, status, bildirishnoma |
| `queues` | `/api/v1/queues` | 2 893 | elektron navbat |
| `dining` | `/api/v1/dining` | 2 313 | umumiy ovqatlanish (menyu, stol) |
| `specialists` | `/api/v1/specialists` | 1 038 | mutaxassislar, bandlik |
| `staff` | `/api/v1` | 1 820 | xodimlar, ruxsatlar (`permissions.py`) |
| `inventory` | `/api/v1/warehouse` | 2 272 | ombor |
| `cash_register` | `/api/v1/cash-register` | 1 360 | kassa |
| `debt_ledger` | `/api/v1/debt-ledger` | 907 | qarzlar daftari |
| `expenses` | `/api/v1/expenses` | 679 | xarajatlar |
| `statistics` | `/api/v1/statistics` | 935 | biznes statistikasi |
| `documents` | `/api/v1/documents` | 1 252 | hujjatlar |
| `education` | `/api/v1/education` | 6 053 | ta'lim markazlari ⚠️ (eng katta modul) |
| `taxi` | `/api/v1/taxi` | 1 669 | taksi |
| `ai_assistant` | `/api/v1/ai-assistant` | 1 141 | AI yordamchi |
| `cabinet_records` | — | 1 631 | kabinet yozuvlari (dual-write, codec) |

### To'lov va admin

| Modul | URL prefiksi | Qator | Nima qiladi |
|---|---|---|---|
| `payments` | `/api/v1/payments` | 1 351 | to'lovlar, obunalar |
| `admin` | `/api/v1/admin`, `/reports` | 2 880 | admin panel, moderatsiya, audit, hisobotlar |

### Infratuzilma (biznes-mantiq emas)

| Modul | Qator | Nima qiladi |
|---|---|---|
| `core` | 325 | `config.py`, `errors.py` (ApiError), `logging.py`, `middleware.py` |
| `db` | 116 | sessiya, `Base`, `all_models.py` |
| `cache` | 81 | Redis client, rate limit |
| `outbox` | 413 | outbox jadvali + fon worker |
| `legacy_migration` | 7 812 | eski v1656 tizimidan ma'lumot ko'chirish ⚠️ |

<!-- STATS:tugadi -->

---

## 6. Ma'lumotlar bazasi

- Barcha jadvallar `app/<modul>/model.py` da, `app/db/all_models.py` da import qilinadi.
- Migratsiyalar: `backend/migrations/versions/0001_foundation.py` dan `0044_media_upload_grants.py` gacha,
  nomlari domen bo'yicha o'qiladi (`0025_dining_domain`, `0038_documents_domain`, ...).
- Yangi migratsiya: `cd backend && alembic revision -m "..."` → `alembic upgrade head`.
- **Migratsiya tarixi = loyiha tarixi.** Domen qachon qo'shilganini bilish uchun shu ro'yxatni o'qing.

---

## 7. Frontend xaritasi

```
src/
├── main.tsx                  ← kirish
├── app/
│   ├── App.tsx               ← 29k — asosiy router/holat
│   ├── AppShell.tsx          ← umumiy karkas
│   ├── entry-routing.ts      ← URL → ekran
│   └── design-tokens.css     ← ranglar, o'lchamlar (bu yerdan boshlang)
├── api/
│   ├── client.ts             ← 53k — BARCHA backend chaqiruvlari ⚠️
│   ├── types.ts              ← 44k — backend javob tiplari
│   └── runtime-base-url.ts   ← API manzilini aniqlash
└── <domen>/                  ← backend modullariga mos ekranlar
```

Domen papkalari va hajmi:

<!-- STATS:boshlanish frontend/src -->

| Papka | Qator | Papka | Qator |
|---|---|---|---|
| `profiles` | 33 982⚠️ | `orders` | 4 963 |
| `legacy/public` | 9 116⚠️ | `dining` | 2 323 |
| `api` | 6 467 | `listings` | 2 787 |
| `admin` | 3 848 | `taxi` | 2 703 |
| `app` | 3 732 | `queues` | 1 802 |
| `auth` | 1 623 | `education` | 4 069 |
| `documents` | 2 080 | `messages` | 1 451 |
| qolganlari | har biri < 1 000 | | |

<!-- STATS:tugadi -->

---

## 8. Ishga tushirish

```bash
# Hammasi birdan (PostgreSQL + Redis + API + worker)
docker compose up

# Backend testlari
cd backend && python -m pytest tests -q

# Frontend
cd frontend && npm install && npm run dev
cd frontend && npm test
cd frontend && npx tsc --noEmit
cd frontend && npm run build
```

`.env.example` dan nusxa oling → `.env`. Production namunasi: `.env.production.example`.

**PR yuborishdan oldin to'rttasi ham yashil bo'lishi shart** (`CLAUDE.md` qoidasi).

---

## 9. ⚠️ Tuzoqlar — bilmasangiz vaqt yo'qotasiz

1. **`business_online` da ikkita xizmat bor — ikkalasi ham tirik.**
   `service.py` → `BusinessOnlineService`: **asosiy**, relatsion jadvallarga yozadi.
   `payload_service.py` → `BusinessOnlinePayloadService`: eski JSON `cabinet_payload`
   yo'li, hali ko'chirilmagan bo'limlar uchun zaxira. `service.py` kerak bo'lganda
   o'ziga chaqiradi. Yangi funksiya **faqat** `service.py` ga yoziladi.

   > Ilgari ikkala fayldagi klass nomi bir xil edi va `main.py` bilan `router.py`
   > har xilini ishlatardi. Bosqich 2 da tuzatildi.

2. **`v1656` = eski tizim bilan bir xillik, versiya raqami emas.**
   v1656 — production'dan chiqarilgan eski monolit. Fayl nomlaridagi `V1656`
   qo'shimchasi olib tashlangan, lekin **CSS klass nomlaridagi `v1656` ataylab
   qoldirilgan** — ularni o'zgartirish saytning ko'rinishini buzadi (bir marta
   buzgan, PR #182 da orqaga qaytarilgan).

3. **`legacy_migration` dan import qilmang.**
   Bu paket — v1656 dan bir martalik ko'chirish. Umumiy narsalar undan chiqarildi:
   `ReviewState`/`OwnerState` → `app/core/enums.py`, eski parol tekshiruvi →
   `app/auth/legacy_passwords.py`. Qolgan 4 ta bog'liqlik haqli va
   `tests/test_legacy_migration_boundary.py` da sabab bilan ro'yxatga olingan.
   Yangi import qo'shsangiz, o'sha test sizni to'xtatadi.

4. **Ulkan fayllar bo'lindi, lekin hammasi emas.**
   `api/types.ts`, `BusinessOnlineViews.tsx`, `EducationManagement.tsx` va boshqalar
   papkaga bo'lingan — eski fayl endi faqat `export * from "./..."` qiladi, ya'ni
   chaqiruv joylari o'zgarmagan. Qaysi fayllar hali katta ekanini
   `python scripts/check_file_length.py` ko'rsatadi.

5. **`docs/superpowers/plans/`** — har bir feature bo'yicha reja hujjati bor.
   "Bu nega shunday qilingan?" degan savolga javob shu yerda.

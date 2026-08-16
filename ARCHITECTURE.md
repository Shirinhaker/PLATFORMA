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

### Ommaviy qism (login talab qilinmaydi)

| Modul | URL prefiksi | Qator | Nima qiladi |
|---|---|---|---|
| `platform` | `/` | 59 | healthcheck, versiya, umumiy ma'lumot |
| `public_discovery` | `/api/v1/public` | 2 094 | ommaviy qidiruv va kashfiyot |
| `catalog` | `/api/v1/public/catalog` | 955 | mahsulot/xizmatlar katalogi |
| `advertisements` | `/api/v1/public`, `/advertisements` | 1 446 | reklama e'lonlari + narxlash |
| `listings` | `/api/v1` | 1 307 | e'lonlar, aktivatsiya |
| `stories` | `/api/v1/stories` | 1 530 | stories (video/rasm), processor |
| `media` | `/api/v1/media` | 406 | R2 ga yuklash, download URL |

### Foydalanuvchi va profil

| Modul | URL prefiksi | Qator | Nima qiladi |
|---|---|---|---|
| `auth` | `/api/v1/auth` | 2 133 | Telegram auth, sessiya, xavfsizlik, shared login |
| `accounts` | — | 129 | account modeli (router yo'q) |
| `profiles` | `/api/v1` | 1 236 | foydalanuvchi/biznes profillari |
| `account_settings` | `/api/v1/account-settings` | 268 | sozlamalar |
| `follows` | `/api/v1/follows` | 601 | obuna, kuzatuvchilar |
| `messages` | `/api/v1/messages` | 1 131 | xabarlar |
| `reviews` | `/api/v1/reviews` | 825 | sharhlar, reyting |
| `notifications` | `/api/v1/notifications` | 1 990 | bildirishnomalar + push worker |

### Biznes kabineti

| Modul | URL prefiksi | Qator | Nima qiladi |
|---|---|---|---|
| `business_opening` | `/api/v1/business-opening` | 276 | biznes ochish oqimi |
| `business_online` | `/api/v1/business-online` | 3 261 | biznes onlayn vitrinasi ⚠️ |
| `orders` | `/api/v1/orders` | 2 143 | buyurtmalar, status, bildirishnoma |
| `queues` | `/api/v1/queues` | 2 542 | elektron navbat |
| `dining` | `/api/v1/dining` | 2 245 | umumiy ovqatlanish (menyu, stol) |
| `specialists` | `/api/v1/specialists` | 918 | mutaxassislar, bandlik |
| `staff` | `/api/v1` | 1 596 | xodimlar, ruxsatlar (`permissions.py`) |
| `inventory` | `/api/v1/warehouse` | 2 060 | ombor |
| `cash_register` | `/api/v1/cash-register` | 1 252 | kassa |
| `debt_ledger` | `/api/v1/debt-ledger` | 894 | qarzlar daftari |
| `expenses` | `/api/v1/expenses` | 669 | xarajatlar |
| `statistics` | `/api/v1/statistics` | 879 | biznes statistikasi |
| `documents` | `/api/v1/documents` | 1 135 | hujjatlar |
| `education` | `/api/v1/education` | 5 519 | ta'lim markazlari ⚠️ (eng katta modul) |
| `taxi` | `/api/v1/taxi` | 1 388 | taksi |
| `ai_assistant` | `/api/v1/ai-assistant` | 1 000 | AI yordamchi |
| `cabinet_records` | — | 1 609 | kabinet yozuvlari (dual-write, codec) |

### To'lov va admin

| Modul | URL prefiksi | Qator | Nima qiladi |
|---|---|---|---|
| `payments` | `/api/v1/payments` | 1 259 | to'lovlar, obunalar |
| `admin` | `/api/v1/admin`, `/reports` | 2 685 | admin panel, moderatsiya, audit, hisobotlar |

### Infratuzilma (biznes-mantiq emas)

| Modul | Qator | Nima qiladi |
|---|---|---|
| `core` | 239 | `config.py`, `errors.py` (ApiError), `logging.py`, `middleware.py` |
| `db` | 116 | sessiya, `Base`, `all_models.py` |
| `cache` | 73 | Redis client, rate limit |
| `outbox` | 421 | outbox jadvali + fon worker |
| `legacy_migration` | 7 533 | eski v1656 tizimidan ma'lumot ko'chirish ⚠️ |

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

| Papka | Qator | Papka | Qator |
|---|---|---|---|
| `profiles` | 28 036 ⚠️ | `orders` | 2 654 |
| `legacy/public` | 9 036 ⚠️ | `dining` | 2 388 |
| `api` | 6 222 | `listings` | 2 007 |
| `admin` | 3 733 | `taxi` | 1 935 |
| `app` | 2 806 | `queues` | 1 767 |
| `auth` | 1 583 | `education` | 1 387 |
| `documents` | 1 584 | `messages` | 1 106 |
| qolganlari | har biri < 1 000 | | |

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

1. **Ikkita `BusinessOnlineService` bor.**
   `business_online/service.py` (2 147 qator) va `business_online/service_relational.py` (1 114 qator) —
   klass nomi bir xil. `main.py` **`service_relational.py`** dagisini ishlatadi,
   `router.py` esa `service.py` dagisini import qiladi. Tahrirlashdan oldin qaysi biri
   ekanini tekshiring.

2. **`V1656` qo'shimchasi = eski tizim bilan bir xillik.**
   v1656 — production'dan chiqarilgan eski monolit. `*_v1656*` nomli fayllar o'sha
   tizim bilan xatti-harakat mosligini ta'minlaydi. Bu versiya raqami emas.

3. **Production kod `legacy_migration` dan import qiladi.**
   `catalog`, `advertisements`, `orders`, `auth`, `education` — hammasi
   `app.legacy_migration.*` ga bog'langan. Migratsiya papkasini o'chirsangiz,
   ishlayotgan kod sinadi.

4. **`profiles/` papkasida `BusinessProfile`, `BusinessProfileV2`, `BusinessProfileV3` bor.**
   Ishlaydigani — **V3**. `BusinessProfile.tsx` shunchaki V3 ga re-export.
   `BusinessProfileV2.tsx` — o'lik kod, hech qayerda import qilinmaydi.

5. **Frontend'ning barcha API chaqiruvlari bitta faylda** — `api/client.ts` (53 KB).
   Yangi endpoint qo'shsangiz, shu yerga va `api/types.ts` ga yoziladi.

6. **`docs/superpowers/plans/`** — har bir feature bo'yicha reja hujjati bor.
   "Bu nega shunday qilingan?" degan savolga javob shu yerda.

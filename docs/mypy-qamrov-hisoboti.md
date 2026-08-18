# Mypy qamrovi — 7-bosqich hisoboti

**Boshlangan:** 2026-08-18 · **Mypy:** `1.18.2` (qat'iy) ·
**Rejim:** `disallow_untyped_defs` hali **yoqilmagan** (u 7.2 da)

## Ishga tushirish

```
cd backend && python -m mypy app/core app/db app/cache app/outbox
```

CI shu buyruqni chaqiradi. **Yo'llar ro'yxati domen tozalangan sari
o'sadi** — shunda qamrov ortga qaytmaydi.

`pyproject.toml` dagi sozlama:

```toml
python_version = "3.12"
warn_unused_ignores = true
warn_redundant_casts = true
no_implicit_optional = true
exclude = ["migrations/", "app/legacy_migration/"]
```

`app/legacy_migration/` chetda: u bir martalik ko'chirish kodi va
7.2 da unga alohida yozma siyosat belgilanadi.

## Boshlang'ich holat

Butun `app/` bo'yicha: **225 ta xato, 87 faylda** (406 fayl tekshirildi).

Diqqat: bular **haqiqiy tur xatolari**, "annotatsiya yetishmayapti"
degani emas — `disallow_untyped_defs` hali yoqilmagan.

### Xato turlari

| Tur | Nechta | Nimani anglatadi |
|---|---:|---|
| `attr-defined` | 95 | mavjud bo'lmagan atribut |
| `arg-type` | 65 | argument turi mos emas |
| `assignment` | 20 | o'zlashtirishda tur mos emas |
| `union-attr` | 14 | `None` bo'lishi mumkin bo'lgan qiymatga murojaat |
| `call-overload` | 10 | chaqiruv hech bir imzoga tushmaydi |
| qolganlari | 21 | |

### Domen bo'yicha

| Domen | Xato | Domen | Xato |
|---|---:|---|---:|
| `public_discovery` | 22 | `taxi` | 6 |
| `notifications` | 14 | `messages` | 5 |
| `queues` | 11 | `inventory` | 5 |
| `payments` | 11 | `profiles` | 4 |
| `stories` | 10 | `catalog` | 3 |
| `education` | 10 | `ai_assistant` | 3 |
| `auth` | 10 | `admin` | 3 |
| `listings` | 8 | `staff` | 1 |
| `cash_register` | 8 | `documents` | 1 |
| `orders` | 7 | `dining` | 1 |

## Bajarilgan: 1-guruh — umumiy qatlam

`core`, `db`, `cache`, `outbox` — qolgan domenlar shularga tayanadi.

**5 ta xato, hammasi tuzatildi:**

| Fayl | Xato | Yechim |
|---|---|---|
| `listings/model.py` | `"FromClause" has no attribute "update"` | `Model.__table__.update()` → `update(Model)` |
| `catalog/model.py` | shu | shu |
| `cache/client.py` | `await` turi mos emas | `cast(Awaitable[bool], ...)` |
| `cache/rate_limit.py` | shu | `cast(Awaitable[tuple[int, int]], ...)` |
| `notifications/push_worker.py` | `firebase_admin` stubi yo'q | faqat shu kutubxona uchun override |

### Nima o'rganildi

**`__table__.update()`** — SQLAlchemy stublarida `__table__`
`FromClause` deb turlangan, unda `update()` yo'q. Ish vaqtida u `Table`,
shuning uchun kod ishlaydi. `update(Model)` — SQLAlchemy 2.0 ning
tavsiya etilgan shakli va to'g'ri turlanadi. Ya'ni bu "linterni
tinchlantirish" emas, kodni zamonaviylashtirish.

**redis-py** sync va async klientni **bitta klass** bilan tasvirlaydi,
shuning uchun `await client.ping()` `Awaitable[bool] | bool` beradi.
Bu kutubxonaning cheklovi; `cast` sababi bilan yozildi.

**`firebase_admin`** tur stublarini umuman tarqatmaydi. Bu bizning
kodimizdagi muammo emas, shuning uchun `ignore_missing_imports` faqat
shu modul uchun ochildi — global emas.

## Keyingi guruhlar

Jadvaldagi tartib bo'yicha, har biri alohida PR:

| Navbat | Domenlar | Xato |
|---:|---|---:|
| 2 | `auth`, `profiles` | 14 |
| 3 | `catalog`, `public_discovery`, `listings`, `advertisements` | 33 |
| 4 | `orders`, `payments`, `queues` | 29 |
| 5 | `dining`, `inventory`, `cash_register`, `documents`, `staff` | 16 |
| 6 | `education`, `specialists`, `taxi`, `messages`, `notifications`, `stories`, `admin`, `ai_assistant` | 51 |

Har bir guruh tugagach uning yo'li CI buyrug'iga qo'shiladi.

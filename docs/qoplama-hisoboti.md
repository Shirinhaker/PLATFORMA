# Backend test qoplamasi — o'lchov hisoboti

**Sana:** 2026-08-17 · **Commit:** `9734945` (PR #209 merge) · **Umumiy qoplama: 77.9%**

Bu hisobot **o'lchov** natijasi. Kod o'zgartirilmadi, yangi test yozilmadi.

## Nega o'lchandi

821 ta test yashil, lekin bu "hamma narsa sinovdan o'tdi" degani emas.
3.1 va 3.2 bosqichlarida 18 ta katta fayl paketlarga bo'lindi va
ko'chirilgan kodning qaysi qatorlari umuman ishga tushmagani noma'lum edi.

Bu ayniqsa 7-bosqich uchun muhim: o'sha yerda taxminan **310 ta
funksiyaga** tur qo'shiladi. Qaysilari sinovdan o'tmagani bilinmasa,
o'sha 310 tadan qaysi biri xavfli ekanini aytib bo'lmaydi.

## Qanday o'lchandi

```
cd backend
python -m pytest tests --cov=app --cov-report=term-missing
```

`pytest-cov` `backend/pyproject.toml` dagi `test` guruhiga qo'shildi.

## ⚠️ Bu raqamlar kam ko'rsatadi

Mahalliy ishga tushirishda **22 ta test o'tkazib yuborildi** — ular
haqiqiy PostgreSQL talab qiladi (`KOPRIK_TEST_DATABASE_URL`), o'lchov
qilingan mashinada esa Docker yo'q. CI'da bu testlar ishlaydi:
u yerda 842 ta test o'tadi, mahalliy esa 821 ta.

O'tkazib yuborilganlar bir tekis taqsimlanmagan:

| Fayl | Nechta skip |
|---|---:|
| `test_auth_service.py` | **9** |
| `test_staff_service.py` | **2** |
| `test_identity_schema.py` | 2 |
| qolgan 9 ta fayl | 1 tadan |

Shuning uchun **`auth` (56.2%) va `staff` (39.0%) raqamlariga
ishonmang** — ularning testlari aynan shu sababdan yurmagan.
Qolgan paketlar uchun raqamlar haqiqiy.

## Paketlar bo'yicha

| Paket | Qoplama | Qator |
|---|---:|---|
| `admin/moderation` | 96.5% | 193/200 |
| `payments/service_parts` | 93.6% | 219/234 |
| `orders/service_parts` | 91.3% | 493/540 |
| `cash_register/service_parts` | 91.2% | 248/272 |
| `inventory/service_parts` | 84.3% | 322/382 |
| `business_online/payload` | 84.0% | 817/973 |
| `queues/service_parts` | 83.3% | 369/443 |
| `dining/service_parts` | 83.2% | 385/463 |
| `education/cabinet` | 82.5% | 146/177 |
| `public_discovery/queries` | 79.0% | 316/400 |
| `documents/service_parts` | 73.4% | 185/252 |
| **`business_online/service_parts`** | **70.7%** | 289/409 |
| **`notifications/service_parts`** | **69.8%** | 148/212 |
| **`education/management`** | **59.5%** | 367/617 |
| **`taxi/service_parts`** | **58.0%** | 210/362 |
| `auth/service_parts` ⚠️ | 56.2% | 216/384 |
| `staff/service_parts` ⚠️ | 39.0% | 123/315 |
| **`stories/service_parts`** | **31.2%** | 73/234 |

⚠️ = raqam ishonchsiz, yuqoridagi izohga qarang.

## 70% dan past paketlar — qaysi funksiyalar ochiq

### `stories/service_parts` — 31.2%

**Barcha ommaviy metodlar qoplanmagan:** `create`, `feed`, `delete`,
`report`, `view`, `owner_stories`.

Ya'ni story joylash, ko'rish va o'chirish oqimining hech biri
avtomatik sinovdan o'tmaydi. Mavjud `test_stories_v1656.py` faqat
yordamchi funksiyalarni (media turini aniqlash, saralash) tekshiradi.

### `taxi/service_parts` — 58.0%

| Funksiya | Holat |
|---|---|
| `topup_driver` | to'liq qoplanmagan — **haydovchi balansi** |
| `cancel_ride` | to'liq qoplanmagan |
| `pending_rides` | to'liq qoplanmagan |
| `update_progress` | to'liq qoplanmagan |
| `set_availability` | to'liq qoplanmagan |
| `_sync_source_order` | 23 qator ochiq |

### `education/management` — 59.5%

| Funksiya | Holat |
|---|---|
| `payments` | to'liq qoplanmagan — **o'quvchi to'lovlari** |
| `payment_control` | to'liq qoplanmagan |
| `payroll` | to'liq qoplanmagan — **o'qituvchi oyligi** |
| `_billing_status` | to'liq qoplanmagan |
| `create_teacher` | to'liq qoplanmagan |
| `create_payment` | 12 qator ochiq |

### `notifications/service_parts` — 69.8%

`notify_listing_published`, `_matches_filter`, `mark_all_read` —
to'liq qoplanmagan. Filtr moslashuvi (`_matches_filter`) sinovdan
o'tmagani ayniqsa noqulay: u qaysi bildirishnoma kimga ko'rinishini
hal qiladi.

### `business_online/service_parts` — 70.7%

`patch_record`, `_education_write`, `_apply_enrollment_action` —
to'liq qoplanmagan.

### `documents/service_parts` — 73.4%

`update_counterparty`, `delete_counterparty` — to'liq qoplanmagan.

## Uchta eng xavfli bo'shliq

Pul yoki ombor bilan bog'liq, lekin qoplanmagan kod:

| # | Qayerda | Nima qiladi | Nega xavfli |
|---:|---|---|---|
| 1 | `education/management/payments.py` → `payments`, `payment_control` | O'quvchi to'lovlarini qabul qilish va nazorat jadvali | Noto'g'ri hisob-kitob to'g'ridan-to'g'ri pulga tegadi va uni faqat o'quv markazi qo'lda sezadi |
| 2 | `education/management/payroll.py` → `payroll` | O'qituvchi oyligini hisoblash | Xato oylik xodimga to'lanadi; orqaga qaytarish qiyin |
| 3 | `taxi/service_parts/drivers.py` → `topup_driver` | Haydovchi balansini to'ldirish | Balans to'g'ridan-to'g'ri pul; komissiya shundan yechiladi |

Uchalasi ham **hech qanday** avtomatik test bilan qoplanmagan.

## Nima qilinmadi

- Yangi test yozilmadi — bu alohida ish.
- `app/` ichidagi kod o'zgartirilmadi.
- Bironta test `skip`/`xfail` qilinmadi.
- Frontend qoplamasi o'lchanmadi.

## Keyingi qadam uchun tavsiya

Uchta xavfli bo'shliqni yopish 7-bosqichdan (mypy) **oldin**
qilinishi ma'qul: tur qo'shish paytida o'sha kod tegiladi, va agar
test bo'lmasa, buzilgani bilinmaydi.

`stories` (31.2%) esa hajmi bo'yicha eng katta bo'shliq, lekin pulga
tegmaydi — shuning uchun ikkinchi navbatda.

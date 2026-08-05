# K13 — Ovqatlanish zanjiri migratsiyasi

**Sana:** 2026-08-05
**Bosqich:** K13a (backend) — bajarildi. K13b (frontend) — keyingi PR.

## Nima uchun

Ovqatlanish yo'nalishi yarim ko'chirilgan va ishlab turgan holatda emas edi.

Yangi backendda `dining` faqat JSON `cabinet_payload` yo'lida mavjud edi
(`app/business_online/service.py`) va atigi 4 ta amalni bilardi:

| Amal | Holat (K13 gacha) |
|---|---|
| Stol band qilish (`book`) | bor |
| Zakaz ochish (`create_order`) | bor |
| Taom qo'shish (`add_items`) | bor |
| Stolni bo'shatish (`clear`) | bor, lekin **hech qachon o'tmasdi** |
| Oshpaz "tayyor" belgisi | **yo'q** |
| Kassir to'lovi | **yo'q** |
| Kassir hisobni tahrirlashi | **yo'q** |
| Yakunlash / bekor qilish | **yo'q** |
| Muammoli hisob | **yo'q** |

v1656 da bu oqim 13 ta endpoint bilan ishlaydi (`api.py:2500-3860`).

### Zanjirning uzilishi

`kitchen_status` butun yangi backendda faqat `"preparing"` qiymatiga,
`payment_status` faqat `"open"` qiymatiga yozilardi
(`service.py:954-955`, `1053`). Ularni oldinga suradigan kod yo'q edi.

Ammo stolni bo'shatish sharti (`service.py:987-988`) aynan shularni
talab qiladi:

```python
order.get("payment_status") != "confirmed"
or order.get("kitchen_status") != "done"
```

Natijada: ofitsiant zakaz ochadi → oshpaz tayyor deb belgilay olmaydi →
kassir to'lovni qabul qila olmaydi → **stol abadiy band qoladi**.
Restoran bir marta zakaz ochgach, o'sha stolni boshqa ishlatib bo'lmasdi.

Bundan tashqari ombor va kassa bilan bog'liqlik butunlay yo'q edi: v1656
da to'lov tasdiqlanganda FIFO bo'yicha xomashyo yechiladi, `stock_moves`
yoziladi va savdo daftariga chek tushadi. Yangi backendda bularning hech
biri bo'lmagani uchun ovqatlanish biznesida savdo hisoboti ham, ombor
qoldig'i ham yangilanmasdi.

## Nega relatsion jadval

Zakaz — kabinetdagi eng tez o'zgaradigan ma'lumot. JSON blobda saqlanganda
har bir o'zgarish butun `cabinet_payload` ni qayta yozadi. Bitta restoranda
oshpaz, bir necha ofitsiant va kassir bir vaqtda ishlaganda bu blob ustida
qulf raqobati bo'ladi va yozuvlar bir-birini yo'q qiladi. 10 000
foydalanuvchi maqsadi uchun bu yo'l yaramaydi.

## Jadvallar

Migratsiya: `backend/migrations/versions/0025_dining_domain.py`

| Jadval | v1656 manbai | Izoh |
|---|---|---|
| `dining_places` | `dining_places` | stol/xona, zal rejasidagi `x`,`y` |
| `dining_orders` | `dining_bookings` | `kind` ustuni zakaz va bandlikni ajratadi |
| `dining_order_items` | `dining_booking_items` | narx zakaz paytidagi holicha |

### v1656 dan farqlar

1. **Jadval nomi.** `dining_bookings` → `dining_orders`. v1656 da bitta
   jadval ham stol bandligini, ham zakazni saqlagani chalkashlik
   tug'dirardi; `kind` ustuni (`order` / `booking`) ikkalasini ajratadi.

2. **Vaqt turi.** Unix son o'rniga `timestamptz`. Sabab: bu domen to'lov
   paytida Kassa va Ombor bilan bitta tranzaksiyada yozadi, ular esa shu
   turdan foydalanadi. API javoblarida vaqt v1656 dagidek unix songa
   aylantiriladi, ya'ni frontend uchun farq yo'q.

3. **Chek bog'lanishi.** `dining_orders.cash_receipt_id` qo'shildi.
   `cash_receipts.order_id` faqat tashqi buyurtmaga tegishli va unda
   `UNIQUE` bor, shuning uchun ichki zakaz teskari tomondan bog'lanadi.
   Qisman unikal indeks bir zakaz uchun ikkinchi chek yozilishini
   to'sadi.

4. **CHECK cheklovlari.** `kind`, `kitchen_status`, `payment_status`,
   `status`, `pay_type` uchun. SQLite'da bunday himoya yo'q edi.
   Alohida: `pay_type = 'qarz'` bo'lsa `debtor_id` bo'sh bo'lolmaydi.

### Eski ma'lumot

Migratsiya mavjud stollarni va ochiq hisoblarni kabinet yozuvlaridan
ko'chiradi — avval V7 relatsion store, u yerda bo'lmasa eski JSON
payload. `legacy_source_id` bo'yicha qisman unikal indeks tufayli
migratsiya qayta ishga tushirilsa ham ma'lumot ikkilanmaydi.

## Endpointlar

Prefiks: `/api/v1/dining`

| Endpoint | Ruxsat |
|---|---|
| `GET /places` | `dining_places`, `dining_internal`, `kassa` |
| `POST /places` | `dining_places` |
| `PUT /places/{id}` | `dining_places` |
| `PUT /places/{id}/position` | `dining_places` |
| `DELETE /places/{id}` | `dining_places` |
| `POST /places/{id}/clear` | `dining_places`, `kassa` |
| `POST /places/{id}/booking` | `dining_places`, `dining_internal` |
| `POST /places/{id}/order` | `dining_internal` |
| `GET /orders` | `dining_internal`, `kitchen`, `kassa`, `dining_places` |
| `POST /orders/{id}/items` | `dining_internal`, `kassa` |
| `PUT /orders/{id}/kitchen` | `kitchen` |
| `POST /orders/{id}/payment` | `payment_confirm`, `kassa` |
| `PUT /orders/{id}/cashier-items` | `kassa` |
| `POST /orders/{id}/finalize` | `kassa`, `payment_confirm` |
| `POST /orders/{id}/cancel` | `kassa` |
| `POST /orders/{id}/problem` | `kassa`, `payment_problems` |
| `POST /orders/{id}/problem/resolve` | `kassa`, `payment_problems` |

Ruxsat nomlari `app/staff/permissions.py:48-52` da allaqachon e'lon
qilingan — yangi ruxsat qo'shilmadi. Rahbar (`permissions is None`)
barcha bo'limlarni ko'radi, v1656 dagidek.

`PUT /places/{id}/position` — v1656 da alohida endpoint yo'q, stol
surilganda butun yozuv yuborilardi. Zal rejasida surish tez-tez
takrorlanadigan amal bo'lgani uchun yengil variant qo'shildi; eski
to'liq `PUT /places/{id}` ham saqlanib qoldi.

## Zanjir

```
ofitsiant                oshpaz              kassir
    │                       │                   │
    ├─ zakaz ochadi ────────┤                   │
    │   kitchen: preparing  │                   │
    │   payment:  open      │                   │
    │                       │                   │
    │                       ├─ "Tayyor" ────────┤
    │                       │  kitchen: done    │
    │                       │                   │
    │                       │                   ├─ to'lov
    │                       │                   │  payment: confirmed
    │                       │                   │  ├─ chek raqami
    │                       │                   │  ├─ FIFO ombor sarfi
    │                       │                   │  ├─ stock_moves
    │                       │                   │  └─ qarz (agar 'qarz')
    │                       │                   │
    │                       │                   ├─ yakunlash
    │                       │                   │  status: done
    │                       │                   │  STOL BO'SHADI
```

### Qoidalar

- Muammoli hisobda oshxona ham, to'lov ham to'xtaydi.
- To'lovi tasdiqlangan zakaz bekor qilinmaydi va tahrirlanmaydi.
- Tayyor deb belgilangan hisobga yangi taom qo'shilsa, oshxona jarayoni
  qayta ochiladi (`kitchen_status` → `preparing`).
- Kassir qatorni o'chirib hisobni bo'shatib yubora olmaydi — jami 0 ga
  tushsa 400 va tranzaksiya orqaga qaytariladi.
- To'lov idempotent: takroriy so'rov ikkinchi chek yozmaydi va omborni
  ikki marta yechmaydi.
- Narx doim server katalogidan olinadi, mijoz yuborgan narx e'tiborga
  olinmaydi.

## Qayta ishlatilgan kod

Yangi FIFO yoki qarz mantiqi yozilmadi:

| Kerak | Mavjud funksiya |
|---|---|
| FIFO sarf + `stock_moves` | `app/inventory/service.py:108` `consume_cash_line` |
| Qatorlarni qulflash | `app/inventory/service.py` `lock_cash_catalog_items` |
| Chek raqami | `app/cash_register/repository.py:46` `next_receipt_no` |
| Qarz tranzaksiyasi | `app/debt_ledger/service.py:253` `create_transaction_in_session` |
| Bildirishnoma | `app/notifications/repository.py:69` `append` |

`app/cash_register/model.py:48` dagi `CHECK` allaqachon `'dining'`
manbaini ruxsat etardi va `waiter_staff_id` / `waiter_name_snapshot`
ustunlari ham bor edi — kassa jadvali bu domenni kutgan.

## Eski JSON yo'li

`business_online/service.py` dagi dining amallari o'chirilmadi. K13a
faqat yangi endpointlarni qo'shadi; mavjud ekran hali eski yo'ldan
ishlaydi. Frontend K13b da yangi endpointlarga o'tkaziladi — shu
tartibda ikki PR orasida hech narsa buzilmaydi.

## Testlar

`backend/tests/test_dining_chain.py` — 24 ta test.

Eng muhimi `test_table_cannot_be_cleared_before_kitchen_and_payment`:
oshxona va to'lov qadamlari bajarilmaguncha stol bo'shamasligini, ikkalasi
bajarilgach bo'shashini tekshiradi. Bu aynan migratsiyagacha bo'lgan
tiqilishning qaytishidan saqlaydi.

Testlar haqiqatan xatoni ushlashi tekshirildi: `kitchen_status` yozuvi
olib tashlanganda 3 ta test, FIFO sarfi olib tashlanganda 2 ta test
qizardi.

Qoplama: to'liq zanjir, ombor sarfi va tannarx, omborda yozuvi yo'q
taom, qarz to'lovi, qarzdorsiz qarz (chek yozilmasligi), idempotentlik,
kassir tahriri va bo'sh hisob taqiqi, bekor qilish, muammoli hisob,
yakunlash shartlari, xodim vakolatlari, begona biznes, narx manbai,
ofitsiant ismi.

## Tekshirish

```
cd backend && .venv/Scripts/python.exe -m pytest tests/test_dining_chain.py -q
cd backend && .venv/Scripts/python.exe -m pytest -q
```

Migratsiya haqiqiy PostgreSQL'da CI orqali tekshiriladi — offline
`--sql` yetarli emas (0019 dagi ustun xatosi shu sababli o'tib ketgan edi).

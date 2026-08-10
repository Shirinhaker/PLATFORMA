# K23 — Obunalarim va To‘lovlarimni yakuniy typed migratsiya qilish

K12 to‘lov jadvallari, narx katalogi, chek saqlash va admin tasdig‘ini
ko‘chirgan edi. Lekin kabinetdagi `Obunalarim` va `To‘lovlarim` o‘qish
yo‘li hanuz umumiy `cabinet_payload` / `business-online` resurslariga
qaytishi mumkin edi. K23 shu ikki ekranning aktiv yo‘lini typed payment
domeniga to‘liq ulaydi.

`static/index.html` v1656 manbasi o‘zgartirilmadi.

## Monolitdagi tartib

| Qism | v1656 manbasi | Ishlashi |
|---|---|---|
| To‘lov katalogi va rekvizit | `static/index.html:11731-11759` | Faol narxlar/usullarni oladi va rekvizit matnini tuzadi |
| To‘lov so‘rovi | `static/index.html:11802-11849` | Tarif → chek → so‘rov → `To‘lovlarim` |
| To‘lovlar tarixi | `static/index.html:11851-11895` | Eng yangi so‘rovlar, holat/sabab, rad etilgan chekni qayta yuborish |
| Joriy obuna va tarix | `static/index.html:11911-11958` | `current` alohida, `history` eski tariflar; pullik tarif bo‘lmasa virtual Bepul |
| Backend obuna qoidasi | `subscriptions.py:349-367` | Faol bo‘lmaganlar `id DESC`; muddati tugagan faol tarif `expired` bo‘ladi |

```text
Biznes kabineti → Obunalarim
                  ├─ current: active Plus/Pro yoki virtual Bepul
                  ├─ history: superseded/expired, id DESC
                  └─ tarif + muddat → chek → payment request

User/Biznes kabineti → To‘lovlarim
                       ├─ payment_requests, yangi → eski
                       ├─ payment_attempts bitta batch so‘rovda
                       └─ rejected → R2 chek → typed resubmit
```

## Moduldagi yangi yo‘l

```text
BusinessSubscriptionsV1656 / PaymentsV1656
        ↓ ApiClient typed metodlari
GET /api/v1/payments/subscription
GET /api/v1/payments/my
POST /api/v1/payments/{id}/resubmit
        ↓ PaymentService
PostgreSQL payment_requests / payment_attempts / business_subscriptions
```

- obuna holati va katalogi mustaqil bo‘lgani uchun `Promise.all` bilan
  parallel yuklanadi;
- to‘lov urinishlari N+1 qilinmaydi, bitta `IN (...)` so‘rovda olinadi;
- tarixning `business_account_id = ? ORDER BY id DESC` so‘rovi uchun
  `ix_business_subscriptions_history` indeksi qo‘shildi;
- foydalanuvchi va biznes bir xil typed `PaymentsV1656` ekranini ishlatadi;
- xodim egaga tegishli obuna/to‘lov bo‘limini to‘g‘ridan-to‘g‘ri API orqali
  ham ocha olmaydi;
- oddiy foydalanuvchi qo‘lda API yuborib biznes obunasini sotib ola olmaydi;
- eski umumiy ekran rollback uchun saqlanadi, ammo to‘liq `ApiClient`
  mavjud bo‘lgan production yo‘lida ishlatilmaydi.

## Release gate

- Alembic `0035_follow_lists → 0036_subscription_payments`;
- typed obuna routeri va biznes-only himoya;
- biznes va foydalanuvchi kabineti typed ekranga ulangan;
- chek R2 kaliti va SHA-256 bilan qayta yuboriladi;
- `static/index.html` — 14 091 qator, `BUILD: v1656` o‘zgarmagan.

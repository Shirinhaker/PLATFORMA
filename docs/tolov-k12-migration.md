# K12 — To'lovlar domeni

To'lov oqimi umuman ko'chirilmagan edi: `/api/payments/*` endpointlari
yo'q edi. Shu sababli obuna sotib olish tugmasi bosilganda **to'lov
oynasi ochilmasdi**.

`static/index.html` v1656 manbasi va frontend fayllari o'zgarmaydi.

## Ko'chirilgan oqim

```
tarif tanlanadi → chek yuklanadi → so'rov yaratiladi
                → admin tasdiqlaydi yoki rad etadi
                → tasdiqlansa obuna faollashadi
```

| Endpoint | Nima qiladi |
|---|---|
| `GET /api/v1/payments/catalog` | tariflar va to'lov usullari |
| `POST /api/v1/payments/requests` | to'lov so'rovi yaratish |
| `GET /api/v1/payments/my` | mening to'lovlarim |
| `POST /api/v1/payments/{id}/resubmit` | yangi chek biriktirish |
| `POST /api/v1/payments/{id}/approve` | tasdiqlash |
| `POST /api/v1/payments/{id}/reject` | rad etish (sabab majburiy) |

## Jadvallar

| Jadval | Mazmuni |
|---|---|
| `platform_prices` | tarif katalogi (9 ta kod, v1656 narxlari bilan) |
| `payment_methods` | to'lov usullari |
| `payment_requests` | to'lov so'rovi va narx snapshot'i |
| `payment_attempts` | chek urinishlari (qayta yuborish tarixi) |
| `payment_events` | holat o'zgarishlari jurnali |
| `business_subscriptions` | faol obuna |

## v1656 pariteti

| Qoida | v1656 | Yangi |
|---|---|---|
| Tarif kodi va parametrlari mos kelishi | `_resolve_price` | `payment_price_mismatch` |
| Faol bo'lmagan tarif rad etiladi | shu yerda | `payment_price_inactive` |
| Rad etishda sabab majburiy | `_review` | `payment_reason_required` |
| Ikkinchi qaror qabul qilinmaydi | `PaymentConflict` | `payment_already_reviewed` |
| Narx so'rov paytida muzlatiladi | `amount_snapshot` | bir xil |
| Bir xil tarif tugash sanasidan uzayadi | `activate_paid_subscription` | bir xil |
| Bir to'lov ikki marta obunaga aylanmaydi | `payment_request_id` tekshiruvi | noyob indeks |
| So'rov kodi `PAY-XXXXXXXXXXXX` | `secrets.token_hex(6)` | bir xil |

## Ataylab kiritilgan farq

| v1656 | Yangi | Sabab |
|---|---|---|
| Chek fayli serverning lokal diskida (`/data/receipts`) | Chek R2'da, jadvalda `receipt_object_key` | Bir nechta API nusxasi ishlaganda fayl boshqa serverda topilmasdi |

Chek yuklash mavjud `media` moduli orqali (presigned URL) bajariladi —
fayl brauzerdan to'g'ridan-to'g'ri R2'ga ketadi, backend orqali
o'tmaydi.

## Backfill

Eski so'rovlar kabinet `payment_requests` resursidan ko'chiriladi
(`legacy_source_id` bo'yicha idempotent). Eski chek fayllari eski
serverda qolgan — ular ko'chirilmaydi, faqat so'rov metama'lumoti
saqlanadi.

## Testlar

`tests/test_payments_v1656.py` — 11 ta test:

- katalog faqat faol tarif va usullarni berishi;
- so'rov narx snapshot'i va birinchi chek urinishi bilan yozilishi;
- tarif parametrlari mos kelmasa rad etilishi;
- faol bo'lmagan tarif rad etilishi;
- tasdiqlash obunani faollashtirishi;
- rad etishda sabab majburiyligi;
- ikkinchi qaror rad etilishi;
- qayta yuborishda eski chek `superseded` bo'lishi;
- bir xil tarif tugash sanasidan uzayishi;
- ro'yxat yangisidan boshlanishi;
- boshqa akkaunt chek biriktira olmasligi.

## Release gate

- Alembic `0023_profile_follows → 0024_payments_domain` offline SQL;
- `base:head` xatosiz, bitta head;
- backend 528 test, frontend 338 test;
- TypeScript toza;
- `rollback` qo'riqchisi ro'yxatida `PaymentService`;
- migratsiya buyruqlari qo'riqchisi yashil.

## Frontend ekrani

`SubscriptionsV1656.tsx` — v1656 `cab-subscriptions` ekranining
ko'chirilgan varianti. Matnlar va tuzilma o'zgarmagan:

- «To'lov tartibi» izohi;
- muddat tanlash (1 / 3 / 12 oy);
- uchta tarif kartochkasi (Bepul, Plus, Pro) va ularning imkoniyatlari;
- «Plus uchun to'lov qilish» tugmasi to'lov oynasini ochadi;
- oynada to'lov usuli, kvitansiya tanlash va yuborish;
- «To'lovlarim» ro'yxati va holatlari.

Kvitansiya `media` moduli orqali to'g'ridan-to'g'ri R2'ga yuklanadi,
so'ng uning kaliti va SHA-256 xesh so'rov bilan yuboriladi. Buning
uchun `payment_receipt` yuklash turi qo'shildi (maksimum 5 MB,
JPG/PNG/WEBP).

## K12 tarkibiga kirmaydi


- reklama va e'lon to'lovlarining faollashtirilishi — ular o'z
  domenlarida ulanadi (`_activate` hozircha faqat obunani yoqadi);
- admin paneli — tasdiqlash endpointi biznes egasi huquqi bilan
  himoyalangan, alohida admin roli keyingi bosqichda.

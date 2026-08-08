# K15 — E'lon joylashni pullik qilish

**Sana:** 2026-08-08
**Bosqich:** backend va frontend — bajarildi.

## Bu v1656 dan farq — ataylab

CLAUDE.md bo'yicha v1656 haqiqat manbai, shuning uchun har bir farq
hujjatlashtiriladi. Bu — o'sha farqlardan biri.

v1656 da `payments.py:57` da `listing_publish` tarifi **bor** edi
(10 000 so'm), lekin uni ishlatadigan oqim yo'q edi: e'lon darhol
`active` bo'lib yaratilardi va tarif hech qachon qo'llanmasdi. Ya'ni
narx e'lon qilingan, pul olinmagan.

Egasining qarori bilan tarif endi haqiqatan ishlaydi: e'lon
`payment_pending` bilan yaratiladi va admin to'lovni tasdiqlagandan
keyingina ochiq ro'yxatlarga chiqadi.

## Oqim

```
e'lon to'ldiriladi
    → `payment_pending` bilan saqlanadi        ← ko'rinmaydi
    → to'lov oynasi darhol ochiladi
    → foydalanuvchi chek yuboradi
    → admin tasdiqlaydi
    → e'lon `active` bo'ladi                   ← ko'rinadi
```

Reklama (K14) bilan bir xil naqsh — `PaymentService._activate` xizmat
turiga qarab tegishli domenga topshiradi.

## Narx tuzatildi: 15 000 → 10 000

`0024` migratsiyasida `listing_publish` 15 000 so'm qilib yozilgan edi,
v1656 da esa 10 000. Bu ko'chirish paytida kiritilgan xato — sababsiz
farq.

`0029_listing_publish_price` uni tuzatadi, lekin **faqat hali
tegilmagan bo'lsa**:

```sql
UPDATE platform_prices SET amount_uzs = 10000
WHERE price_code = 'listing_publish' AND amount_uzs = 15000
```

Admin panelida narx allaqachon o'zgartirilgan bo'lsa, o'sha qiymat
saqlanadi.

## Ichki raqam ochiq kontraktda yo'q

Reklamada to'lov so'rovi `target_id` (ichki raqam) bilan keladi —
reklamaning muallif sxemasi uni beradi.

E'londa bunday emas: `ListingRead` ochiq sxema (aynan shu sxema public
ro'yxatlarda ham ishlatiladi) va u faqat `public_id` (`l_…`) beradi.
Ichki raqamni unga qo'shish public feedda e'lonlar sonini va
sanab chiqish imkonini ochib qo'yardi.

Shuning uchun to'lov so'rovi kalit bilan keladi:

| Maydon | Kim uchun |
|---|---|
| `target_id` | reklama |
| `target_public_id` | e'lon |

`ListingActivationService.resolve_owned()` kalitni ichki raqamga
aylantiradi va **shu paytning o'zida egalikni tekshiradi**. Ya'ni
begona e'lonning kalitini yuborsangiz, to'lov so'rovi umuman
yaratilmaydi (`listing_not_found`), tasdiqlash bosqichigacha
yetib bormaydi.

## Yangi va o'zgargan joylar

| Fayl | Nima |
|---|---|
| `app/listings/activation.py` | `activate_paid()` va `resolve_owned()` |
| `app/listings/service.py` | `create()` endi `payment_pending` yozadi; `_listing_status()` holatni egasiga saqlaydi |
| `app/listings/schemas.py` | `ListingStatus` ga `payment_pending` qo'shildi |
| `app/payments/schemas.py` | `target_public_id` maydoni |
| `app/payments/service.py` | `listing` xizmat turi: yaratishda kalit yechiladi, tasdiqlashda e'lon yoqiladi |
| `migrations/versions/0029_listing_publish_price.py` | narx tuzatildi |
| `frontend/src/listings/OwnerListingsV1656.tsx` | holat matni, «To‘lov qilish» tugmasi, to'lov oynasi |

## Egasi nima ko'radi

- E'lon ro'yxatida holat: **To‘lov kutilmoqda** (ilgari «O'chiq» deb
  ko'rinardi — bu chalg'ituvchi edi).
- Har bir kutilayotgan e'londa **To‘lov qilish** tugmasi.
- E'lon joylangach to'lov oynasi darhol ochiladi — qadam
  o'tkazib yuborilmaydi.
- Katalog yuklanmasa sabab ko'rsatiladi, oyna jimgina ochilmay
  qolmaydi.

## Testlar

**Backend** — `backend/tests/test_listing_paid_publish.py` (9 ta):
to'lovsiz e'lon `list_public` da yo'q; egasi o'z e'lonini holati bilan
ko'radi; tasdiqlash e'lonni chiqaradi; ikkinchi tasdiqlash rad etiladi;
begona akkauntning to'lovi e'lonni chiqarmaydi; uchidan-uchiga
chek → admin tasdig'i; rad etilgan to'lovda e'lon yashirin qoladi;
begona kalit bilan so'rov yaratilmaydi; kalitsiz so'rov rad etiladi.

`test_listings_live_v1656.py` dagi mavjud tekshiruvlar
zaiflashtirilmadi — aksincha, e'lon `payment_pending` bilan
yaratilishi va public ro'yxatda yo'qligi **qo'shildi**, keyin
faollashtirib eski tekshiruvlar o'z holicha ishlaydi.

**Frontend** — `src/listings/OwnerListingPayment.test.tsx` (6 ta):
holat matni; oyna ochilishi va tarif; joylangach oyna avtomatik
ochilishi; so'rovda `target_public_id` yuborilishi; katalog xatosi
ko'rsatilishi; to'lov API'si yo'q kabinetda tugma chiqmasligi.

## Tekshirildi

```
backend:  624 passed, 21 skipped
frontend: 440 passed, tsc --noEmit toza
```

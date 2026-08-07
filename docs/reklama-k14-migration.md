# K14 — Reklama joylash migratsiyasi

**Sana:** 2026-08-07
**Bosqich:** K14a (backend) — bajarildi. Frontend keyingi PR'da.

## Nima uchun

Reklama joylash oqimi ko'chirilmagan edi va bu **jimgina buziq** holatda
turardi.

Yangi backendda ikkita alohida joy bor edi:

| Joy | Nima qiladi |
|---|---|
| `advertisements` jadvali | public reklamalar **shu yerdan** o'qiladi |
| kabinet JSON `cabinet_payload` | yangi reklama **shu yerga** yozilardi |

Relatsion jadvalni faqat eski ma'lumot ko'chiruvchi to'ldirardi
(`legacy_migration/advertisement_stage.py`). Ya'ni bugun reklama
joylasangiz, u JSON blobga tushardi va **hech qachon bosh sahifada
chiqmasdi**.

Ustiga to'lov ham yakunlanmagan edi: JSON yo'lida reklama
`payment_pending` bilan yaratilardi, lekin `PaymentService._activate`
faqat obunani bilardi — kodda izoh ham bor edi: *«Reklama va e'lon o'z
domenlarida yoqiladi»*. Ya'ni to'lov qabul qilinardi, reklama esa
abadiy `payment_pending` da qolardi.

## Oqim

```
hudud va davomiylik tanlanadi
    → narx hisoblanadi (tuman-soat birligida)
    → reklama `payment_pending` bilan yaratiladi   ← ko'rinmaydi
    → foydalanuvchi chek yuboradi
    → admin tasdiqlaydi
    → jadval suriladi va reklama `active` bo'ladi  ← ko'rinadi
```

## Narx

v1656 `ad_pricing.py` aynan ko'chirildi
(`app/advertisements/pricing.py`):

```
narx = tumanlar soni × kunlik soatlar × kunlar × tuman-soat tarifi
```

Tarif admin panelidan boshqariladi (`advertisement_district_hour`).
Sozlama bo'lmasa 20 000 so'm.

Davomiylik faqat 1, 3, 7, 14 yoki 30 kun. Respublika tanlansa boshqa
hudud qo'shilmaydi.

## v1656 dagi xato tuzatildi

`normalize_ad_geo` viloyat nomidan "shahri" va "viloyati" so'zlarini
olib tashlaydi. Natijada **"Toshkent shahri" va "Toshkent viloyati"
bitta kalitga tushardi** va katalogda shahar tumanlari viloyatnikiga
almashib ketardi.

Oqibati v1656 da:

- Toshkent shahridagi tumanga (Chilonzor, Yunusobod va h.k.) reklama
  **umuman sotib bo'lmasdi** — "Tanlangan tuman backend katalogida
  yo'q" xatosi chiqardi;
- "Toshkent shahri" viloyat sifatida tanlansa, narx 11 emas, 14
  tumanga hisoblanardi.

Toshkent — eng katta bozor, ya'ni bu pulga ta'sir qiladigan xato.

**Tuzatish:** viloyat kaliti uchun alohida `normalize_ad_region`
ishlatiladi — u turini bildiruvchi so'zni saqlaydi. Tuman nomlari
uchun v1656 dagi normallashtirish o'zgarmadi (u yerda to'qnashuv yo'q,
tekshirildi).

Reklamani **ko'rsatish** tomoni (`target_specificity`) to'liq nomni
solishtiradi, ya'ni u yerda bu muammo yo'q edi — tuzatish faqat narx
katalogiga tegishli.

## Endpointlar

| Endpoint | Vazifasi |
|---|---|
| `GET /api/v1/advertisements/rates` | tarif va ruxsat etilgan kunlar |
| `POST /api/v1/advertisements/price` | narxni oldindan ko'rish |
| `POST /api/v1/advertisements` | yaratish (`payment_pending`) |
| `GET /api/v1/advertisements/my` | o'z reklamalarim |
| `DELETE /api/v1/advertisements/{id}` | o'chirish |

Public reklamalar `/api/v1/public/advertisements` da qolgan.

## To'lov bog'lanishi

`PaymentService._activate` endi `service_type="advertisement"` ni
biladi va `AdvertisementService.activate_paid` ni chaqiradi. U:

- reklamani qulflaydi va `payment_pending` ekanini tekshiradi;
- **to'lov egasi reklama egasi ekanini tekshiradi** — boshqa
  akkauntning to'lovi reklamani yoqmaydi;
- jadvalni suradi (`shift_schedule_start`): tasdiq boshlanish
  sanasidan keyin bo'lsa, reklama keyingi mos soatdan boshlanadi;
- `end_at` ni qayta hisoblaydi va holatni `active` qiladi.

Hammasi to'lov tranzaksiyasi ichida — chek tasdiqlanib, reklama
yoqilmay qolishi mumkin emas.

## Migratsiya

`0028_advertisement_authoring.py` — `migration_run_id` ixtiyoriy
bo'ldi. U faqat ko'chirilgan yozuvlar uchun mantiqiy; e'lonlarda
allaqachon shunday edi.

Eski `test_phase3c_models` shu ustun majburiyligini tekshirardi.
Tekshiruv olib tashlanmadi — u yangi shartga o'tkazildi va
"ko'chirilgan yozuvda run id doim to'ladi" degan qoplama alohida
testga ko'chirildi.

## Public kontrakt

`scripts/verify_phase3c.py` `advertisements/schemas.py` ni public
kontrakt deb tekshiradi va unda saqlash kalitlari (`*_object_key`)
bo'lishini taqiqlaydi.

Reklama yaratishda esa rasm kaliti kerak — mijoz uni grant orqali
yuklab, kalitni qaytaradi (chek bilan bir xil naqsh). Shu sababli
joylash sxemalari alohida `authoring_schemas.py` ga chiqarildi:
public fayl toza qoladi, tekshiruv o'z kuchida.

## Testlar

`backend/tests/test_advertisement_authoring.py` — 13 ta test.

Toshkent xatosi, narx formulasi, tarifning admin panelidan kelishi,
noto'g'ri davomiylik, respublika aralashmasligi, to'lovsiz
ko'rinmaslik, egalik, ikki marta yoqilmaslik va jadval surilishi.

Buzib tekshirildi: Toshkent tuzatishi bekor qilinganda va reklama
darhol `active` qilinganda 8 test qizardi.

## Qolgan ish

Frontend: reklama joylash ekrani — hudud tanlash, davomiylik, narxni
oldindan ko'rish va to'lov oynasiga o'tish. Hozircha reklama faqat API
orqali joylanadi.

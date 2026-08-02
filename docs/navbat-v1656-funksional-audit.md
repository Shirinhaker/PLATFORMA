# Navbat tizimi — v1656 funksional paritet auditi

Sana: 2026-08-02

Haqiqat manbai: ishlab turgan `static/index.html` (`BUILD v1656`), uning
legacy API mantiqi joylashgan `api.py` va SQLite sxemasi joylashgan
`database.py`.

## Audit maqsadi

`docs/onlaynlashtirish-parity-audit.md` biznes kabinetidagi uchta navbat
ekranini React View va ko'rinish testlari mavjudligi sabab `migrated` deb
belgilaydi:

- `cab-medical-doctors`;
- `cab-medical-doctor-form`;
- `cab-medical-queue`.

Bu holat faqat **ekran paritetini** bildiradi. Ishlab turgan v1656dagi to'liq
navbat zanjiri biznes kabinetidan tashqari ommaviy profil, oddiy foydalanuvchi
kabineti, bildirishnomalar va alohida relatsion navbat jadvallarini ham qamrab
oladi. Ushbu hujjat shu **funksional domen paritetini** tekshiradi.

Q0 faqat audit blokidir. Kod, `static/index.html`, `api.py`, `database.py`,
Tizimlashtirish modullari, `main` va production o'zgartirilmaydi.

## Holat mezonlari

- `migrated` — React oqimi typed `/api/v1` endpoint va relatsion domen bilan
  v1656 xatti-harakatini to'liq bajaradi, parity testi mavjud;
- `partial` — ko'rinish yoki mantiqning bir qismi mavjud, ammo zanjirning
  majburiy qismi generic snapshot, ishlamaydigan tugma yoki yetishmagan API
  sabab tugallanmagan;
- `missing` — v1656 funksiyasi uchun yangi frontend/backend oqimi yoki
  relatsion saqlash mavjud emas.

## v1656dagi to'liq navbat zanjiri

```text
Navbatli yo'nalishdagi xizmat
  -> "Navbat tizimi: Yoqilgan"
  -> faol xodimni xizmat ko'rsatuvchi sifatida biriktirish
  -> ish kunlari, vaqt, o'rtacha qabul va live/slot rejimi
  -> ommaviy profilda "Navbat olish"
  -> sana -> xizmat ko'rsatuvchi -> bo'sh vaqt (slot bo'lsa)
  -> onlayn navbat yozuvi + "Navbat olindi" bildirishnomasi
  -> biznesning onlayn/oflayn yagona navbati
  -> Chaqirish / Qabul / Yakunlash / Kelmadi / Bekor qilish
  -> mijozning "Navbatlar" ro'yxati, oldindagi odam va kutish vaqti
  -> bildirishnomadan aynan shu navbat kartasiga o'tish
```

`live` yoki `slot` rejimi v1656da xizmatga emas, xizmat ko'rsatuvchiga
biriktiriladi: `medical_doctors.mode`.

## Yo'nalish va atama matritsasi

Monolit 14 yo'nalishda navbatni yoqadi:
`static/index.html:3680–3681`, `api.py:5506–5547`.

1. Transport va logistika
2. Xizmat ko'rsatish
3. Maishiy xizmatlar
4. Qurilish
5. Tibbiy xizmatlar
6. Ko'chmas mulk
7. Axborot texnologiyalari
8. Konsalting va professional
9. Madaniyat, sport, ko'ngilochar
10. Turizm va mehmonxona
11. Reklama va marketing
12. Poligrafiya va nashriyot
13. Moliyaviy faoliyat
14. Import-eksport

Tibbiy xizmatlarda `Shifokor`, `Shifokorlar`, `Bemor`; qolgan 13 yo'nalishda
`Xizmat ko'rsatuvchi`, `Xizmat ko'rsatuvchilar`, `Mijoz` ishlatiladi:
`static/index.html:12076–12078`, `api.py:5535–5540`.

Navbat menyusi Savdo, Umumiy ovqatlanish, Ta'lim faoliyati, Qishloq
xo'jaligi, Ishlab chiqarish va Hunarmandchilikda ko'rinmaydi.

## Funksional birliklar bo'yicha audit

| # | Funksional birlik | Joriy holat | Yangi koddagi dalil | v1656 etaloni | Yetishmayotgan qism / test |
|---:|---|---|---|---|---|
| 1 | 14 yo'nalish guardi va dinamik atamalar | migrated | `frontend/src/profiles/business-profile-config.ts:43–50, 388–389`; `backend/app/business_online/service.py` direction guardi | `static/index.html:3680–3681, 12076–12078`; `api.py:5506–5547` | Mavjud matritsa testlari saqlanadi |
| 2 | Xizmatda navbatni yoqish/o'chirish | migrated | `BusinessItemsV1656Forms.tsx` v1656 maydonini faqat 14 navbatli yo'nalishdagi xizmatda ko'rsatadi; qiymat `business-online/items` yozuvi orqali relatsion katalogning `queue_enabled` ustuniga sinxronlanadi | `static/index.html:2135, 12906, 12947, 13008`; `api.py:2391–2434` | `BusinessItemsV1656Parity.test.tsx` yoqish, yashirish va majburiy o'chirishni tekshiradi |
| 3 | Xizmat ko'rsatuvchilar ro'yxati va formasi | migrated | `BusinessQueueV1656.tsx` setup/list/create/update oqimini typed `/api/v1/queues/business/providers`ga ulaydi; `BusinessMedicalProvidersV1656View`ning v1656 markup va matnlari saqlangan | `static/index.html:2107–2108, 11637–11641`; `api.py:5557–5599` | `BusinessQueueV1656Integration.test.tsx` generic snapshot chaqirilmasligini ham tekshiradi |
| 4 | Biznesning yagona navbat boshqaruvi | migrated | `BusinessQueueV1656.tsx` sana bo'yicha list, offline create, status va swapni typed `/api/v1/queues/business/entries` endpointlariga ulaydi | `static/index.html:2109, 11642–11669`; `api.py:5743–5778` | Integration testi to'rtala amal payloadini va v1656 ko'rinish testlari matn/modal paritetini tekshiradi |
| 5 | Ommaviy profil/katalogdagi `Navbat olish` | partial | `PublicProfileV1656.tsx:137–147` tugmani handlersiz chiqaradi; `CatalogItemCard.tsx:16–20, 50–57` tugma matnini chiqarib profilni ochadi | `static/index.html:5112–5115, 5700–5708, 11711` | Login guardi va booking oqimini ochadigan handler; provider/count payloadi |
| 6 | Sana va xizmat ko'rsatuvchini tanlash | partial | Q1 typed `GET /api/v1/queues/options` va response schemani berdi; `frontend/src/queues` komponenti yo'q | `static/index.html:11682–11694`; `api.py:5600–5605` | Q3 client, modal va parity testi |
| 7 | Slot rejimida bo'sh vaqtlarni olish | partial | Q1 typed `/slots` endpointida ish kuni, o'tgan vaqt va band slot filtri bor; frontend tanlovi yo'q | `static/index.html:11695–11704`; `api.py:5607–5700` | Q3 slot tanlash React oqimi |
| 8 | Onlayn navbat yaratish | partial | Q1 typed `POST /api/v1/queues`, ownership, duplicate/slot unique, atomar live counter va idempotent notificationni berdi | `static/index.html:11705–11710`; `api.py:5624–5676, 5702–5710` | Q3 ommaviy booking komponenti va frontend parity testi |
| 9 | Mijozning `📋 Navbatlar` ro'yxati | partial | Q1 typed `/mine` endpointini berdi; `UserProfile.tsx:446–460` va `MyQueues` View hali yo'q | `static/index.html:6996–7025`; `api.py:5712–5731` | Q4 mijoz View va API client ulanishi |
| 10 | Oldindagi odam va kutish vaqti | partial | Q1 repository bitta indeksli projectionda `ahead_count` va `wait_minutes` hisoblaydi; frontend ko'rsatmaydi | `static/index.html:7007–7010`; `api.py:5716–5730` | Q4 navbat kartasida ko'rsatish |
| 11 | Mijoz navbatini bekor qilish | partial | Q1 ownershipli `POST /{queue_id}/cancel` va history yozuvini berdi; React tasdiqlash oqimi yo'q | `static/index.html:7009, 11712`; `api.py:5733–5741` | Q4 aynan v1656 matnli tasdiqlash va karta yangilanishi |
| 12 | Navbat bildirishnomasi va deep-link | partial | Q1 booked/called/soon/cancelled/changed hodisalarini `notifications` jadvaliga idempotent yozadi; `UserProfile.tsx:469–480` faqat `order_id`ni ochadi | `static/index.html:7561, 7596–7628`; `api.py:5670–5676, 5760–5766` | Q4 `medical_queue_id` deep-linki va read holati |
| 13 | Alohida relatsion navbat jadvallari | migrated | Q1 `backend/app/queues/model.py` va `0012_queue_domain.py`da provider, link, entry, history, counter hamda idempotent dual-source backfillni yaratdi | `database.py:1726–1747` | Q1 model/migration testlari mavjud |
| 14 | Parallel navbat raqami/slot xavfsizligi | migrated | Q1 `QueueRepository.allocate_live_number()` atomar UPSERT/RETURNING, unique slot/customer indekslari va doimiy lock tartibini ishlatadi | `api.py:5649–5668`; `database.py:1733–1743` | PostgreSQL integratsiya tekshiruvi CI migratsiya oqimida ishlaydi |
| 15 | Ikki aktyorli end-to-end parity testi | missing | Biznes ekran parity testi bor, ammo `mijoz -> navbat -> biznes -> bildirishnoma -> mijoz` testi yo'q | Yuqoridagi barcha v1656 oqimlari | Backend transaction va frontend integration/parity testlari |

Q1dan keyingi natija: **3 migrated, 11 partial, 1 missing** funksional birlik.

Q2dan keyingi natija: **6 migrated, 8 partial, 1 missing** funksional birlik.

## Nima uchun mavjud uchta ekran yetarli emas

Q2da `BusinessMedicalV1656View.tsx`ning v1656 ko'rinishi saqlanib,
`BusinessQueueV1656.tsx` adapteri orqali Q1 typed backend domeniga ulandi.
Biznes provider va navbat amallari endi generic `medical_*` snapshotini
o'zgartirmaydi. Biroq Q3/Q4gacha qoladigan frontend oqimi:

- ommaviy foydalanuvchiga sana/provider/slot bermaydi;
- foydalanuvchiga tegishli navbat yozuvini yaratmaydi;
- ommaviy va mijoz typed `/api/v1/queues` endpointlarini chaqirmaydi;
- relatsion navbat yozuvlarini foydalanuvchiga ko'rsatmaydi.

Shu sabab biznesning uch ekrani ham ekran va funksional darajada `migrated`,
ammo ommaviy navbat olish va mijoz zanjiri tugamagani uchun butun **navbat
domeni funksional darajada `partial`**.

## Majburiy biznes qoidalari

1. Queue faqat yuqoridagi 14 yo'nalishda ishlaydi; boshqa yo'nalish 403 oladi.
2. Faqat `kind=service` va `queue_enabled=true` xizmat navbatga ulanadi.
3. Xizmat ko'rsatuvchi faol xodim va faol queue xizmatiga biriktiriladi.
4. `live/slot` rejimi xizmat ko'rsatuvchi kesimida saqlanadi.
5. O'tgan sana, ishlamaydigan kun, o'tgan/band slot qabul qilinmaydi.
6. Bitta foydalanuvchi bir xizmat/provider/sanaga takror faol live navbat
   ololmaydi; slotda aynan bir vaqt takror band qilinmaydi.
7. Mijoz faqat o'zining `waiting` yoki `called` navbatini bekor qiladi.
8. Biznes faqat o'z navbatlarini ko'radi va o'zgartiradi.
9. Faqat bir xil sana, xizmat va providerning ikkita navbati almashtiriladi.
10. `called`, navbati yaqinlashgan, biznes bekor qilgan va raqami o'zgargan
    hodisalar foydalanuvchiga idempotent bildirishnoma yaratadi.
11. Statuslar va matnlar v1656 bilan harfma-harf bir xil bo'ladi.

## Tizimlashtirish bilan chegara

Navbat providerini tanlash v1656da Ma'muriyatdagi faol xodimni o'qiydi. Bu
navbat domenining **read-only bog'liqligi** bo'lib qoladi:

- Xodimlar/Ma'muriyat moduliga yangi qator yozilmaydi;
- Tizimlashtirish komponentlari o'zgartirilmaydi;
- queue provider relatsiyasi biznes, mavjud xodim manba IDsi va ism/kasb
  snapshotini o'zida saqlaydi;
- xodimlar domeni keyin relatsion migratsiya qilinganda optional FK alohida
  blokda ko'rib chiqiladi.

## Rejalashtirilgan modul va papkalar

| Qatlam | Rejalashtirilgan joy | Vazifa |
|---|---|---|
| Backend model | `backend/app/queues/model.py` | provider, provider-service, queue entry, history va atomar counter |
| Backend schema | `backend/app/queues/schemas.py` | public/business request va response turlari |
| Backend repository | `backend/app/queues/repository.py` | ownership va indeksli so'rovlar |
| Backend service | `backend/app/queues/service.py` | live/slot, duplicate, status, swap, ahead/wait va notification qoidalari |
| Backend router | `backend/app/queues/router.py` | typed `/api/v1/queues` endpointlari |
| Migratsiya | `backend/migrations/versions/0012_queue_domain.py` | generic snapshot/fallbackdan idempotent backfill |
| Public booking | `frontend/src/queues/QueueBookingV1656.tsx` | sana, provider, slot va navbat yaratish |
| Mijoz ro'yxati | `frontend/src/queues/MyQueuesV1656.tsx` | `📋 Navbatlar`, ahead/wait, cancel va focus |
| Biznes oqimi | `frontend/src/queues/BusinessQueueV1656.tsx` yoki mavjud `BusinessMedicalV1656View.tsx` adapteri | typed API bilan yagona navbat |
| Frontend API | `frontend/src/api/client.ts`, `frontend/src/api/types.ts` | queue client metodlari va typed DTOlar |
| Testlar | `backend/tests/test_queue_*.py`, `frontend/src/queues/*.test.tsx` | TDD, parity, ownership, concurrency va deep-link |

## Bloklar va PR chegarasi

1. **Q0 — audit:** ushbu hujjat; kod yozilmaydi.
2. **Q1 — relatsion domen:** model, migratsiya/backfill, repository, service va
   typed API.
3. **Q2 — biznes oqimi:** xizmat toggle, provider va biznes navbat ekranlarini
   typed queue APIga ulash.
4. **Q3 — ommaviy navbat olish:** sana, provider, bo'sh slot va online create.
5. **Q4 — mijoz oqimi:** `📋 Navbatlar`, ahead/wait, cancel va notification
   deep-link.
6. **Q5 — yakuniy parity:** ikki aktyorli integration, concurrency, to'liq
   frontend/backend test va audit holatlarini yangilash.

Har blok alohida PR bo'ladi. Keyingi blok faqat oldingi PR CI va Claude Code
Reviewda jiddiy/o'rtacha kamchiliksiz merge qilingandan, keyin foydalanuvchi
ruxsat bergandan so'ng boshlanadi.

## Q0 yakuniy hisoboti

`Navbat funksional pariteti: 1/15 migrated, partial: 5, missing: 9.`

`Onlaynlashtirish ekranlari: 21/21 migrated; navbat domeni: partial.`

## Q1 yakuniy hisoboti

Q1 faqat backend relatsion domenini tayyorladi. `0012_queue_domain.py` kodi
yaratildi, lekin staging/production bazasiga migratsiya va deploy qilinmadi.
Bu amallar uchun alohida foydalanuvchi ruxsati talab qilinadi.

`Navbat funksional pariteti: 3/15 migrated, partial: 11, missing: 1.`

`Onlaynlashtirish ekranlari: 21/21 migrated; navbat domeni: partial.`

## Q2 yakuniy hisoboti

Q2 xizmat formasidagi `Navbat tizimi` maydonini v1656 yo'nalish/kind guardi
bilan qaytardi. Xizmat ko'rsatuvchilar setup/list/create/update hamda biznesning
kunlik list/offline create/status/swap oqimlari typed relatsion queue APIga
ulandi. Tizimlashtirish komponentlari o'zgartirilmadi; Ma'muriyat xodimlari
faqat setup orqali read-only o'qiladi.

`Navbat funksional pariteti: 6/15 migrated, partial: 8, missing: 1.`

`Onlaynlashtirish ekranlari: 21/21 migrated; navbat domeni: partial.`

# Hujjatlar K25 yakuniy migratsiyasi

K25 v1656dagi `Mening hujjatlarim`, hujjatlar markazi, kontragentlar,
hujjat shablonlari va firmalararo almashinuvni umumiy `cabinet_payload`
ro‘yxatidan ajratib, typed PostgreSQL domeniga to‘liq ko‘chiradi.

`static/index.html` v1656 manbasi o‘zgartirilmadi.

## Monolit etalon

| Funksiya | v1656 qatorlari | Moduldagi joyi |
|---|---:|---|
| Ma’muriyat menyusi va `Mening hujjatlarim` | `static/index.html:2771–2788` | `business-profile-config.ts`, `DocumentsV1656.tsx` |
| Hujjatlar markazi | `2808–2817` | `DocumentsV1656.tsx` |
| Kontragentlar ro‘yxati va formasi | `2820–2840`, `9854–9929` | `DocumentsV1656.tsx`, `/api/v1/documents/counterparties` |
| Yaratish, shablon, ro‘yxat, ko‘rish va javob | `2842–2903`, `9932–10370` | `DocumentsV1656.tsx`, `templates.ts` |
| Ekran yuklovchilari va rahbar/STIR saqlash | `12017–12021`, `12347–12359` | `BusinessProfileV3.tsx`, typed profil API |
| Eski hujjat/kontragent backend amallari | `api.py:6253–6591` | `app/documents/*` |

## Monolitdagi ishlash tartibi

```text
Biznes kabineti
  ├─ Mening hujjatlarim
  │    └─ Rahbar + STIR → biznes profilida saqlash
  └─ Hujjatlar
       ├─ Kontragentlar → qo‘shish / tahrirlash / o‘chirish
       ├─ Hujjat yaratish → yo‘nalish → tur → shablon → saqlash
       ├─ Ichki → ko‘rish / tahrirlash / o‘chirish
       ├─ Chiquvchi → STIR bo‘yicha yuborish
       │                 └─ qabul qiluvchida Kiruvchi nusxa
       └─ Kiruvchi → faqat o‘qish → qabul yoki rad
                                      └─ yuboruvchidagi holat yangilanadi
```

## Moduldagi yakuniy yo‘l

```text
DocumentsV1656 + v1656 shablonlari
        │ typed ApiClient
        ▼
/api/v1/documents/*
        │ CSRF + biznes/xodim vakolati
        ▼
DocumentService ── DocumentRepository
        │ bitta DB tranzaksiyasi
        ▼
PostgreSQL
  ├─ document_counterparties
  └─ business_documents
       └─ source_document_id → yuborilgan va kiruvchi nusxa bog‘lanishi
```

## Ma’lumot migratsiyasi

`0038_documents_domain` eski normalizatsiyalangan kabinet yozuvlari va profil
JSON fallbackini bir xil manba sifatida o‘qiydi:

- kontragentlar: `contractors`, `counterparties`;
- hujjatlar: `documents`, `business_documents`, `incoming_documents`,
  `outgoing_documents`, `internal_documents`;
- relatsion manba JSON fallbackdan ustun;
- eski raqamli ID yoki qator xeshi bilan dublikatlar birlashtiriladi;
- `business_account` legacy ID xaritasi yuboruvchi firma bog‘lanishini saqlaydi;
- mavjud typed yozuvlar `ON CONFLICT ... DO NOTHING` bilan ustidan
  yozilmaydi;
- kiruvchi nusxa mos chiquvchi hujjat bilan `source_document_id` orqali
  bog‘lanadi.

## Saqlangan qoidalar

- barcha o‘qish/yozishlar biznes akkaunt doirasidan chiqmaydi;
- xodimga `documents` vakolati kerak;
- kontragentni faqat biznes egasi o‘zgartira oladi;
- kiruvchi hujjat matni o‘zgarmaydi va shu ekrandan o‘chirilmaydi;
- yuborishda STIR normallashtiriladi, faol va yagona firma topiladi;
- o‘ziga yuborish va bir STIRga bir nechta firma topilishi bloklanadi;
- yuborish va qabul/rad javobi atomar tranzaksiyada bajariladi;
- javob avval aniq `source_document_id`, eski ma’lumotda esa v1656 moslik
  qoidasi bilan yuboruvchiga qaytariladi.

## Release gate

- Alembic: `0037_inventory_live_completion → 0038_documents_domain`;
- PostgreSQL offline SQL generatsiyasi: o‘tdi;
- backend hujjat/migratsiya testlari: o‘tdi;
- frontend typed API, hujjat oqimi va kabinet navigatsiyasi testlari: o‘tdi;
- frontend production build: o‘tdi;
- `static/index.html`: 14 091 qator, `BUILD: v1656`, o‘zgarmagan.

## Holat

`Hujjatlar: migrated; partial: 0; missing: 0.`

Monolit etalon rollback va taqqoslash uchun o‘zgartirilmagan. Yangi production
yo‘li hujjatlarni faqat typed modul va PostgreSQL jadvallaridan boshqaradi.

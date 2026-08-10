# Ombor K24 yakuniy migratsiyasi

K24 v1656dagi Ombor ekranini eski umumiy `cabinet_payload` ro‘yxatidan
ajratib, mavjud typed Ombor domeniga to‘liq ulaydi.

## Monolit etalon

| Funksiya | v1656 qatorlari | Moduldagi joyi |
|---|---:|---|
| Ombor menyusi va ekran | `static/index.html:1786`, `2243–2247` | `BusinessProfileV3.tsx`, `WarehouseV1656.tsx` |
| Mahsulotning Ombor maydonlari | `2110–2134`, `12895–13035` | `BusinessItemsV1656Forms.tsx`, `inventory/live_sync.py` |
| Kartalar, guruhlar, kam qoldiq va FIFO | `9195–9244` | `GET /api/v1/warehouse/items`, `WarehouseV1656.tsx` |
| Kirim, retsept va ishlab chiqarish | `9246–9314` | `POST /api/v1/warehouse/moves` |
| Chiqim | `9318–9356` | `POST /api/v1/warehouse/moves` |
| Harakat tarixi va o‘chirish | `9360–9402` | typed moves GET/DELETE |
| Ishlab chiqarish tarixi | `9404–9416` | `GET /api/v1/warehouse/production` |

Oqim:

```text
Mahsulot (“Omborda hisoblash”)
        │
        ├─ mahsulot kartasi / guruh / minimal qoldiq
        ├─ kirim ──> FIFO partiya ──> avtomatik xarajat
        ├─ chiqim ─> FIFO sarfi
        └─ tayyor taom ─> xomashyo sarfi ─> retsept / ishlab chiqarish
```

## Yakuniy modul oqimi

```text
WarehouseV1656
    │ typed ApiClient
    ▼
/api/v1/warehouse/*
    │
    ▼
InventoryService ──> PostgreSQL inventory_* jadvallari
```

- Ombor menyusi endi `warehouse_items`/`warehouse_tx` JSON ro‘yxatini
  ko‘rsatmaydi.
- Yangi tracked mahsulot katalog va Omborga bitta DB tranzaksiyasida ulanadi.
- Boshlang‘ich qoldiq tarix harakati va FIFO partiyasi bilan bir marta yoziladi.
- Mahsulot tahriri joriy qoldiqni qayta yozmaydi; qoldiq faqat Ombor harakati
  orqali o‘zgaradi.
- `0037_inventory_live_completion` 0015dan keyin ulanmay qolgan tracked
  mahsulotlarni qo‘shadi, ammo mavjud Ombor qoldig‘iga tegmaydi.
- Xodim vakolatlari serverda ham saqlanadi: `production` faqat tayyor taom
  kirimini qiladi; `ombor` to‘liq boshqaradi; tannarx ruxsatsiz yashiriladi.

## Ataylab saqlangan xavfsiz farq

Eski v1656 chiqimda manfiy qoldiqqa tushishi mumkin edi. Typed Ombor FIFO
partiyasi yetmasa `409` qaytaradi va tranzaksiyani rollback qiladi. Bu avvalgi
K2–K4 migratsiyasida qabul qilingan ma’lumot yaxlitligi qoidasi bo‘lib qoladi.

## Holat

`Ombor: migrated; partial: 0; missing: 0.`

Monolit etalon rollback va taqqoslash uchun o‘zgartirilmagan.

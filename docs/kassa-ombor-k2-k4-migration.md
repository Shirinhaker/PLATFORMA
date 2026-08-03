# Kassa/Ombor K2–K4 migratsiyasi

Bu paket v1656dagi oddiy Kassa oqimi va tashqi Buyurtma → Kassa → Ombor
zanjirini relatsion PostgreSQL domeniga ko‘chiradi. `static/index.html` v1656
manbasi o‘zgartirilmaydi.

## Ko‘chirilgan funksiyalar

- bir chekda 1–30 ta katalog yoki erkin mahsulot;
- `naqd` va `karta` to‘lovi, bugungi yoki o‘tgan sana;
- biznes bo‘yicha atomar, takrorlanmaydigan chek raqami;
- parallel ko‘p-mahsulotli savdolarda Ombor qatorlarini deterministik tartibda qulflash;
- kunlik tushum va to‘lov turi kesimi;
- xodim uchun serverdagi `kassa` vakolati;
- katalog va Ombor qoldig‘ini bitta so‘rovda ko‘rish;
- chek saqlanganda FIFO chiqimi va tannarx;
- qo‘lda yozilgan chek o‘chirilganda ayni FIFO sarfini qaytarish;
- FIFO sarfi to‘liq topilmasa chek va qoldiqni o‘zgartirmasdan rollback qilish;
- tashqi buyurtma `handoff` qilinganda Kassa va Omborni ayni tranzaksiyada yozish;
- Kassa/Ombor xatosida buyurtma holati, chek va qoldiqni birga rollback qilish;
- eski `sales` yozuvlarini, agar ular bo‘lmasa `cash_transactions` yoki
  `cash_register_transactions`ni idempotent backfill qilish.

## Ataylab xavfsizroq qilingan joylar

| v1656 xatti-harakati | Yangi xatti-harakat | Sabab |
|---|---|---|
| Parallel savdo `MAX(chek_no)+1` ishlatadi | PostgreSQL atomic counter ishlatiladi | Bir xil chek raqamini yo‘qotish |
| UI yetmagan qoldiqni minusga tushirishni taklif qiladi, backend FIFO esa bloklaydi | Frontend ogohlantiradi va backend butun tranzaksiyani `409` bilan bekor qiladi | UI/backend qarama-qarshiligini va manfiy qoldiqni yo‘qotish |
| `qarz` savdosi `qarz_tx` bilan birga yoziladi | `cash_debt_module_required` bilan vaqtincha bloklangan | Qarz daftari hali relatsion migratsiya qilinmagan; ajralgan yozuv yaratmaslik |

## Keyingi alohida integratsiyalar

Quyidagilar K2–K4ning oddiy Kassa va tashqi buyurtma chegarasiga kirmaydi:

- Qarz daftari va `qarz_tx`;
- restoran `dining_bookings` ochiq/yakuniy hisoblari;
- ta’lim `education_payments` kassiri;
- Ombor kirimini Xarajatlarga avtomatik yozish.

Ular o‘z domenlari relatsion ko‘chirilganda Kassa chek manbalariga ulanadi. Eski
yozuvlar hozirgi `0016_cash_register_domain` backfillida saqlanadi; yangi noto‘liq
yozuvchi oqim yoqilmaydi.

## Release gate

- Alembic `0015_inventory_domain → 0016_cash_register_domain` PostgreSQL SQL;
- backend va frontend to‘liq testlari;
- parallel chek raqami va FIFO rollback regressiyalari;
- TypeScript va production build;
- Phase 3A/3B/3C kontraktlari;
- haqiqiy biznesda faqat tasdiqlangan backupdan keyingi read-only smoke-test.

# Xarajatlar K6 migratsiyasi

K6 v1656dagi Xarajatlar ekranini va Ombor kirimi bilan bog‘langan avtomatik
xarajatni relatsion PostgreSQL domeniga ko‘chiradi. `static/index.html` v1656
manbasi o‘zgartirilmaydi.

## Ko‘chirilgan funksiyalar

- tanlangan kun xarajatlari, jami summa va toifalar kesimini ko‘rish;
- oldingi, bugungi va keyingi kun orasida yurish;
- toifa, summa va izoh bilan qo‘lda xarajat yaratish;
- standart toifalardan foydalanish va yangi toifa yaratish;
- Omborga musbat miqdor va tannarx bilan tovar kirganda `Tovar xaridi`
  xarajatini ayni DB tranzaksiyasida avtomatik yozish;
- Ombor kirimi o‘chirilganda bog‘langan avtomatik xarajatni ayni DB
  tranzaksiyasida o‘chirish;
- avtomatik xarajatni Xarajatlar ekranidan alohida o‘chirishni bloklash;
- biznes va xodim vakolatini har bir so‘rovda tekshirish;
- eski `expense_cats` va `expenses` yozuvlarini dublikatsiyasiz ko‘chirish,
  `stock_move_id` orqali mavjud Ombor kirimiga qayta bog‘lash.

## v1656 ekran pariteti

- Ekran tanlangan kun, kunlik jami va toifalar kesimini ko‘rsatadi.
- Xarajatlar teskari xronologik tartibda ko‘rinadi.
- Yangi xarajat oynasida toifa, summa va ixtiyoriy izoh bor.
- Yangi toifa shu oynadan yaratiladi va darhol tanlanadi.
- Ombordan kelgan yozuv `Avto` belgisi bilan ko‘rinadi va alohida o‘chirish
  tugmasiga ega emas.

## Xavfsizlik va yaxlitlik

| Holat | Himoya |
|---|---|
| Begona biznes xarajati yoki toifasi so‘raladi | Har bir query `business_account_id` bilan scope qilinadi |
| Xodimda Xarajatlar vakolati yo‘q | Server `staff_permission_required` bilan rad etadi |
| Bir xil toifa parallel yaratiladi | Biznes+nom noyob indeksi va idempotent javob |
| Ombor kirimi qayta ishlanadi | `inventory_stock_move_id` bo‘yicha noyob indeks |
| Avtomatik xarajat qo‘lda o‘chiriladi | Server `expense_stock_locked` bilan rad etadi |
| Ombor yozuvi yoki xarajat yaratish yiqiladi | Ikkala yozuv bitta DB tranzaksiyasida rollback qilinadi |
| Legacy yozuv qayta migratsiya qilinadi | Biznes+legacy ID upserti dublikatni oldini oladi |

## K6 tarkibiga kirmaydi

- to‘liq Statistika va hisobot analitikasi;
- restoran ichki kassasi va xarajat oqimlari;
- ta’lim to‘lov kassasi;
- restoran yoki ta’limning maxsus xarajat turlari.

Ular keyingi domen migratsiyalarida umumiy Xarajatlar va Ombor
kontraktlaridan foydalanadi.

## Release gate

- Alembic `0017_debt_ledger_domain → 0018_expense_domain` PostgreSQL SQL;
- qo‘lda xarajat va Ombor → Xarajat atomar testlari;
- legacy toifa/xarajat backfill va dublikat testlari;
- backend va frontend to‘liq testlari;
- TypeScript va production build;
- Phase 3A/3B/3C kontraktlari;
- `BUILD v1656`, 98 ekran va `static/index.html` qator soni saqlanishi.

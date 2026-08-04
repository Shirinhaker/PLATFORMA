# Statistika K8 migratsiyasi

K8 v1656dagi umumiy biznes Statistika ekranini relatsion PostgreSQL
manbalariga ko‘chiradi. `static/index.html` v1656 manbasi o‘zgartirilmaydi.
Ta’lim faoliyatining maxsus statistikasi bu bosqichga kirmaydi.

## Ko‘chirilgan funksiyalar

- kun, hafta, oy, chorak, yarim yil va yil davrlari;
- O‘zbekiston vaqti (`UTC+5`) bo‘yicha davr chegaralari;
- oldingi va keyingi davrga yurish;
- jami savdo, haqiqiy pul tushumi, FIFO tannarxi, yalpi va sof foyda;
- operatsion xarajatlar va Ombor xaridlarini alohida ko‘rsatish;
- naqd, karta, qarz va buyurtma to‘lovlari kesimi;
- ichki, tashqi va qo‘lda kiritilgan savdolar kesimi;
- davriy tushum/xarajat/foyda grafigi;
- eng ko‘p sotilgan mahsulotlar va ularning marjasi;
- kam qolgan tovarlar;
- kassir va ofitsiant natijalarini alohida hisoblash;
- xodimning `statistics` vakolatini va biznes scope’ini tekshirish.

## Relatsion manbalar va formulalar

| Ko‘rsatkich | PostgreSQL manbasi | Formula |
|---|---|---|
| Jami savdo | `cash_receipts` + `cash_receipt_lines` | qarz to‘lovidan boshqa qatorlar jami |
| Haqiqiy pul tushumi | shu jadvallar | naqd + karta savdosi + qarz qaytimi |
| FIFO tannarxi | `cash_receipt_lines.cost_total` | saqlangan tannarx; eski qator uchun joriy Ombor tannarxi fallback |
| Yalpi foyda | agregat | jami savdo − FIFO tannarxi |
| Operatsion xarajat | `expenses` | `Tovar xaridi`dan boshqa toifalar |
| Ombor xaridi | `expenses` | faqat `Tovar xaridi` |
| Sof foyda | agregat | yalpi foyda − operatsion xarajat |
| Kam qolgan tovar | `inventory_items` + `catalog_items` | qoldiq bo‘yicha eng past 8 ta kuzatiladigan tovar |

`Tovar xaridi` sof foydadan yana ayrilmaydi: sotilgan mahsulot tannarxi FIFO
orqali allaqachon `cogs`ga kirgan. Uni ikkinchi marta ayirish foydani sun’iy
kamaytirardi. v1656 ham shu formulani ishlatadi.

Agregatlar Python’ga barcha savdo qatorlarini yuklamaydi. Yig‘indi, guruhlash,
davr bucketlari, top mahsulot va xodim kesimlari PostgreSQL so‘rovlarida
hisoblanadi.

## Kassir va ofitsiant atributsiyasi

v1656da ichki restoran buyurtmasini yopgan kassir va buyurtmani olgan
ofitsiant ikki alohida xodim bo‘lishi mumkin. Shu sabab `cash_receipts`ga:

- `waiter_staff_id`;
- `waiter_name_snapshot`

qo‘shildi. `0020` migratsiya eski `dining_bookings` va `dining_orders`
yozuvlarini biznes hamda legacy buyurtma ID bo‘yicha bog‘laydi. Noto‘g‘ri legacy
ID matni xavfsiz `CASE` orqali tashlab ketiladi; begona biznes xodimi yoki
Ombor yozuvi statistikaga qo‘shilmaydi.

## Indekslar

Mavjud vaqt oralig‘i indekslari ishlatiladi:

- `ix_cash_receipts_business_created`;
- `ix_cash_receipts_business_source`;
- `ix_expenses_business_created`.

K8 kam qolgan tovarlar so‘rovi uchun qisman indeks qo‘shadi:

`ix_inventory_items_business_stock_qty`

U faqat `track_stock IS true` yozuvlarini saqlaydi va
`business_account_id, stock_qty, id` tartibida ishlaydi.

## API va ekran pariteti

- `GET /api/v1/statistics?period=...&anchor=...` — bitta to‘liq hisobot;
- `GET /api/v1/statistics/nav?period=...&dir=...&anchor=...` — davr yurishi;
- davr yoki sana almashganda kechikkan eski javob yangi ekranni bosmaydi;
- grafik ko‘rsatkichi almashishi yangi API so‘rovi yubormaydi;
- v1656dagi kartalar, grafik, to‘lov/manba kesimi, mahsulot, qoldiq va xodim
  bloklari saqlanadi;
- umumiy Statistika `Ta'lim faoliyati` kabinetida ko‘rinmaydi.

## Xavfsizlik va yaxlitlik

| Holat | Himoya |
|---|---|
| Xodimda Statistika vakolati yo‘q | `staff_permission_required` |
| Oddiy foydalanuvchi endpointni chaqiradi | `business_account_required` |
| Begona biznes savdo/xarajati mavjud | Har query `business_account_id` bilan scope qilinadi |
| FK noto‘g‘ri biznes xodimi yoki Omboriga qaraydi | JOINning o‘zi ham biznes bilan cheklanadi, snapshot/fallback ishlaydi |
| Eski ofitsiant ID matni noto‘g‘ri | Migratsiya `CASE` bilan cast xatosini oldini oladi |
| Katta savdo tarixi | Hisob SQL agregatsiya va indekslar orqali bajariladi |

## K8 tarkibiga kirmaydi

- Ta’limning dars, davomat, to‘lov, o‘qituvchi va maxsus statistikasi;
- to‘liq Hisobotlar moduli va eksportlar;
- yangi analitik ko‘rsatkich yoki v1656da bo‘lmagan dashboard;
- restoran buyurtma domenining to‘liq JSONdan relatsion migratsiyasi.

## Release gate

- Alembic `0019_education_domain → 0020_statistics_query_indexes` PostgreSQL
  SQL renderi;
- v1656 formulalari, davrlar, vakolat va bizneslararo himoya testlari;
- kassir/ofitsiant alohida atributsiya testi;
- backend va frontend to‘liq testlari;
- TypeScript, Python compile va production build;
- Phase 3A/3B/3C kontraktlari;
- `BUILD v1656`, 98 ekran va `static/index.html` qator soni saqlanishi.

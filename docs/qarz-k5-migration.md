# Qarz daftari K5 migratsiyasi

K5 v1656dagi Qarz daftari, Kassadagi `qarz` to‘lovi va tashqi buyurtmani
qarzga rasmiylashtirishni relatsion PostgreSQL domeniga ko‘chiradi.
`static/index.html` v1656 manbasi o‘zgartirilmaydi.

## Ko‘chirilgan funksiyalar

- qarzdorni ism, ixtiyoriy telefon va boshlang‘ich qarz bilan yaratish;
- har bir qarzdorning joriy qoldig‘i va qarz/to‘lov tarixini ko‘rish;
- yangi qarz va qarz to‘lovini izoh bilan yozish;
- qarz to‘lovi kiritilganda o‘sha kun Kassasiga tushum cheki yaratish;
- Kassada `qarz` to‘lov turini tanlab mavjud yoki yangi qarzdorga yozish;
- qarz savdosi cheki o‘chirilganda FIFO qoldig‘i va qarz yozuvini bitta
  tranzaksiyada qaytarish;
- qabul qilingan tashqi buyurtmani qarzga rasmiylashtirish va takroriy
  so‘rovda ikkinchi qarz yozuvi yaratmaslik;
- buyurtma topshirilganda mavjud qarz yozuvini Kassa cheki va Ombor FIFO
  sarfiga ayni tranzaksiyada bog‘lash;
- bizneslararo qarzdor ID’larini serverda rad etish;
- `debts`, `kassa`, `payment_confirm` va `payment_review` vakolatlarini
  v1656dagi amal chegarasiga mos tekshirish;
- eski `debtors`, `qarz_transactions` va `qarz_tx` yozuvlarini dublikatsiyasiz
  ko‘chirish, eski `sales.qarz_tx_id` orqali Kassa chekiga qayta bog‘lash.

## v1656 ekran pariteti

- Qarz daftari umumiy qarz va qarzdorlar sonini ko‘rsatadi.
- Yangi qarzdor oynasida aynan uch maydon bor: ism, telefon va boshlang‘ich
  qarz.
- Qarz/to‘lov oynasida aynan summa va ixtiyoriy izoh bor.
- Qarzdor kartasida amaliyotlar teskari xronologik tartibda, sana va izoh
  bilan ko‘rinadi.
- Kassa va tashqi buyurtma oynalari bir xil qarzdor tanlash formasidan
  foydalanadi.

## Xavfsizlik va yaxlitlik

| Holat | Himoya |
|---|---|
| Bir buyurtma qayta qarzga yuboriladi | `order_id` bo‘yicha qisman noyob indeks va idempotent servis |
| Begona biznes qarzdori yuboriladi | Har bir so‘rovda `business_account_id` bilan scope tekshiruvi |
| Kelajak sanaga qarz/to‘lov yoziladi | Server `debt_future_date_forbidden` bilan rad etadi |
| Qarz cheki o‘chiriladi | Qarz yozuvi, chek va FIFO qaytarishi bitta DB tranzaksiyasida |
| Legacy yozuv ikki eski nomda mavjud | `qarz_transactions` ustuvor deduplikatsiyasi |
| Legacy sana buzilgan | PostgreSQL `pg_input_is_valid` orqali xavfsiz fallback |

## K5 tarkibiga kirmaydi

- restoran ichki hisoblarini qarzga yozish;
- ta’lim to‘lov kassasi va to‘lov nazorati;
- Xarajatlar moduli;
- restoran yoki ta’limning maxsus Kassa oqimlari.

Ular o‘z domenlari relatsion ko‘chirilganda Qarz/Kassa bog‘lanishidan
foydalanadi.

## Release gate

- Alembic `0016_cash_register_domain → 0017_debt_ledger_domain` PostgreSQL SQL;
- Qarz → Kassa, Buyurtma → Qarz → Kassa/Ombor atomar testlari;
- backend va frontend to‘liq testlari;
- TypeScript va production build;
- Phase 3A/3B/3C kontraktlari;
- `BUILD v1656`, 98 ekran va `static/index.html` qator soni saqlanishi.

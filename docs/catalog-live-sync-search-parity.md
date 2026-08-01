# Katalog live-sync va qidiruv pariteti

## Monolitdagi etalon

- `static/index.html:4717–4755` — bosh sahifa qidiruv so‘rovini yuboradi va
  natijalarni ko‘rsatadi.
- `api.py:8277–8290` — `/api/search` endpointi.
- `api.py:8496–8526` — mahsulot va xizmatlar bevosita `items` jadvalidan
  qidiriladi; FTS ishlamasa `LIKE` zaxirasi qo‘llanadi.

Monolitda biznes kabinetiga qo‘shilgan faol mahsulot yoki xizmat shu zahoti
qidiruv manbaiga aylanadi. Yangi arxitekturada kabinet yozuvlari
`cabinet_records`da, public qidiruv esa `catalog_items`da saqlangani uchun ular
orasida jonli sinxronizatsiya bo‘lishi shart.

## Yangi ma’lumot oqimi

1. `BusinessOnlineService` `items` yoki `item_groups` yozuvini yaratadi,
   tahrirlaydi yoki o‘chiradi.
2. Shu PostgreSQL tranzaksiyasi ichida `sync_business_catalog` public katalogni
   tenglashtiradi.
3. Commit muvaffaqiyatli bo‘lgach `CatalogCacheEpoch` oshadi. Oldingi qidiruv va
   katalog keshi qayta ishlatilmaydi.
4. `/api/v1/public/search` `catalog_items`dagi `active + ready` yozuvlarni
   qaytaradi.

Har bir live yozuv `(business_account_id, source_record_key)` composite kaliti
bilan aniqlanadi. Shu sabab ikki biznesdagi ichki `id=1` yozuvlari bir-biriga
aralashmaydi.

## Stagingga chiqarish tartibi

Public flag backfill tekshirilmasdan yoqilmaydi.

1. API deploymentda yangi kodni joylang.
2. `backend/` ichida `python -m alembic upgrade head` bajaring. Revision
   `0007_catalog_live_sync`:
   - Phase 3C katalog yozuvlarini V7 kabinet source keylari bilan bog‘laydi;
   - mavjud `cabinet_records`ni, marker bo‘lmasa JSON fallbackni o‘qiydi;
   - `item_groups` va `items`ni idempotent `ON CONFLICT` backfill qiladi;
   - kabinetda o‘chirilgan tarixiy public yozuvlarni olib tashlaydi.
3. Quyidagi gate’larni flag o‘chiq holatda tekshiring:
   - bir biznes uchun `catalog_items` soni kabinet `items` soniga teng;
   - `(business_account_id, source_record_key)` takrorlanmagan;
   - `stomatolog`, `ingliz tili` va `fsf` yozuvlari `catalog_items`da mavjud;
   - bo‘sh nomli yozuv `review_required` holatida.
4. Faqat gate’lar o‘tgach Railway API variables ichida
   `KOPRIK_PHASE3C_PUBLIC_ENABLED=true` qilib API’ni qayta deploy qiling.
5. Bosh sahifada Qumqo‘rg‘on hududi bilan `stomatolog` va `ingliz tili`
   qidiruvlarini qo‘lda tekshiring.

Rollbackda avval `KOPRIK_PHASE3C_PUBLIC_ENABLED=false` qilinadi. Schema
downgrade faqat alohida tasdiqlangan texnik rollbackda bajariladi, chunki u
revisiondan keyin yaratilgan live public katalog nusxalarini olib tashlaydi;
kabinetning asosiy `cabinet_records` ma’lumotlariga tegmaydi.

# Phase 2 `/me` profil xulosasi cache dizayni

## Maqsad

`GET /api/v1/me` endpointini 1000 parallel so‘rovda barqaror ishlatish:

- xatolar soni: `0`;
- `p95`: `500 ms` dan past;
- profil yangilangandan keyin foydalanuvchi eski ma’lumotni ko‘rmasligi;
- Redis ishlamasa ham endpoint PostgreSQL orqali ishlashda davom etishi.

## Joriy holat va sabab

Session aniqlash Redis cache’iga ko‘chirilgandan keyingi diagnostika:

- `auth_session`: 1000/1000 HTTP 200, `p95 = 830 ms`;
- `/me`: 1000/1000 HTTP 200, `p95 = 2864 ms`.

`/me` har bir so‘rovda yangi SQLAlchemy sessiyasi ochib, foydalanuvchi yoki
biznes profilini PostgreSQL’dan o‘qiydi. API pool’i `20 + 20 overflow` ulanish
bilan cheklangan. Shu sabab 1000 parallel so‘rov DB ulanishini kutib navbatga
tushadi.

## Tanlangan yechim

Redis profil xulosasi cache’i va bir xil akkauntga tegishli parallel cache
miss’larni bitta DB o‘qishiga birlashtirish.

Faqat DB pool’ni kattalashtirish tanlanmadi: u xarajatni oshiradi va navbat
muammosini yuqori yuklamada yana qaytaradi. Oddiy Redis cache ham yetarli emas:
cache bo‘sh paytda 1000 so‘rov bir vaqtda DB’ga tushishi mumkin.

## Arxitektura

Yangi `ProfileSummaryService` quyidagi yagona vazifaga ega:

1. akkaunt turi va ID bo‘yicha ixcham `/me` javobini Redis’dan o‘qish;
2. cache miss bo‘lsa, shu kalit uchun faqat bitta davom etayotgan DB vazifasini
   yaratish;
3. profilni service’ga tegishli DB sessiyasi orqali o‘qish;
4. `MeRead` xulosasini Redis’ga TTL bilan yozish;
5. barcha parallel so‘rovlarga bir xil natijani qaytarish.

Service ilova lifespan’ida yaratiladi va
`app.state.profile_summary_service` orqali ishlatiladi. `/me` endi request
dependency orqali alohida `ProfileSession` ochmaydi. Boshqa profil endpointlari
mavjud sessiya oqimini saqlab qoladi.

### Cache kaliti va qiymati

Kalit:

```text
profile:me:v1:{account_type}:{account_id}
```

Qiymat faqat quyidagi maydonlardan iborat JSON bo‘ladi:

- `account_id`;
- `account_type`;
- `name`;
- `profile_complete`.

Standart TTL: `30` soniya. Sozlama
`KOPRIK_PROFILE_SUMMARY_CACHE_TTL_SECONDS` orqali `5–300` soniya oralig‘ida
o‘zgartiriladi.

## Ma’lumot oqimi

### O‘qish

1. Auth dependency sessiyani aniqlaydi.
2. `/me` `ProfileSummaryService.resolve(account_type, account_id)` ni chaqiradi.
3. Yaroqli Redis qiymati bo‘lsa, darhol qaytariladi.
4. Cache miss bo‘lsa, shu akkaunt uchun mavjud in-flight vazifa qayta ishlatiladi.
5. Vazifa yo‘q bo‘lsa, service o‘z DB sessiyasini ochib profilni bir marta
   o‘qiydi, xulosani hisoblaydi va cache’ga yozadi.

### Yozish va invalidatsiya

Quyidagi muvaffaqiyatli `commit`lardan keyin tegishli cache kaliti o‘chiriladi:

- `PUT /api/v1/user-profile`;
- `PUT /api/v1/business-profile`;
- `PUT /api/v1/user-profile/avatar`;
- `PUT /api/v1/business-profile/logo`.

Invalidatsiya faqat DB commit muvaffaqiyatli tugagandan keyin bajariladi.
Keyingi `/me` yangi profil qiymatini DB’dan olib cache’ni qayta yaratadi.

## Parallel so‘rovlarni birlashtirish

Service jarayon ichida `account_type + account_id` bo‘yicha in-flight task
saqlaydi. Birinchi cache miss DB o‘qishini boshlaydi; qolgan so‘rovlar shu taskni
kutadi. Task tugashi bilan xaritadan olib tashlanadi. Kutuvchi request bekor
bo‘lsa, umumiy DB vazifasi `asyncio.shield` orqali bekor qilinmaydi.

Bu mexanizm har bir API replica ichida ishlaydi. Redis barcha replicalar uchun
umumiy cache bo‘lib qoladi.

## Xatolarni boshqarish

- Redis read xatosi: warning log yoziladi va PostgreSQL fallback ishlaydi.
- Redis qiymati noto‘g‘ri JSON yoki schema’ga mos emas: kalit o‘chiriladi va DB
  fallback ishlaydi.
- Redis write xatosi: DB’dan olingan to‘g‘ri javob qaytariladi; cache’siz davom
  etiladi.
- Redis invalidatsiya xatosi: profil saqlanishi bekor qilinmaydi; warning log
  yoziladi va TTL eski qiymatning eng ko‘p yashash muddatini cheklaydi.
- DB yoki profil topilmasligi: mavjud `ApiError` xatti-harakati saqlanadi.

## Testlar

Avval muvaffaqiyatsiz testlar yoziladi, keyin minimal implementatsiya qilinadi:

1. birinchi resolve DB’dan o‘qiydi, ikkinchisi Redis’dan qaytadi;
2. bir akkaunt uchun parallel cache miss’lar faqat bitta DB sessiyasi ochadi;
3. boshqa akkauntlar alohida cache kalitlaridan foydalanadi;
4. yaroqsiz cache qiymati DB fallback’ga o‘tadi;
5. Redis read/write xatolari endpointni yiqitmaydi;
6. profil update commit’idan keyin cache invalidatsiya qilinadi;
7. update rollback bo‘lsa cache o‘chirilmaydi;
8. mavjud `/me`, user profile va business profile contract testlari o‘tadi.

To‘liq regressiya tekshiruvi:

- legacy testlar;
- backend testlar;
- frontend test va production build;
- legacy contract;
- `BUILD: v1656`;
- `static/index.html` qator soni o‘zgarmaganini tekshirish.

## Railway tekshiruvi

Kod GitHub checks’dan o‘tgach `api-staging`ga deploy qilinadi. `/readyz` 200
bo‘lgandan keyin mavjud latency diagnostikasi qayta ishga tushiriladi.

Phase 2 gate faqat quyidagi shartlarda o‘tadi:

- `/me`: 1000 parallel so‘rov;
- xatolar: `0`;
- barcha javoblar: HTTP `200`;
- `p95 < 500 ms`.

## Qamrovdan tashqari

- frontend dizaynini o‘zgartirish;
- to‘liq user/business profile javoblarini cache qilish;
- DB pool hajmini oshirish;
- global distributed lock;
- 10 000 parallel foydalanuvchi uchun yakuniy production load testi.

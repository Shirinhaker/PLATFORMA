# Ko‘prik biznes “Obunalarim” — dizayn spetsifikatsiyasi

## Maqsad

Biznes kabinetining `Onlaynlashtirish` guruhiga pullik tariflarni boshqarish uchun
alohida `Obunalarim` bo‘limini qo‘shish. Karta `Profil / Mening sahifam`dan keyin,
`Mahsulot yoki xizmatlar` kartasidan oldin turadi.

Bu birinchi bosqich demo faollashtirish bo‘ladi. Haqiqiy to‘lov, karta rekvizitini
kiritish, Click/Payme va avtomatik yechib olish bu versiyaga kirmaydi.

## Birinchi versiya chegarasi

- Faqat biznes profil obunasi qo‘shiladi.
- Tariflar: `Bepul`, `Plus`, `Pro`.
- Plus va Pro uchun muddat: 1 oy, 3 oy yoki 12 oy.
- Narxlar hali kelishilmagan; kodga taxminiy narx yozilmaydi.
- Mahsulot/xizmat joylash barcha tariflarda tarif bo‘yicha cheklanmaydi.
- Istoriya funksiyasi obuna tariflaridan mustaqil va hozirgi tartibda ishlaydi.
- Demo tarif serverdagi SQLite bazasida saqlanadi va boshqa qurilmada ham tiklanadi.
- Bir biznesda bir vaqtda faqat bitta joriy tarif bo‘ladi.
- Bir xil tarif qayta faollashtirilsa, yangi muddat mavjud tugash sanasidan uzayadi.
- Boshqa tarif tanlansa, oldingi yozuv tarixga o‘tadi va yangi tarif darhol boshlanadi.
- `Bepul` tarif muddatsiz hisoblanadi.
- Biznes tarifini faqat biznes egasi ko‘rishi va o‘zgartirishi mumkin; xodimga
  ushbu bo‘lim ko‘rsatilmaydi.

## Kelishilgan tarif imkoniyatlari

### Bepul

- Amaldagi asosiy biznes profil va onlayn bo‘limlardan foydalanish.
- Mahsulot/xizmat joylash tarif bo‘yicha cheklanmaydi.

### Plus

- Bepul tarif imkoniyatlari.
- Mahsulot yoki xizmatlar bosh sahifadagi `Sizga yaqin` bo‘limiga chiqarilish
  huquqiga ega bo‘ladi.

### Pro

- Plus tarif imkoniyatlari.
- Biznes metkasi xaritada ko‘rsatilish huquqiga ega bo‘ladi.

Bu versiya obuna yozuvi va kelajakdagi tekshiruv uchun yagona entitlement yordamchisini
yaratadi. Bosh sahifadagi tuman takliflari va xarita shu yordamchidan foydalanadi.
Istoriya karuseli va istoriya endpointlari obuna yordamchisiga ulanmaydi.

## Kabinet interfeysi

`cabGridOnline` ichidagi tartib:

1. `Profil / Mening sahifam`.
2. `Obunalarim`.
3. Yo‘nalishga mos `Mahsulotlar`, `Xizmatlar` yoki boshqa mavjud karta.
4. Qolgan amaldagi onlayn kartalar.

`Obunalarim` ekrani:

- yuqorida joriy tarif kartasi;
- tarif holati, boshlanish va tugash sanasi;
- 1/3/12 oy tanlash tugmalari;
- Bepul, Plus va Pro imkoniyat kartalari;
- `Demo faollashtirish` tugmasi;
- avvalgi obunalar tarixi;
- yuklanish, bo‘sh tarix va xato holatlari;
- telefon, planshet va kompyuterga mos responsive ko‘rinish.

Ijtimoiy kuzatuv ma’nosidagi mavjud `Obunalarim` nomlari yangi pullik bo‘lim bilan
chalkashmasligi uchun `Kuzatayotganlar` deb o‘zgartiriladi. Follow mexanizmi
o‘zgarmaydi.

## Ma’lumotlar modeli

Yangi `business_subscriptions` jadvali:

- `id` — birlamchi kalit;
- `business_id` — obuna egasi;
- `plan_code` — `free`, `plus`, `pro`;
- `duration_months` — Plus/Pro uchun `1`, `3`, `12`, Bepul uchun `0`;
- `starts_at` va `expires_at` — amal qilish vaqti, Bepul uchun `expires_at=0`;
- `status` — `active`, `superseded`, `expired`;
- `is_demo` — demo yozuv belgisi;
- `created_at` — yaratilgan vaqt.

Joriy tarifni topish uchun bitta backend yordamchi ishlatiladi. Muddat tugagan
Plus/Pro yozuvi so‘rov vaqtida `expired` sifatida qaraladi va biznes Bepul tarifga
qaytadi. Eski yozuvlar tarix uchun saqlanadi.

## API

- `GET /api/business/subscription` — biznes egasining joriy tarifi, imkoniyatlari
  va tarixini qaytaradi.
- `POST /api/business/subscription/demo-activate` — `plan_code` va
  `duration_months`ni tekshirib demo tarifni faollashtiradi.

Noto‘g‘ri tarif yoki muddat `400`, tizimga kirmagan foydalanuvchi `401`, biznes
egasi bo‘lmagan aktyor `403` oladi. Takroriy bosishni kamaytirish uchun frontend
tugmani so‘rov tugaguncha bloklaydi.

## Mavjud funksiyalarni himoyalash

- `CAB_PLANS` va 20 yo‘nalish moslashuvi saqlanadi.
- Navbat, ta’lim, umumiy ovqatlanish va xodim kartalarining ko‘rinish qoidalari
  o‘zgarmaydi.
- Mahsulot, istoriya, xarita, qidiruv, buyurtma va follow endpointlarining mavjud
  javobi bu bosqichda o‘zgarmaydi.
- Kassa, ombor, qarz, xarajat, statistika va ma’muriyatga tegilmaydi.

## Testlar

- jadval migratsiyasi va default Bepul tarif;
- Plus/Pro muddat tekshiruvi;
- bir xil tarif muddatini uzaytirish;
- tarif almashtirilganda tarix saqlanishi;
- bizneslar ma’lumotining aralashmasligi;
- faqat egasi faollashtira olishi, xodimga taqiq;
- API kontrakti va xato kodlari;
- `Obunalarim` kartasi `Profil`dan keyin turishi;
- eski follow nomining `Kuzatayotganlar`ga o‘zgarishi;
- mobil ekran overflow bermasligi;
- barcha mavjud regressiya testlari.

## Versiya va topshirish

- Yakuniy build: `v1612`.
- To‘liq loyiha ZIP va faqat o‘zgargan fayllar ZIP’i beriladi.
- O‘zgargan fayllar, build raqami va `static/index.html` qatorlar soni alohida
  ko‘rsatiladi.

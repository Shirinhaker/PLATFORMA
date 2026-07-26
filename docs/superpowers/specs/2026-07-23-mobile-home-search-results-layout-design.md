# BUILD v1631 — mobil bosh sahifa va qidiruv natijalari dizayni

## Maqsad

Telefon bosh sahifasida xarita egallayotgan joyni biroz kamaytirish, qidiruv
natijalarini xaritaning bevosita ostida ko‘rsatish va bosh sahifadagi eski
qidiruv turi filtrlarini olib tashlash.

## Qamrov

- Joylashuv va o‘lcham o‘zgarishlari telefon kengligi — `620px` va undan
  kichik ekranlar uchun.
- Bosh sahifadagi to‘rtta tezkor filtr barcha ekran o‘lchamlarida olib
  tashlanadi.
- Oddiy bosh sahifa bitta ekran ichida qoladi.
- Qidiruv natijalari ochilganda sahifa vertikal aylantirilishi mumkin.
- Filtrlar olib tashlanishidan tashqari desktop va planshet ko‘rinishi
  o‘zgarmaydi.
- Qidiruv API, natijalarni saralash, xarita metkalari va profil rollari
  o‘zgarmaydi.

## Bosh sahifa

### Olib tashlanadigan qism

Bosh sahifadagi quyidagi tezkor filtr tugmalari olib tashlanadi:

- Mahsulot
- Xizmat
- Biznes
- Mutaxassis

Faqat bosh sahifadagi tugmalar olib tashlanadi. Backenddagi `result_type`
qo‘llab-quvvatlashi va katalog orqali qidirish imkoniyati saqlanadi.

### Bo‘shagan joy taqsimoti

Filtr tugmalaridan bo‘shagan joy quyidagicha taqsimlanadi:

- istoriyalar qatori biroz kattalashadi;
- qidiruv maydoni va `Qidirish` tugmasi kattalashadi;
- `Katalog bo‘yicha` tugmasi kattalashadi;
- reklama bloki kattalashadi;
- hududiy mahsulot/xizmat/e’lon kartalari kattalashadi;
- xarita balandligi hozirgidan biroz kamayadi.

Telefon bosh sahifasi odatiy holatda vertikal yoki gorizontal chiqib ketmasligi
kerak.

## Qidiruv natijalari holati

Qidiruv bajarilganda:

1. Xarita ixcham balandlikka o‘tadi.
2. Natijalar xaritaning bevosita ostida ochiladi.
3. Reklama natijalardan keyin turadi.
4. Hududiy takliflar reklamadan keyin turadi.
5. Natijalar ko‘p bo‘lsa, bosh sahifada vertikal aylantirish yoqiladi.

Qidiruv yopilganda oddiy bitta ekranli bosh sahifa holati qayta tiklanadi.

## Texnik yondashuv

- `.phone` elementiga qidiruv natijalari ochiqligini bildiruvchi alohida CSS
  klass qo‘shiladi.
- `enterResults()` klassni yoqadi, `exitResults()` klassni o‘chiradi.
- Mobil qidiruv holatida `resWrap` vizual tartib bo‘yicha xaritadan keyin,
  reklamadan oldin joylashtiriladi.
- Oddiy mobil holatdagi v1630 grid alohida saqlanadi.
- Qidiruv natijalari HTML kartalari va server so‘rovlari qayta yozilmaydi.

## Qabul mezonlari

- `320×568`, `360×640`, `390×844` ekranlarda oddiy bosh sahifa bitta ekranga
  sig‘adi.
- Mahsulot/Xizmat/Biznes/Mutaxassis bosh sahifa filtrlari ko‘rinmaydi.
- Qidiruv natijalari telefonda xaritaning ostidan chiqadi.
- Natijalardan keyin reklama va hududiy takliflar saqlanadi.
- Qidiruvdan chiqilganda bosh sahifa yana aylantirilmaydigan holatga qaytadi.
- Desktop va planshet shartnomalari o‘tadi.
- Mavjud Python va frontend testlari yashil qoladi.

## O‘zgarmaydigan qismlar

- qidiruv algoritmi va API parametrlari;
- xarita metkalarini tanlash va chizish;
- Pro/Plus va oddiy profil qoidalari;
- reklama va hududiy takliflarning ma’lumot manbalari;
- katalog ichidagi qidiruv va faoliyat turlari;
- e’lonlar sahifasi.

# Koprik Taxi chaqiruv oynasini tozalash — dizayn spetsifikatsiyasi

## Maqsad

Telefon va planshetda Taxi chaqiruv oynasi ochilganda bosh sahifadagi reklama,
mahsulot, xizmat va e’lon kartalari ko‘rinmasligi kerak. Taxi oqimi v1630–v1631
mobil bosh sahifa grididan mustaqil ishlashi va pastdagi kartalar buyurtma
panelining ustiga chiqmasligi kerak.

## Tasdiqlangan ko‘rinish

Taxi rejimida quyidagilar qoladi:

- bosh sahifa yuqori paneli;
- istoriyalar qatori;
- Taxi/Dostavka buyurtma paneli;
- manzil tanlash uchun asosiy xarita;
- haydovchini qidirish va faol buyurtma holatlari.

Taxi rejimida quyidagilar yashiriladi:

- bosh sahifa qidiruv va katalog kartasi;
- qidiruv natijalari;
- reklama banneri va uning nuqtalari;
- tumandagi mahsulot, xizmat va e’lonlar karuseli;
- Taxi buyurtmasiga aloqasi bo‘lmagan boshqa bosh sahifa bloklari.

## Texnik yechim

`enterCall()` Taxi oqimini boshlaganda asosiy `.phone` elementiga alohida
`taxi-call-active` holati qo‘shiladi. `exitCall()` bu holatni olib tashlaydi.
Holatga bog‘langan CSS Taxi sahifasining mobil joylashuvini oddiy vertikal
oqimga qaytaradi va v1630–v1631 ning besh qatorli bosh sahifa gridini Taxi
paneliga qo‘llamaydi.

Reklama va hududiy takliflar faqat JavaScript orqali bir marta yashirilmaydi.
`taxi-call-active` CSS holati ham ularni majburiy yashiradi. Shuning uchun
fon API so‘rovi kechroq tugab, hududiy mahsulotlarni qayta chizsa ham ular Taxi
rejimida ko‘rinmaydi.

Mavjud Taxi API, narx hisoblash, GPS, xaritadan manzil tanlash, Taxi/Dostavka
almashtirish va buyurtma yuborish jarayonlari o‘zgartirilmaydi.

## Holatlar oqimi

1. Foydalanuvchi xaritadagi Taxi tugmasini bosadi.
2. `enterCall()` Taxi holatini yoqadi, boshqa bosh sahifa bloklarini yashiradi
   va buyurtma panelini ochadi.
3. Foydalanuvchi xaritada boshlanish va borish manzilini tanlaydi.
4. Buyurtma yuborilganda haydovchi qidirish/faol buyurtma paneli shu toza Taxi
   sahifasida ko‘rsatiladi.
5. Yopish tugmasi bosilganda `exitCall()` Taxi holatini o‘chiradi, xaritani bosh
   sahifa holatiga qaytaradi va reklama/takliflarni yana ko‘rsatishga ruxsat
   beradi.

## Xatolarga chidamlilik

- Hududiy takliflar API javobi Taxi ochilgandan keyin kelsa ham kartalar
  ko‘rinmaydi.
- Taxi yopilganda yashirilgan bosh sahifa bloklari tiklanadi.
- Bir necha marta ochib-yopish eski CSS holatini qoldirmaydi.
- Qidiruv natijalari ochiq paytda Taxi bosilsa, avval qidiruv holati yopiladi.

## Qabul mezonlari

1. Telefon ekranida Taxi paneli va xarita bir-birining ustiga chiqmaydi.
2. Taxi rejimida reklama, mahsulot, xizmat va e’lonlar ko‘rinmaydi.
3. Istoriyalar qatori ko‘rinib turadi.
4. Taxi/Dostavka, GPS, xaritadan manzil tanlash, “O‘zim aytaman”, buyurtma va
   yopish tugmalari ishlaydi.
5. Taxi yopilganda odatiy bosh sahifa to‘liq qaytadi.
6. Desktop va planshetda ham Taxi rejimida reklama va hududiy takliflar
   ko‘rinmaydi.
7. Mavjud backend va boshqa bo‘limlar o‘zgarmaydi.

## Testlar

- Taxi holati yoqilganda `taxi-call-active` klassi qo‘shilishini tekshirish.
- Taxi yopilganda klass olib tashlanishini tekshirish.
- Taxi holatida reklama, qidiruv, natijalar va `districtOffersMount` yashirin
  bo‘lishini tekshirish.
- Kechikkan `renderDistrictOffers()` chaqiruvi Taxi holatida kartalarni ko‘rsata
  olmasligini tekshirish.
- Taxi oqimining mavjud JavaScript sintaksisi va loyiha testlarini ishga
  tushirish.

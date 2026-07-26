# Koprik alohida Taxi sahifasi — dizayn spetsifikatsiyasi

## Maqsad

Taxi chaqiruv oqimini bosh sahifa ichidan chiqarib, boshqa bo‘limlar kabi
alohida sahifaga o‘tkazish. Bosh sahifadagi qidiruv, istoriyalar, reklama,
mahsulot, xizmat va e’lonlar faqat `home` sahifasida ko‘rinadi.

## Ekranlar chegarasi

`home` sahifasi quyidagilarga egalik qiladi:

- qidiruv va katalog;
- istoriyalar;
- bosh sahifa xaritasi;
- reklama;
- tumandagi mahsulot, xizmat va e’lonlar.

Yangi `taxi-call` sahifasi quyidagilarga egalik qiladi:

- Taxi/Dostavka buyurtma paneli;
- haydovchi qidirilayotgan holat;
- qabul qilgan haydovchi ma’lumoti;
- manzil tanlash xaritasi;
- sahifa sarlavhasi va orqaga/yopish amali.

`taxi-call` sahifasida bosh sahifa qidiruvi, istoriyalar, reklama va hududiy
takliflar markup sifatida ham joylashtirilmaydi.

## Xarita arxitekturasi

Loyihada mavjud bitta Leaflet xarita instansi saqlanadi. Ikkinchi xarita
yaratilmaydi va Taxi backend oqimi o‘zgarmaydi.

Taxi ochilganda mavjud `.home-map-pane` elementi `home` ichidan
`#taxiMapHost` konteyneriga ko‘chiriladi. Taxi yopilganda aynan shu element
`#homeDiscovery` ichidagi oldingi ikkinchi joyiga qaytariladi. Har ikki
ko‘chirishdan keyin Leaflet o‘lchami `invalidateSize()` bilan qayta hisoblanadi.

## Navigatsiya

1. Bosh sahifadagi Taxi tugmasi `enterCall()`ni ishga tushiradi.
2. `enterCall()` buyurtma holatini tayyorlaydi, xaritani Taxi sahifasiga
   ko‘chiradi va `nav("taxi-call")`ni chaqiradi.
3. Paneldagi yopish tugmasi, xaritadagi Taxi tugmasi yoki yuqori orqaga tugmasi
   `exitCall()`ni chaqiradi.
4. `exitCall()` buyurtma UI holatini tozalaydi, xaritani bosh sahifaga
   qaytaradi va `nav("home")`ni chaqiradi.
5. Tizimga kirmagan foydalanuvchi buyurtma yuborsa, Taxi holati xavfsiz yopilib,
   xarita bosh sahifaga qaytarilgandan keyin login sahifasi ochiladi.

## O‘zgarmaydigan qismlar

- Taxi/Dostavka tanlovi;
- GPS va xaritani surib manzil tanlash;
- narx va masofa hisoblash;
- buyurtma yuborish;
- haydovchi qidirish va qabul qilingan safar holatlari;
- Taxi API va ma’lumotlar bazasi;
- bosh sahifa qidiruvi, istoriyalar, reklama va hududiy takliflar algoritmi.

## Xatolarga chidamlilik

- Taxi sahifasi bir necha marta ochilib-yopilganda xarita elementi
  ko‘paytirilmaydi.
- Orqaga tugmasi oddiy `nav("home")` qilmaydi; doim `exitCall()` orqali xaritani
  joyiga qaytaradi.
- Login sahifasiga o‘tishda xarita Taxi sahifasida qolib ketmaydi.
- Kechikkan reklama yoki hududiy taklif javobi faqat faol bo‘lmagan `home`
  ichida chizilishi mumkin; Taxi sahifasiga kira olmaydi.

## Qabul mezonlari

1. Taxi bosilganda faol ekran `data-screen="taxi-call"` bo‘ladi.
2. Taxi sahifasida istoriyalar, qidiruv, reklama va takliflar mavjud emas.
3. Taxi paneli, haydovchi kartasi va xarita to‘g‘ri tartibda chiqadi.
4. Yuqori orqaga va paneldagi yopish tugmalari xaritani bosh sahifaga qaytaradi.
5. Taxi yopilganda bosh sahifadagi qidiruv, istoriyalar, reklama va takliflar
   odatdagidek ko‘rinadi.
6. Mavjud Taxi funksiyalari va boshqa bo‘limlar buzilmaydi.

## Testlar

- `taxi-call` screen va uning yagona Taxi elementlari mavjudligini tekshirish.
- Bosh sahifa promo bloklari Taxi screen markupida yo‘qligini tekshirish.
- Xarita ochishda `taxiMapHost`ga, yopishda `homeDiscovery`ga ko‘chishini
  tekshirish.
- Yuqori orqaga tugmasi Taxi holatida `exitCall()`ni chaqirishini tekshirish.
- Login yo‘nalishida Taxi holati yopilishini tekshirish.
- Inline JavaScript sintaksisi va barcha loyiha testlarini ishga tushirish.

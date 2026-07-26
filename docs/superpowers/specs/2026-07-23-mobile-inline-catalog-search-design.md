# Mobil qidiruv ichidagi katalog — dizayn spetsifikatsiyasi

## Maqsad

Telefon bosh sahifasida `Katalog bo‘yicha` tugmasini qidiruvning alohida
pastki qatoridan olib, qidiruv inputi va `Qidirish` tugmasi bilan bitta qatorga
joylashtirish. Tejalgan vertikal joy reklama blokining balandligini oshirishga
beriladi.

## Qamrov

- O‘zgarish faqat telefon kengligida (`max-width: 620px`) ko‘rinadi.
- Desktop va planshetdagi mavjud qidiruv ko‘rinishi saqlanadi.
- Taxi va boshqa screenlar o‘zgarmaydi.
- Qidiruv, katalog ochish va reklama ma’lumotlarini yuklash mantig‘i
  o‘zgarmaydi.
- Telefon bosh sahifasidagi Leaflet `+` va `−` zoom boshqaruv tugmalari
  ko‘rsatilmaydi. Xaritaning barmoq bilan zoom qilish imkoniyati saqlanadi.

## Mobil ko‘rinish

Qidiruv qatori chapdan o‘ngga uch qismdan iborat:

1. qidiruv belgisi, input va tozalash tugmasi;
2. `Katalog bo‘yicha` tugmasi;
3. `Qidirish` tugmasi.

`Katalog bo‘yicha` tugmasi avvalgi `Yaqin atrofda` tanloviga o‘xshab qidiruv
qatorining ichida ko‘rinadi. U bosilganda mavjud katalog ekrani ochiladi.

Telefon qatorida joy yetishi uchun katalog tugmasining matni ixcham
o‘lchamda ko‘rsatiladi. Qidiruv inputi qolgan bo‘sh joyni egallaydi.

## Fokus holati

- Foydalanuvchi qidiruv blokidagi inputga kirganda `Katalog bo‘yicha` tugmasi
  yashiriladi.
- Katalog tugmasi yashirilganda input kengayib, uning o‘rnini egallaydi.
- Foydalanuvchi qidiruv blokining tashqarisiga bosganda katalog tugmasi yana
  ko‘rinadi.
- Inputning `focus` va `blur` hodisalari qidiruv kartasidagi
  `mobile-search-focused` klassini boshqaradi. Bu katalog tugmasining o‘zini
  bosganda uning bexosdan yashirinib, bosilmay qolishining oldini oladi.
- `Qidirish` va inputni tozalash amallari mavjud funksiyalarni ishlatishda
  davom etadi.

## Reklama balandligi

- Mobil reklama qatori 72 px dan 100 px ga oshiriladi.
- Reklama rasmi ham 100 px balandlikka moslashtiriladi.
- Matn va `Reklama` belgisi kattaroq blok ichida kesilmaydigan qilib
  joylashtiriladi.
- Bosh sahifa telefonning bitta ekranli tartibida qoladi; reklama uchun joy
  alohida pastki katalog qatori yo‘qolishi hisobidan olinadi.

## Mobil xarita boshqaruvi

- `max-width: 620px` da bosh sahifa xaritasining Leaflet zoom control bloki
  yashiriladi.
- Bu faqat ekrandagi `+` va `−` tugmalariga ta’sir qiladi.
- Pinch-to-zoom, xaritani surish va dasturiy markazlash ishlashda davom etadi.
- Desktop, planshet va Taxi ekranidagi xarita boshqaruvi o‘zgarmaydi.

## Markup va CSS

`#homeCatalogOpen` elementi `.home-search-row` ichiga ko‘chiriladi.

Katta ekranda CSS grid hududlari avvalgi ikki qatorli ko‘rinishni saqlaydi:

- birinchi qatorda input va `Qidirish`;
- ikkinchi qatorda katalog.

Telefonda grid hududlari bitta qatorga o‘tadi:

- input;
- katalog;
- `Qidirish`.

`mobile-search-focused` holatida mobil grid ikki ustunga — input va
`Qidirish`ga o‘tadi.

## Qabul mezonlari

1. 620 px va undan kichik ekranda input, katalog va `Qidirish` bitta qatorda.
2. Input fokus olganda katalog tugmasi ko‘rinmaydi va input kengayadi.
3. Qidiruv blokidan fokus chiqqanda katalog tugmasi qaytadi.
4. Katalog tugmasi avvalgidek katalog ekranini ochadi.
5. Mobil reklama balandligi 100 px.
6. Telefon bosh sahifasi gorizontal va vertikal kesilmaydi.
7. Desktop qidiruv ko‘rinishi va Taxi screen o‘zgarmaydi.
8. Telefon bosh sahifasida xaritaning `+` va `−` tugmalari ko‘rinmaydi.
9. Xarita barmoq bilan kattalashtiriladi va suriladi.
10. Mavjud frontend va backend testlari yashil qoladi.

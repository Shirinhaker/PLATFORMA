# Ko‘prik v1628 — telefonda E’lonlar tugma orqali alohida oynada

## Talab

Telefonda E’lonlar bosh sahifada turmasin (v1619 qarori telefonga ham
tegishli), lekin ularga kirish yo‘li bo‘lsin: bosh sahifadagi tugma alohida
oynani ochsin.

## O‘zgarishlar

- v1626 dagi `placeElonSection()` ko‘chirish mantiqi va `homeElonMount`
  olib tashlandi — E’lonlar bo‘limi endi doim `listings` oynasida turadi.
- Bosh sahifaga (tuman takliflaridan keyin) `homeElonOpenBtn` tugmasi
  qo‘shildi: «📋 E’lonlarni ko‘rish». U `openWebListings()` ni chaqiradi.
- Yangi `.phone-only` klassi: 1080 px va undan keng ekranlarda yashirinadi,
  chunki desktopda yuqori web menyudagi «E’lonlar» tugmasi bor.
- Telefonda `listings` oynasi sub-ekran sifatida ochiladi: sarlavha
  «E’lonlar», orqaga tugmasi bosh sahifaga qaytaradi (nav/BACKMAP standarti).

## Qabul mezoni

Telefon bosh sahifasi: istoriyalar → qidiruv/xarita → reklama → tuman
takliflari → «E’lonlarni ko‘rish» tugmasi. Tugma bosilganda toifalar va
ro‘yxat alohida oynada chiqadi, orqaga tugmasi ishlaydi. Desktopda (>=1080px)
tugma ko‘rinmaydi, bosh sahifa va yuqori menyu o‘zgarmagan.

## Test

`tests/test_mobile_home_listings_contract.py` v1628 kontraktiga yangilandi:
tugma mavjudligi va o‘rni, handler, `.phone-only` qoidasi, bosh sahifada
E��lonlar bo‘limi yo‘qligi. Versiya tekshiruvlari `v1628`.

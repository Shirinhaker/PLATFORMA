# Ko‘prik mobil bosh sahifasini bitta ekranga sig‘dirish

## Maqsad

Telefon qurilmalarida Ko‘prik bosh sahifasining barcha asosiy bo‘limlari bir vaqtning o‘zida bitta ekran ichida ko‘rinsin. Sahifa pastga yoki yon tomonga chiqib ketmasin. Desktop va planshet dizayni, qidiruvning ishlash tartibi, xarita ma’lumotlari va boshqa sahifalar o‘zgarmasin.

## Qo‘llanish sohasi

- O‘zgarish faqat telefon bosh sahifasiga qo‘llanadi.
- Asosiy sinov o‘lchamlari: `320×568`, `360×640` va `390×844`.
- Kattaroq ekranlarda mavjud desktop/planshet dizayni saqlanadi.
- Boshqa sahifalarda odatdagi vertikal aylantirish saqlanadi.

## Mobil bosh sahifa tartibi

Bo‘limlar quyidagi tartibda bitta ekran ichida ko‘rinadi:

1. Ixcham yuqori menyu.
2. Ixcham istoriyalar qatori.
3. Ixcham qidiruv va katalog kartasi.
4. Balandligi ekranga moslashadigan xarita.
5. Pastroq reklama banneri.
6. Ixcham mahsulot, xizmat va e’lonlar karuseli.

Bo‘limlar bir-birining ustini yopmaydi va almashib ochilmaydi. Har biri bir vaqtning o‘zida ekranda turadi.

## O‘lcham va moslashuv

- Telefon bosh sahifasi balandligi `100dvh` asosida hisoblanadi.
- Yuqori menyu va bo‘limlar orasidagi bo‘shliqlar kichraytiriladi.
- Elementlarning balandligi ekran balandligiga qarab `clamp()` va balandlikka bog‘liq media qoidalari bilan moslashadi.
- Juda past telefon ekranida avval tashqi bo‘shliqlar, keyin xarita va banner balandligi kamayadi.
- Matnlar sig‘masa bir yoki ikki qatorda kesiladi; ular ekran kengligini oshirmaydi.
- Bosh sahifada `overflow-x` va `overflow-y` yashiriladi, lekin istoriyalar va takliflar ichida gorizontal aylantirish ishlaydi.

## Yuqori menyu

- Ko‘prik nomi, E’lonlar, manzil, savat, Taxi va kabinet boshqaruvlari bitta ixcham qatorga sig‘adi.
- Telefon ekranida uzun matnli yorliqlar ko‘rsatilmaydi; kerakli boshqaruvlar ikonka ko‘rinishida qoladi.
- Tugmalar bosilishi va mavjud sahifalarga o‘tishi saqlanadi.
- Hech bir tugma ekran tashqarisiga chiqmaydi.

## Istoriyalar

- Istoriya kartalari va ular orasidagi bo‘shliq kichraytiriladi.
- “Istoriya qo‘shish” tugmasi saqlanadi.
- Istoriyalar gorizontal yo‘nalishda aylantiriladi.
- Istoriya ochish va joylash funksiyasi o‘zgarmaydi.

## Qidiruv va katalog

- Sarlavha, qidiruv maydoni, “Qidirish” tugmasi, katalog tugmasi va mavjud tezkor yo‘nalishlar kichraytiriladi.
- Qidiruv funksiyasi va yuboriladigan ma’lumotlar o‘zgarmaydi.
- Ushbu bosqichda qidiruv natijalarining ochilish dizayni o‘zgartirilmaydi; u keyingi alohida ish bo‘ladi.

## Xarita

- Xarita bosh sahifadagi qolgan bo‘sh balandlikka moslashadi.
- Xaritaning markeri, kattalashtirish, kichraytirish va bosish funksiyalari saqlanadi.
- Xarita boshqa bo‘limlarning ustini yopmaydi.
- Qidiruv va obuna metkalari algoritmi ushbu o‘zgarishda o‘zgartirilmaydi.

## Reklama

- Reklama banneri pastroq ko‘rinishga o‘tkaziladi.
- Rasm, sarlavha va bosish funksiyasi saqlanadi.
- Sig‘magan tavsif matni ikki qatordan oshmaydi.

## Takliflar karuseli

- Mahsulot, xizmat va e’lon kartalari balandligi kichraytiriladi.
- Gorizontal harakatlanish saqlanadi.
- Kartani bosib ochish funksiyasi o‘zgarmaydi.

## Demo tugmasi

- Bosh sahifadagi **“20 ta demo taklif qo‘shish”** tugmasi interfeysdan olib tashlanadi.
- Oldin yaratilgan takliflar yoki bazadagi boshqa ma’lumotlar o‘chirilmaydi.
- Demo ma’lumot yaratadigan backend kodiga ushbu bosqichda tegilmaydi.

## Tegilmaydigan qismlar

- Desktop va planshet bosh sahifasi.
- Qidiruv API va natijalarni saralash algoritmi.
- Xarita API va markerlarni tanlash algoritmi.
- Oddiy va biznes profil ma’lumotlari.
- Obunalar va istoriyalar qoidalari.
- E’lonlar alohida sahifasi.

## Qabul mezonlari

1. `320×568`, `360×640` va `390×844` ekranlarda bosh sahifa pastga aylanmaydi.
2. Bosh sahifa yon tomonga chiqmaydi.
3. Yuqori menyu, istoriyalar, qidiruv, xarita, reklama va takliflar bo‘limi bir vaqtda ko‘rinadi.
4. Bo‘limlar bir-birining ustini yopmaydi.
5. Manzil, savat, Taxi, kabinet, E’lonlar, qidiruv, katalog, istoriyalar, reklama va taklif kartalari bosilganda ishlaydi.
6. “20 ta demo taklif qo‘shish” tugmasi ko‘rinmaydi.
7. Desktop va boshqa sahifalarda regressiya bo‘lmaydi.

## Tekshiruv

- Telefon o‘lchamlarida `scrollWidth <= clientWidth` va bosh sahifa uchun `scrollHeight <= clientHeight` tekshiriladi.
- Har bir asosiy bo‘limning pastki chegarasi ko‘rinadigan ekran chegarasidan oshmasligi tekshiriladi.
- Yuqori menyu va bosh sahifadagi interaktiv elementlar bosib ko‘riladi.
- Desktop o‘lchamida mavjud bosh sahifa ko‘rinishi solishtirib tekshiriladi.
- Mavjud avtomatik testlar qayta ishga tushiriladi.

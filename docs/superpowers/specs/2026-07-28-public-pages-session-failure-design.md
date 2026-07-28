# Ommaviy sahifalarda sessiya xatosidan himoya dizayni

## Muammo

Frontend ishga tushganda `GET /api/v1/auth/session` so‘rovi bajariladi. Bu so‘rov 401 qaytarsa foydalanuvchi mehmon sifatida ko‘riladi, lekin tarmoq, CORS yoki vaqtinchalik server xatosi yuz bersa `App` barcha kontent o‘rniga `Server bilan bog‘lanib bo‘lmadi` ekranini chiqaradi. Natijada serverga bog‘liq bo‘lmagan `Bosh sahifa`, `Manzil` va katalog ham ochilmay qoladi.

## Maqsad

Sessiya API vaqtincha ishlamasa ham ommaviy sahifalarni ishlatish mumkin bo‘lsin. Kirish yoki kabinet ochilganda sessiya talab qilinadi va mavjud qayta urinish xabari o‘sha yerda ko‘rsatiladi.

## Ko‘rib chiqilgan yondashuvlar

1. **Tavsiya etilgan: ommaviy sahifalarni sessiyadan ajratish.** Sessiya xatosida foydalanuvchi vaqtincha mehmon holatiga o‘tadi. Xato faqat `auth` yoki `cabinet` ko‘rinishida bloklovchi bo‘ladi. Bu eng kichik va xavfsiz o‘zgarish.
2. **Har bir sessiya so‘roviga avtomatik retry qo‘shish.** Vaqtinchalik uzilishni yashirishi mumkin, lekin ommaviy sahifani kutishga majbur qiladi va asl arxitektura muammosini hal qilmaydi.
3. **Barcha xatolarni 401 kabi qabul qilish.** Ommaviy sahifalar ochiladi, ammo foydalanuvchi kirish/kabinetda nima sabab ishlamayotganini bilmaydi.

Birinchi yondashuv tanlandi.

## Xatti-harakat

- `home`, `location`, `catalog` va `category` ko‘rinishlari sessiya yuklanayotgan yoki sessiya so‘rovi xato bergan paytda ham render qilinadi.
- Sessiya so‘rovi 401 qaytarsa mavjud mehmon xatti-harakati saqlanadi.
- Sessiya so‘rovi tarmoq yoki 5xx xatosi bilan tugasa, public header `Kirish` holatini ko‘rsatadi.
- Foydalanuvchi `Kirish` yoki `Kabinet` ko‘rinishiga o‘tsa, `Server bilan bog‘lanib bo‘lmadi` va `Qayta urinish` boshqaruvi ko‘rsatiladi.
- `Qayta urinish` mavjud sessiya so‘rovini qayta ishga tushiradi.
- Authenticated sessiya muvaffaqiyatli yuklansa, mavjud `Kabinet` xatti-harakati o‘zgarmaydi.

## Komponent chegarasi

Faqat quyidagi frontend qatlamiga tegiladi:

- `frontend/src/app/App.tsx` — sessiya bootstrap holatini public va account ko‘rinishlaridan ajratish.
- `frontend/src/app/App.test.tsx` — regressiya testlari.

Backend API, PostgreSQL, Redis, R2, profil formalar, public sahifalar dizayni va marshrutlar o‘zgarmaydi.

## Ma’lumot oqimi

1. `App` public shell’ni darhol ko‘rsatadi va sessiya so‘rovini fon rejimida boshlaydi.
2. 200 javob account identifikatorini o‘rnatadi va header `Kabinet`ga o‘tadi.
3. 401 javob mehmon holatini o‘rnatadi va header `Kirish` bo‘lib qoladi.
4. Tarmoq/5xx xatosi mehmon fallback’ini va retry mumkin bo‘lgan xato holatini saqlaydi.
5. Public ko‘rinishlar fallback bilan ishlashda davom etadi; account ko‘rinishlari xato/retry ekranini ko‘rsatadi.

## Xatolarni boshqarish

- Xato yashirilmaydi: account ko‘rinishida foydalanuvchi uni ko‘radi va qayta urinadi.
- Public ko‘rinishda xato butun sahifani bloklamaydi.
- Foydalanuvchi sessiyasi yo‘q qilinmaydi; keyingi muvaffaqiyatli retry haqiqiy sessiyani tiklaydi.

## Testlar

TDD orqali avval quyidagi regressiya testi yoziladi va joriy kodda kutilgan sabab bilan yiqilishi tasdiqlanadi:

- `getSession` tarmoq xatosi berganda `Manzil` public formasi ochilishi va global server xatosi ko‘rinmasligi.

Keyin mavjud xatti-harakatlar tekshiriladi:

- 401 mehmon holati;
- authenticated header va kabinet;
- account ko‘rinishidagi retryable server xatosi;
- barcha frontend testlari va production build.

## Qabul mezonlari

- Sessiya API xatosida `Bosh sahifa`, `Manzil` va katalog ishlaydi.
- `Kirish/Kabinet`da server xatosi va retry ko‘rinadi.
- Mavjud login, profil va logout testlari o‘tadi.
- Frontend production build muvaffaqiyatli tugaydi.

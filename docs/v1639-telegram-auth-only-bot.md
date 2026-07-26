# v1639 — Telegram faqat autentifikatsiya uchun

## Natija

Telegram bot endi faqat Ko‘prik saytida ro‘yxatdan o‘tish va yangi
qurilmadan kirishni tasdiqlash uchun 6 xonali kod yuboradi. Mahsulot,
e’lon, buyurtma, chat va media xabarlari bot orqali yuborilmaydi.

Tasdiqlangan qurilmada sayt 30 kunlik Bearer sessiya yaratadi. Doimiy
login va parol yangi profil yaratilgandan keyin saytda bir marta
ko‘rsatiladi va shu Telegram akkauntiga ham yuboriladi.

## Railway o‘zgaruvchilari

Quyidagilar Railway Variables bo‘limida bo‘lishi shart:

- `BOT_TOKEN` — BotFather bergan bot tokeni.
- `BASE_URL=https://koprik.uz` — webhook ishlaydigan asosiy HTTPS manzil.
- `WEBHOOK_SECRET` — kamida 32 belgili tasodifiy maxfiy qiymat.
- `MOBILE_OTP_SECRET` — `WEBHOOK_SECRET`dan boshqa maxfiy qiymat.
- `BOT_USERNAME` — ixtiyoriy, `@` belgisiz bot username. Bo‘sh qolsa
  server uni Telegram `getMe` so‘rovi orqali aniqlaydi.

`TEST_MODE=0` bo‘lishi kerak. Haqiqiy maxfiy qiymatlarni GitHub yoki ZIP
ichiga yozmang.

## Deploy tartibi

1. Deploydan oldin amaldagi SQLite bazasining zaxira nusxasini oling.
2. Railway Volume `/data` manziliga ulanganini tekshiring.
3. Yuqoridagi environment qiymatlarini kiriting.
4. v1639 kodini deploy qiling.
5. Deploy logida `Bot sozlandi: https://koprik.uz` yozuvini tekshiring.
6. `/healthz` va `/api/build` javobida `v1639` ko‘rinishini tekshiring.

Server ishga tushganda webhookni `/webhook` manziliga avtomatik
o‘rnatadi, faqat `message` update turini qabul qiladi va bot menyusini
oddiy holatga qaytaradi.

## Qabul tekshiruvi

### Ro‘yxatdan o‘tish

1. Saytda `Ro‘yxatdan o‘tish`ni oching.
2. Oddiy yoki biznes profilni tanlab ma’lumotlarni kiriting.
3. `Telegram orqali kod olish` tugmasini bosing.
4. Telegram avtomatik ochilib, botga bir martalik `/start` havolasi
   yuborilsin.
5. Bot 6 xonali kod yuborsin; kod 5 daqiqa amal qilsin.
6. Kod saytda tasdiqlangach profil ochilsin va 30 kunlik sessiya
   saqlansin.
7. Doimiy login-parol saytda bir marta va Telegram botda ko‘rinsin.

### Yangi qurilmadan kirish

1. Login va doimiy parolni kiriting.
2. Sayt sessiyani darhol ochmasin; Telegram tasdiqlash bosqichiga o‘tsin.
3. Bir martalik havola faqat akkauntga bog‘langan Telegram tomonidan
   ishlatilsin.
4. To‘g‘ri 6 xonali koddan keyingina 30 kunlik sessiya ochilsin.
5. Ishlatilgan yoki muddati tugagan kod qayta qabul qilinmasin.

### Bot chegarasi

- Oddiy `/start` foydalanuvchiga kod so‘rovini `koprik.uz` saytidan
  boshlashni tushuntirsin.
- Bot media, e’lon, buyurtma yoki chatni qabul qilib qayta ishlamasin.
- Eski tasdiqlash inline tugmalari va Mini App menyusi ishlatilmasin.

## Keyingi bosqichga qoldirilgan

QR orqali kirish, SMS tasdiqlash va parolni tiklash v1639 tarkibiga
kirmaydi. Ular keyingi alohida bosqichda loyihalanadi va ulanadi.

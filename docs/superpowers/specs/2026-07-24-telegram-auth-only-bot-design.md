# Ko‘prik Telegram autentifikatsiya boti — dizayn

Sana: 2026-07-24  
Holat: foydalanuvchi bilan kelishilgan dizayn

## Maqsad

Ko‘prik Telegram botini Mini App va xizmat xabarlari botidan sayt
autentifikatsiyasi uchun ishlaydigan sodda botga aylantirish.

Bot faqat:

1. ro‘yxatdan o‘tish tasdiqlash kodini;
2. yangi qurilmadan kirish tasdiqlash kodini;
3. yangi akkaunt yaratilganda doimiy login va parolni yuboradi.

Oddiy kirish avval tasdiqlangan 30 kunlik qurilmada qayta Telegram kodini
talab qilmaydi.

## Botdan olib tashlanadigan vazifalar

- Mini App yoki saytni ochuvchi Web App menyusi va tugmasi;
- rasm va video qabul qilib `media_inbox`ga joylash;
- buyurtma, navbat va boshqa xizmat xabarlari;
- yangi qurilmadan kirishni `Tasdiqlash` yoki `Rad etish` tugmalari bilan
  boshqarish;
- Telegram ichidagi boshqa kabinet funksiyalari.

Oddiy `/start` buyrug‘i faqat botning vazifasini tushuntiradi va kod olishni
`koprik.uz` saytidan boshlash kerakligini aytadi.

## Tanlangan yondashuv

Sayt bir martalik, taxmin qilib bo‘lmaydigan Telegram deep-link yaratadi:

`https://t.me/<bot_username>?start=<bir_martalik_token>`

Foydalanuvchi saytdagi `Telegram orqali kod olish` tugmasini bosganda bot
avtomatik ochiladi. Telegram webhook tokenni va foydalanuvchining haqiqiy
Telegram ID raqamini oladi. Shundan keyingina bot shu chatga 6 xonali kod
yuboradi.

Telegram username qo‘lda kiritilmaydi. Username o‘zgarishi mumkinligi sababli
akkaunt Telegram ID orqali bog‘lanadi.

## Ro‘yxatdan o‘tish oqimi

1. Foydalanuvchi saytda oddiy yoki biznes ro‘yxatdan o‘tish formasini
   to‘ldiradi.
2. Server vaqtinchalik ro‘yxatdan o‘tish yozuvi va bir martalik Telegram
   tokenini yaratadi.
3. Sayt `Telegram orqali kod olish` tugmasi orqali botni ochadi.
4. Bot `/start <token>` orqali kelgan Telegram ID ni vaqtinchalik yozuvga
   bog‘laydi.
5. Bot shu foydalanuvchiga 6 xonali kod yuboradi.
6. Foydalanuvchi kodni saytga kiritadi.
7. Server kodni tekshiradi va akkaunt yaratadi.
8. 30 kunlik xavfsiz sayt sessiyasi yaratiladi.
9. Doimiy login va parol:
   - saytda faqat bir marta ko‘rsatiladi;
   - Telegram botga faqat bir marta yuboriladi;
   - bazada parolning o‘zi emas, faqat xavfsiz xeshi saqlanadi.

## Yangi qurilmadan kirish oqimi

1. Foydalanuvchi saytda doimiy login va parolini kiritadi.
2. Server login-parolni tekshiradi, lekin darhol sessiya bermaydi.
3. Server bir martalik Telegram deep-link yaratadi.
4. Foydalanuvchi `Telegram orqali kod olish` tugmasini bosadi.
5. Bot ochilib, 6 xonali kodni yuboradi.
6. Akkaunt avval Telegramga bog‘langan bo‘lsa, botni aynan o‘sha Telegram
   akkaunti ochishi shart.
7. Telegramga hali bog‘lanmagan eski akkauntda to‘g‘ri login-parol va
   deep-link orqali ochilgan Telegram ID tasdiqlashdan keyin akkauntga
   biriktiriladi.
8. Kod saytda to‘g‘ri kiritilgach, 30 kunlik sessiya beriladi.

Foydalanuvchi saytdan `Chiqish`ni bossa, joriy sessiya bekor qilinadi. Qayta
kirishda Telegram kodi yana talab qilinadi.

## Ma’lumotlar modeli

Yangi Telegram autentifikatsiya jadvallari vazifasi bo‘yicha ajratiladi:

- `telegram_pending_registrations`
  - ro‘yxatdan o‘tish formasi ma’lumotlari;
  - profil turi;
  - yaratilgan va tugash vaqti;
  - ishlatilgan holati.
- `telegram_auth_challenges`
  - maqsad: `register` yoki `login`;
  - bir martalik tokenning xeshi;
  - 6 xonali kodning xeshi;
  - foydalanuvchi yoki vaqtinchalik ro‘yxat ID si;
  - bog‘langan Telegram ID;
  - urinishlar soni;
  - yaratilgan, tugash va tasdiqlangan vaqt.

Ochiq token va 6 xonali kod bazada oddiy matn ko‘rinishida saqlanmaydi.

## API chegaralari

Sayt uchun alohida endpointlar:

- ro‘yxatdan o‘tish Telegram chaqiruvini boshlash;
- yangi qurilma login Telegram chaqiruvini boshlash;
- bot kod yuborganini tekshirish;
- ro‘yxatdan o‘tish kodini tasdiqlash;
- login kodini tasdiqlash;
- kodni 60 soniyadan keyin qayta yuborish.

Webhook faqat:

- maxfiy Telegram webhook sarlavhasini tekshiradi;
- `/start` autentifikatsiya tokenlarini ishlaydi;
- oddiy `/start` tushuntirishini qaytaradi.

## Xavfsizlik qoidalari

- Deep-link token bir marta ishlaydi va bazada faqat SHA-256 xeshi turadi.
- Tasdiqlash kodi 5 daqiqa amal qiladi.
- Bir kod uchun ko‘pi bilan 5 ta urinish beriladi.
- Yangi kod kamida 60 soniyadan keyin olinadi.
- Yangi chaqiruv yaratilsa, oldingi faol chaqiruv bekor qilinadi.
- Telegramga bog‘langan akkauntni boshqa Telegram ID tasdiqlay olmaydi.
- Login mavjud yoki yo‘qligi begona foydalanuvchiga oshkor qilinmaydi.
- `TEST_MODE` kodi HTTP javobi, log yoki diagnostika endpointiga chiqmaydi.
- 30 kunlik sessiyaning faqat xeshi bazada saqlanadi.
- Doimiy parol Telegramga foydalanuvchi talabi bo‘yicha bir marta yuboriladi;
  server uni qayta o‘qiy olmaydi.

## Sayt interfeysi

Ro‘yxatdan o‘tish va yangi qurilmadan kirish sahifasida:

- `Telegram orqali kod olish` asosiy tugmasi;
- Telegram ochilgach, 6 xonali kod kiritish maydoni;
- kodning amal qilish vaqti;
- 60 soniyalik qayta yuborish hisoblagichi;
- `Boshqa Telegram akkaunti ochildi` va `Kod muddati tugadi` kabi aniq
  xato xabarlari;
- Telegram ochilmasa, deep-linkni qayta bosish tugmasi.

Telefon, planshet va kompyuterda bir xil oqim ishlaydi.

## Eski foydalanuvchilar

- Telegram ID si mavjud akkauntlar o‘sha Telegram akkaunti orqali
  tasdiqlanadi.
- Telegram ID si yo‘q sayt akkauntlari birinchi yangi-qurilma tasdiqlashida
  Telegramga bog‘lanadi.
- Mavjud login, parol, profil, biznes va boshqa ma’lumotlar o‘zgarmaydi.

## Test va qabul mezonlari

1. Ro‘yxatdan o‘tish deep-linki to‘g‘ri Telegram foydalanuvchiga kod yuboradi.
2. Noto‘g‘ri Telegram akkaunti bog‘langan login chaqiruvini tasdiqlay olmaydi.
3. Noto‘g‘ri, muddati tugagan va ishlatilgan kod rad etiladi.
4. 5 ta noto‘g‘ri urinishdan keyin kod bloklanadi.
5. Tasdiqdan keyin sessiya 30 kunlik bo‘ladi.
6. Login-parol sayt va botda faqat akkaunt yaratilganda bir marta beriladi.
7. Bot foto va videoni `media_inbox`ga yozmaydi.
8. Bot Mini App tugmasini va xizmat xabarlarini yubormaydi.
9. Oddiy `/start` autentifikatsiya botining qisqa yo‘riqnomasini beradi.
10. Eski Telegram ID li va Telegram ID siz akkauntlar uchun migratsion oqim
    ishlaydi.
11. OTP test javoblari va loglarda oshkor bo‘lmaydi.
12. Mavjud to‘liq testlar buzilmaydi.

## Ushbu bosqichga kirmaydigan ishlar

- QR kod orqali kirish;
- SMS integratsiyasi;
- parolni unutish/tiklash oqimi;
- Telegram orqali buyurtma va navbat xabarlari;
- Mini App rejimi;
- Telegram ichida profil yoki kabinet boshqaruvi.


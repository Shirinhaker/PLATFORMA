# v1641 — Ro‘yxatdan o‘tgan Telegram akkauntini qayta ro‘yxatdan o‘tkazishni bloklash

## Talab

Ko‘prikda profili mavjud Telegram akkaunti yangi profil ochish jarayonida qayta tasdiqlash kodini olmasligi kerak.

## Ishlash tartibi

1. Foydalanuvchi saytdagi ro‘yxatdan o‘tish jarayonidan Telegram botga o‘tadi.
2. Bot `/start <token>` so‘rovini olganda Telegram foydalanuvchi ID sini aniqlaydi.
3. Challenge maqsadi `register` bo‘lsa, bot kod yaratishdan oldin `users.tg_id` orqali mavjud profilni tekshiradi.
4. Mavjud profil topilsa:
   - tasdiqlash kodi yaratilmaydi va yuborilmaydi;
   - ro‘yxatdan o‘tish challenge’i bekor qilinadi;
   - bot foydalanuvchiga profil allaqachon mavjudligini va saytdagi **Kirish** bo‘limidan foydalanish kerakligini bildiradi.
5. Login uchun yaratilgan challenge’lar bu tekshiruv bilan bloklanmaydi.

## Qabul mezonlari

- Mavjud Telegram ID bilan yangi profil ochish kodi yuborilmaydi.
- Bekor qilingan challenge qayta ishlatilmaydi.
- Bot javobida foydalanuvchiga **Kirish** bo‘limidan foydalanish ko‘rsatiladi.
- Yangi Telegram akkauntining ro‘yxatdan o‘tishi ishlashda davom etadi.
- Mavjud akkauntning login jarayoni ishlashda davom etadi.

## Test

`tests/test_telegram_auth_bot_contract.py` ichidagi
`test_registered_telegram_cannot_receive_new_profile_code` testi mavjud Telegram
ID uchun kod yuborilmasligi, challenge bekor qilinishi va bot xabari to‘g‘ri
qaytishini tekshiradi.

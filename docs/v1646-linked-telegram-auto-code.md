# v1646 — Bog‘langan Telegramga kodni avtomatik yuborish

## Muammo

Avval ro‘yxatdan o‘tgan foydalanuvchi login va parolini kiritganda ham
Telegram botdagi `/start` tugmasini har safar bosishi kerak edi.

## Yechim

- Profilning `tg_id` qiymati mavjud bo‘lsa, kirish kodi shu Telegram
  akkauntiga avtomatik yuboriladi.
- Bunday holatda sayt Telegram deep-link ochmaydi va
  “Telegramni ochish” tugmasini ko‘rsatmaydi.
- Telegram hali bog‘lanmagan eski profil uchun avvalgi xavfsiz deep-link
  orqali bog‘lash tartibi saqlanadi.
- Joriy qurilmadagi 30 kunlik sessiya amal qilsa, kod kiritishning o‘zi
  ham talab qilinmaydi.

## Qabul mezonlari

1. Bog‘langan profil login/parolini kiritsa, botga kod avtomatik keladi.
2. Foydalanuvchi botdagi `/start` tugmasini bosmaydi.
3. Bog‘lanmagan profil Telegram havolasi orqali birinchi marta bog‘lanadi.
4. Tasdiqlash yakunlanmaguncha mobil sessiya yaratilmaydi.
5. Barcha avtomatik testlar yashil qoladi.

## Tekshiruv

- `252` ta Python avtomatik test muvaffaqiyatli.
- Frontend kontrakti avtomatik yuborishda keraksiz tugma yashirilishini
  tekshiradi.
- Telegram API testi noto‘g‘ri akkauntni qabul qilmaslik qoidasini
  saqlaydi.

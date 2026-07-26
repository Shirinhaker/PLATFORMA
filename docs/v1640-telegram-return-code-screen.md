# v1640 — Telegramdan qaytganda kod oynasini tiklash

## Tuzatilgan muammo

Telefon brauzeri Telegram havolasini shu oynada ochganda, foydalanuvchi
saytga qaytishi bilan bosh sahifa chiqib qolardi. Sababi tasdiqlash
so‘rovi faqat JavaScript o‘zgaruvchilarida saqlanib, sahifa qayta
yuklanganda yo‘qolishi edi.

## Yangi ishlash tartibi

- Telegram ro‘yxatdan o‘tish va kirish so‘rovi joriy brauzer oynasining
  `sessionStorage` xotirasida vaqtincha saqlanadi.
- Foydalanuvchi Telegramdan saytga qaytganda kod kiritish oynasi
  avtomatik tiklanadi.
- Tasdiqlash muvaffaqiyatli tugasa, foydalanuvchi ortga qaytsa yoki
  so‘rov muddati tugasa, vaqtinchalik ma’lumot o‘chiriladi.
- Avtomatik yangi oyna brauzer tomonidan bloklansa, sayt o‘z joyida
  qoladi va foydalanuvchiga `Telegramni ochish` tugmasi ko‘rsatiladi.
- Shu himoya ro‘yxatdan o‘tish va yangi qurilmadan kirish jarayonlarining
  ikkalasiga ham qo‘llanadi.

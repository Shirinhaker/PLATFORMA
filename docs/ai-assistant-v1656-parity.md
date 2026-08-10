# AI yordamchi — v1656 pariteti

## Etalon

AI yordamchi uchun etalon `static/index.html` dagi v1656 ekranidir:

- menyu nomi va izohi;
- beshta tezkor savol;
- chatning bo'sh, yuklanish, yozish va xatolik holatlari;
- AI faqat ma'lumotni o'qishi, o'zi o'zgartirish kiritmasligi haqidagi izoh.

React ekranidagi foydalanuvchiga ko'rinadigan matnlar va v1656 CSS klasslari
shu etalonga harfma-harf mos saqlanadi. v1656 Hujjatlar ekranida AI tugmasi
bo'lmagani uchun yangi tugma chiqarilmaydi; mavjud AI hujjat draft API shartnomasi
esa eski integratsiyalar uchun saqlanadi.

## Hujjatlashtirilgan tuzatish

v1656 da `Eng ko'p sotilgan` tezkor savoli bor edi, lekin lokal AI kontekstida
eng ko'p sotilgan mahsulotlar ma'lumoti va shu savol uchun alohida javob yo'q edi.
Typed modul bu mavjud tugmani haqiqiy ishlatish uchun bugungi savdo satrlarini
summalaydi, qarz to'lovini savdo tushumiga qo'shmaydi va top mahsulotlarni javobda
ko'rsatadi. Bu foydalanuvchi interfeysiga yangi amal qo'shmaydi; mavjud v1656
tugmasining bajarilmay qolgan amalini tiklaydi.

## Ma'lumot migratsiyasi

`ai_chat_history` SQLite snapshotdan to'g'ridan-to'g'ri PostgreSQL jadval nomi
sifatida o'qilmaydi. Complete-cabinet migratsiyasi har bir eski `business_id` ni
`legacy_id_map` orqali yangi business accountga bog'lab, tarixni
`ai_chat_messages` ga idempotent ko'chiradi. Migratsiya sxema belgisi
`0007_phase3c_ai_assistant_v1` bo'lib, oldingi tugallangan run bilan chalkashmaydi.

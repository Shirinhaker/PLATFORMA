# Reklama rasmi o‘chirish dizayni

## Maqsad

Oddiy foydalanuvchi va biznes reklama joylash formasida tanlangan rasmni,
formaning boshqa ma’lumotlarini yo‘qotmasdan, tasdiqlash orqali olib tashlash.

## Interfeys

- `baPreview` va `uaPreview` bloklaridagi rasmning yuqori o‘ng burchagida
  yumaloq qizil `×` tugmasi ko‘rinadi.
- Tugma faqat rasm tanlanganda ko‘rinadi.
- Tugmaning ekran o‘quvchi matni `Tanlangan reklama rasmini o‘chirish` bo‘ladi.
- Tugma rasm ustida qoladi va telefon hamda kompyuterda bosish uchun yetarli
  o‘lchamga ega bo‘ladi.

## Xatti-harakat

1. Foydalanuvchi `×` tugmasini bosadi.
2. Mavjud `askConfirm` oynasi
   `Tanlangan reklama rasmi o‘chirilsinmi?` matni bilan ochiladi.
3. Bekor qilinsa hech qanday holat o‘zgarmaydi.
4. Tasdiqlansa:
   - forma holatidagi `file` va `image_file` tozalanadi;
   - `input[type=file]` qiymati tozalanadi;
   - vaqtinchalik `blob:` manzil bekor qilinadi;
   - rasm previewi va kesish oynasi yopiladi;
   - rasm o‘lchami/sifat ma’lumoti tozalanadi;
   - kesish koordinatalari `50 / 50 / 1` qiymatlariga qaytariladi.
5. Sarlavha, qisqa matn, hududlar, boshlanish vaqti, kunlik vaqt va davomiylik
   o‘zgarmaydi.
6. Foydalanuvchi darhol boshqa rasm tanlay oladi.

## Texnik chegaralar

- Faqat `static/index.html` ichidagi reklama formasi HTML, CSS va JavaScript
  o‘zgaradi.
- Backend API, reklama narxi, hudud tanlash va e’lon media oqimi o‘zgarmaydi.
- Xatti-harakat `ba` (business) va `ua` (oddiy foydalanuvchi) prefikslari uchun
  bitta umumiy funksiya orqali ishlaydi.
- Reliz BUILD qiymati `v1648` bo‘ladi.

## Test va qabul mezonlari

- Ikkala preview blokida ham `×` tugmasi mavjud.
- Tugma tasdiqlash oynasini chaqiradi.
- Bekor qilish tanlangan rasmni saqlab qoladi.
- Tasdiqlash forma media holati, preview, crop va ma’lumot matnini tozalaydi.
- Boshqa forma qiymatlari saqlanadi.
- Yangi rasm tanlash mumkin.
- Mavjud avtomatik testlar yashil qoladi.

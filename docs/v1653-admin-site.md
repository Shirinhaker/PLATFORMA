# Ko‘prik v1653 — alohida admin sayti

## Natija

- `admin.koprik.uz` uchun oddiy foydalanuvchi kabinetidan ajratilgan admin sayt;
- Telegram ID + bir martalik kod + HttpOnly admin sessiyasi;
- to‘lov navbati, private kvitansiyani ko‘rish, tasdiqlash/rad etish/bekor qilish;
- narxlar va to‘lov rekvizitlarini boshqarish;
- foydalanuvchi va bizneslarni qidirish, ichki izoh, mustaqil `content_hidden` va `account_blocked` cheklovlari;
- mahsulot, xizmat, reklama, biznes va profil kontentini reaktiv yashirish/tiklash;
- shikoyatlarni qabul qilish va atomar qaror;
- o‘zgartirish/o‘chirishdan SQLite triggerlari bilan himoyalangan audit tarixi va CSV eksport.

## Maxfiylik va xavfsizlik

Admin javoblarida parol, mobil sessiya, receipt fayl yo‘li yoki maxfiy env qiymati
chiqmaydi. Oddiy profilning hududi admin ro‘yxatida ham kerak bo‘lmagani uchun
berilmaydi. `content_hidden` egasining kabinetidagi ma’lumotni o‘chirmaydi;
faqat public qidiruv, xarita, reklama va tuman takliflaridan yashiradi.

## Migratsiya va rollback

`init_db()` yangi jadvallarni xavfsiz `CREATE TABLE IF NOT EXISTS` bilan qo‘shadi.
Rollbackda v1652 kodini qaytarish mumkin; yangi jadvallar eski kodga halaqit
bermaydi. Audit va moderatsiya ma’lumotlarini fizik o‘chirish tavsiya etilmaydi.

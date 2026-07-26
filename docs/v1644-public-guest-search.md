# v1644 — Profilga kirmasdan qidirish

## Natija

- Mehmon foydalanuvchi `/api/search` orqali mahsulot, xizmat, e’lon,
  mutaxassis, biznes va ochiq foydalanuvchi profilini qidira oladi.
- Katalogdan faoliyat turi tanlanganda `/api/browse` ham mehmon uchun ishlaydi.
- Mehmon qidiruvi brauzerda birinchi kirishda tanlangan viloyat va tuman bilan
  chegaralanadi.
- Hudud tanlanmagan bo‘lsa, tuman qidiruvi butun bazani ochmaydi va avval
  manzilni belgilashni so‘raydi.

## Kirgan profil bilan farqi

- Tizimga kirgan foydalanuvchida qidiruv avvalgidek joriy oddiy yoki biznes
  kabinet kontekstida ishlaydi.
- Mehmon rejimida `actor_type=business` qabul qilinmaydi; qidiruv oddiy
  foydalanuvchi ko‘rinishida bajariladi.
- Obuna bo‘lish, saqlash, buyurtma berish va navbat olish amallari login talab
  qilishda davom etadi.

## Maxfiylik

- Qidiruv natijasidagi oddiy foydalanuvchi kartasidan viloyat va tuman
  maydonlari chiqarib tashlandi.
- Mehmon qidiruvi serverga faqat tanlangan viloyat va tumanni yuboradi; aniq
  koordinata yoki yashash manzili yuborilmaydi.
- Javob `private, no-store` va autentifikatsiya sarlavhalari bo‘yicha `Vary`
  bilan qaytariladi.

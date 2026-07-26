# Ko‘prik v1637 — responsive kabinet bosh sahifasi

## Natija

Kabinet bosh sahifasi biznes va oddiy foydalanuvchi uchun alohida, bir xil dizayn tizimida qayta tuzildi. Ichki sahifalar, API yo‘llari, ruxsatlar va mavjud tugmalar saqlandi.

## Biznes kabinet

- Biznes nomi, faoliyat yo‘nalishi, turi va hududi yuqorida ko‘rsatiladi.
- To‘rtta ko‘rsatkich kartasi faoliyat yo‘nalishiga mos nom bilan chiqadi.
- Ko‘rsatkichlar faqat mavjud API ma’lumotlaridan hisoblanadi; ma’lumot bo‘lmasa `0` ko‘rsatiladi.
- Mavjud `Onlinelashtirish` va `Tizimlashtirish` guruhlari saqlandi.
- So‘nggi buyurtmalar haqiqiy buyurtma ma’lumotlari bilan chiqadi.
- Kompyuterda boshqaruv kartalari va so‘nggi faoliyat yonma-yon, telefonda esa ketma-ket joylashadi.

## Oddiy foydalanuvchi kabineti

- Foydalanuvchi nomi va hududi yuqorida ko‘rsatiladi.
- Faol buyurtmalar, obunalar, saqlanganlar va bildirishnomalar soni ko‘rsatiladi.
- Mavjud kabinet bo‘limlari va ularning yo‘nalishlari saqlandi.
- So‘nggi buyurtma faoliyati pastki qismda ko‘rsatiladi.

## Faoliyat yo‘nalishlari

Quyidagi 20 ta yo‘nalish uchun ko‘rsatkich nomlari moslashtirildi:

1. Savdo
2. Transport va logistika
3. Xizmat ko‘rsatish
4. Maishiy xizmatlar
5. Umumiy ovqatlanish
6. Qurilish
7. Tibbiy xizmatlar
8. Ta’lim faoliyati
9. Ko‘chmas mulk
10. Qishloq xo‘jaligi
11. Axborot texnologiyalari
12. Konsalting va professional
13. Madaniyat, sport, ko‘ngilochar
14. Turizm va mehmonxona
15. Ishlab chiqarish
16. Hunarmandchilik
17. Reklama va marketing
18. Poligrafiya va nashriyot
19. Moliyaviy faoliyat
20. Import-eksport

Yo‘nalishga maxsus ma’lumot mavjud bo‘lmasa, umumiy va tushunarli ko‘rsatkichlar ishlatiladi.

## Ma’lumot manbalari

- Biznes buyurtmalari: `/api/orders/inbox`
- Bugungi savdo: `/api/stats?period=kun`
- Qarzlar: `/api/qarz/debtors`
- Ombor va mahsulotlar: `/api/items`
- Oddiy foydalanuvchi buyurtmalari: `/api/orders/my`
- Saqlanganlar: `/api/saved`
- Bildirishnomalar: `/api/notifications`

Har bir so‘rov xatoga uchrasa, kabinetning qolgan qismi ishlashda davom etadi va tegishli ko‘rsatkich `0` bo‘ladi.

## Responsive qoidalar

- Telefon: KPI kartalari `2 × 2`, menyu kartalari ikki ustunda.
- Planshet: kabinet kengligi oshadi, kartalar moslashadi.
- Kompyuter: boshqaruv bo‘limlari va so‘nggi faoliyat ikki ustunda.

## Moslik

- Eski kabinet ichki ekranlari olib tashlanmadi.
- Mavjud element IDlari va tugma hodisalari saqlandi.
- `BUILD`: `v1637`


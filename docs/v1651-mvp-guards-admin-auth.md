# v1651 — MVP guardlari va admin kirishi

Bu versiyada Ko‘prikning birinchi ishga tushirish bosqichi server boshqaradigan
feature flaglarga o‘tkazildi.

- `E’lonlar`, `Istoriyalar`, umumiy `Suhbatlar` va `Tizimlashtirish` frontendda
  yashiriladi va backendda `feature_disabled` javobi bilan bloklanadi.
- Buyurtmalar, xizmat buyurtmalari va buyurtma ichidagi chat ochiq qoladi.
- E’lonlar o‘chiq bo‘lganda ular qidiruv, ommaviy profil, saqlanganlar va tuman
  takliflari orqali sizib chiqmaydi.
- Bosh sahifada istoriya o‘rniga joriy kabinet obuna bo‘lgan oddiy va biznes
  profillari ko‘rsatiladi. Oddiy profilning yashash tumani payloadga berilmaydi.
- `admin.koprik.uz` uchun `ADMIN_TG_IDS`ga asoslangan Telegram kodi va alohida
  `HttpOnly`, `Secure`, `SameSite=Strict` sessiyasi qo‘shildi.
- Admin sessiyasi 8 soat, faoliyatsizlik muddati 30 daqiqa; kod bir martalik va
  5 daqiqa amal qiladi.

Productionda to‘rtta `MVP_*_ENABLED` qiymati `0` bo‘lishi kerak. Keyin admin
panel orqali audit qilinadigan SQLite override qo‘shilishi mumkin.

# Ko‘prik v1615 — Pro/kuzatuv xaritasi va vaqtinchalik yopiq rejim

## Xarita

Bosh sahifa xaritasida faqat quyidagi profillarning joylashuvi bor metkalari
ko‘rinadi:

- muddati tugamagan faol Pro obunali bizneslar;
- joriy foydalanuvchi yoki uning biznesi kuzatayotgan faol bizneslar;
- joriy foydalanuvchi yoki uning biznesi kuzatayotgan, xaritada ko‘rinishga
  ruxsat bergan mutaxassislar.

Pro uchun alohida rang, belgi yoki maxsus metka yo‘q. Barcha bizneslar mavjud
oddiy metka komponentida chiqadi va bosilganda profil ochiladi. Pro biznes ayni
paytda kuzatilayotgan bo‘lsa, xaritada bir marta chiqadi.

Pro muddati tugaganda biznes ommaviy xaritadan chiqadi. Lekin foydalanuvchi shu
biznesni kuzatayotgan bo‘lsa, kuzatuv asosida ko‘rinishda davom etadi.
Joylashuvi belgilanmagan yoki faol bo‘lmagan biznes xaritada ko‘rsatilmaydi.
Oddiy foydalanuvchi va mutaxassisning yashash tumani xarita API javobiga
berilmaydi.

## Vaqtinchalik yopiq rejim

`PROJECT_ACCESS_RESTRICTED` hozir standart holatda yoqilgan. Faqat
`PRIVILEGED_TG_IDS` ichidagi Telegram IDlar yoki aynan shu IDga bog‘langan mobil
sessiyalar API’dan foydalanadi. Staff tokeni va ommaviy endpointlar global
blokni chetlab o‘tmaydi.

Ruxsatsiz foydalanuvchi `403` va `project_temporarily_closed` kodini oladi;
frontend butun ekran bo‘ylab `Loyiha vaqtincha yopiq` xabarini ko‘rsatadi.

Loyihani keyin qayta ochish uchun Railway muhitida
`PROJECT_ACCESS_RESTRICTED=0` berish kifoya. Shunda eski ochiq kirish tartibi
qaytadi va kodni almashtirish talab qilinmaydi.

# Ko‘prik “Istoriyalarim” bo‘limi dizayni

**Sana:** 2026-07-20  
**Asos:** Platforma/Ko‘prik v1609  
**Holat:** foydalanuvchi tomonidan tasdiqlangan dizayn

## Maqsad

Shaxsiy va biznes profillari joylagan istoriyalarini bitta boshqaruv bo‘limida ko‘radi. Istoriya ommaga 24 soat ko‘rinadi, keyin esa egasining yopiq arxivida o‘zi o‘chirguncha saqlanadi. Shaxsiy va biznes arxivlari bir-biridan alohida bo‘ladi.

## Foydalanuvchi tajribasi

Shaxsiy kabinet va biznes kabinet menyulariga alohida `Istoriyalarim` kartasi qo‘shiladi. Kartani bosganda joriy aktyorga mos bo‘lim ochiladi:

- `Faol` tabi — 24 soati tugamagan istoriyalar.
- `Arxiv` tabi — 24 soati tugagan, ommaga ko‘rinmaydigan istoriyalar.

Har bir istoriya kartasida quyidagilar ko‘rinadi:

- rasm yoki video muqovasi;
- ixtiyoriy qisqa matn;
- joylangan sana va vaqt;
- `Faol` yoki `Arxiv` holati;
- jami ko‘rishlar soni;
- `Ko‘rish` va `O‘chirish` amallari.

Faol kartada 24 soatlik muddatdan qancha vaqt qolgani ham ko‘rsatiladi. Arxiv kartasi faqat egasiga ochiladi. Arxivdagi istoriyani qayta joylash, tahrirlash yoki yuklab olish birinchi versiya doirasiga kirmaydi.

## Saqlash va hayot sikli

Mavjud `stories`, `story_views` va `story_reports` jadvallari ishlatiladi. Alohida arxiv jadvali yoki media nusxasi yaratilmaydi.

- `expires_at > hozir` bo‘lsa holat `active` deb hisoblanadi.
- `expires_at <= hozir` bo‘lsa holat `archived` deb hisoblanadi.
- Arxiv holati so‘rov vaqtida hisoblanadi; fon vazifasi shart emas.
- `deleted` va `failed` yozuvlar bo‘limda chiqmaydi.
- Mavjud v1608/v1609 istoriyalari avtomatik ravishda yangi bo‘limga kiradi.
- Media `/data/stories` papkasida saqlanishda davom etadi.
- Istoriya egasi o‘chirganda MP4/rasm va video muqovasi fayllari o‘chiriladi. `stories` yozuvi bazadan butunlay o‘chadi; tashqi kalitlar orqali tegishli ko‘rish va report yozuvlari ham avtomatik tozalanadi.

## Aktyorlar va ruxsatlar

`actor_type=user` shaxsiy arxivni, `actor_type=business` biznes arxivini anglatadi.

- Oddiy foydalanuvchi va mutaxassis faqat o‘z shaxsiy istoriyalarini ko‘radi.
- Biznes egasi faqat o‘z biznesi istoriyalarini ko‘radi.
- `ads` ruxsatiga ega biznes xodimi biznes istoriyalarini ko‘rishi va boshqarishi mumkin.
- Shaxsiy va biznes istoriyalari bir ro‘yxatda aralashmaydi.
- Begona foydalanuvchi arxiv ro‘yxati va arxiv mediasini ololmaydi.

## Backend interfeyslari

### `GET /api/stories/mine`

Parametrlar:

- `actor_type=user|business`
- `state=active|archived|all`

Natija joriy aktyorning istoriyalarini yangidan eskiga qaytaradi. Har bir element quyidagilarni beradi:

```json
{
  "id": 41,
  "media_type": "video",
  "caption": "Bugungi yangilik",
  "created_at": 1721000000,
  "expires_at": 1721086400,
  "state": "archived",
  "view_count": 18,
  "thumbnail_url": "/api/stories/41/owner-media?thumbnail=1&actor_type=user",
  "media_url": "/api/stories/41/owner-media?actor_type=user"
}
```

### `GET /api/stories/{story_id}/owner-media`

Parametrlar:

- `actor_type=user|business`
- `thumbnail=0|1`

Endpoint faol yoki arxivdagi media faylni faqat istoriya egasiga qaytaradi. So‘rov mobil token, Telegram initData yoki xodim sessiyasi bilan tekshiriladi. Media nomi bazaviy fayl nomi ekanligi va fayl aynan story papkasida joylashgani qayta tekshiriladi.

### `DELETE /api/stories/{story_id}`

Mavjud endpoint faol va arxiv istoriyalari uchun ishlaydi. Egasi tekshirilgach media fayllari va story yozuvi butunlay o‘chiriladi; u ommaviy hamda yopiq endpointlardan yo‘qoladi.

## Frontend media oqimi

Arxiv media endpointi autentifikatsiya talab qilgani sabab oddiy `<img src>` yoki `<video src>` orqali token siz yuborilmaydi. Frontend `fetch` va mavjud `apiHeaders()` yordamida muqova/media blobini oladi, vaqtinchalik `URL.createObjectURL` yaratadi va bo‘lim yopilganda URL’larni bekor qiladi.

Ro‘yxat ochilganda avval metadata va skelet kartalar chiqadi. Muqovalar navbat bilan yuklanadi. To‘liq video faqat foydalanuvchi `Ko‘rish`ni bosganda olinadi; shu sabab arxiv sahifasi katta videolarni oldindan xotiraga yuklamaydi.

## Xatolar va bo‘sh holatlar

- Istoriya bo‘lmasa: `Hali istoriya joylamagansiz` va `Istoriya joylash` tugmasi chiqadi.
- Arxiv bo‘lmasa: `24 soati tugagan istoriyalar shu yerda saqlanadi` matni chiqadi.
- Media fayli topilmasa karta saqlanadi, muqova o‘rniga format belgisi va `Media topilmadi` holati chiqadi.
- Ruxsat xatosida bo‘lim yopiladi va foydalanuvchiga tushunarli xabar ko‘rsatiladi.
- O‘chirishdan oldin ilova ichidagi tasdiqlash oynasi chiqadi.
- Internet xatosida `Qayta yuklash` tugmasi chiqadi.

## Sinovlar

- Faol va arxiv holatlari `expires_at` bo‘yicha to‘g‘ri ajralishi.
- Shaxsiy va biznes arxivlari aralashmasligi.
- Egasi va `ads` ruxsatli xodim kira olishi; begona aktyor 403 olishi.
- Arxiv media endpointi faol va muddati tugagan faylni egasiga qaytarishi.
- O‘chirish media fayllarini va ro‘yxat elementini yo‘qotishi.
- Frontendda ikki tab, bo‘sh holatlar, ko‘rishlar soni va o‘chirish tugmasi mavjudligi.
- Telefon va planshetda kartalar kesilmasligi va gorizontal overflow bo‘lmasligi.
- Mavjud bosh sahifa istoriyalari, joylash oynasi va viewer regressiyasiz ishlashi.

## Qabul mezonlari

Funksiya tayyor hisoblanadi, agar shaxsiy va biznes kabinetlarida alohida `Istoriyalarim` bo‘limi ochilsa, faol va arxiv istoriyalari to‘g‘ri ajralsa, muddati tugagan media faqat egasiga ko‘rinsa, ko‘rishlar soni chiqsa, o‘chirish media fayllarini tozalasa va mavjud istoriya joylash/ko‘rish oqimi buzilmasa.

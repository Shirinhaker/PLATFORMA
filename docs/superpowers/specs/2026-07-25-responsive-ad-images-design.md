# Responsive reklama rasmlari dizayni

## Maqsad

Ko‘prik bosh sahifasidagi reklama telefonda va kompyuterda ekran shakliga
mos, minimal kesilish bilan va dizayn buzilmasdan ko‘rinsin. Reklama ma’lumoti
bitta bo‘ladi, lekin reklama egasi kompyuter va telefon uchun alohida
tayyorlangan rasm yuklay oladi.

## Tasdiqlangan foydalanuvchi oqimi

1. Reklama joylash formasida `Kompyuter uchun rasm` yuklanadi.
2. Uning ostida `Telefon uchun rasm` yuklanadi.
3. Har bir rasm o‘z preview oynasida ko‘rinadi va yuqori o‘ng burchakdagi
   `×` orqali tasdiqlash bilan o‘chiriladi.
4. Kompyuter rasmi majburiy, telefon rasmi tavsiya etiladi.
5. Telefon rasmi yuklanmasa, kompyuter rasmi telefonda ham fallback sifatida
   ko‘rsatiladi.
6. Sarlavha, qisqa matn, hudud, vaqt va reklama muddati ikkala rasm uchun
   umumiy qoladi.

## Rasm talablari

Saytdagi mavjud banner konteynerlari o‘zgartirilmaydi:

| Qurilma | Saytda ko‘rinadigan o‘lcham | Nisbat | Yuklanadigan rasm uchun tavsiya |
|---|---:|---:|---:|
| Kompyuter | maksimal `1372 × 184 px` | taxminan `7.46:1` | `2744 × 368 px` |
| Telefon, 390 px ekran | `374 × 122 px` | taxminan `3.07:1` | `748 × 244 px` |
| Telefon, 420 px ekran | `404 × 122 px` | taxminan `3.31:1` | `808 × 244 px` |

- Kompyuter rasmi uchun asosiy nisbat `7.46:1`.
- Telefon rasmi uchun moslashuvchan o‘rtacha nisbat `3.2:1`; tavsiya etilgan
  standart fayl o‘lchami `800 × 250 px`.
- Jadvaldagi ikki baravar katta yuklash o‘lchamlari yuqori aniqlikdagi
  ekranlarda rasm xiralashib qolmasligi uchun berilgan.
- JPG, PNG yoki WEBP.
- Har bir rasm hajmi 5 MB gacha.
- Frontend rasm nisbatini tekshiradi va mos bo‘lmasa ogohlantiradi, lekin
  reklama joylashni to‘liq bloklamaydi.

Bu o‘lchamlar bevosita hozirgi Ko‘prik banner konteynerlaridan olingan.
Bannerning mavjud `184 px` desktop va `122 px` mobil balandligi hamda bosh
sahifa kompozitsiyasi o‘zgarmaydi. Tavsiya etilgan nisbat saqlanmasa
`object-fit: cover` sabab rasmning chetlaridan ozgina kesilishi mumkin.

## Ma’lumotlar modeli

Mavjud `advertisements.image_file` maydoni kompyuter rasmi sifatida saqlanadi.
Yangi ustun qo‘shiladi:

```text
mobile_image_file TEXT NOT NULL DEFAULT ''
```

Mavjud `crop_x`, `crop_y`, `crop_zoom` ustunlari eski reklamalar bilan
moslik uchun saqlanadi. `mobile_image_file` mavjud bo‘lgan yangi responsive
reklamalarda rasm tayyor formatda ko‘rsatiladi va qo‘shimcha crop ishlatilmaydi.

## API

Mavjud `/api/advertisements/image` endpointi ikkala rasmni alohida yuklash
uchun qayta ishlatiladi.

`POST /api/advertisements` quyidagilarni qabul qiladi:

```json
{
  "image_file": "/uploads/ads/desktop.jpg",
  "mobile_image_file": "/uploads/ads/mobile.jpg"
}
```

- `image_file` majburiy.
- `mobile_image_file` ixtiyoriy.
- Ikkala yo‘l ham faqat `/uploads/ads/` ichidagi server fayliga ishora qilishi
  kerak.
- API javoblarida `mobile_image_file` qaytariladi.

## Bosh sahifada ko‘rsatish

Reklama rasmi `<picture>` yordamida chiqariladi:

- ekran kengligi `1079px` va undan kichik bo‘lsa `mobile_image_file`;
- ekran kengligi `1080px` va undan katta bo‘lsa `image_file`;
- mobil rasm bo‘lmasa `image_file` fallback bo‘ladi.

Yangi responsive reklamada `transform: scale(...)` va crop qiymatlari
qo‘llanmaydi. Eski reklamalar uchun hozirgi crop oqimi saqlanadi.

## Orqaga moslik

- Mavjud reklama yozuvlari avtomatik migratsiya orqali saqlanadi.
- Eski reklamalarda `mobile_image_file` bo‘sh bo‘ladi.
- Ular avvalgidek `image_file` va mavjud crop qiymatlari orqali ko‘rsatiladi.
- Reklama narxi, hudud, vaqt, ko‘rishlar va bosishlar oqimi o‘zgarmaydi.
- Oddiy va biznes reklama formasi bir xil umumiy JavaScript funksiyalaridan
  foydalanadi.

## Xatolar va foydalanuvchi xabarlari

- Noto‘g‘ri format: faqat JPG, PNG yoki WEBP tanlash so‘raladi.
- 5 MB dan katta rasm qabul qilinmaydi.
- Kompyuter rasmi yo‘q bo‘lsa reklama joylash bloklanadi.
- Telefon rasmi yo‘q bo‘lsa ogohlantirish beriladi, lekin kompyuter rasmi
  fallback sifatida ishlaydi.
- Rasmni `×` bilan o‘chirish sarlavha va boshqa forma maydonlarini o‘chirmaydi.

## Testlar

1. Baza migratsiyasi `mobile_image_file` ustunini qo‘shadi.
2. API mobil rasmni saqlaydi va qaytaradi.
3. API xavfsiz bo‘lmagan mobil rasm yo‘lini rad etadi.
4. Frontendda oddiy va biznes formalarida ikkita upload/preview mavjud.
5. Har ikki previewdagi `×` faqat tegishli rasmni o‘chiradi.
6. Bosh sahifa mobil va desktop rasmni ekran kengligiga qarab tanlaydi.
7. Mobil rasmi yo‘q eski reklama desktop rasmga fallback qiladi.
8. Mavjud to‘liq regressiya testlari yashil qoladi.

## Build

Yangi build: `v1649`.

`data-ui-release="v1647"` o‘zgarmaydi, chunki mavjud profil va autentifikatsiya
dizayn selektorlari shu qiymatga bog‘langan.

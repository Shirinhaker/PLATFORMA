# Kabinet: 2 guruh — Onlaynlashtirish va Tizimlashtirish (v1611)

Biznes kabinetidagi bo'limlar endi 2 guruhga ajratilgan va 20 faoliyat yo'nalishining
har biriga avtomatik moslashadi.

## Guruhlar

**🌐 Onlaynlashtirish** — mijozlar ko'radigan va onlayn savdo bo'limlari:
Profil, Mahsulot/Xizmatlar, Stollar (ovqatlanish), Xizmat ko'rsatuvchilar + Navbat
(navbatli yo'nalishlar), Kursga yozilishlar (ta'lim), Buyurtmalar, Xizmat buyurtmalari,
Suhbatlar, Mijoz fikrlari, E'lonlar va reklamalar, Istoriyalar, Bildirishnomalar.

**🗂 Tizimlashtirish** — ichki tartib: hisob-kitob, ombor va boshqaruv:
Kassa, Xarajatlar, Qarz daftari, Ombor, Statistika, ta'limning ichki bo'limlari
(Guruhlar, O'quvchilar, Dars jadvali, Davomat, To'lov nazorati, O'qituvchilar,
Maosh, Ta'lim statistikasi), AI yordamchi, Ma'muriyat, Hisobot, Sozlamalar.

## Qanday ishlaydi

Butun mantiq `static/index.html` dagi bitta konfiguratsiyada:

- `CAB_PLANS` — 20 yo'nalishning har biri uchun reja: `labels` (bo'lim nomi/tavsifi)
  va `hide` (shu yo'nalishga kerak bo'lmagan bo'limlar).
- `applyCabinetLayout(direction)` — kabinet ochilganda `/api/me` dagi `business.yon`
  bo'yicha rejani qo'llaydi. Avval hammasini standart holatga qaytaradi, shuning uchun
  yo'nalish o'zgarsa ham eski sozlash "yopishib" qolmaydi.

Yangi yo'nalish qo'shish yoki matnni o'zgartirish uchun faqat `CAB_PLANS` ni tahrirlash
kifoya — HTML yoki boshqa funksiyalarga tegish shart emas.

## 20 yo'nalish matritsasi

| Yo'nalish | Mahsulot/Xizmatlar nomi | Yashirilgan | Boshqa moslashuvlar |
|---|---|---|---|
| Savdo | Mahsulotlar | — | Ombor: tovar qoldig'i |
| Transport va logistika | Xizmatlar va tariflar | Ombor | Navbat menyusi; qarz: mijoz/hamkor |
| Xizmat ko'rsatish | Xizmatlarim | — | Ombor: ehtiyot qismlar; navbat |
| Maishiy xizmatlar | Xizmatlar va narxlar | — | Ombor: kosmetika; yozilishlar |
| Umumiy ovqatlanish | Menyu va xizmatlarimiz | — | Stollar va xonalar; ombor: masalliqlar |
| Qurilish | Xizmatlar va ishlar | — | Ombor: materiallar; navbat |
| Tibbiy xizmatlar | Xizmatlar va narxlar | — | Shifokorlar + Navbat; ombor: dori |
| Ta'lim faoliyati | Kurslar va xizmatlar | Buyurtma, Xizmat buy., Qarz, Ombor, Statistika, Hisobot | 9 ta ta'lim bo'limi ochiladi |
| Ko'chmas mulk | Obyektlar bazasi | Ombor | Navbat; ko'rik murojaatlari |
| Qishloq xo'jaligi | Mahsulotlarim | — | Ombor: hosil va em-xashak |
| Axborot texnologiyalari | Xizmatlar va paketlar | Ombor | Navbat; loyiha buyurtmalari |
| Konsalting va professional | Xizmatlar va narxlar | Ombor | Navbat; qabul murojaatlari |
| Madaniyat, sport, ko'ngilochar | Xizmatlar va narxlar | Ombor | Navbat; bron va yozilishlar |
| Turizm va mehmonxona | Xonalar va turpaketlar | Ombor | Navbat; bron buyurtmalari |
| Ishlab chiqarish | Mahsulotlar katalogi | — | Ulgurji buyurtmalar; ombor: xomashyo |
| Hunarmandchilik | Buyumlarim | — | Ombor: material va tayyor buyumlar |
| Reklama va marketing | Xizmatlar va paketlar | Ombor | Navbat; loyiha buyurtmalari |
| Poligrafiya va nashriyot | Xizmatlar va narxlar | — | Chop buyurtmalari; ombor: qog'oz |
| Moliyaviy faoliyat | Xizmatlar va tariflar | Ombor | Navbat; murojaat va arizalar |
| Import-eksport | Tovarlar va xizmatlar | — | Partiya buyurtmalari; ombor: yuk |

## Texnik o'zgarishlar (v1611)

- `static/index.html`: kabinet menyusi 2 ta `cab-group` konteynerga bo'lindi
  (`cabGridOnline`, `cabGridTizim`); `CAB_PLANS` + `applyCabinetLayout()` qo'shildi;
  `applyEducationMenuVisibility` olib tashlandi (uning `remove()` xatti-harakati
  endi qaytariladigan `hide` bilan almashdi — yo'nalish o'zgarsa bo'limlar qaytadi);
  `ensureQueueMenu` navbat kartalarini onlayn gridga joylaydi; buyurtma badge'lari
  yo'nalishga mos tavsifni saqlaydi.
- `main.py`: `APP_BUILD = "v1611"`.
- `tests/test_story_frontend_contract.py`: versiya tekshiruvi v1611 ga yangilandi.

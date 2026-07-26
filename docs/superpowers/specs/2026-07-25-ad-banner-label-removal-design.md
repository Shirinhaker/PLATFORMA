# Reklama banneridagi xizmat yozuvlarini olib tashlash dizayni

## Maqsad

Bosh sahifadagi reklama bannerida foydalanuvchiga ko‘rinadigan
`Tavsiya etamiz` va alohida `Reklama` xizmat yozuvlari ko‘rsatilmasin.
Reklamaning o‘z sarlavhasi, qisqa matni, rasmi va `Ko‘rish` tugmasi
saqlansin.

## O‘zgarish chegarasi

Faqat bosh sahifadagi `#adBox` bannerining ko‘rinadigan matn qismi
o‘zgartiriladi:

- `#adEyebrow` elementi HTML’dan olib tashlanadi;
- JavaScript `#adEyebrow` elementiga matn yozmaydi;
- aktiv reklama sarlavhasi bo‘sh bo‘lsa, `Reklama` zaxira sarlavhasi
  o‘rniga neytral `Taklif bilan tanishing` matni ishlatiladi;
- banner ichida alohida `Reklama` tegi qayta paydo bo‘lmasligi test bilan
  himoyalanadi.

## O‘zgarmaydigan qismlar

- reklama rasmi va telefon/kompyuter uchun alohida rasmlar;
- reklama sarlavhasi va tavsifi;
- `Ko‘rish` tugmasi;
- reklama karuseli va almashish tezligi;
- ko‘rishlar va bosishlarni hisoblash;
- reklama joylash va boshqarish oynalari;
- qidiruv, xarita, istoriyalar, takliflar va kabinetlar;
- API, ma’lumotlar bazasi va reklama tariflari.

## Xatolik holati

Reklamalar ro‘yxati bo‘sh bo‘lsa, mavjud boshlang‘ich banner ishlashda
davom etadi. Faqat `Tavsiya etamiz` qatori ko‘rinmaydi. Reklama ma’lumoti
kelmasa, JavaScript mavjud DOM elementiga murojaat qilib xato bermaydi.

## Qabul mezonlari

1. Bosh sahifa bannerining HTML qismida `id="adEyebrow"` yo‘q.
2. Banner JavaScript kodida `adEyebrow` ga murojaat yo‘q.
3. Bannerning aktiv reklama zaxira sarlavhasi `Reklama` emas.
4. `alt="Reklama"` accessibility matni saqlanadi; u ekranda ko‘rinmaydi.
5. Banner rasmi, sarlavhasi, tavsifi va `Ko‘rish` tugmasi saqlanadi.
6. Mavjud barcha avtomatik testlar yashil qoladi.

## Testlash

- frontend kontrakt testi olib tashlangan yozuvlar qaytmasligini tekshiradi;
- mavjud reklama, qidiruv va responsive banner testlari qayta ishlatiladi;
- to‘liq test to‘plami regressiyani tekshiradi;
- inline JavaScript sintaksisi alohida tekshiriladi.

# Ko‘prik — brauzer Back tugmasi uchun ichki navigatsiya

## Maqsad

Kompyuter brauzeridagi Back tugmasi va telefonning tizim Back tugmasi sayt
ichidagi oldingi ekranga qaytarsin. Foydalanuvchi ichki bo‘limda yoki qidiruv
natijasida turganida bir bosishda `koprik.uz`dan chiqib ketmasin.

## Muammoning sababi

Mavjud `nav(screen)` faqat `.screen` elementlarining `active` klassini
almashtiradi. U `history.pushState()` ishlatmaydi va kodda `popstate`
tinglovchisi yo‘q. Shu sabab brauzer Ko‘prikning `catalog`, `listings`,
`cabinet`, `taxi-call` va boshqa ichki ekranlarini tarix sifatida bilmaydi.

Qidiruv natijasi ham alohida ekran emas: u bosh sahifadagi `#resWrap`
holatidir. Shuning uchun natija ochilganda ham brauzer tarixiga alohida holat
yozilishi kerak.

## Tanlangan yechim

### Tarix holati

Har bir Ko‘prik tarix yozuvi quyidagi shaklda bo‘ladi:

```javascript
{
  koprikApp: true,
  screen: "home",
  results: false
}
```

- `screen` — joriy ichki ekran nomi.
- `results` — bosh sahifada qidiruv natijalari ochiqligini bildiradi.
- Birinchi yuklanishda joriy browser yozuvi `replaceState()` bilan Ko‘prikning
  `home` holatiga aylantiriladi.
- Keyingi haqiqiy ichki o‘tishlar `pushState()` orqali yoziladi.
- Bir xil ekran qayta chizilganda ortiqcha tarix yozuvi yaratilmaydi.

### Oddiy ekranlar

- `nav(screen)` orqali boshqa ekranga o‘tilganda yangi tarix yozuvi qo‘shiladi.
- `popstate` kelganda `nav(screen, {fromHistory:true})` ishlatiladi va yangi
  tarix yozuvi yaratilmaydi.
- Brauzer Forward tugmasi ham saqlangan ichki ekranni qayta ochadi.
- Sayt ichidagi yuqori chap Back tugmasi ham browser tarixidagi oldingi
  Ko‘prik holatiga qaytadi.
- Tarix bo‘lmasa, mavjud `BACKMAP` fallbacki ishlaydi.

### Qidiruv natijalari

- Birinchi qidiruv natijasi ochilganda `{screen:"home", results:true}` holati
  bir marta tarixga qo‘shiladi.
- Qidiruvning loading holatidan yakuniy natijaga o‘tishda yoki “yana ko‘rsat”
  bosilganda ikkinchi bir xil tarix yozuvi yaratilmaydi.
- Back bosilganda `results:false` holatiga qaytilsa, `exitResults()` natija
  oynasini yopadi va bosh sahifani tiklaydi.
- Qidiruv katalogdan boshlangan bo‘lsa, Back katalog ekraniga qaytadi.
- Forward bosilganda `RES` keshidagi natija qayta ko‘rsatiladi.

### Taxi

- Taxi ekranidan browser Back bosilganda faqat ekran almashtirilmaydi:
  `exitCall()`ning xaritani bosh sahifaga qaytarish, timerlarni to‘xtatish va
  Taxi holatini tozalash ishlari ham bajariladi.
- Popstate orqali bajarilgan Taxi chiqishi yangi tarix yozuvi yaratmaydi.

## Bosh sahifada chiqish

- Ichki sahifalarda Back foydalanuvchini saytdan chiqarmaydi.
- Foydalanuvchi boshlang‘ich bosh sahifaga qaytib bo‘lgach, yana Back bossa,
  brauzerning odatiy xatti-harakati ishlaydi va oldingi tashqi saytga qaytishi
  mumkin.
- Bosh sahifada Back tugmasini doimiy bloklash qilinmaydi.

## O‘zgarmaydigan qismlar

- `BACKMAP` fallback sifatida saqlanadi.
- Qidiruv API, natijalar tartibi va xarita metkalari o‘zgarmaydi.
- Kabinet ruxsatlari, login, buyurtmalar va boshqa biznes mantiqi o‘zgarmaydi.
- URL’ga yangi server route qo‘shilmaydi; History API bir xil `koprik.uz`
  hujjati ichida ishlaydi.

## Qabul mezonlari

- Kodda `history.replaceState`, `history.pushState` va `popstate` mavjud.
- `home → catalog → cat-types` ketma-ketligida Back avval `catalog`, keyin
  `home`ga qaytaradi.
- `home → listings` ketma-ketligida Back `home`ga qaytaradi.
- Bosh sahifadagi qidiruv natijasidan Back natijani yopib, bosh sahifani
  saqlaydi.
- Katalogdan ochilgan natijadan Back katalogga qaytaradi.
- Taxi ekranidan Back xaritani bosh sahifaga qaytaradi.
- Popstate ichida yangi `pushState` yaratilmaydi.
- Barcha mavjud testlar o‘tadi.

## Tekshiruv

- History API markup/JavaScript contract testi.
- Browser tarixining minimal model testi: oddiy ekran, natija va Taxi oqimi.
- Mavjud qidiruv, mobil, desktop va Taxi regression testlari.
- Inline JavaScript sintaksis tekshiruvi.
- To‘liq Python testlari.


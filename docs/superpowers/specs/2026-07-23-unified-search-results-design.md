# Ko‘prik — qidiruv natijalarini barcha ekranlarda birlashtirish

## Maqsad

Telefon, planshet va kompyuterda qidiruv natijalari bir xil tartibda:
xaritaning ostida va reklamaning ustida ko‘rinsin. Ortiqcha katta natijalar
kartasi olib tashlansin, reklamadagi ko‘rinadigan `Reklama` belgisi chiqmasin.

## Joriy muammoning sababi

`#resWrap` HTML ichida reklama va hududiy takliflardan keyin joylashgan.
Faqat `620px` va undan kichik ekranlardagi CSS `order` qoidalari uni xaritaning
ostiga ko‘chiradi. Shu sabab telefon va kompyuterda natijalar boshqa-boshqa
joyda chiqadi.

`#resBar` esa ikonka, izoh va ochish-yopish strelkasiga ega katta `menu-card`
bo‘lgani sabab natijalar tepasida ortiqcha balandlik egallaydi.

## Tanlangan yechim

### Natijalar joylashuvi

- `#resWrap` bosh sahifa DOM tartibida `#homeDiscovery`dan keyin,
  `#adBox`dan oldin joylashtiriladi.
- Shuning uchun telefon, planshet va desktopda natijalar tabiiy ravishda
  xaritaning ostida, reklamaning ustida chiqadi.
- Mobil `search-results-active` holati va vertikal aylantirish saqlanadi.
- Qidiruv API, xarita metkalari, saralash va profil turlari o‘zgarmaydi.

### Ixcham natijalar sarlavhasi

- Katta oq `#resBar.menu-card` butunlay olib tashlanadi.
- Uning ikonka, `Profillarni ko‘rish uchun bosing` izohi va strelkasi ham
  olib tashlanadi.
- `#resCount` natijalar ro‘yxatining yuqorisida ixcham satr sifatida qoladi:
  masalan, `Natijalar — 1 ta`.
- `#resList` natija kelganda darhol ochiq turadi; eski sarlavhani bosib
  yig‘ish-ochish hodisasi olib tashlanadi.
- Ko‘k `«so‘rov» bo‘yicha natijalar ko‘rsatilmoqda` izohi saqlanadi.
- `Mahsulot va xizmatlar`, `E’lonlar`, `Mutaxassislar`, `Bizneslar` kabi
  natija guruhlari sarlavhalari saqlanadi.

### Reklama

- Bosh sahifa reklamasidagi ko‘rinadigan `<span class="tag">Reklama</span>`
  olib tashlanadi.
- Reklama rasmi, sarlavhasi, tavsifi, aylanishi va bosish funksiyasi
  o‘zgarmaydi.
- Rasmning `alt="Reklama"` matni accessibility uchun saqlanadi; u ekranda
  ko‘rinadigan belgi emas.

## Responsive tartib

Qidiruv natijasi mavjud bo‘lganda barcha ekranlarda:

1. Qidiruv va xarita;
2. Ixcham `Natijalar — N ta` satri;
3. Natija kartalari;
4. Reklama;
5. Hududiy takliflar.

Oddiy, qidiruvsiz bosh sahifa tartibi o‘zgarmaydi.

## Qabul mezonlari

- Visible `Reklama` tagi bosh sahifa bannerida yo‘q.
- `#resWrap` DOM’da `#homeDiscovery`dan keyin va `#adBox`dan oldin turadi.
- `#resBar` va uning click handleri kodda yo‘q.
- `#resCount` ixcham natijalar sarlavhasi sifatida mavjud.
- Ko‘k tuzatilgan-so‘rov izohi saqlangan.
- Telefon, planshet va desktop natijalari bir xil tarkibiy tartibda.
- Mavjud qidiruv, xarita, reklama va Taxi funksiyalari regressiyasiz ishlaydi.

## Tekshiruv

- Yangi frontend contract testi eski kodda yiqiladi va o‘zgarishdan keyin
  o‘tadi.
- Mobil, desktop, qidiruv, xarita va Taxi kontrakt testlari o‘tadi.
- Inline JavaScript sintaksisi tekshiriladi.
- Barcha Python testlari bajariladi.


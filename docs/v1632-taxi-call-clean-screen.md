# BUILD v1632 — Taxi chaqiruv uchun toza sahifa

## Muammo

v1630–v1631 mobil bosh sahifa besh qatorli gridga o‘tkazilgandan so‘ng Taxi
paneli shu gridga qo‘shimcha element sifatida kirib qolgan. Hududiy mahsulot va
e’lonlar uchun yangi `districtOffersMount` bloki eski Taxi yashirish ro‘yxatiga
kiritilmagani sababli kartalar Taxi panelining ustiga chiqayotgan edi.

## Yechim

- Taxi ochilganda `.phone` elementiga `taxi-call-active` holati qo‘shiladi.
- Mobil Taxi sahifasi vertikal oqimda: istoriyalar, Taxi paneli, haydovchi
  ma’lumoti va xarita tartibida ishlaydi.
- Qidiruv/katalog kartasi, qidiruv natijalari, reklama va tumandagi mahsulot,
  xizmat hamda e’lonlar Taxi rejimida majburiy yashiriladi.
- Kechikkan hududiy taklif API javobi kartalarni qayta ko‘rsata olmaydi.
- Taxi yopilganda alohida holat olib tashlanib, odatiy bosh sahifa tiklanadi.
- Taxi API, narx, GPS, Taxi/Dostavka va buyurtma oqimlari o‘zgartirilmadi.

## O‘zgargan ishlab chiqarish fayllari

- `static/index.html`
- `main.py`

## Test fayli

- `tests/test_taxi_call_clean_screen_contract.py`

## Tekshiruv

```bash
python -m unittest tests.test_taxi_call_clean_screen_contract -v
python -m unittest discover -s tests -v
node --check /tmp/koprik-v1632-inline.js
```

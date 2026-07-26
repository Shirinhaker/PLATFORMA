# BUILD v1633 — Taxi alohida ekran

## Maqsad

Taxi chaqiruv oqimini bosh sahifa ichidagi yashiriladigan holatdan chiqarib,
boshqa bo‘limlar kabi mustaqil `taxi-call` ekranga o‘tkazish.

## O‘zgarishlar

- Taxi ekranida faqat buyurtma paneli, haydovchi ma’lumoti va xarita qoladi.
- Qidiruv, istoriyalar, reklama va hududiy takliflar faqat bosh sahifada
  saqlanadi; ular Taxi ekranining HTML tarkibiga kirmaydi.
- Ikkinchi xarita yaratilmaydi. Mavjud Leaflet xarita Taxi ochilganda
  `taxiMapHost`ga ko‘chiriladi va chiqilganda `homeDiscovery`ga qaytariladi.
- Yuqori orqaga tugmasi, paneldagi yopish tugmasi va buyurtmani bekor qilish
  `exitCall()` orqali bosh sahifaga xavfsiz qaytadi.
- Login talab qilinganda ham xarita avval bosh sahifaga qaytariladi.
- Taxi API, GPS, narx va buyurtma holati mantig‘i o‘zgartirilmadi.

## BUILD

- `APP_BUILD = "v1633"`
- `/api/build`: `"separate_taxi_screen_v1633": true`

## Ishlab chiqarish fayllari

- `static/index.html`
- `main.py`

## Tekshiruv

```bash
python -m unittest tests.test_taxi_call_clean_screen_contract -v
python -m unittest discover -s tests -q
node --check /tmp/koprik-v1633-inline.js
node tests/district-offers-ui-smoke.cjs --contract-only
```

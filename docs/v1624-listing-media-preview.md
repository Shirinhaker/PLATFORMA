# Ko‘prik v1624 — e’lon media ko‘rinishi

## Tuzatildi

- E’lon joylash formasida rasm belgisi o‘rniga haqiqiy rasm miniaturasi chiqadi.
- Video belgisi o‘rniga videoning boshlang‘ich kadri va `VIDEO` belgisi chiqadi.
- Tanlangan rasm yoki video miniaturasi bosilganda katta oynada ochiladi.
- E’lon ichidagi rasm va videolar bir xil `4:3` o‘lchamli kartalarda ko‘rsatiladi.
- Katta oynada rasm to‘liq ko‘rinadi, video boshqaruv tugmalari bilan ijro etiladi.
- Media yuklanishi tugamaguncha `Joylash` tugmasi bloklanadi.

## Tekshiruv

- `node --check static/app.js` — muvaffaqiyatli.
- HTTP smoke: HTML, CSS va JavaScript `200`, BUILD `v1624`.
- `python -m unittest discover -s tests` — 172/172 test muvaffaqiyatli.

## O‘zgarmagan qismlar

- E’lon API formati va ma’lumotlar bazasi o‘zgarmadi.
- Istoriya va tariflar o‘zaro mustaqil qoladi.
- Pro uchun maxsus metka qo‘shilmadi.
- Tuman maxfiyligi va vaqtinchalik loyiha bloki saqlandi.

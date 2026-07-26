# Ko‘prik v1623 — frontend fayllarini optimallashtirish

## Natija

- Katta inline CSS `static/app.css` fayliga ajratildi.
- Katta inline JavaScript `static/app.js` fayliga ajratildi.
- `static/index.html` hajmi 935 KB dan 143 KB gacha kamaydi.
- HTML har safar yangilanadi, versiyalangan statik fayllar esa brauzerda keshlanadi.
- Mavjud ekranlar, funksiyalar va integratsiya sozlamalari o‘zgartirilmadi.

## Kesh siyosati

- `/`, `/index.html`, diagnostika va dinamik reklama API javoblari: `no-store`.
- `/app.css`, `/app.js`, `/regions.js`, `/qrcode.min.js` va demo reklama fayllari:
  `public, max-age=86400, stale-while-revalidate=604800`.
- CSS va JavaScript manzillarida `?v=1623` versiya parametri ishlatiladi.

## Tekshiruv

- `node --check static/app.js` — muvaffaqiyatli.
- HTTP smoke — HTML, CSS va JavaScript `200`, kesh sarlavhalari to‘g‘ri.
- `python -m unittest discover -s tests` — 167/167 test muvaffaqiyatli.

## Deploy

Railway’ga to‘liq v1623 arxivini yuklash kifoya. Yangi tashqi servis yoki yangi muhit
o‘zgaruvchisi talab qilinmaydi. Integratsiyalar avvalgidek o‘chirilgan holatda qoladi.

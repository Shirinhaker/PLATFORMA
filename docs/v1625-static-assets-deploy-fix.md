# Ko‘prik v1625 — statik fayllar deploy tuzatishi

## Sabab

Railway’da `static/index.html` bor edi, ammo `static/app.css` va `static/app.js`
GitHub reposiga yuklanmagan. HTML ochilgan, lekin CSS va JavaScript `404` qaytargani
uchun sahifa uslubsiz ko‘ringan.

## Tuzatish

- `static/app.css` va `static/app.js` deploy paketiga majburiy kiritildi.
- `index.html` statik fayllarni `?v=1625` orqali chaqiradi; avval keshlangan 404 chetlab o‘tiladi.
- Faqat muvaffaqiyatli statik javoblar keshlanadi.
- `404` va boshqa xato javoblar `Cache-Control: no-store` oladi.

## GitHub joylashuvi

- `main.py` — repo boshida.
- `index.html`, `app.css`, `app.js` — aynan `static/` papkasida.

## Tekshiruv

- JavaScript sintaksisi to‘g‘ri.
- Lokal HTTP: CSS `200`, JS `200`, mavjud bo‘lmagan fayl `404 no-store`.
- 172/172 test muvaffaqiyatli.

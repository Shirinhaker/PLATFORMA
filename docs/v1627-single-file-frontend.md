# Ko‘prik v1627 — bitta faylli frontend

## Talab

`app.js`, `app.css` va `index.html` alohida ajratilmasin — hammasi bitta faylda
bo‘lsin. v1625 dagi kabi `app.css`/`app.js` GitHub’ga yuklanmay qolishi yoki
keshlangan `404` muammolari umuman yuzaga kelmasligi kerak.

## O‘zgarishlar

- `static/app.css` mazmuni `index.html` ichidagi `<style>` blokiga ko‘chirildi.
- `static/app.js` mazmuni `index.html` oxiridagi inline `<script>` blokiga
  ko‘chirildi.
- `static/app.css` va `static/app.js` fayllari olib tashlandi; ularga `?v=`
  havolalar ham yo‘q.
- `regions.js`, `qrcode.min.js` va `demo_ads/` avvalgidek alohida qoladi va
  eski kesh siyosati bilan xizmat qiladi.
- `index.html` hajmi ~943 KB (v1623 dan avvalgi holatga qaytdi); HTML `no-store`
  bo‘lgani uchun har deploy’da darhol yangilanadi, qo‘shimcha versiya parametri
  talab qilinmaydi.
- v1626 dagi telefon tuzatishi (bosh sahifadagi E’lonlar, `placeElonSection`)
  o‘z holicha inline skript ichida ishlaydi.

## Deploy

GitHub’ga endi frontend uchun faqat `static/index.html` yuklash kifoya —
`app.css`/`app.js` ni alohida kuzatish shart emas.

## Tekshiruv

- Inline skript sintaksisi `node --check` bilan tasdiqlandi.
- Lokal HTTP: `/` — `200`, ichida `<style>` va inline `<script>`;
  `/app.css` va `/app.js` — `404 no-store` (eski keshlangan havolalar zararsiz).
- `tests/test_frontend_assets.py` bitta-fayl kontraktiga qayta yozildi;
  to‘liq regressiya barcha testlarni bajaradi.

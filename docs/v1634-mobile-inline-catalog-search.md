# Ko‘prik v1634

## Mobil bosh sahifa

- `Katalog bo‘yicha` tugmasi qidiruv qatorining ichiga joylashtirildi.
- Qidiruv maydoni fokus olganda katalog tugmasi vaqtincha yashiriladi.
- Qidiruv maydonidan chiqilganda katalog tugmasi yana ko‘rinadi.
- Bo‘shagan vertikal joy hisobiga reklama bloki 100 pikselgacha balandlashtirildi.
- Telefon bosh sahifasidagi xaritada `+` va `−` tugmalari yashirildi.
- Xaritani barmoq bilan surish va ikki barmoq bilan kattalashtirish ishlashda davom etadi.

## O‘zgarmagan qismlar

- Kompyuter va planshetdagi qidiruv ko‘rinishi o‘zgarmadi.
- Taksi sahifasidagi xarita boshqaruvlari o‘zgarmadi.
- Qidiruv, katalog, xarita va reklama funksiyalarining API ishlashi o‘zgarmadi.

## Versiya

- `APP_BUILD`: `v1634`
- `/api/build`:
  - `mobile_inline_catalog_search_v1634`
  - `mobile_home_zoom_controls_hidden_v1634`

## Ishlab chiqarish fayllari

- `static/index.html`
- `main.py`

## Tekshiruv

```bash
python -m unittest tests.test_mobile_home_single_screen_contract
python -m unittest discover -s tests -q
node tests/district-offers-ui-smoke.cjs --contract-only
```

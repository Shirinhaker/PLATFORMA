# Ko‘prik v1635

## Qidiruv natijalari

- Telefon, planshet va kompyuterda natijalar xaritaning ostida, reklamaning
  ustida chiqadi.
- Katta oq natijalar kartasi olib tashlandi.
- Natijalar soni ro‘yxat tepasida ixcham `Natijalar — N ta` satrida chiqadi.
- Natijalar darhol ochiq ko‘rinadi.
- Ko‘k qidiruv izohi va natija guruhlari sarlavhalari saqlandi.

## Reklama

- Banner ustidagi ko‘rinadigan `Reklama` belgisi olib tashlandi.
- Reklama rasmi, matni, aylanishi va bosish funksiyasi o‘zgarmadi.

## O‘zgarmagan qismlar

- Qidiruv API va saralash.
- Xarita metkalari va natijalarga mos markazlash.
- Oddiy va biznes profillar, mutaxassislar hamda e’lonlar natijalari.
- Taxi sahifasi.

## Versiya

- `APP_BUILD`: `v1635`
- `/api/build`:
  - `unified_search_results_v1635`
  - `home_ad_tag_hidden_v1635`

## Ishlab chiqarish fayllari

- `static/index.html`
- `main.py`

## Tekshiruv

```bash
python -m unittest tests.test_unified_search_results_contract
python -m unittest discover -s tests -q
node tests/district-offers-ui-smoke.cjs --contract-only
```

# v1645 — Obuna bo‘lingan biznes metkasi

## Xarita qoidasi

- Joriy oddiy profil obuna bo‘lgan biznes metkasi tarifidan qat’i nazar
  ko‘rinadi.
- Biznes rejimida faqat shu biznes profil nomidan qilingan obunalar olinadi.
- Obuna bo‘linmagan bizneslardan faqat faol `Pro` tarifdagilar ko‘rinadi.
- `Plus` tarifning o‘zi xarita metkasini bermaydi.
- Barcha natijalar tanlangan tuman, faol biznes holati va mavjud koordinata
  bo‘yicha tekshiriladi.
- Tarifga qarab alohida marker uslubi berilmaydi.

## O‘zgargan asosiy fayllar

- `api.py` — `/api/map` nomzodlarini `obuna qilingan OR Pro` qoidasi bilan
  tanlaydi.
- `tests/test_pro_follow_map_api.py` — oddiy profil, biznes profil va mehmon
  holatlari uchun regressiya testlari.
- `main.py`, `static/index.html` — `v1645` build belgisi.


# Phase 3C V7 — cabinet JSON normalization

## Maqsad

`user_profiles.cabinet_payload` va `business_profiles.cabinet_payload` ichida vaqtincha saqlangan haqiqiy v1656 ma’lumotlarini yo‘qotishsiz relational jadvallarga o‘tkazish.

## Qat’iy tartib

1. Yangi relational schema yaratiladi.
2. Eski JSON va yangi relational yozuvlar dual-read/dual-write rejimida ishlaydi.
3. Barcha profillar uchun resource count, record count va canonical SHA-256 digest tekshiriladi.
4. Verify 100% bo‘lmaguncha JSON kalitlari o‘chirilmaydi.
5. Staging smoke testdan keyin read path relational jadvallarga o‘tadi.
6. Keyingi alohida cleanup migratsiyasida faqat tasdiqlangan kalitlar `cabinet_payload`dan olib tashlanadi.

## Xavfsizlik chegarasi

- V7 staging migratsiyasi qayta ishlatilmaydi.
- Production monolit BUILD v1656 va `static/index.html` o‘zgarmaydi.
- Production DBga yozilmaydi.
- Demo/test yozuvlar qayta qo‘shilmaydi.
- Account ownership va resource chegaralari FK va unique constraintlar bilan himoyalanadi.
- Maxfiy token/parol/hash maydonlari normalizatsiya qatlamiga kiritilmaydi.

## GREEN gate

- nested dict/list/scalar round-trip tengligi;
- account type/account id/resource isolation;
- source/target resource va record count tengligi;
- canonical SHA-256 digest tengligi;
- idempotent backfill;
- dual-write mutation parity;
- full Phase 3A/3B/3C CI.

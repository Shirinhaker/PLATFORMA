# BUILD v1630 — telefon bosh sahifasi bitta ekranda

## O‘zgarishlar

- Telefon bosh sahifasi `320×568`, `360×640` va `390×844` ekranlarga moslandi.
- Yuqori menyu, istoriyalar, qidiruv, xarita, reklama va takliflar bir vaqtda ko‘rinadi.
- Sahifaning gorizontal va vertikal chiqib ketishi bloklandi.
- “20 ta demo taklif qo‘shish” tugmasi frontenddan olib tashlandi.
- Desktop, planshet, backend demo endpointi, qidiruv va xarita algoritmlari o‘zgartirilmadi.

## Tekshiruv

- Python testlari: `187/187` muvaffaqiyatli.
- JavaScript sintaksis tekshiruvi muvaffaqiyatli.
- Playwright viewport kontrakti: `320×568`, `360×640`, `390×844`, `820×1180`, `1440×1000`.
- District offers UI kontrakti muvaffaqiyatli.
- Ushbu ish muhitida Chromium yuklab olinmagani sababli real Playwright render testi bajarilmadi.

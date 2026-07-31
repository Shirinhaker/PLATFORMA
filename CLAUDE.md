# PLATFORMA — loyiha qoidalari

Bu fayl Claude uchun. Kod yozishda va PR ko'rib chiqishda quyidagi
qoidalarga amal qilinadi.

## Loyiha tuzilishi

- **Backend**: FastAPI (Python), ildizdagi `main.py`, `api.py` va modullar.
- **Frontend**: React + TypeScript + Vite, `frontend/` papkasida.
- **Testlar**: frontend uchun vitest — `cd frontend && npm test`.
- **Tip tekshiruvi**: `cd frontend && npx tsc --noEmit`.
- **Hujjatlar**: `docs/` papkasida bosqichlar bo'yicha (Phase 2, 3, 3C, V7).

## Eng muhim qoida: v1656 pariteti

Ishlab turgan eski monolit sayt (v1656) — haqiqat manbai. Yangi modullarga
ko'chirilgan har qanday ekran undan **aynan** nusxa bo'lishi shart:

- tugma va sarlavha matnlari harfma-harf bir xil (o'zbekcha matnlar ham),
- CSS klass nomlari va ko'rinish bir xil,
- xatti-harakat bir xil (qidiruv paytida nima yashirinadi, menyu qanday
  ochiladi, bo'sh holatda nima yoziladi).

Farq kiritish kerak bo'lsa, avval sababini `docs/` ichida hujjatlashtiring.

## Testlar bo'yicha qat'iy talablar

- Test **hech qachon** `skip`, `todo` yoki o'chirish yo'li bilan
  "yashil" qilinmaydi. Test yiqilsa — kod tuzatiladi, test emas.
- Assert zaiflashtirilmaydi. Mavjud tekshiruv olib tashlansa, o'sha
  qoplama boshqa test fayliga ko'chirilishi shart.
- Yangi ekran qo'shilsa, unga parity testi ham qo'shiladi.
- PR yuborishdan oldin `npm test` va `npx tsc --noEmit` toza o'tishi kerak.

## Ish uslubi

- TDD: avval qizil test, keyin tuzatish, keyin yashil.
- Commitlar mayda va aniq, prefikslar bilan: `feat:`, `fix:`, `test:`,
  `refactor:`, `style:`, `docs:`, `chore:`, `ops:`.
- Har bir ish alohida branchda, `main` ga faqat PR orqali qo'shiladi.

## Xavfsizlik va UX talablari

- **O'chirish amali doim tasdiqlash so'raydi** ("Ishonchingiz komilmi?").
- Forma saqlanmasa, foydalanuvchiga sabab ko'rsatiladi — jim turmaydi.
- Narx, miqdor kabi raqamli maydonlar validatsiya qilinadi.
- Tugma qo'yilgan bo'lsa, u haqiqiy amal bajarishi shart — bo'sh
  yoki aldamchi tugma qoldirilmaydi.
- API kalitlar, parollar va maxfiy qiymatlar repoga yozilmaydi.

## V7 migratsiya davrida

Kabinet ma'lumotlari JSON'dan relatsion bazaga ko'chirilmoqda. Shu sababli:

- maydon nomlari uchun fallback saqlanadi (`group_id` / `item_group_id`,
  `note` / `description`),
- guruhi yo'q ("yetim") yozuvlar yo'qolmaydi, "Guruhsiz" bo'limiga tushadi,
- migratsiya skriptlari qaytadan ishga tushirilganda ma'lumot buzmasligi
  (idempotent) shart.

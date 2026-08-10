# K20 — Ta'lim boshqaruvi migratsiyasi

## Monolitdagi manba

`static/index.html` o'zgartirilmagan. v1656 xatti-harakatining manbasi:

- menyu: `1790–1795`;
- ekranlar: `2044–2088`;
- dars jadvali: `9018–9048`;
- davomat: `9050–9082`;
- o'quvchi to'lovlari va nazorati: `9084–9123`;
- o'qituvchilar: `9125–9135`;
- o'qituvchi maoshi: `9143–9149`;
- ekran ochish hooklari: `12001–12006`;
- vakolatlar: `13894–13900`.

Legacy backend manbasi `api.py`da:

- davomat: `2969–3041`;
- to'lov nazorati va hisoblash: `3044–3133`;
- to'lovlar: `3136–3255`;
- o'qituvchilar: `3258–3319`;
- maosh: `3457–3500`.

## Ishlash zanjiri

```text
Guruh + o'qituvchi
        │
        ├──> haftalik dars jadvali
        ├──> davomat ──> o'quvchi to'lov hisobi ──> Kassa cheki
        └──> o'tilgan darslar ──> o'qituvchi maoshi ──> Xarajat
```

## Modulli joylashuv

```text
React ekranlari
frontend/src/education/EducationManagementV1656.tsx
        │ typed HTTPS
        ▼
backend/app/education/router.py
        ▼
management_service.py
        ├── management_repository.py ──> education_* jadvallari
        ├── CashRegisterRepository ────> cash_receipts + lines
        └── Expense ──────────────────> expenses
```

Typed APIlar:

- `GET /api/v1/education/groups`;
- `GET|PUT /api/v1/education/attendance`;
- `GET /api/v1/education/payment-control`;
- `GET|POST /api/v1/education/payments`;
- `POST /api/v1/education/payments/{id}/void`;
- `GET|POST|PUT|DELETE /api/v1/education/teachers`;
- `GET|POST|DELETE /api/v1/education/teacher-payroll`.

## Yaxlitlik va xavfsizlik

- Har bir so'rov `business_account_id` bilan tenant-scoped.
- Faqat `Ta'lim faoliyati` yo'nalishi ishlata oladi.
- Xodim uchun `education_attendance`, `education_payments`,
  `education_teachers`, `education_payroll` vakolatlari serverda tekshiriladi.
- O'quvchi to'lovi va Kassa cheki bitta tranzaksiyada yaratiladi.
- To'lovni bekor qilish faqat biznes egasiga ruxsat; bekor qilingan summa
  hisob-kitobga kirmaydi va chek satri tozalanadi.
- Maosh va `education_salary` xarajati bitta tranzaksiyada yaratiladi hamda
  birga o'chiriladi.
- `0034_education_management` eski ta'lim to'lovini mavjud Kassa cheki bilan
  bog'laydi; qayta deploy dublikat yaratmaydi.

## Migratsiyadan keyingi holat

K9/K10 hujjatlarida keyinga qoldirilgan besh ta boshqaruv ekrani endi React,
typed API va relatsion jadvallarda ishlaydi. Guruh/o'quvchi/ariza/statistika
oldingi modullarda qoladi va shu relatsion ma'lumotlardan foydalanadi.

Legacy fallback kodini olib tashlash faqat production backfill, paritet
tekshiruvi va rollback oynasi yakunlangach alohida cleanup migratsiyasida
bajariladi. Ushbu PR `static/index.html`ni o'zgartirmaydi.

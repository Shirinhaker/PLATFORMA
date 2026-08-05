# K10 — Ta'lim guruhlari va o'quvchilari boshqaruvi

K7 guruh va o'quvchi jadvallarini yaratdi, K9 ularga statistika uchun
kerak bo'lgan maydonlarni qo'shdi. Ikkalasida ham **faqat o'qish** bor
edi: kabinet ekranida guruh yaratib ham, o'quvchi qo'shib ham
bo'lmasdi. K10 shu bo'shliqni yopadi.

`static/index.html` v1656 manbasi va frontend fayllari o'zgarmaydi.

## Ko'chirilgan funksiyalar

- guruh yaratish, tahrirlash va yumshoq o'chirish;
- o'quvchi qo'shish, tahrirlash va yumshoq o'chirish;
- o'quvchini **guruhdan guruhga ko'chirish** va ko'chirish tarixi;
- guruh o'zgarganda tarix avtomatik yopiladi va yangisi ochiladi;
- barcha tekshiruvlar v1656 bilan bir xil.

## v1656 tekshiruvlari pariteti

| Qoida | v1656 manbasi | Yangi kod |
|---|---|---|
| Guruh nomi majburiy (80 belgi) | `_education_group_payload` | `education_group_name_required` |
| Kurs shu biznesning `service` mahsuloti bo'lishi | shu yerda | `education_course_not_found` |
| Sig'im 0–10000 | shu yerda | `_bounded(low=0, high=10000)` |
| Hafta kunlari faqat `mon…sun` | shu yerda | noma'lum kunlar tashlab yuboriladi |
| To'lov turi `monthly`/`attendance` | shu yerda | boshqasi `monthly` ga tushadi |
| `attendance` uchun paket majburiy | shu yerda | `education_package_required` |
| O'quvchi ismi majburiy (120 belgi) | `_education_student_payload` | `education_student_name_required` |
| Guruh shu biznesniki bo'lishi | shu yerda | `education_group_required` |
| Guruh/o'quvchi o'chirilganda arxivga o'tadi | `status='deleted'` | bir xil |

## Ko'chirish tarixi

`education_student_group_history` jadvali qo'shildi. v1656dagi kabi:
ko'chirishda ochiq yozuv yopiladi (`ended_date`) va yangisi ochiladi.
Migratsiya mavjud o'quvchilar uchun boshlang'ich yozuvni o'sha yerdagi
`INSERT … SELECT` mantiqi bilan seed qiladi.

Tarix uchta joyda yangilanadi: o'quvchi yaratilganda, tahrirlashda
guruh o'zgarganda va alohida `transfer` amalida.

## Ulanish

Yozish amallari kabinetning umumiy API'si orqali keladi va
`service_relational.py` da relatsion jadvalga yo'naltiriladi:

```
POST   /api/v1/business-online/education_groups
PUT    /api/v1/business-online/education_groups/{id}
DELETE /api/v1/business-online/education_groups/{id}
POST   /api/v1/business-online/education_students
PUT    /api/v1/business-online/education_students/{id}
DELETE /api/v1/business-online/education_students/{id}
POST   /api/v1/business-online/education_students/actions/transfer
```

Barcha yozuvlar chaqiruvchining tranzaksiyasida bajariladi — o'quvchi,
tarix va guruh birga qaytadi. Kabinet payloadi jadvallardan yig'ilgani
uchun frontend o'zgarmadi.

## Ma'lum farq

v1656da bu endpointlar `items` vakolatini talab qiladi. Yangi kabinet
esa aniqroq `education_groups` / `education_students` vakolatlarini
tekshiradi (`RESOURCE_PERMISSIONS`). Bu qat'iyroq va o'zgartirilmadi —
ammo v1656da `items` vakolatiga ega xodim guruh yarata olardi, endi
unga ta'lim vakolati kerak.

## Testlar

`tests/test_education_cabinet_v1656.py` — 10 ta test:

- guruh v1656 maydonlari bilan yaratilishi va noma'lum hafta kunlari
  tashlanishi;
- bo'sh nom va noma'lum kurs rad etilishi;
- `attendance` to'lov turida paket majburiyligi;
- guruh va o'quvchi o'chirilishi **yumshoq** bo'lishi;
- o'quvchi yaratilganda tarix ochilishi;
- ko'chirishda eski tarix yopilib, yangisi ochilishi;
- shu guruhga va mavjud bo'lmagan guruhga ko'chirish rad etilishi;
- tahrirlashda guruh o'zgarsa tarix yangilanishi.

## Release gate

- Alembic `0021_education_statistics → 0022_education_group_history`
  offline SQL;
- `base:head` xatosiz (59 jadval, bitta head);
- backend 482 test, frontend 338 test;
- TypeScript toza;
- `rollback` qo'riqchisi yashil.

## K10 tarkibiga kirmaydi

Dars jadvali, davomat kiritish, o'quvchi to'lovlari, o'qituvchilar va
maosh — ular uchun jadvallar K9 da yaratilgan, ammo boshqaruv
ekranlari alohida bosqichda ulanadi.

# Ta'lim K7 migratsiyasi — guruhlar, o'quvchilar va kurs arizalari

K7 v1656dagi kursga yozilish zanjirini relatsion PostgreSQL domeniga
ko'chiradi. `static/index.html` v1656 manbasi o'zgartirilmaydi.
Frontend fayllari ham o'zgarmaydi.

## Nima uchun kerak edi

Ariza shunday saqlanardi:

```python
profile = await session.get(BusinessProfile, account_id, with_for_update=True)
enrollments = await repository.resource_rows(...)   # hammasi o'qiladi
enrollments.append(row)
await repository.replace_resource(..., rows=enrollments)   # hammasi qayta yoziladi
sync_json_fallback(business, payload)                       # JSON nusxasi ham
```

- har ariza o'quv markazining profil qatorini qulflardi — qabul
  mavsumida arizalar bittalab navbatda kutardi;
- har yangi ariza avvalgi barcha arizalarni qayta yozardi;
- takroriylik butun ro'yxatni Pythonda skanerlab tekshirilardi.

## Ko'chirilgan funksiyalar

- kursga ariza berish — endi **bitta INSERT**, profil qulfi yo'q;
- takroriy arizani **baza** to'sadi (qisman noyob indeks), Pythonda
  ro'yxat skanerlanmaydi;
- rad etilgan arizadan keyin qayta yozilish mumkin — v1656dagidek;
- arizani qabul qilish: guruh tekshiriladi, o'quvchi yoziladi yoki
  guruhi yangilanadi, ariza holati o'zgaradi — **uchalasi bitta
  tranzaksiyada**;
- biznes kabineti ekrani o'zgarishsiz ishlaydi: payload endi
  jadvallardan yig'iladi;
- eski `education_groups`, `education_students`, `education_enrollments`
  yozuvlari `cabinet_records` va `cabinet_payload` dan idempotent
  ko'chiriladi.

## Jadvallar

| Jadval | Mazmuni |
|---|---|
| `education_groups` | guruhlar |
| `education_students` | o'quvchilar |
| `course_enrollments` | kurs arizalari |

Eski `id` qiymatlari har biznes ichida qaytadan boshlanadi, shuning
uchun ular global birlamchi kalit bo'la olmaydi. Ular
`legacy_source_id` da saqlanadi; guruhga havolalar backfill paytida
yangi kalitlarga bog'lanadi. `course_item_id` esa eski katalog
identifikatori bo'lib qoladi, chunki katalog hali kabinet payloadida.

## Xavfsizlik va yaxlitlik

| Holat | Himoya |
|---|---|
| Bir xil kursga ikki marta yozilish | `uq_course_enrollments_active_account` qisman noyob indeksi |
| Begona biznes arizasi so'raladi | Har so'rov `business_account_id` bilan scope qilinadi |
| Qabul qilishda guruh topilmaydi | Butun tranzaksiya `400` bilan qaytariladi, o'quvchi yaratilmaydi |
| Guruh boshqa kursga tegishli | `education_group_course_mismatch` |
| Ariza allaqachon ko'rib chiqilgan | Faqat `new` holatidagi ariza qabul/rad qilinadi, qator qulflanadi |
| Backfill qayta ishga tushadi | `legacy_source_id` upserti dublikatni oldini oladi |

## v1656 pariteti

- Ariza kartasi maydonlari va tartibi o'zgarmadi (`education_enrollment_rows`
  projeksiyasi avvalgidek ishlaydi);
- qabul qilinganda o'quvchi kartasidagi `Kurs arizasi: …` izohi saqlandi;
- kirgan har qanday akkaunt kursga yozila oladi — biznes akkaunt uchun
  ariza uning bog'langan oddiy profili nomidan yoziladi.

## Testlar

`tests/test_education_enrollment_v1656.py`:

- ariza **bitta INSERT** bilan yozilishi va `business_profiles` ga
  `UPDATE` bo'lmasligi (SQL sanog'i bilan);
- takroriy arizani baza to'sishi;
- biznes akkaunt bog'langan profil nomidan yozilishi;
- yopiq kursga ariza rad etilishi;
- qabul qilishda o'quvchi va holat birga yozilishi;
- guruh topilmasa hech narsa qolmasligi;
- rad etilgandan keyin qayta yozilish mumkinligi;
- payload maydon nomlari v1656 bilan bir xil qolishi.

## Release gate

- Alembic `0018_expense_domain → 0019_education_domain` offline SQL;
- `base:head` zanjiri xatosiz (54 jadval, bitta head);
- backend 457 test, frontend 327 test;
- TypeScript toza;
- `rollback` qo'riqchisi ro'yxatida `EducationEnrollmentService`.

## K7 tarkibiga kirmaydi

`education_schedule`, `education_attendance`, `education_payments`,
`education_teachers`, `education_payroll`, `education_statistics` — ular
hali `cabinet_payload` da. K7 faqat ariza → guruh → o'quvchi zanjirini
qamradi, chunki atomiklik aynan shu uch resursni talab qilardi.

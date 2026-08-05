# Ta'lim statistikasi K9 migratsiyasi

K9 v1656dagi maxsus Ta'lim statistikasi ekranini relatsion PostgreSQL
manbalariga ko'chiradi. `static/index.html` v1656 manbasi o'zgartirilmaydi.
K8dagi umumiy biznes Statistikasi Ta'lim kabinetida ko'rinmaydi; uning o'rniga
faqat ushbu maxsus ekran ochiladi.

## Ko'chirilgan funksiyalar

- kun, oy va yil davrlari;
- O'zbekiston vaqti (`UTC+5`) bo'yicha davr chegaralari;
- oldingi va keyingi davrga yurish;
- faol o'quvchi va faol guruhlar soni;
- davrdagi yangi kurs arizalari;
- umumiy va guruhlar kesimidagi davomat foizi;
- o'quvchilarga hisoblangan summa, qabul qilingan to'lov va qarzdorlik;
- o'qituvchilarga hisoblangan maosh, to'langan summa va qoldiq;
- boshqa xarajat, haqiqiy pul oqimi va hisoblangan natija;
- guruhlar kesimidagi hisob, to'lov va qarz;
- xodimning `education_statistics` vakolati va biznes scope'i.

## Relatsion manbalar

K7dagi `education_groups`, `education_students` va `course_enrollments`
jadvallari saqlanadi. K9 quyidagilarni qo'shadi:

| Jadval | Mazmuni |
|---|---|
| `education_attendance` | dars sanasi va o'quvchi davomat holati |
| `education_payments` | o'quvchi to'lovlari va bekor qilish izi |
| `education_teachers` | o'qituvchi, ishga kirgan sana va maosh usuli |
| `education_teacher_payments` | o'qituvchiga berilgan maosh to'lovlari |

`0021_education_statistics` migratsiyasi shu resurslarni avval
`cabinet_records`, keyin fallback sifatida `business_profiles.cabinet_payload`
dan idempotent ko'chiradi. Bir xil yozuv ikki manbada bo'lsa, normallashtirilgan
`cabinet_records` qatori ustun turadi. Eski identifikatorlar
`legacy_source_id` maydonlarida saqlanadi.

Guruh va o'quvchi jadvallariga v1656 hisoblari uchun kerak bo'lgan paket,
oylik to'lov, o'qituvchi, xona va sana maydonlari ham backfill qilinadi.
Kabinet proyeksiyasi ularni yana v1656 maydon nomlari bilan qaytaradi.

## Formulalar pariteti

| Ko'rsatkich | Manba va formula |
|---|---|
| Yangi yozilishlar | `course_enrollments.created_at` tanlangan davr ichida |
| Davomat | `(present + late) / barcha davomat yozuvlari × 100` |
| Oylik o'quvchi hisobi | `monthly_fee ×` tanlangan davrdagi, qo'shilgan oydan keyingi mos oylar soni |
| Davomat asosidagi hisob | har oy uchun `package_price / package_lessons × min(hisoblanadigan dars, package_lessons)` |
| Qabul qilingan to'lov | davr ichidagi, `voided_at IS NULL` o'quvchi to'lovlari |
| Oylik o'qituvchi maoshi | `salary_amount ×` ishga kirgan oydan keyingi mos oylar soni |
| Darsbay maosh | `salary_amount × DISTINCT(group_id, lesson_date)` |
| Boshqa xarajat | `expenses`, lekin `source = education_salary` emas |
| Haqiqiy pul oqimi | o'quvchi to'lovi − o'qituvchi to'lovi − boshqa xarajat |
| Hisoblangan natija | o'quvchi hisobi − o'qituvchi hisobi − boshqa xarajat |

Kun davrida oylik o'quvchi to'lovi va oylik o'qituvchi maoshi hisoblanmaydi;
faqat haqiqiy kunlik to'lovlar, xarajatlar va davomatga bog'liq hisoblar kiradi.

O'qituvchi maoshi to'langanda yaratilgan `education_salary` xarajati boshqa
xarajatdan chiqarib tashlanadi. Aks holda maosh `teacher_paid`da ham,
`other_expenses`da ham ayrilib, pul oqimi ikki marta kamayardi. v1656 ham shu
himoyani ishlatadi.

## Indeks va so'rov chegarasi

Davr bo'yicha issiq so'rovlar quyidagi indekslardan foydalanadi:

- `ix_education_attendance_business_date`;
- `ix_education_attendance_student_date`;
- `ix_education_payments_business_created`;
- `ix_education_payments_student_month`;
- `ix_education_teacher_payments_business_created`;
- `ix_education_teacher_payments_teacher_month`.

Faol o'quvchi/guruh, davomat, to'lov, o'qituvchi darslari va xarajatlar
biznes hamda davr bo'yicha bazada guruhlanadi. Hisoblash servisi JSON ro'yxatini
o'qimaydi va begona biznes qatorini xotiraga yuklamaydi.

## API va ekran pariteti

- `GET /api/v1/education/statistics?period=...&date=...` bitta typed hisobot
  qaytaradi;
- faqat v1656dagi `Kun`, `Oy`, `Yil` davrlari mavjud;
- v1656dagi besh blok va guruh kartalari aynan saqlanadi;
- davr almashtirilganda kechikkan eski javob yangi ekranni bosmaydi;
- umumiy `Statistika` Ta'lim kabinetidan yashiriladi;
- `Ta'lim statistikasi` boshqa biznes yo'nalishlarida ko'rinmaydi.

## Xavfsizlik va yaxlitlik

| Holat | Himoya |
|---|---|
| Xodimda vakolat yo'q | `staff_permission_required` |
| Oddiy foydalanuvchi endpointni chaqiradi | `business_account_required` |
| Biznes yo'nalishi Ta'lim emas | `education_direction_required` |
| Begona biznes qatori mavjud | Har query `business_account_id` bilan scope qilinadi |
| Eski ID noto'g'ri yoki boshqa biznesniki | xavfsiz `CASE` cast va tenant-scoped JOIN |
| Bekor qilingan o'quvchi to'lovi | `voided_at IS NULL` bo'lmasa hisobga kirmaydi |
| Backfill qayta ishlaydi | `(business_account_id, legacy_source_id)` upserti dublikatni to'sadi |

## K9 tarkibiga kirmaydi

- dars jadvali, davomat kiritish, to'lov olish, o'qituvchi CRUD va maosh
  to'lash ekranlarining to'liq React/typed-API migratsiyasi;
- imtihon va natijalar migratsiyasi;
- umumiy Hisobotlar, PDF/Excel eksport va yangi analitik ko'rsatkichlar;
- v1656da mavjud bo'lmagan grafik yoki prognoz.

## Release gate

- Alembic `0020_statistics_query_indexes → 0021_education_statistics`
  PostgreSQL SQL renderi;
- v1656 formulalari, kun/oy/yil, vakolat va bizneslararo himoya testlari;
- typed API, kabinet menyusi va kechikkan javob regressiya testlari;
- backend va frontend to'liq testlari;
- TypeScript, Python compile va production build;
- Phase 3A/3B/3C kontraktlari;
- `BUILD v1656`, 98 ekran va `static/index.html` qator soni saqlanishi.

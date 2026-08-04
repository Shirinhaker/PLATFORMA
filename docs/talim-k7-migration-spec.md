# K7 spetsifikatsiyasi — Ta'lim domenini relatsion bazaga ko'chirish

Bu hujjat bajarilishi kerak bo'lgan ishning texnik topshirig'i. K5 (qarz)
va K6 (xarajat) bilan bir xil shaklda. `static/index.html` v1656 manbasi
o'zgartirilmaydi.

---

## Nima uchun kerak

Hozir kursga yozilish arizasi shunday saqlanadi
(`app/education/service.py`):

```python
profile = await session.get(BusinessProfile, account_id, with_for_update=True)
enrollments = await repository.resource_rows(session, business, "education_enrollments")
enrollments.append(row)
await repository.replace_resource(..., rows=enrollments)      # hammasini qayta yozadi
payload["education_enrollments"] = deepcopy(enrollments)
sync_json_fallback(business, payload)                          # JSON nusxasi ham
```

Uchta muammo:

1. **Yozish navbati.** Har ariza o'quv markazining profil qatorini
   qulflaydi. Qabul mavsumida 200 kishi bir vaqtda ariza bersa, hammasi
   bittalab kutadi.
2. **O(N) yozuv.** Har yangi ariza avvalgi barcha arizalarni qayta
   yozadi. 500-ariza 499 tasini qayta yozadi.
3. **Ikki nusxa.** Ma'lumot `cabinet_records` da ham, `cabinet_payload`
   JSON'ida ham saqlanadi.

Bu — buyurtma bildirishnomalarida (#55) va qarz daftarida (#73)
allaqachon hal qilingan naqsh. Ta'lim — qolgan yagona modul.

---

## Nima uchun faqat arizalarni ko'chirib bo'lmaydi

Arizani qabul qilish amali (`business_online/service.py:1405`
`apply_education_enrollment_action`) **uchta resursni bitta
tranzaksiyada** o'zgartiradi:

| Resurs | Amal |
|---|---|
| `education_groups` | o'qiladi (guruh mavjudligi va kursga mosligi) |
| `education_students` | yoziladi (o'quvchi yaratiladi yoki guruhi yangilanadi) |
| `education_enrollments` | yoziladi (`status` → `accepted`, `group_id`) |

Faqat arizalarni relatsion jadvalga ko'chirsak, bu tranzaksiya ikki
omborga bo'linadi (relatsion ariza + JSON o'quvchi) va atomiklik
yo'qoladi — bu **hozirgidan yomonroq**.

Shuning uchun K7 qamrovi: **`education_groups`, `education_students`,
`education_enrollments` — uchalasi birga.**

---

## Bajarilishi kerak bo'lgan ish

### 1. Jadvallar (`app/education/model.py`)

Uchta jadval. Pul butun son (`BigInteger`), sana `Date`, matn
uzunliklari v1656 qiymatlariga mos.

**`education_groups`** — `id`, `business_account_id` (FK accounts,
CASCADE), `legacy_source_id`, `course_item_id`, `name`, `teacher_id`,
`status`, `created_at`, `updated_at`.

**`education_students`** — `id`, `business_account_id`, `legacy_source_id`,
`group_id` (FK education_groups, SET NULL), `user_account_id` (FK
accounts, SET NULL), `legacy_user_id`, `full_name`, `phone`,
`joined_date`, `note`, `monthly_fee` (BigInteger), `status`,
`created_at`, `updated_at`.

**`course_enrollments`** — `id`, `business_account_id`,
`legacy_source_id`, `course_item_id`, `user_account_id`,
`legacy_user_id`, `customer_name`, `phone`, `note`, `status`
(`new`/`accepted`/`rejected`), `group_id` (qabul qilinganda),
`created_at`, `updated_at`.

**Cheklovlar va indekslar:**

- `CheckConstraint("status IN ('new','accepted','rejected')")`;
- takroriy arizani **bazada** to'sish (hozir Pythonda ro'yxat
  skanerlanadi) — qisman noyob indeks:
  ```
  UNIQUE (business_account_id, course_item_id, user_account_id)
  WHERE user_account_id IS NOT NULL AND status IN ('new','accepted')
  ```
  Xuddi shu shart `legacy_user_id` uchun ham ikkinchi indeks bilan;
- `UNIQUE (business_account_id, legacy_source_id) WHERE legacy_source_id IS NOT NULL`
  — backfill idempotentligi uchun (har uch jadvalda);
- ro'yxat so'rovlari uchun `(business_account_id, status, created_at)`.

### 2. Migratsiya `0019_education_domain`

- uch jadval yaratiladi;
- `cabinet_records` dagi `education_groups`, `education_students`,
  `education_enrollments` resurslaridan **partiyali va idempotent**
  backfill (`legacy_source_id` upserti bo'yicha);
- backfill offline (`--sql`) rejimida o'tkazib yuboriladi — namuna:
  `0010_public_id_indexed_lookup.py` (`context.is_offline_mode()`);
- `downgrade()` uch jadvalni o'chiradi.

### 3. Repozitoriy (`app/education/repository.py`)

Namuna: `app/notifications/repository.py` — aynan shu shaklda.

- `supported(session)` — SQLite testlari uchun;
- `list_rows(session, business_account_id, resource)` → v1656 shaklidagi
  `dict` ro'yxati (maydon nomlari **aynan** hozirgi JSON qatorlaridek);
- `create_enrollment(...)` — **bitta INSERT**, profil qulfi yo'q;
- `update_enrollment_status(...)`, `upsert_student(...)`,
  `group_by_id(...)`.

### 4. Servis (`app/education/service.py`)

- `create()` da `locked_course_context` **profil qulfini olmasin** —
  kurs qatorini o'qish uchun qulf kerak emas;
- takroriy ariza `IntegrityError` bilan ushlanadi va
  `course_enrollment_duplicate` xatosiga aylantiriladi (hozirgi
  Pythondagi `_active_duplicate` skani olib tashlanadi);
- `sync_json_fallback` va `replace_resource` chaqiriqlari olib
  tashlanadi.

### 5. Kabinet o'qish va yozishni ulash

**O'qish** — `app/profiles/router.py:102 assembled_cabinet_payload`
ichida bildirishnomalar uchun mavjud qatlam kabi:

```python
rows = await _education.list_rows(session, account_id=..., resource=...)
if rows is not None:
    result["education_enrollments"] = rows
```

**Yozish** — `app/business_online/service_relational.py` da
`notifications` uchun qilingandek (87, 214, 223, 237-qatorlar) ushlab
qolinadi. `apply_education_enrollment_action` ning `accept` shoxi
relatsion jadvalga yozadigan yangi servis metodiga yo'naltiriladi va
**uch yozuv bitta tranzaksiyada** qoladi.

Frontend (`BusinessEducationEnrollmentsV1656View.tsx`) **o'zgarmaydi** —
u payload orqali o'qiydi, payload esa endi jadvaldan yig'iladi.

### 6. Testlar

- ariza yaratishda bitta INSERT bo'lishi (SQL sanog'i bilan);
- takroriy ariza bazada to'silishi;
- qabul qilish: guruh + o'quvchi + ariza **bitta tranzaksiyada**, xato
  bo'lsa uchalasi ham qaytarilishi;
- backfill idempotentligi (ikki marta ishga tushirilganda dublikat
  bo'lmasligi);
- `assembled_cabinet_payload` jadvaldan o'qishi;
- `rollback` qo'riqchisi (`tests/test_session_rollback_guard.py`)
  ro'yxatiga yangi servis qo'shilishi.

---

## Release gate

- Alembic `0018_expense_domain → 0019_education_domain` offline SQL;
- `base:head` zanjiri xatosiz;
- backend va frontend to'liq testlari;
- TypeScript va production build;
- `BUILD v1656`, 98 ekran va `static/index.html` qator soni saqlanishi;
- v1656 ekranlari o'zgarmasligi (frontend fayllari tegilmaydi).

---

## Qamrovdan tashqarida

`education_schedule`, `education_attendance`, `education_payments`,
`education_teachers`, `education_payroll`, `education_statistics` — ular
hali `cabinet_payload` da va o'z bosqichida ko'chiriladi. K7 faqat
ariza → guruh → o'quvchi zanjirini qamraydi, chunki atomiklik shu uch
resursni talab qiladi.

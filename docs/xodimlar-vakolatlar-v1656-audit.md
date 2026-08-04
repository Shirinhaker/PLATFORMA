# Xodimlar va vakolatlar — v1656 funksional paritet auditi

Bu hujjat K-seriya migratsiyalarida (buyurtma, navbat, kassa, qarz,
xarajat) yuritilgan audit shakliga amal qiladi. `static/index.html` v1656
manbasi o'zgartirilmaydi.

Audit sanasi: 2026-08-04
Tekshirilgan PR'lar: #68 (v1656 bo'limlarini ochish), #69 (xodimlar va
vakolatlar domeni), #70 (`MissingGreenlet` hotfix)

---

## 1. Vakolat kalitlari — 36/36 bir xil

Ikkala ro'yxat skript bilan solishtirildi
(`api.py:_STAFF_PERM_KEYS` ↔ `app/staff/permissions.py:ALL_PERMISSION_KEYS`):

```
v1656 vakolatlari : 36
yangi vakolatlar  : 36
yangida yo'q      : 0
qo'shimcha        : 0
```

Guruhlar bo'yicha: umumiy (14), umumiy ovqatlanish (12), ta'lim (10).

## 2. Tekshirish semantikasi — bir xil

| Qoida | v1656 | Yangi |
|---|---|---|
| Ega to'liq huquqli | `_staff_perms_of() is None → return` | `actor_type != "staff" → return` |
| Xodimga kamida bitta vakolat | `need_any_perm(*allowed)` | `require_staff_permission(current, *perms)` |
| Aniq bitta vakolat | `need_perm(perm)` | `require_staff_permission(current, perm)` |
| Faqat ega uchun bo'lim | `deny_staff(section)` | `require_business_owner(current)` |
| Tannarx ko'rinishi | `_can_view_costs()` | `InventoryService._can_view_costs()` |

Tannarx qoidasi ikkalasida ham bir xil: **ega**, yoki `expenses`, yoki
`statistics` vakolatiga ega xodim ko'radi.

## 3. Endpoint pariteti

| # | v1656 | Yangi | Holat |
|---|---|---|---|
| 1 | `POST /staff-auth` | `POST /api/v1/staff-auth/login` | migrated |
| 2 | `GET /staff-auth/me` | umumiy sessiya cookie'si + `resolve_session` | migrated (mexanizm o'zgardi) |
| 3 | `POST /staff-auth/logout` | `StaffService.revoke_session()` | migrated |
| 4 | `GET /staff/professions` | `GET /api/v1/staff` javobida `professions` | migrated (birlashtirildi) |
| 5 | `POST /staff/professions` | `POST /api/v1/staff/professions` | migrated |
| 6 | `GET /staff` | `GET /api/v1/staff` | migrated |
| 7 | `POST /staff` | `POST /api/v1/staff` | migrated |
| 8 | `PUT /staff/{id}` | `PUT /api/v1/staff/{id}` | migrated |
| 9 | `POST /staff/{id}/fire` | `POST /api/v1/staff/{id}/fire` | migrated |
| 10 | `POST /staff/{id}/rehire` | `POST /api/v1/staff/{id}/rehire` | migrated |
| 11 | `DELETE /staff/{id}` | `DELETE /api/v1/staff/{id}` | migrated |
| 12 | `PUT /staff/{id}/schedule` | `PUT /api/v1/staff/{id}/schedule` | migrated |
| 13 | `PUT /staff/{id}/access` | `PUT /api/v1/staff/{id}/access` | migrated |
| 14 | `GET /tabel` | `GET /api/v1/staff/attendance` | migrated |
| 15 | `POST /tabel` | `PUT /api/v1/staff/{id}/attendance` | migrated |

`Xodimlar pariteti: 15/15 migrated, partial: 0, missing: 0.`

## 4. Qo'shimcha xatti-harakatlar

Ishdan bo'shatish yoki o'chirishda yangi kod ikkita qo'shimcha amalni
ayni tranzaksiyada bajaradi:

- xodimning barcha faol sessiyalari bekor qilinadi
  (`revoke_staff_sessions`);
- xodim biriktirilgan navbat provayderlari o'chiriladi
  (`deactivate_queue_providers`).

v1656da sessiyalar alohida jadvalda bo'lmagani uchun bunday tozalash
mavjud emas edi. Bu funksional yo'qotish emas — ishdan bo'shagan xodim
tizimda qololmasligi uchun qo'shilgan.

---

## 5. Ataylab kiritilgan farqlar

| v1656 | Yangi | Sabab |
|---|---|---|
| `staff.pass_plain` — parol ochiq matnda saqlanadi va ega ekranida ko'rsatiladi (`showCredentials(r.login, r.password)`) | Faqat `password_hash` saqlanadi; ekranda «Parol o'rnatilgan» yoziladi | Ochiq parol saqlash jiddiy xavfsizlik nuqsoni. Ega endi unutilgan parolni **ko'ra olmaydi**, faqat yangisini qo'yadi |
| Kasblar alohida endpointdan olinadi | `GET /api/v1/staff` javobiga kiritilgan | Ekran ochilishida bitta so'rov kamayadi; ma'lumot bir xil |
| `GET /staff-auth/me` alohida token bilan | Umumiy sessiya cookie'si orqali | Xodim va ega sessiyalari bitta mexanizmda; CSRF himoyasi umumiy |

Birinchi qatorni foydalanuvchiga tushuntirish kerak: **ega xodimning
parolini endi ko'ra olmaydi**. Amaliy yo'l — yangi parol qo'yib, uni
xodimga aytish.

---

## 6. Qamrovdan tashqarida

- Xodim maoshi va ish haqi hisob-kitobi (`education_payroll` ta'lim
  domenida alohida ko'chiriladi);
- xodim statistikasi va hisobotlari;
- xodimlarning yo'nalishga xos maxsus ekranlari (restoran smenalari,
  ta'lim o'qituvchi kartasi) — o'z domenlarida.

---

## 7. Tekshirilgan release gate

- Vakolat kalitlari skripti: 36/36;
- backend to'liq testlari;
- `rollback` naqshi bo'yicha qo'riqchi test (`StaffService` toza);
- Alembic `0013_queue_provider_backfill → 0014_staff_domain` PostgreSQL SQL;
- `BUILD v1656`, 98 ekran va `static/index.html` qator soni saqlanishi.

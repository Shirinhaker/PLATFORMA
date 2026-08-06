# A2 va A3 — moderatsiya, shikoyatlar va audit tarixi

**Sana:** 2026-08-06
**Bosqich:** A1, A2, A3 bajarildi. Admin sayti to'liq.

## Nima qo'shildi

A1 da admin sessiyasi va to'lov navbati bor edi. Bu bosqich v1656 admin
saytining qolgan qismini beradi.

| Bo'lim | v1656 manbai |
|---|---|
| Profil va biznes qidiruvi, cheklash, ichki izoh | `admin_api.py`, `moderation.py` |
| Kontentni yashirish / tiklash / o'chirish | `moderation.py` |
| Shikoyatlar navbati | `moderation.py` |
| O'zgartirib bo'lmaydigan audit tarixi + CSV | `admin_audit.py` |

## Jadvallar

Migratsiya: `backend/migrations/versions/0027_admin_moderation.py`

| Jadval | Vazifasi |
|---|---|
| `account_restrictions` | akkaunt cheklovlari va ularning tarixi |
| `admin_account_notes` | adminning ichki izohlari (egasiga ko'rinmaydi) |
| `content_moderation` | kontent ko'rinishi tarixi |
| `moderation_reports` | shikoyatlar navbati |
| `admin_audit_log` | barcha admin amallari |

## Qoidalar

### Ikki cheklov mustaqil

`content_hidden` egasining kabinetidagi ma'lumotni **o'chirmaydi** —
faqat public qidiruv, xarita va takliflardan yashiradi. `account_blocked`
esa yozish amallarini to'xtatadi. Biri ikkinchisini yoqmaydi.

Bir akkauntda bir turdagi faol cheklov bittadan ortiq bo'lmaydi: buni
qisman unikal indeks ta'minlaydi. Servis ham takroriy so'rovni idempotent
qaytaradi, lekin himoya baza darajasida ham bor.

### Sabab hamma joyda majburiy

Cheklash, cheklovni olib tashlash, kontentni yashirish yoki o'chirish va
shikoyat qarori — barchasi sababsiz bajarilmaydi. Faqat kontentni
tiklash (`visible`) sababsiz mumkin.

### Shikoyat qarori atomar

Shikoyat qatori qulflanadi va holat o'tishi tekshiriladi, shuning uchun
ikki admin bir shikoyatni ikki marta hal qila olmaydi — ikkinchisi 409
oladi.

Bir foydalanuvchi bitta kontentga takror shikoyat yozsa, navbatga
ikkinchi qator qo'shilmaydi.

### Audit jurnali o'zgarmaydi

Har bir admin amali (cheklash, izoh, kontent, shikoyat qarori, to'lov)
jurnalga tushadi: kim, nima qildi, oldingi va yangi holat, sabab.

`UPDATE` va `DELETE` **baza darajasida** to'silgan — `plpgsql`
funksiyasi istisno ko'taradi. v1656 da bu SQLite triggerlari bilan
qilingan edi. Ilova kodiga ishonilmaydi.

**Xom IP hech qachon saqlanmaydi** — faqat server siri bilan HMAC xeshi.
Jurnal joylashuvni oshkor qilmaydi, lekin bir manzildan kelgan amallarni
solishtirish mumkin.

CSV eksportda IP xeshi va brauzer satri **bo'lmaydi** — ular faqat bitta
yozuv batafsil ochilganda ko'rinadi.

## Endpointlar

Admin: `/api/v1/admin` — jami 29 ta (A1 dagi 14 + bu bosqichdagi 15).

| Endpoint | Vazifasi |
|---|---|
| `GET /accounts/{actor_type}` | qidiruv (matn va cheklov bo'yicha) |
| `GET /accounts/{actor_type}/{id}` | tafsilot, cheklov tarixi, izohlar |
| `POST /accounts/{actor_type}/{id}/restrict` | cheklash |
| `POST /accounts/{actor_type}/{id}/unrestrict` | cheklovni olib tashlash |
| `POST /accounts/{actor_type}/{id}/notes` | ichki izoh |
| `GET /content/{kind}/{id}` | joriy holat va tarix |
| `POST /content/{kind}/{id}/{hide\|restore\|remove}` | ko'rinishni o'zgartirish |
| `GET /reports` | shikoyat navbati |
| `GET /reports/{id}` | tafsilot |
| `POST /reports/{id}/assign` | o'ziga biriktirish |
| `POST /reports/{id}/resolve` | hal qilish |
| `POST /reports/{id}/dismiss` | rad etish |
| `GET /audit` | jurnal (amal bo'yicha filtr) |
| `GET /audit/{id}` | oldingi va yangi holat bilan |
| `GET /audit/export.csv` | CSV eksport |

Foydalanuvchi uchun bitta endpoint qo'shildi: `POST /api/v1/reports` —
shikoyatni admin emas, mijoz yuboradi, shuning uchun u oddiy sessiya
bilan ishlaydi.

## Admin paneli

Beshta bo'lim: **To'lovlar**, **Narxlar va usullar**, **Profil va
bizneslar**, **Shikoyatlar**, **Audit tarixi**.

v1656 da yana "Boshqaruv paneli" (umumiy ko'rsatkichlar) bo'limi bor.
U qo'shilmadi: ko'rsatkichlar boshqa domenlardan yig'iladi va alohida
ish talab qiladi. Ishlamaydigan menyu tugmasi qoldirilmaydi.

Shikoyat ekranida qaror bilan birga kontentni darhol yashirish tugmasi
bor — v1656 da bu ikki alohida ekranda edi.

## Testlar

### Backend — 23 ta yangi (butun to'plam 599)

`tests/test_admin_moderation.py`: qidiruv, cheklov va idempotentlik,
sabab majburiyligi, ikki cheklovning mustaqilligi, izohlar, kontent
tarixi, shikoyat oqimi, ikkinchi qarorning rad etilishi, audit filtri
va CSV eksporti.

### Frontend — 15 ta yangi (butun to'plam 404)

`src/admin/AdminModeration.test.tsx`: qidiruv filtrlari, sababsiz
cheklovning to'silishi, faol cheklovni olib tashlash, bo'sh izoh,
shikoyat biriktirish va qaror, kontentni yashirish, audit batafsili
va CSV havolasi.

### Buzib tekshirildi

| Buzilgan joy | Qizargan testlar |
|---|---|
| Takroriy cheklov tekshiruvi | 1 (baza indeksi ham ushladi) |
| Ikkinchi qarorni to'sish | 1 |
| Frontendda sabab tekshiruvi (cheklov) | 1 |
| Frontendda sabab tekshiruvi (kontent) | 1 |

## Sozlama

Ixtiyoriy: `KOPRIK_ADMIN_AUDIT_IP_SECRET` — audit jurnalidagi IP xeshi
uchun. Berilmasa `KOPRIK_CSRF_SECRET` ishlatiladi.

Majburiy sozlama A1 dagi kabi bitta: `KOPRIK_ADMIN_TELEGRAM_IDS`.

## Qolgan ishlar

Admin sayti tugadi. Umuman ko'chirilmagan bo'limlar:
hujjatlar, kontragentlar, taxi va haydovchi kabineti, mutaxassis xizmat
takliflari, ish haqi.

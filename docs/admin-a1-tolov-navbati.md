# A1 — Admin sessiyasi va to'lov navbati

**Sana:** 2026-08-06
**Bosqich:** A1 bajarildi. A2 (moderatsiya), A3 (shikoyat va audit) keyingi PR'larda.

## Nima uchun

Yangi backendda **admin tushunchasi umuman yo'q edi**. Shu sababli obuna
to'lovini tasdiqlash endpointi biznes routerida turgan va faqat shu bilan
himoyalangan edi:

```python
@router.post("/{payment_id}/approve")
    require_business_owner(current)   # faqat "biznes egasimi?" deb tekshiradi
```

`review()` esa to'lovni egasiga bog'lamasdi:

```python
select(PaymentRequest).where(PaymentRequest.id == payment_id)
```

Ikkalasi birgalikda: **har qanday biznes egasi o'zining to'lovini o'zi
tasdiqlab, bepul Pro obuna olishi mumkin edi.**

Ikkinchi muammo: tasdiqlash uchun ekran yo'q edi. Foydalanuvchi to'lov
yuborardi, ariza «Tekshiruvda» holatida qolib ketardi.

## Yechim

### Alohida admin sessiyasi

v1656 (`admin_auth.py`) bilan bir xil oqim:

```
Telegram ID (ro'yxatda bo'lishi shart)
  → bir martalik kod botga yuboriladi
  → kod tekshiriladi
  → alohida HttpOnly `koprik_admin_session` cookie
```

Admin sessiyasi oddiy foydalanuvchi sessiyasidan **butunlay ajratilgan**.
Bu ataylab: o'g'irlangan foydalanuvchi cookie'si admin bo'limlarini
ochmaydi. v1656 hujjatida bu "saqlangan himoya" sifatida sanalgan.

| Qoida | Qiymat |
|---|---|
| Ro'yxat | `KOPRIK_ADMIN_TELEGRAM_IDS` (vergul bilan) |
| Kod muddati | 5 daqiqa |
| Urinishlar | 5 ta, keyin bloklanadi |
| Sessiya muddati | 8 soat |
| Bo'sh turish | 30 daqiqa |

**v1656 dan farq:** ro'yxatning standart qiymati **bo'sh**. v1656 da
`PRIVILEGED_TG_IDS` ga ikkita ID kodda yozib qo'yilgan edi — sozlama
unutilsa, o'sha ikki kishi avtomatik admin bo'lardi. Endi ro'yxat
sozlanmaguncha hech kim admin emas.

Ro'yxatdan chiqarilgan adminning ochiq sessiyasi keyingi so'rovdayoq
bekor qilinadi.

### Kod hech qayerda saqlanmaydi

Kod na bazada, na outbox navbatida ochiq turadi: u challenge id sidan
server siri bilan qayta hisoblanadi (`derive_otp`) — auth domeni bilan
bir xil yondashuv. Bazada faqat uning xeshi bor. Sessiya tokeni ham
xesh ko'rinishida saqlanadi (SHA-256), ya'ni baza sizib chiqsa ham
cookie tiklanmaydi.

### Jadvallar

Migratsiya: `backend/migrations/versions/0026_admin_domain.py`

| Jadval | Vazifasi |
|---|---|
| `admin_auth_challenges` | bir martalik kodlar |
| `admin_sessions` | faol admin sessiyalari |

`payment_requests` ga `reviewed_by_admin_tg_id` ustuni qo'shildi —
`reviewed_by_account_id` faqat akkauntlar uchun, adminda akkaunt yo'q.

## Endpointlar

Prefiks: `/api/v1/admin`. Har biri o'z sessiyasini tekshiradi.

| Endpoint | Vazifasi |
|---|---|
| `POST /auth/start` | ro'yxatdagi ID ga kod yuborish |
| `POST /auth/verify` | kodni tekshirish, cookie berish |
| `GET /auth/me` | joriy admin |
| `POST /auth/logout` | sessiyani yopish |
| `GET /payments` | navbat (holat va xizmat bo'yicha filtr) |
| `GET /payments/{id}` | tafsilot va urinishlar tarixi |
| `GET /payments/{id}/receipt` | kvitansiyaga 5 daqiqalik havola |
| `POST /payments/{id}/approve` | tasdiqlash (obuna yoqiladi) |
| `POST /payments/{id}/reject` | rad etish (sabab shart) |
| `POST /payments/{id}/cancel` | bekor qilish (sabab shart) |
| `GET /prices`, `PUT /prices/{id}` | tariflar |
| `GET/POST/PUT /payment-methods` | to'lov rekvizitlari |

**Olib tashlandi:** `POST /api/v1/payments/{id}/approve` va `/reject`.

Chek fayli yo'li javobda umuman chiqmaydi — faqat qisqa muddatli
imzolangan havola beriladi. v1656 da fayl to'g'ridan-to'g'ri uzatilardi.

Qaror mantiqi `PaymentService.review` da qoldi — obunani yoqish kodi
ikki nusxada saqlanmaydi.

## Admin paneli

Alohida sayt: `frontend/admin.html` → `src/admin/`. Vite ikkinchi kirish
nuqtasi sifatida quradi, ya'ni admin JS foydalanuvchi ilovasi bilan
bitta to'plamda emas (15 kB alohida chunk).

Bo'limlar: **To'lovlar** va **Narxlar va usullar**.

v1656 panelida yana beshta bo'lim bor (boshqaruv paneli, profillar,
kontent, shikoyatlar, audit). Ular A2 va A3 da qo'shiladi — ishlamaydigan
menyu tugmasi qoldirilmaydi (`CLAUDE.md`).

Kvitansiya faqat "Kvitansiyani ko'rish" bosilganda yuklanadi: navbatni
varaqlagan admin har bir chekni beixtiyor ochib yubormaydi.

## Testlar

### Backend — 17 ta yangi (butun to'plam 573)

`tests/test_admin_auth.py` (12): ro'yxat, kod muddati va urinishlar,
bir martalik ishlatish, sessiya muddati va bo'sh turish, ro'yxatdan
chiqarish, chiqish.

`tests/test_admin_payment_authorization.py` (5): eski endpoint yo'qligi,
biznes cookie'si admin bo'limlarini ochmasligi, cookie ajratilganligi,
haqiqiy admin sessiyasi bilan navbat ochilishi.

### Frontend — 10 ta yangi (butun to'plam 389)

`src/admin/AdminPayments.test.tsx`: navbat, filtrlar, tafsilot,
kvitansiya, uchala qaror, sababsiz rad etish taqiqi.

### Buzib tekshirildi

| Buzilgan joy | Qizargan testlar |
|---|---|
| Eski `approve` endpointi qaytarildi | 1 |
| Admin cookie oddiy cookie bilan almashtirildi | 1 |
| Sababsiz rad etishga ruxsat berildi | 2 |
| Kvitansiya avtomatik yuklandi | 1 |

## Ishga tushirish

Railway'da bitta o'zgaruvchi qo'shiladi:

```dotenv
KOPRIK_ADMIN_TELEGRAM_IDS=1423181561,607563067
```

Bu berilmaguncha admin paneliga hech kim kira olmaydi — to'lovlar
«Tekshiruvda» holatida turaveradi.

## Keyingi bosqichlar

- **A2** — moderatsiya: profil va biznes qidiruvi, cheklash, ichki izoh,
  kontentni yashirish/tiklash.
- **A3** — shikoyatlar navbati va o'zgartirib bo'lmaydigan audit tarixi
  (CSV eksport bilan).

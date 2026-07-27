# Phase 2 warm authenticated load gate dizayni

Sana: 2026-07-28  
Holat: foydalanuvchi tomonidan tasdiqlangan dizayn

## 1. Maqsad

Phase 2 autentifikatsiya va profil oqimini staging muhitida takrorlanadigan, xavfsiz va real foydalanuvchi trafikiga yaqin yuklama sinovi bilan yopish.

Asosiy gate:

- `100`, `500` va `1000` parallel autentifikatsiyalangan `GET /api/v1/me` so‘rovi;
- har bir bosqichda transport va HTTP xatolari soni `0`;
- har bir bosqichda warm trafik uchun `p95 < 500 ms`;
- barcha javoblar kutilgan `HTTP 200` holatida bo‘lishi.

Yangi HTTPS ulanishining DNS/TCP/TLS xarajati alohida diagnostika sifatida o‘lchanadi, ammo warm application gate natijasiga qo‘shilmaydi.

## 2. Hozirgi holat va muammo

Amaldagi `scripts/phase2_load.js` k6 uchun yozilgan va `100 → 500 → 1000` yuklama bosqichlarini tekshiradi. Windows staging tekshiruvlarida esa vaqtinchalik PowerShell skriptlari ishlatilgan.

O‘lchovlar quyidagini ko‘rsatdi:

- autentifikatsiya, profil va Telegram tasdiqlash oqimlari ishlaydi;
- API, frontend va worker Railway’da sog‘lom;
- `1000` parallel so‘rovda HTTP xatolari bo‘lmagan holatlar mavjud;
- yangi HTTPS ulanishlari qayta-qayta ochilganda handshake va tarmoq xarajati latency natijasini sun’iy oshiradi;
- bir xil ulanish havzasi qayta ishlatilgan warm so‘rovlar sezilarli tezroq;
- Railway metrikalarida API CPU, xotira va Postgres resurslarining to‘lib qolishi kuzatilmagan.

Shuning uchun Phase 2 gate real brauzerga yaqin warm, qayta ishlatiladigan HTTPS ulanishlari bilan o‘lchanadi. Cold connection natijasi yashirilmaydi, lekin alohida ko‘rsatiladi.

## 3. Tanlangan yondashuv

Repository ichiga rasmiy Windows PowerShell staging yuklama skripti qo‘shiladi. U foydalanuvchini Telegram OTP orqali tizimga kiritadi, sessiyani faqat xotirada saqlaydi va bir xil `HttpClient` hamda connection pool orqali bosqichma-bosqich warm yuklama beradi.

k6 skripti CI yoki Linux/macOS muhiti uchun saqlanadi. Windows operatori uchun PowerShell skripti asosiy qo‘lda ishga tushiriladigan staging gate bo‘ladi.

Bu yondashuv tanlanishining sabablari:

- foydalanuvchi Windows PowerShell muhitida ishlayapti;
- qo‘shimcha k6 o‘rnatishni talab qilmaydi;
- autentifikatsiya va Telegram OTP oqimini bir buyruqda bajaradi;
- real HTTP ulanishini qayta ishlatishni nazorat qilish imkonini beradi;
- maxfiy qiymatlarni faylga yozmasdan sinov o‘tkazadi.

## 4. Qamrov

O‘zgartiriladigan qismlar:

1. `scripts/phase2_load.ps1` — rasmiy Windows warm-load gate;
2. `tests/test_phase2_operational_contract.py` — skript shartlari va xavfsizlik kontrakti;
3. `docs/deploy-auth-profile-staging.md` — Windows ishga tushirish yo‘riqnomasi, cold/warm izohi va Phase 2 yakunlash mezoni;
4. zarur bo‘lsa mavjud `scripts/phase2_load.js` hujjat izohlari — k6’ning CI/advanced roli aniq ko‘rsatiladi.

Qamrovga kirmaydi:

- API endpointlarining biznes logikasini o‘zgartirish;
- frontend sahifalarini o‘zgartirish;
- Postgres sxemasi yoki migratsiyasini o‘zgartirish;
- Redis topologiyasini o‘zgartirish;
- Railway resurslarini ko‘r-ko‘rona kattalashtirish;
- production `web` yoki `koprik.uz` xizmatiga o‘zgartirish kiritish.

## 5. Autentifikatsiya oqimi

Skript quyidagi ketma-ketlikda ishlaydi:

1. API base URL parametr yoki xavfsiz standart qiymatdan olinadi.
2. Staging login operator tomonidan kiritiladi.
3. Parol clipboard orqali olinadi; format va bo‘sh qiymat tekshiriladi.
4. Clipboard darhol tozalanadi.
5. Login so‘rovi yuboriladi va Telegram OTP jarayoni boshlanadi.
6. Operator Telegram’dan kelgan 6 xonali kodni kiritadi.
7. Sessiya cookie qiymati faqat jarayon xotirasida saqlanadi.
8. `GET /api/v1/me` orqali sessiya va hisob turi tekshiriladi.
9. Yuklama bosqichlari tugagach, CSRF talabiga mos logout yuboriladi.
10. `finally` blokida parol, OTP, cookie va sessiya o‘zgaruvchilari tozalanadi, HTTP obyektlari dispose qilinadi.

Login, parol, Telegram kodi, session cookie yoki CSRF qiymati logga va JSON natija fayliga yozilmaydi.

## 6. O‘lchov modeli

### 6.1 Cold connection diagnostikasi

Boshlanishida yangi HTTPS ulanishi bilan bitta yoki kichik nazorat o‘lchovi bajariladi. Natija cold DNS/TCP/TLS/application latency sifatida alohida qayd etiladi.

Bu qiymat informatsion bo‘ladi va Phase 2 gate’ni yiqitmaydi.

### 6.2 Warm-up

Har bir concurrency bosqichidan oldin o‘sha bosqichda ishlatiladigan bir xil `HttpClient`, cookie container va connection pool bilan warm-up bajariladi.

Warm-up talablari:

- measured passdan oldin tugashi;
- warm-up so‘rovlari gate statistikalariga kiritilmasligi;
- ulanish qayta ishlatilayotganini buzadigan yangi client-per-request naqshidan foydalanilmasligi;
- warm-up xatosi bo‘lsa measured bosqich boshlanmasligi.

### 6.3 Measured bosqichlar

Bosqichlar qat’iy tartibda bajariladi:

1. `100` parallel so‘rov;
2. `500` parallel so‘rov;
3. `1000` parallel so‘rov.

Har bir bosqich:

- aynan o‘sha concurrency miqdorida `GET /api/v1/me` yuboradi;
- bir xil autentifikatsiyalangan sessiyadan foydalanadi;
- bir xil qayta ishlatiladigan HTTP connection pooldan foydalanadi;
- har bir so‘rovning millisekund davomiyligini va statusini yig‘adi;
- `p50`, `p95`, `p99`, jami davomiylik, status count va error countni hisoblaydi.

Bosqichlar orasida natijalarni aralashtirmaslik uchun statistik kollektor yangilanadi, lekin HTTP connection pool saqlanadi.

## 7. Gate qoidalari

Har bir `100`, `500`, `1000` bosqichi uchun:

- `errors == 0`;
- barcha kutilgan javoblar `HTTP 200`;
- `p95_ms < 500`.

Umumiy `passed` faqat uchala bosqich ham o‘tganda `true` bo‘ladi. Bitta bosqich yiqilsa skript non-zero exit code bilan tugaydi.

Cold connection diagnostikasi, birinchi TLS handshake yoki operatorning OTP kiritish vaqti warm p95 hisobiga kirmaydi.

## 8. Natija formati

Skript ekranga qisqa bosqich natijalarini chiqaradi va xavfsiz JSON hisobot yaratadi.

Hisobot tarkibi:

- `generated_at`;
- `api_base_url`;
- `account_type`;
- `connection_model` (`reused_https_connections`);
- max connection sozlamasi;
- cold diagnostika latency qiymati;
- har bir bosqich uchun concurrency, request count, error count, p50/p95/p99, duration va status counts;
- yakuniy gate booleans va `passed`.

Hisobot tarkibida quyidagilar bo‘lmaydi:

- login;
- parol;
- Telegram OTP;
- session yoki cookie;
- CSRF secret/token;
- Telegram bot token yoki webhook secret.

## 9. Xatolarni boshqarish

Skript quyidagi holatlarda aniq va xavfsiz xabar bilan to‘xtaydi:

- API URL yaroqsiz;
- login yoki parol bo‘sh;
- parol minimal kontraktga mos emas;
- Telegram kodi 6 xonali emas;
- login/OTP tekshiruvi muvaffaqiyatsiz;
- `/api/v1/me` sessiyani tasdiqlamaydi;
- warm-upda HTTP/transport xatosi bor;
- measured bosqichda non-200 yoki transport xatosi bor;
- p95 gate bajarilmaydi.

Agar o‘lchov boshlanganidan keyin xato yuz bersa, mavjud xavfsiz metrikalar imkon qadar hisobotga yoziladi. Maxfiy qiymatlar hech qachon exception matniga qo‘shilmaydi.

## 10. Test strategiyasi

Operational contract testlari quyidagilarni tekshiradi:

- PowerShell skripti repositoryda mavjud;
- `100`, `500`, `1000` bosqichlari mavjud;
- `GET /api/v1/me` ishlatiladi;
- warm-up measured statistikadan ajratilgan;
- bir martalik client-per-request emas, qayta ishlatiladigan HTTP client/connection pool mavjud;
- strict `errors == 0` va `p95 < 500` gate mavjud;
- non-zero exit code bilan failure signal beriladi;
- logout/finally cleanup mavjud;
- JSON hisobotda maxfiy qiymatlar chiqarilmasligi aniq kontrakt bilan himoyalangan;
- mavjud Phase 1 va Phase 2 testlari regressiyasiz o‘tadi.

Qo‘lda staging tasdig‘i:

1. API, worker va frontend healthy;
2. test user Telegram OTP bilan login qiladi;
3. `/api/v1/me` `200` qaytaradi;
4. `100`, `500`, `1000` warm bosqichlarida `0` xato;
5. uchala bosqichda `p95 < 500 ms`;
6. logout ishlaydi;
7. hisobotda secret yo‘q.

## 11. Rollback

Bu o‘zgarish production biznes logikasiga tegmaydi. Rollback quyidagicha:

- PowerShell skripti va tegishli docs/test commitlarini revert qilish;
- amaldagi k6 skriptini CI varianti sifatida ishlatishda davom etish;
- Railway API/frontend/worker deploymentlarini o‘zgartirmaslik.

## 12. Phase 2 yakunlash mezoni

Phase 2 quyidagilarning barchasi bajarilganda yopiladi:

- autentifikatsiya, Telegram OTP, user va business profil oqimlari stagingda ishlaydi;
- avatar/logo saqlash tekshirilgan;
- API, frontend va worker healthy;
- GitHub CI tekshiruvlari yashil;
- database backup olingan;
- rasmiy PowerShell warm-load gate uchala bosqichdan `0` xato va `p95 < 500 ms` bilan o‘tgan;
- natija JSON arxivlangan va maxfiy qiymat saqlamagan;
- staging runbook yakuniy natija bilan yangilangan.

Ushbu mezonlardan keyin Phase 2 tugagan deb belgilanadi va keyingi phase ishlariga o‘tiladi.

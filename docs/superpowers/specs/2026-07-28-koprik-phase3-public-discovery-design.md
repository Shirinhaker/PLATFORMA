# Koprik Phase 3 — Public Discovery dizayni

Sana: 2026-07-28  
Holat: tasdiqlangan dizayn  
Branch: `codex/phase3-public-discovery`

## 1. Maqsad

Yangi React frontenddagi katalog va qidiruvni mavjud PostgreSQL ma'lumotlaridagi haqiqiy oddiy foydalanuvchi va biznes profillariga ulash.

Bu bo'lak strangler migratsiyaning xavfsiz davomi bo'ladi:

- ishlayotgan `koprik.uz` o'zgarmaydi;
- legacy `static/index.html` va BUILD v1656 o'zgarmaydi;
- frontend eski SQLite `/api/search` endpointiga bog'lanmaydi;
- mahsulot, xizmat va e'lon modellari Phase 3C ga qoldiriladi.

## 2. Tanlangan yondashuv

Yangi FastAPI backendda faqat o'qish uchun public discovery API yaratiladi. API mavjud Phase 2 PostgreSQL profillaridan xavfsiz, ommaga ko'rsatish mumkin bo'lgan qisqa kartalarni qaytaradi.

React frontend:

1. katalog yoki faoliyat turidan parametr oladi;
2. yangi public API ga so'rov yuboradi;
3. haqiqiy natija kartalarini chiqaradi;
4. yuklanish, bo'sh natija va server xatosini alohida ko'rsatadi;
5. API ishlamasa mavjud public navigatsiya ishlashda davom etadi.

## 3. API shartnomasi

### Endpoint

`GET /api/v1/public/search`

### So'rov parametrlari

- `q`: ixtiyoriy qidiruv matni, trim qilinadi, ko'pi bilan 120 belgi;
- `result_type`: `all | business | user`, standart `all`;
- `direction`: biznes yo'nalishi bo'yicha ixtiyoriy filter;
- `activity_type`: biznes faoliyat turi bo'yicha ixtiyoriy filter;
- `region`, `district`, `mahalla`: mavjud bo'lgan joylashuv maydonlari bo'yicha ixtiyoriy filter;
- `page`: 1 dan boshlanadi;
- `page_size`: standart 20, maksimum 50.

### Javob

```json
{
  "items": [
    {
      "kind": "business",
      "public_id": "business:123",
      "name": "Sinov biznes",
      "public_username": "sinov_biznes",
      "description": "Qisqa tavsif",
      "direction": "Savdo",
      "activity_type": "Oziq-ovqat",
      "region": "",
      "district": "",
      "mahalla": "",
      "image_url": null
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1,
  "has_next": false,
  "supported_result_types": ["all", "business", "user"]
}
```

User kartasida biznesga tegishli maydonlar `null` yoki yo'q bo'ladi. Frontend `kind` bo'yicha kartani render qiladi.

## 4. Maxfiylik chegarasi

Public API quyidagilarni hech qachon qaytarmaydi:

- telefon;
- login yoki password hash;
- Telegram user ID;
- to'lov kartasi va karta egasi;
- STIR;
- rahbar/direktor ma'lumoti;
- aniq latitude/longitude;
- ichki R2 object key;
- session yoki auth ma'lumoti.

Rasm bo'lsa, faqat backend yaratgan vaqtinchalik yoki public-safe URL qaytariladi. URL xavfsiz tayyor bo'lmasa, `image_url: null` beriladi; object key frontendga chiqarilmaydi.

## 5. Qidiruv xulqi

- Bizneslar: nom, public username, tavsif, yo'nalish va faoliyat turi bo'yicha izlanadi.
- Foydalanuvchilar: ism va public username bo'yicha izlanadi.
- Qidiruv katta-kichik harfga bog'liq bo'lmaydi.
- Faqat `status = active` akkauntlar natijaga kiradi.
- Public username bo'sh bo'lgan profil qidiruvda chiqishi mumkin, lekin unga public username linki yaratilmaydi.
- Natija avval nom mosligi, keyin username mosligi, keyin qolgan matn mosligi bo'yicha barqaror tartiblanadi.
- Bir xil natijalar account ID bo'yicha barqaror tartibda saqlanadi.

Birinchi versiyada PostgreSQL `ILIKE` va indekslanadigan normalizatsiya ishlatiladi. Ma'lumot hajmi oshganda FTS/trigram alohida optimizatsiya qilinadi.

## 6. Backend tuzilmasi

Yangi `public_discovery` moduli quyidagilarga bo'linadi:

- `schemas.py`: public response va query turlari;
- `repository.py`: PostgreSQL querylari;
- `service.py`: normalizatsiya, cache va response mapping;
- `router.py`: public HTTP endpoint;
- `dependencies.py` zarur bo'lsa dependency wiring.

`app/main.py` faqat yangi routerni ulaydi. Mavjud auth/profile yozish oqimlari o'zgartirilmaydi.

## 7. Redis cache

- Faqat muvaffaqiyatli public search javoblari cache qilinadi.
- Cache kaliti barcha normallashtirilgan filterlar, page va page_size dan tuziladi.
- TTL: 30 soniya.
- Redis ishlamasa API PostgreSQL orqali javob berishda davom etadi.
- Cache xatosi foydalanuvchiga 500 bermaydi.
- Profil yangilanganda darhol invalidatsiya qilish birinchi bo'lak uchun shart emas; 30 soniyalik TTL stale oynani cheklaydi.

## 8. Frontend xulqi

`CatalogScreen` va `CategoryScreen` mavjud local katalogni saqlaydi, ammo tanlangan query/filter bilan public search route yoki natija holatiga o'tadi.

Natijalar ekranida:

- skeleton/loading;
- natija soni;
- business va user kartalari;
- bo'sh natija matni;
- server xatosida `Qayta urinish`;
- keyingi sahifa tugmasi;
- eski katalogga qaytish imkoniyati bo'ladi.

Frontend API session bootstrap ishlamasa ham public qidiruvni chaqira oladi. Public route auth talab qilmaydi.

## 9. Xatolar

- Noto'g'ri parametr: standart typed 422 javobi;
- juda uzun query: 422;
- database vaqtincha ishlamasa: umumiy xavfsiz 503 API xatosi;
- Redis ishlamasa: PostgreSQL fallback;
- frontend network xatosi: sahifa buzilmaydi, retry holati chiqadi.

## 10. Test strategiyasi

Backend testlari:

- business va user qidiruvi;
- result_type filteri;
- qidiruv va joylashuv filterlari;
- pagination va barqaror ordering;
- inactive account natijaga kirmasligi;
- maxfiy maydonlarning response schema ga kirmasligi;
- Redis hit/miss/failure fallback;
- invalid query validation.

Frontend testlari:

- typed client query serialization;
- loading;
- business/user kartalari;
- bo'sh natija;
- retry;
- pagination;
- katalog va faoliyat turidan filter o'tishi;
- session bootstrap xatosi public natijani bloklamasligi.

Regressiya:

- mavjud Phase 1 va Phase 2 testlari;
- frontend build;
- legacy BUILD v1656 va `static/index.html` line-count contract o'zgarmaganini tekshirish.

## 11. Muvaffaqiyat mezonlari

Bo'lak tayyor hisoblanadi, agar:

1. real PostgreSQL profillari frontend qidiruvida chiqsa;
2. public API authsiz ishlasa;
3. maxfiy maydonlar javobda bo'lmasa;
4. xato holatida public sahifa buzilmasa;
5. backend/frontend testlari va production build o'tsa;
6. legacy production fayllari o'zgarmasa;
7. Railway staging deploy sog'lom bo'lsa.

## 12. Non-goals

Bu bo'lakda qilinmaydi:

- mahsulot, xizmat va e'lon jadvallari;
- eski SQLite qidiruvini proxy qilish;
- buyurtma va to'lov oqimlari;
- `koprik.uz` domenini yangi frontendga ko'chirish;
- exact geo-distance ranking;
- full-text search infratuzilmasi;
- legacy v1656 ni o'zgartirish.

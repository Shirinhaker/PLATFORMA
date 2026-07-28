# Koprik Phase 3 public discovery staging yo‘riqnomasi

Bu yo‘riqnoma public qidiruv va katalogni faqat Railway staging muhitida
qabul qilish uchun ishlatiladi. Production `web`, `koprik.uz` va legacy
BUILD v1656 ni o‘zgartirmang.

## Staging konfiguratsiyasi

- Frontend servisi: `frontend-staging`
- API servisi: `api-staging`
- Frontenddagi `VITE_API_BASE_URL` `api-staging` HTTPS domainiga qarasin.
- API Postgres va Redis staging servislariga reference orqali ulangan
  bo‘lsin.
- Public qidiruv keshi 30 soniya saqlanadi. Redis vaqtincha ishlamasa,
  qidiruv PostgreSQL orqali davom etishi kerak.

## Avtomatik qabul

1. GitHub pull request checks’lari yashil ekanini tekshiring.
2. Railway `api-staging` va `frontend-staging` deploymentlari
   `Successful` bo‘lsin.
3. Brauzerda `https://<api-staging-domain>/healthz` va `/readyz`
   manzillari HTTP `200` qaytarsin.
4. Quyidagi so‘rov HTTP `200` va paging obyektini qaytarsin:

   `GET https://<api-staging-domain>/api/v1/public/search?page=1&page_size=20`

5. Javob elementlarida faqat public maydonlar bo‘lsin. Telefon, aniq
   koordinata, karta, STIR va xom object key qaytmasin.

## Brauzer qabul checklisti

- [ ] Mehmon foydalanuvchi bosh sahifa, katalog va yo‘nalish sahifalarini
  sessiyasiz ochadi.
- [ ] Qidiruv so‘zi natijalarni yangilaydi.
- [ ] Oddiy va biznes filtrlar tegishli profil turini qaytaradi.
- [ ] Viloyat, tuman va mahalla tanlovi qidiruvga qo‘llanadi.
- [ ] Yo‘nalish va faoliyat turi filtrlari biznes natijalarini yangilaydi.
- [ ] Loading, bo‘sh natija va server xatosi holatlari tushunarli
  ko‘rsatiladi.
- [ ] Login, Telegram kodi, oddiy kabinet va biznes kabinet avvalgidek
  ishlaydi.
- [ ] Alohida tabda `koprik.uz` legacy v1656 ishlashda davom etadi.

Mahsulot, xizmat va e’lon natijalari bu qabulga kirmaydi; ular keyingi
Phase 3C ishidir.

## Muammo bo‘lsa rollback

1. Railway’da xato chiqqan `api-staging` yoki `frontend-staging`
   servisiga kiring.
2. Deployments tarixidan oxirgi ishlagan `Successful` deploymentni
   tanlang.
3. `Redeploy` orqali o‘sha versiyani qayta ishga tushiring.
4. `/healthz`, `/readyz` va `/api/v1/public/search` ni qayta tekshiring.
5. Production `web`, `koprik.uz`, Postgres ma’lumotlari va legacy v1656
   fayllarini rollback paytida o‘zgartirmang.

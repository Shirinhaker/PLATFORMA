# Koprik Phase 3B frontend-staging qabul va rollback yo‘riqnomasi

Bu yo‘riqnoma v1656 ko‘rinishidagi ochiq React oqimini faqat Railway
`frontend-staging` servisida tekshirish uchun ishlatiladi. Production `web`
servisi va `koprik.uz` domeni o‘zgartirilmaydi.

## Deploy chegarasi

- Frontend servisi: faqat `frontend-staging`.
- API servisi: mavjud `api-staging`.
- Branch: GitHub’dagi qabul qilingan `main`.
- Root Directory: `/frontend`.
- `VITE_API_BASE_URL`: `api-staging` HTTPS domeni.
- Production `web`, uning volume’i, custom domaini va `koprik.uz`ga tegmang.

## Avtomatik gate

1. GitHub pull request checks yashil bo‘lishi kerak.
2. Lokal yoki CI muhitida quyidagi buyruq PASS bo‘lishi kerak:

   ```bash
   python scripts/verify_phase3b.py
   ```

3. Natijada v1656 BUILD belgisi, 14 091 qatorli legacy HTML va 98 ekranli
   inventar o‘zgarmagan bo‘lishi kerak.

Quyidagi desktop va mobil tekshiruvlarning ikkalasi ham majburiy.

## Desktop qabul checklisti

Tekshiruvni kamida 1280 px kenglikda bajaring.

- [ ] Bosh sahifa mehmon holatida ochiladi.
- [ ] Headerda `Bosh sahifa`, `Manzil` va `Kirish` amallari ishlaydi.
- [ ] Bosh sahifadagi qidiruv `Katalog` ekranini ochadi.
- [ ] Katalog qidiruvi va kategoriya kartalari ishlaydi.
- [ ] Kategoriya kartasi `Yo‘nalish` ekranini ochadi.
- [ ] Orqaga tugmasi Yo‘nalish → Katalog → Bosh sahifa tartibida ishlaydi.
- [ ] Manzil ekranida viloyat va tuman tanlanadi, saqlangach Bosh sahifada
  ko‘rinadi va sahifa yangilanganda saqlanib qoladi.
- [ ] Kirish → Telegram kodi → sessiya oqimi ishlaydi.
- [ ] Oddiy kabinet ochiladi va profil/avatar ma’lumotlari saqlanadi.
- [ ] Biznes kabinet ochiladi va profil/logotip ma’lumotlari saqlanadi.

## Mobil qabul checklisti

Tekshiruvni 390 px kenglikda bajaring.

- [ ] Gorizontal scroll yo‘q.
- [ ] Headerning asosiy tugmalari ekranga sig‘adi.
- [ ] Bosh sahifa, Katalog, Yo‘nalish va Manzil kartalari bir ustunda
  o‘qiladigan ko‘rinishda turadi.
- [ ] Kirish, Oddiy kabinet va Biznes kabinet formalari ekrandan chiqmaydi.
- [ ] Barcha asosiy tugmalar bosiladi va fokus ko‘rinadi.

## Yakuniy staging tasdig‘i

- [ ] `frontend-staging` deployment holati `Successful`.
- [ ] `api-staging/healthz` HTTP 200 va status `ok`.
- [ ] `api-staging/readyz` HTTP 200, database va Redis tayyor.
- [ ] Brauzer konsolida CORS yoki JavaScript xatosi yo‘q.
- [ ] Alohida tabda production `koprik.uz` v1656 o‘zgarishsiz ishlamoqda.

Barcha avtomatik va qo‘lda tekshiruvlar o‘tgach, Phase 3B parity qatorlari
`staging-accepted` holatiga o‘tkaziladi.

## Muammo bo‘lsa rollback

1. Railway’da faqat `frontend-staging` servisiga kiring.
2. Deployments tarixidan oldingi ishlagan `Successful` deploymentni tanlang.
3. `Redeploy` orqali o‘sha versiyani qayta ishga tushiring.
4. Root sahifa va kirish oqimini qayta tekshiring.
5. Production `web`, `koprik.uz`, `api-staging`, worker, Postgres va Redis
   servislariga rollback paytida o‘zgartirish kiritmang.

Rollback faqat `frontend-staging`ni oldingi holatiga qaytaradi.

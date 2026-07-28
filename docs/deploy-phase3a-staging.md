# Koprik Phase 3A staging qabul va rollback yo‘riqnomasi

Bu yo‘riqnoma Phase 3A frontendini Railway staging muhitida tekshirish
uchun ishlatiladi. Tekshiruv production `web` servisi yoki `koprik.uz`
saytini o‘zgartirmaydi.

## Tasdiqlangan staging konfiguratsiyasi

- Frontend servisi: `frontend-staging`
- API servisi: `api-staging`
- Frontend API manzili faqat `VITE_API_BASE_URL` orqali beriladi.
- `VITE_API_BASE_URL` qiymati `api-staging` servisining HTTPS domainiga
  qarashi kerak.
- Secret qiymatlarni ushbu hujjatga yoki GitHub izohlariga yozmang.

## Qabul checklisti

- [ ] 1. GitHub pull request checks’lari yashil ekanini tekshiring.
- [ ] 2. Railway `frontend-staging` deployment holati `Successful`
  ekanini tekshiring.
- [ ] 3. `frontend-staging` Variables bo‘limida `VITE_API_BASE_URL`
  `api-staging` HTTPS domainiga qaraganini tekshiring.
- [ ] 4. Brauzerda `https://<api-staging-domain>/readyz` manzilini ochib,
  HTTP status `200` qaytishini tekshiring.
- [ ] 5. Desktop qabulini 1280 px kenglikda bajaring: header, mehmon auth
  sahifasi, oddiy kabinet va biznes kabinet to‘g‘ri ko‘rinsin.
- [ ] 6. Mobil qabulini 390 px kenglikda bajaring: gorizontal scroll
  bo‘lmasin, formalar bir ustunda va barcha asosiy tugmalar ko‘rinsin.
- [ ] 7. Auth oqimini to‘liq bajaring: login → Telegram kodi → kabinet →
  sahifani yangilash → chiqish.
- [ ] 8. Profil oqimlarini tekshiring: oddiy profil/avatar va biznes
  profil/logotipni saqlang; sahifani yangilagandan keyin ma’lumotlar
  qayta ko‘rinsin.
- [ ] 9. Alohida brauzer tabida legacy `koprik.uz` v1656 bosh sahifa,
  qidiruv, katalog va kabinet bilan ishlashda davom etishini tekshiring.
- [ ] 10. Barcha bandlar o‘tgachgina staging qabulini tasdiqlang.

## Muammo bo‘lsa rollback

1. Railway’da faqat `frontend-staging` servisiga kiring.
2. Deployments tarixidan oxirgi ishlagan `Successful` deploymentni
   tanlang.
3. `Redeploy` orqali o‘sha versiyani qayta ishga tushiring.
4. `frontend-staging` online ekanini va sahifa ochilishini tekshiring.
5. Production `web`, `koprik.uz`, `api-staging`, Postgres va Redis
   servislariga rollback jarayonida o‘zgartirish kiritmang.

Rollback productionni mutatsiya qilmaydi: `web` va `koprik.uz`
o‘zgarishsiz qoladi.

# Ko‘prik v1612 — biznes “Obunalarim”

> v1614 aniqligi: istoriya obuna tariflaridan to‘liq ajratildi. Quyidagi tarif
> tavsifi loyihaning amaldagi holatini aks ettiradi.

## Qayerda joylashgan

Biznes kabineti → `Onlaynlashtirish` → `Profil / Mening sahifam`dan keyin
`Obunalarim` kartasi qo‘shildi.

Bu bo‘lim faqat biznes egasiga ko‘rinadi. Xodimlar menyusiga qo‘shilmagan va
server ham xodim so‘rovini `403` bilan rad etadi.

## Tariflar

### Bepul

- Biznes profili va amaldagi asosiy onlayn bo‘limlar.
- Mahsulot va xizmatlarni tarif bo‘yicha cheklovsiz joylash.
- Muddatsiz.

### Plus

- Bepul tarifdagi barcha imkoniyatlar.
- Mahsulot yoki xizmatni bosh sahifadagi `Sizga yaqin` bo‘limiga chiqarish
  huquqi.
- 1, 3 yoki 12 oylik muddat.

### Pro

- Plus tarifdagi barcha imkoniyatlar.
- Biznes metkasini xaritada ko‘rsatish huquqi.
- 1, 3 yoki 12 oylik muddat.

## Istoriyalar

Istoriya joylash, ko‘rish va amaldagi tartiblash qoidalari obuna tarifiga bog‘liq
emas. Bepul, Plus va Pro tariflari istoriya imkoniyatini kengaytirmaydi yoki
cheklamaydi; v1614 bu funksiyaning o‘zini o‘zgartirmaydi.

Narxlar kelishilmagani uchun v1612 kodida pul qiymati yo‘q.

## Hozirgi ishlash tartibi

- Bu versiya sinov rejimi: haqiqiy karta, Click, Payme yoki avtomatik pul yechish
  ulanmagan.
- `Demo faollashtirish` bosilganda tanlangan tarif SQLite bazasida saqlanadi.
- Shu biznes boshqa qurilmadan ochilganda joriy tarif serverdan qayta yuklanadi.
- Bir xil Plus yoki Pro qayta tanlansa, yangi muddat amaldagi tugash sanasidan
  uzayadi.
- Boshqa tarif tanlansa, oldingi tarif tarixga o‘tadi va yangi tarif darhol
  boshlanadi.
- Plus yoki Pro muddati tugasa, biznes avtomatik Bepul tarifga qaytadi; tugagan
  yozuv tarixda qoladi.
- Bepul tarif muddatsiz va ketma-ket bosilganda takroriy yozuv yaratmaydi.

## Entitlement yordamchisi

`subscriptions.py` ichidagi
`business_has_entitlement(conn, business_id, feature, now=None)` kelajakdagi
ikkita ko‘rinish nuqtasi uchun yagona server tekshiruvidir:

- `home_nearby_eligible` — Plus va Pro;
- `map_marker_eligible` — faqat Pro.

Bosh sahifadagi tuman takliflari birinchi entitlementga, v1615 xaritasi esa
ikkinchi entitlementga ulangan. Istoriya endpointlari va algoritmlari obuna
yordamchisiga ulanmaydi.

## API

- `GET /api/business/subscription` — joriy tarif, imkoniyatlar, muddatlar va
  tarix.
- `POST /api/business/subscription/demo-activate` — `plan_code` va
  `duration_months` bilan demo tarifni faollashtirish.

Xatolar: noto‘g‘ri tarif yoki muddat `400`, tizimga kirmagan foydalanuvchi
`401`, shaxsiy profil yoki xodim `403`.

## Nomlar aniqlashtirildi

Ijtimoiy follow ro‘yxatining eski `Obunalarim` nomi `Kuzatayotganlar`ga
o‘zgartirildi. Follow mexanizmi va endpointlari o‘zgarmadi.

## Runtime o‘zgargan fayllar

- `subscriptions.py`
- `database.py`
- `api.py`
- `main.py`
- `static/index.html`

Deployment fayllari (`railpack.json`, `nixpacks.toml`) o‘zgartirilmadi.

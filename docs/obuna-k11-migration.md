# K11 — Obuna bo'lish va bekor qilish

Obunalar hozirgacha kabinet JSON'ida saqlanardi va faqat **o'qib**
ko'rsatilardi: foydalanuvchi obunani bekor qila olardi (kabinet
resursidan o'chirish), ammo **obuna bo'la olmasdi** — bunday endpoint
umuman yo'q edi.

`static/index.html` v1656 manbasi va frontend fayllari o'zgarmaydi.

## Ko'chirilgan funksiyalar

- obuna bo'lish va bekor qilish — v1656 kabi **bitta amal**
  (`api.py:toggle_follow`): bo'lmagan bo'lsa bo'ladi, bo'lgan bo'lsa
  bekor qiladi;
- oddiy foydalanuvchi ham, biznes kabineti ham obuna bo'la oladi;
- nishon — foydalanuvchi yoki biznes profili;
- `followers_count` va `following_count` har amaldan keyin jadvaldan
  qayta hisoblanadi;
- obuna bo'lingan profillar ro'yxati endi jadvaldan o'qiladi.

## Jadval

`profile_follows` — bitta jadval. v1656da ikkitasi bor edi (`follows`
foydalanuvchi uchun, `business_follows` biznes uchun), chunki u yerda
obunachi turi jadval bilan belgilanardi. Yangi modelda obunachi ham
akkaunt, turi `accounts.account_type` dan ma'lum — shuning uchun bitta
jadval yetarli.

| Himoya | Qanday |
|---|---|
| Bir nishonga ikki marta obuna | `uq_profile_follows_pair` noyob indeksi |
| O'ziga obuna bo'lish | `ck_profile_follows_not_self` + servis tekshiruvi |
| Biznes egasining o'z profiliga obunasi | `profile_links` orqali tekshiriladi |
| Ikki so'rov bir vaqtda | `IntegrityError` ushlanadi, natija bir xil qaytadi |
| Mavjud bo'lmagan profil | `follow_target_not_found` |

## v1656 pariteti

| Qoida | v1656 | Yangi |
|---|---|---|
| Bitta amal holatni almashtiradi | `toggle_follow` | `POST /api/v1/follows/toggle` |
| Javobda `following` va `followers` | shu yerda | bir xil |
| O'ziga obuna taqiqlangan | `O'zingizga obuna bo'la olmaysiz.` | bir xil xabar |
| Biznes egasi o'z profiliga obuna bo'lolmaydi | `business_follows` tekshiruvi | `profile_links` orqali |
| Nishon faol bo'lishi | `status='active'` | bir xil |

## Backfill

Migratsiya eski obunalarni `cabinet_records` va `cabinet_payload` dan
o'qiydi (`follows` — foydalanuvchi, `following` — biznes), eski
`target_id` ni `legacy_id_map` orqali akkaunt identifikatoriga
xaritalaydi va jadvalga yozadi. Xaritasi topilmagan yozuv tashlab
yuboriladi — u endi mavjud bo'lmagan profilga ishora qiladi.

Backfilldan keyin ikkala profil jadvalining hisoblagichlari qayta
hisoblanadi.

## API

```
POST /api/v1/follows/toggle
     {"kind": "user"|"business", "public_id": "u_… | b_…"}
  →  {"following": true|false, "followers": 12}
```

CSRF talab qilinadi. `public_id` — qolgan ommaviy API'lardagi kabi
hash, ichki identifikator tashqariga chiqmaydi.

## Testlar

`tests/test_follow_flow_v1656.py` — 8 ta test:

- birinchi chaqiruv obuna qiladi, ikkinchisi bekor qiladi;
- hisoblagichlar jadvalga mos yurishi;
- foydalanuvchi boshqa foydalanuvchiga obuna bo'la olishi;
- o'ziga obuna bo'lish rad etilishi;
- biznes egasining o'z profiliga (ikki yo'nalishda ham) obuna
  bo'lolmasligi;
- noma'lum nishon rad etilishi;
- biznes kabineti obuna bo'la olishi;
- `is_following` mehmon va boshqa foydalanuvchi uchun to'g'ri javob
  berishi.

## Release gate

- Alembic `0022_education_group_history → 0023_profile_follows` offline
  SQL;
- `base:head` xatosiz, bitta head;
- backend 491 test, frontend 338 test;
- TypeScript toza;
- `rollback` qo'riqchisi ro'yxatida `FollowService`.

## K11 tarkibiga kirmaydi

Obunachilar ro'yxatini kabinetda ko'rsatish hali JSON resursidan
(`followers`) o'qiladi — u alohida bosqichda jadvalga o'tkaziladi.
Obuna bildirishnomalari ham shu bosqichda ulanadi.

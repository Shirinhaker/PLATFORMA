# K22 — Obunachilar va kuzatilayotganlar

K22 kabinetdagi obunachilar va kuzatilayotgan profillar ro'yxatini eski
JSON resursidan yakuniy typed follow domeniga ko'chiradi. Monolit
`static/index.html` v1656 o'zgartirilmaydi.

## Monolitdagi oqim

```text
cab-followers / cab-following
  static/index.html:2756–2764
              │
              ▼
loadBusinessOnlineView(...)
  static/index.html:12037–12060
              │
              ▼
GET /api/business/followers | /api/business/following
  api.py:4668–4740
              │
              ▼
followers / business_follows + profil ma'lumoti
```

Obuna holatini almashtirish esa `api.py:4598–4665` dagi
`toggle_follow` orqali ishlaydi. K11 shu amalni `profile_follows`
jadvaliga ko'chirgan, lekin kabinet ro'yxati va yangi obunachi
bildirishnomasi qolgan edi.

## Yangi moduldagi oqim

```text
UserProfile / BusinessProfileV3
              │
              ▼
FollowListsV1656 (umumiy React ekran)
              │
              ▼
GET /api/v1/follows/followers
GET /api/v1/follows/following
              │
              ▼
FollowService → FollowRepository
              │
              ▼
profile_follows + accounts + user_profiles/business_profiles
```

Ro'yxat bir profil uchun alohida so'rovlar yubormaydi: foydalanuvchi va
biznes profillari bitta `UNION ALL` so'rovida olinadi. Kuzatilayotganlar
eng yangisidan boshlanadi. Obunachilar v1656dagi kabi avval oddiy,
keyin biznes profillariga ajratiladi va har guruh ichida eng yangisidan
boshlanadi (`created_at DESC, id DESC`).

## API javobi

```json
{
  "items": [
    {
      "kind": "business",
      "public_id": "b_1234567890abcdef",
      "name": "Hamkor",
      "info": "Savdo",
      "image_url": "https://...",
      "crop_x": 50,
      "crop_y": 50,
      "crop_zoom": 1,
      "followed_at": 1750000000
    }
  ],
  "count": 1
}
```

Ichki akkaunt identifikatori tashqariga chiqmaydi. Oddiy profil uchun
faqat ommaviy `public_username`, biznes uchun yo'nalish qaytariladi;
tuman kabi yopiq profil maydonlari ro'yxatga qo'shilmaydi. Faqat faol
akkauntlar ko'rsatiladi.

## Profilga o'tish va bildirishnoma

- ro'yxatdagi kartochka bosilganda `kind + public_id` orqali ommaviy
  profil ochiladi;
- yangi obuna yaratilganda nishon akkauntga `Yangi obunachi`
  bildirishnomasi yoziladi;
- bildirishnoma `profile_kind` va `profile_public_id`ni olib yuradi,
  shuning uchun u bosilganda ham obunachining profili ochiladi;
- obunani bekor qilish yangi bildirishnoma yaratmaydi;
- `profile_follow:{follow_id}` hodisa kaliti takroriy yozishni to'sadi.

## Indeks va migratsiya

`0035_follow_lists` migratsiyasi `ix_profile_follows_target` indeksini
`(target_account_id, created_at, id)` ko'rinishiga o'tkazadi. Mavjud
`ix_profile_follows_follower (follower_account_id, created_at, id)`
kuzatilayotganlar so'rovini qoplaydi.

## Orqaga qaytish

Frontend API metodlari mavjud bo'lmasa oldingi `PeopleView` yo'liga
qayta oladi. Alembic downgrade nishon indeksini eski
`(target_account_id, id)` shakliga qaytaradi. Monolit fayli o'zgarmagani
uchun alohida statik rollback talab qilinmaydi.

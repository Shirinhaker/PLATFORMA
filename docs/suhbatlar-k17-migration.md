# K17 — umumiy Suhbatlar migratsiyasi

K17 v1656dagi buyurtmaga bog‘lanmagan umumiy yozishmani relatsion PostgreSQL
domeni, R2 media va umumiy React ekraniga ko‘chiradi. Buyurtma chati alohida
`orders` domenida qoladi va bu migratsiyada o‘zgartirilmaydi.

`BUILD v1656` va `static/index.html` haqiqat manbai o‘zgartirilmaydi.

## Monolitdagi etalon

| Qism | v1656 manbasi | Ishlashi |
|---|---|---|
| Kabinet menyulari | `static/index.html:1773`, `2368` | Oddiy va biznes kabinetidagi `Suhbatlar` kirishi |
| Chat ekrani | `static/index.html:2636–2645` | Xabarlar oqimi, rasm tanlash va yozish paneli |
| Reply/edit/delete/copy | `static/index.html:7160–7338` | Xabar menyusi va holat paneli |
| Suhbatni ochish va polling | `static/index.html:7341–7404` | Oqim yuklanadi, har 3 soniyada yangilanadi, kunlar bo‘yicha ajraladi |
| Rasm va yuborish | `static/index.html:7413–7478` | 8 MB gacha rasm, rasm-only, matn va reply yuborish |
| Suhbatlar ro‘yxati | `static/index.html:7705–7723` | Avatar, ism, oxirgi xabar va o‘qilmaganlar soni |
| Profil orqali kirish | `static/index.html:5766–5784`, `7735–7760` | Biznes yoki foydalanuvchi profilidan `Xabar yozish` |
| Server qoidalari | `api.py:9107–9448` | Ikki aktyor, owner-only edit/delete, soft delete va unread |
| Eski jadval | `database.py:774–825` | `messages` va aktyor juftligi indekslari |

Monolit oqimi:

```text
ochiq profil / kabinetdagi Suhbatlar
            │
            ▼
  suhbatlar ro‘yxati ── avatar + ism + last + unread
            │ suhbat tanlanadi
            ▼
  thread GET ── kelgan xabarlar read bo‘ladi
            │
            ├── matn yuborish
            ├── rasm yuborish (8 MB, rasm-only mumkin)
            ├── reply / copy
            └── faqat o‘z xabarini edit / soft delete
                         │
                         └── har 3 soniyada thread yangilanadi
```

## Modulli yechim

```text
PublicProfile / UserProfile / BusinessProfile
                    │
                    ▼
           MessagesV1656 (umumiy UI)
                    │ typed /api/v1/messages
                    ▼
      router → service → repository → PostgreSQL
                    │
                    ├── message_conversations
                    ├── message_conversation_members
                    └── messages
                              │
                              └── yangi va eski chat rasmlari R2 da
```

Akkaunt juftligi `low_account_id < high_account_id` ko‘rinishida kanonik
saqlanadi. Noyob indeks bir juftlik uchun faqat bitta suhbat bo‘lishini
kafolatlaydi. Reply faqat o‘sha suhbatdagi xabarga beriladi. Tahrirlash va
o‘chirish sender akkaunti bilan tekshiriladi. Staff uchun `chats` vakolati
talab qilinadi.

Ichki raqamlar frontendga berilmaydi. Nishon `u_…` yoki `b_…` public ID bilan
tanlanadi; barcha yozuvchi endpointlar sessiya va CSRF bilan himoyalangan.

## API

```text
GET    /api/v1/messages/conversations
GET    /api/v1/messages/with/{kind}/{public_id}
POST   /api/v1/messages/send
POST   /api/v1/messages/image
PUT    /api/v1/messages/{message_id}
DELETE /api/v1/messages/{message_id}
GET    /api/v1/messages/unread-count
```

## Backfill va media tartibi

1. Alembic `0031_messages` uchta jadval va kerakli indekslarni yaratadi.
2. Birinchi manba — normallashtirilgan `cabinet_records`; profilning
   `cabinet_payload.messages` massivi fallback bo‘ladi.
3. Eski user/business aktyor ID’lari `legacy_id_map` orqali yangi account
   ID’lariga o‘tkaziladi.
4. Takrorlangan xabar `legacy_source_id` partial unique indeksi bilan bir
   marta yoziladi; reply bog‘lanishi xabarlar yozilgandan keyin tiklanadi.
5. Eski `/uploads/chat/...` rasmlari legacy media bosqichida R2 ga ko‘chadi va
   relatsion xabarning `media_object_key` maydoniga ulanadi. Yetishmagan media
   verification hisobotida alohida ko‘rinadi.

Rollback jadvallarni teskari FK tartibida olib tashlaydi. Eski profil JSON’i
backfill vaqtida o‘chirilmaydi; release tekshiruvlari tugamaguncha xavfsizlik
nusxasi bo‘lib turadi.

## Frontend ulanishi

- `MessagesV1656` oddiy va biznes kabineti uchun bitta jonli ekran;
- kabinet kartasida relatsion unread soni;
- ochiq user/business profilida `✍️ Xabar yozish`;
- guest avval login oqimiga yo‘naltiriladi;
- profil orqali ochilgan threaddan orqaga qaytish profilni saqlaydi;
- matn, rasm-only, reply, copy, edit, soft delete, kun guruhlari va 3 soniyalik
  polling v1656 bilan bir xil.

## Monolit kodini olib tashlash gate’i

Quyidagilarning barchasi bajarilgandan keyin umumiy chatning monolit kodi
olib tashlanishi mumkin:

1. staging va productionda `0031_messages` muvaffaqiyatli bajarilgan;
2. legacy media run qayta bajarilib, verification `passed=true` bergan va chat
   rasmlari uchun `missing=0`, `invalid=0`, `failed=0` tasdiqlangan;
3. xabar, suhbat va media sonlari snapshot bilan solishtirilgan;
4. user → business va business → user matn/rasm/reply/read/edit/delete oqimi
   haqiqiy ikki akkauntda tekshirilgan;
5. yangi frontend barcha chat kirishlarini typed API’ga yo‘naltirgan;
6. rollback uchun PostgreSQL backup va immutable legacy snapshot saqlangan.

Bu gate’largacha `api.py` va SQLite `messages` jadvalini o‘chirish mumkin emas.
Gate’dan keyin umumiy chat monolit kodi olinadi; `order_messages` va buyurtma
chat kodi esa o‘z migratsiya chegarasi sababli qoladi.

## Test qamrovi

- backend model, schema, feature flag, router, backfill va reversibility;
- sender ownership, self-message, reply conversation va media object-key
  chegaralari;
- legacy chat rasmini R2 ga ko‘chirish;
- ikki aktyorli text → unread/read → image reply → forbidden edit → owner
  edit/delete oqimi;
- typed API path va CSRF;
- suhbatlar ro‘yxati, unread, rasm-only, reply, edit/delete;
- ikkala kabinet va ochiq profildan jonli chatga ulanish.

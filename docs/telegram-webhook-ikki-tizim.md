# Telegram webhook: bitta bot, ikkita tizim

## Muammo

2026-08-24 da yangi saytda ro'yxatdan o'tish ishlamayotgani aniqlandi:
havolani bosgan foydalanuvchiga "havola noto'g'ri" chiqardi.

Sabab kodda emas, sozlamada edi. Telegram **bitta botga bitta webhook
manzilini** biriktiradi, va o'sha manzil hali eski v1656 monolitiga
qarab turgan edi:

```
https://monolitkoprik-production.up.railway.app/webhook
```

Natijada zanjir uzilardi:

| Bosqich | Qayerda |
|---|---|
| Token yaratiladi va saqlanadi | **yangi** backend, yangi baza |
| Foydalanuvchi `/start <token>` yuboradi | Telegram uni **eski** monolitga beradi |
| Token qidiriladi | **eski** baza — u yerda bunday token yo'q |
| Natija | "havola noto'g'ri" |

Kirish (login) ishlayverardi, chunki mavjud foydalanuvchining Telegram
id'si allaqachon bog'langan va yangi backend kodni to'g'ridan-to'g'ri
Bot API orqali yuboradi — webhook kerak emas. Ro'yxatdan o'tishda esa
id hali noma'lum, shuning uchun webhook majburiy.

Dalil: yangi backendga Telegramdan bitta ham so'rov kelmagan — na ilova,
na Railway proksi jurnalida.

## Yechim: taniqli bo'lmaganini uzatish

Webhook yangi backendga o'tadi. Yangi backend har bir yangilanishni
ko'radi va **faqat o'ziniki bo'lsa** ishlatadi; qolganini eski tizimga
uzatadi. Shunday qilib bitta bot bilan ikkala sayt ham ishlaydi.

```
Telegram
   │
   ▼
yangi backend  /api/v1/auth/telegram/webhook
   │
   ├── `/start <token>` va token bizda bor  → o'zimiz ishlaymiz
   │
   └── qolgan hamma narsa                   → eski monolit /webhook
       (boshqa matnlar, tokensiz `/start`,
        bizda topilmagan token)
```

Uzatish qoidasi `backend/app/auth/router.py` da:

- `/start <token>` emas → uzatiladi
- `/start` tokensiz → uzatiladi (eski tizim salomlashish xabarini beradi)
- token bizda topilmadi (`invalid_start_token`) → uzatiladi
- token bizniki, lekin boshqa xato (masalan allaqachon faollashtirilgan)
  → **uzatilmaydi**, xato o'zimizniki

Shu sababli har bir havolaga faqat bitta tizim javob beradi va
foydalanuvchi ikkita qarama-qarshi xabar olmaydi.

Uzatish muvaffaqiyatsiz bo'lsa (eski tizim o'chgan, 403 qaytardi va
hokazo) xato **yutiladi** va Telegramga baribir `200` qaytariladi. Aks
holda Telegram butun yangilanishni qayta yuboradi va biz allaqachon
ko'rib chiqqan xabarni yana qayta ishlagan bo'lardik.

## Sozlamalar

| O'zgaruvchi | Ma'nosi |
|---|---|
| `KOPRIK_TELEGRAM_LEGACY_WEBHOOK_URL` | Eski monolit webhook manzili. **Bo'sh bo'lsa uzatish butunlay o'chiq** — hozirgi xulq o'zgarmaydi. |
| `KOPRIK_TELEGRAM_LEGACY_WEBHOOK_SECRET` | Eski monolit kutadigan sir (u yerda `WEBHOOK_SECRET` deb ataladi). |

## Yoqish tartibi

> Bu qadamlar jonli tizimga tegadi — egasining ruxsati bilan bajariladi.

**1. Yangi backendga sozlamalarni berish**

```
KOPRIK_TELEGRAM_LEGACY_WEBHOOK_URL=https://monolitkoprik-production.up.railway.app/webhook
KOPRIK_TELEGRAM_LEGACY_WEBHOOK_SECRET=<eski servisdagi WEBHOOK_SECRET qiymati>
```

**2. Eski monolitni webhookni tortib olishdan to'xtatish**

Bu qadam **majburiy**. Eski monolit har ishga tushganda o'zini webhookka
qaytadan ro'yxatdan o'tkazadi (`main.py:427` — startup'da `setWebhook`).
Ya'ni bu qadamsiz webhook eski monolit qayta deploy bo'lishi bilanoq
o'g'irlanadi va ro'yxatdan o'tish yana uziladi.

Eski servisda `BASE_URL` ni bo'shatish kifoya: u **faqat** webhook
ro'yxatdan o'tkazish uchun ishlatiladi (`main.py:424-444`, `1020`).
Bot orqali xabar yuborish `BOT_TOKEN` ga bog'liq va ishlashda davom
etadi, ya'ni eski sayt foydalanuvchilariga kod yetib boraveradi.

**3. Webhookni o'tkazish**

```
setWebhook
  url            = https://<yangi-domen>/api/v1/auth/telegram/webhook
  secret_token   = KOPRIK_TELEGRAM_WEBHOOK_SECRET
  allowed_updates= ["message"]
  drop_pending_updates = false
```

**4. Tekshirish**

- `getWebhookInfo` yangi manzilni ko'rsatsin, `last_error_message` bo'sh bo'lsin
- yangi saytda ro'yxatdan o'tish uchidan-uchiga sinaladi
- eski saytda ham kirish sinaladi — ikkalasi ham ishlashi kerak

## Orqaga qaytarish

`setWebhook` ni eski manzilga qaytarish kifoya. Yangi backenddagi kod
uzatishni o'zi to'xtatadi, chunki unga yangilanish kelmay qoladi.
Sozlamalarni ham o'chirish shart emas — ular zararsiz.

## Bog'liq eslatma

`backend/app/auth/telegram_cutover_once.py` shu ishni avtomatlashtirish
uchun yozilgan edi, lekin **ishlay olmaydi**: u `_verify_legacy_freeze()`
da `https://web-production-302eb.up.railway.app/readyz` ni tekshiradi,
o'sha servis esa o'chirilgan va 404 qaytaradi, shuning uchun skript
`setWebhook` ga yetmay to'xtaydi. Haqiqiy eski monolit boshqa manzilda
turibdi. Bundan tashqari u skript eski tizimning **muzlatilgan**
bo'lishini talab qiladi, bu yerdagi maqsad esa aksincha — ikkalasi ham
ishlashi kerak.

## Cheklov

Bir chatdan daqiqasiga 60 tadan ko'p `/start` kelsa tezlik chegarasi
ishlaydi va o'sha yangilanish uzatilmaydi. Oddiy foydalanishda bunga
yetib bo'lmaydi.

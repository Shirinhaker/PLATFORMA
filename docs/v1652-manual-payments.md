# Ko‘prik v1652 — qo‘lda to‘lovlar

## Ishlaydigan oqimlar

- Plus va Pro obuna uchun serverdagi amaldagi narx tanlanadi.
- Reklama avval `payment_pending` holatida yaratiladi va to‘lov
  tasdiqlanmaguncha bosh sahifada ko‘rinmaydi.
- Foydalanuvchi JPG, PNG yoki WEBP kvitansiya yuboradi (maksimum 5 MB).
- Kvitansiya public `/uploads` ichida emas, private katalogda saqlanadi.
- Administrator to‘lovni tasdiqlaydi yoki sabab bilan rad etadi.
- Tasdiqlanganda obuna yoki reklama bir marta atomar faollashadi.
- Rad etilganda foydalanuvchi “To‘lovlarim” orqali yangi kvitansiya
  yuborishi mumkin.
- Sayt bildirishnomasi va Telegram outbox qaror tranzaksiyasidan
  ajratilgan; Telegram vaqtincha ishlamasa qaror yo‘qolmaydi.

## Muhit o‘zgaruvchilari

Productionda quyidagilar majburiy:

```env
PAYMENT_RECEIPT_DIR=/data/private/payment_receipts
PAYMENT_TOKEN_SECRET=kamida-48-belgili-alohida-maxfiy-kalit
ADMIN_TG_IDS=1423181561
```

`PAYMENT_RECEIPT_DIR` public static yoki uploads katalogiga
yo‘naltirilmasligi kerak.

## To‘lov holatlari

`pending → approved` yoki `pending → rejected`.
Faqat `rejected` so‘rov yangi kvitansiya bilan yana `pending` bo‘ladi.
Tasdiqlangan to‘lovni bekor qilish admin sababi bilan bajariladi va
bankdagi pulni avtomatik qaytarmaydi.

## MVP cheklovi

E’lon to‘lovi backendda tayyor, lekin `MVP_LISTINGS_ENABLED=0` bo‘lsa
e’lon yaratish interfeysi va public endpointlar yopiq qoladi.

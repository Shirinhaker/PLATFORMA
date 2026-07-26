# Ko‘prik v1622 — koprik.uz va integratsiyaga tayyor qatlam

## Hozirgi qaror

Asosiy sayt manzili `https://koprik.uz`. SMS, to‘lov va tashqi object storage
provayderlari hozircha ulanmaydi; ularning holati `disabled`. Asosiy API endi
provayderning ichki kodiga bog‘lanmaydi — keyingi adapter umumiy interfeys orqali
ulanadi.

## Railway’da domenni qo‘shish

1. Ko‘prik servisini oching: **Settings → Networking → Public Networking**.
2. **Custom Domain** orqali `koprik.uz` ni kiriting.
3. Railway ko‘rsatgan `CNAME`/`A` yoki `ALIAS` va domenni tasdiqlovchi `TXT`
   yozuvlarini aynan o‘z holicha nusxalang.
4. Eskiz.uz domen panelida `koprik.uz` DNS boshqaruvini ochib, Railway bergan
   yozuvlarni kiriting. Eski, bir xil hostga tegishli qarama-qarshi `A`, `AAAA`
   yoki `CNAME` yozuvini saqlab qolmang.
5. `www.koprik.uz` ham ishlashi kerak bo‘lsa, uni Railway’da ikkinchi Custom
   Domain sifatida qo‘shing va uning ko‘rsatgan DNS yozuvlarini ham kiriting.
6. Railway’da ikkala domen yonida yashil tasdiq paydo bo‘lishini kuting. SSL
   sertifikat Railway tomonidan avtomatik olinadi.

Railway bergan qiymat loyiha uchun alohida bo‘ladi. Uni taxmin qilish yoki boshqa
loyihadagi qiymatdan nusxalash mumkin emas. `TXT` yozuvisiz domen Railway’da 404
qaytarishi mumkin.

## Railway Variables

`.env.production.example` namunasiga muvofiq quyidagilarni belgilang:

```text
APP_ENV=production
BASE_URL=https://koprik.uz
PRIMARY_DOMAIN=koprik.uz
ALLOWED_HOSTS=koprik.uz,www.koprik.uz,*.up.railway.app,*.railway.internal,localhost,127.0.0.1
CANONICAL_WWW_REDIRECT=1
```

`www` orqali kelgan so‘rov yo‘li va query parametrlari saqlangan holda 308 bilan
`https://koprik.uz` ga o‘tadi. Productionda noma’lum Host qiymati 400 qaytaradi.

## Integratsiya adapterlari

`integrations.py` uchta barqaror chegara beradi:

- `sms` — ro‘yxatdan o‘tish va kirish tasdiqlash kodi;
- `payment` — to‘lov yaratish va webhookni tekshirish;
- `object_storage` — media faylini yozish va o‘chirish.

Hozirgi sozlama:

```text
SMS_PROVIDER=disabled
PAYMENT_PROVIDER=disabled
OBJECT_STORAGE_PROVIDER=disabled
```

Shu sabab sayt tashqi integratsiyaga so‘rov yubormaydi. SMS adapteri keyin
ro‘yxatdan o‘tkazilganda mavjud mobil OTP endpointlari o‘zgarmasdan ishlaydi.

## Buzilmagan qoidalar

- biznes verifikatsiyasi qo‘shilmadi;
- istoriyalar tariflardan mustaqil;
- Pro uchun alohida metka yo‘q;
- foydalanuvchi tumani maxfiy;
- vaqtinchalik loyiha bloki o‘chirilmagan.

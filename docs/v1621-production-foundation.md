# Ko‘prik v1621 — rasmiy ishlab chiqarish poydevori

## Maqsad

Sinov maketini rasmiy sayt qurilishi uchun xavfsiz bazaga aylantirish. Bu versiya
to‘lov, SMS provayder yoki biznes verifikatsiyasi haqida yangi mahsulot qarori
qabul qilmaydi; faqat serverni noto‘g‘ri production sozlamasi bilan ishga
tushirishni to‘xtatadi va doimiy ma’lumotlar uchun poydevor yaratadi.

## Production talablari

Railway Volume `/data` manziliga ulansin va `.env.production.example` dagi
o‘zgaruvchilar Railway Variables bo‘limiga ko‘chirilsin. Haqiqiy sirlar faylga
yozilmasin.

`APP_ENV=production` holatida quyidagilarning barchasi majburiy:

- `BASE_URL` haqiqiy HTTPS manzil;
- `BOT_TOKEN`;
- kamida 32 belgili, bir-biridan boshqa `WEBHOOK_SECRET` va
  `MOBILE_OTP_SECRET`;
- `/data` ichidagi mutlaq `DB_PATH`, `UPLOAD_DIR` va `BACKUP_DIR`;
- `TEST_MODE=0` va `TEST_OTP_CODE` yo‘qligi;
- yopiq rejim davomida aniq `PRIVILEGED_TG_IDS`.

Birortasi noto‘g‘ri bo‘lsa server xatoni aniq ko‘rsatib, ishga tushmaydi.

## Zaxira nusxasi

Productionda `DATABASE_BACKUP_ON_START` standart bo‘yicha yoqilgan. Har deploy
oldidan emas, har yangi server jarayoni ishga tushganida SQLite online-backup API
orqali butun nusxa olinadi, `integrity_check` bilan tekshiriladi va oxirgi 14 ta
nusxa saqlanadi.

Qo‘lda nusxa olish:

```bash
python backup_database.py --db /data/platforma.db --dir /data/backups --retention 14
```

Bu lokal volume zaxirasi. Keyingi bosqichda alohida tashqi storage va rejalangan
off-site backup ulanadi.

## Deploy tekshiruvlari

- `GET /healthz` — server jarayoni tirikligini ko‘rsatadi;
- `GET /readyz` — SQLite va media papkasi ishlashga tayyorligini tekshiradi;
- ikkala endpoint ham foydalanuvchi, yo‘l yoki sirlarni oshkor qilmaydi;
- vaqtinchalik loyiha bloki saqlanadi, diagnostika esa avvalgidek o‘chiq.

## Saqlangan mahsulot cheklovlari

- istoriyalar tariflardan mustaqil;
- Pro uchun alohida metka yo‘q;
- oddiy foydalanuvchining tumani boshqalarga berilmaydi;
- vaqtinchalik global blok olib tashlanmagan;
- biznes verifikatsiyasi keyingi mahsulot qarorigacha qo‘shilmagan.

# Ko‘prik v1656 — tayyor funksional bo‘limlarni ochish

## Maqsad

Monolit `v1656`da kodi va ma’lumot modeli tayyor bo‘lib, MVP guardlari bilan
yopilgan bo‘limlarni paritet solishtiruvi uchun ochish. Build marker va mavjud
ekran tuzilmasi o‘zgarmaydi.

## Ochiq bo‘limlar

- E’lonlar: ko‘rish, yaratish, tahrirlash va o‘chirish.
- Istoriyalar: feed, joylash, profil istoriyasi va arxiv.
- Umumiy suhbatlar.
- Tizimlashtirish: kassa, ombor, qarz, xarajat, xodimlar, hujjatlar,
  kontragentlar va ta’lim boshqaruvi.
- Taxi: chaqirish va haydovchi kabineti.
- AI yordamchi: barcha biznes egalari uchun; xodim sessiyasi uchun avvalgi
  ruxsat cheklovi saqlanadi.

## Saqlangan himoyalar

- adminning alohida autentifikatsiya va HttpOnly sessiya oqimi;
- bloklangan akkauntlarning yozish amallarini to‘xtatish;
- biznes, foydalanuvchi va xodim rollari hamda ma’lumot egaligi;
- kvitansiyalarni public media papkalaridan alohida saqlash;
- o‘chirishdan oldingi tasdiqlash;
- `PROJECT_ACCESS_RESTRICTED=1` orqali butun loyihani vaqtincha yopish.

`Hisobot` ochilmagan: u tayyor funksiya emas va vazifasi keyingi bosqichda
belgilanadigan ekran bo‘lib qoladi.

## Production konfiguratsiyasi

Deploydan oldin quyidagi besh qiymat aynan `1` bo‘lishi shart:

```dotenv
MVP_LISTINGS_ENABLED=1
MVP_STORIES_ENABLED=1
MVP_CHAT_ENABLED=1
MVP_SYSTEMIZATION_ENABLED=1
MVP_TAXI_ENABLED=1
```

Noto‘g‘ri yoki yetishmagan qiymatda server xavfsiz ishga tushmaydi.

## Mavjud bazani ochish

Eski `platform_feature_flags` yozuvlari `0` bo‘lishi mumkin. Deploydan oldin
odatiy backup va integrity tekshiruvi bilan release migratsiyasi bajariladi:

```bash
python migration_check.py \
  --db "$DB_PATH" \
  --backup-dir "$BACKUP_DIR" \
  --schema v1656-unlocked
```

Migratsiya mavjud besh flagni `1`ga o‘tkazadi. Yangi bazada ular sukut bo‘yicha
ochiq. Baza, upload va private receipt papkalari o‘chirilmaydi.

## Readiness va qabul mezonlari

- `/api/features` besh flag uchun `true` qaytaradi.
- `/api/build` barcha olti ochilgan qismni, jumladan
  `ai_all_businesses_enabled:true`ni qaytaradi.
- `/readyz` DB, integrity, upload, private receipt, admin assetlar va besh
  flagning ochiq holatini birga tekshiradi.
- `BUILD v1656` saqlanadi.
- `static/index.html` 14 091 qator bo‘lib qoladi.
- Monolit va yangi modulli versiya Cloud Browser’da bir xil haqiqiy profil
  bilan ekranma-ekran tekshiriladi.

## Rollback

Muammo chiqsa yangi ma’lumotlar o‘chirilmaydi. Avval besh flag `0` qilinadi yoki
butun loyiha `PROJECT_ACCESS_RESTRICTED=1` bilan yopiladi; zarur bo‘lsa faqat
migratsiyadan oldin yaratilgan, integrity tekshiruvidan o‘tgan backup alohida
yo‘lda tiklanadi.

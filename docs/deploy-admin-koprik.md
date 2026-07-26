# Ko‘prik v1654 — Railway va admin domenini ishga tushirish

## 1. Majburiy infratuzilma

1. Railway xizmatiga bitta Volume ulang: mount path `/data`.
2. Replica sonini **1** qilib qoldiring. SQLite bazani bir nechta replica o‘rtasida ulash mumkin emas.
3. Railway Variables’ni `.env.production.example` bo‘yicha kiriting.
4. Haqiqiy sirlarni repozitoriyga, ZIPga yoki logga yozmang.
5. `TEST_MODE=0`, `TEST_OTP_CODE` esa umuman mavjud bo‘lmasin.

## 2. Deploydan oldingi baza tekshiruvi

Avval production bazasining staging nusxasida:

```bash
python migration_check.py \
  --db /data/db/platforma.db \
  --backup-dir /data/backups \
  --schema v1654
```

Buyruq backup va uning JSON manifestini yaratadi, backupga `integrity_check`,
migratsiyadan keyin target bazaga yana `integrity_check` bajaradi. Natijada
`integrity: "ok"` bo‘lmasa deployni davom ettirmang.

## 3. Railway deploy

`railpack.json` quyidagi qat’iy kontraktni ishlatadi:

- `ffmpeg` o‘rnatiladi;
- `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1`;
- healthcheck: `/readyz`;
- healthcheck timeout: 120 soniya;
- xatoda ko‘pi bilan 3 restart.

Deploydan so‘ng:

```bash
curl -fsS https://koprik.uz/healthz
curl -fsS https://koprik.uz/readyz
curl -fsS https://koprik.uz/api/build
```

`/readyz` javobida database, integrity, uploads, private payment receipts va
admin assets `true`; to‘rtta MVP flag esa `false` bo‘lishi kerak.

## 4. `admin.koprik.uz`

1. Railway’da shu xizmatga `admin.koprik.uz` Custom Domain qo‘shing.
2. Railway bergan target nomini nusxalang.
3. Cloudflare’da CNAME yarating:
   - Name: `admin`
   - Target: Railway bergan target
   - dastlab Proxy status: **DNS only**
4. Railway domenni tasdiqlagach Cloudflare proxy’ni yoqing.
5. Cloudflare SSL/TLS rejimini **Full (strict)** qiling.
6. `https://admin.koprik.uz` alohida admin shell ochishini tekshiring.
7. Admin Telegram OTP bilan kirsin; asosiy sayt Bearer tokeni admin panelda
   ishlamasligi kerak.

## 5. Qabul smoke sinovi

1. Test deb belgilangan pending subscription payment yarating.
2. Admin paneldan kvitansiyani ko‘ring.
3. Tasdiqlang va subscription aynan bir marta faollashganini tekshiring.
4. Reject → resubmit va cancel sabablarini tekshiring.
5. Guest search, map va district offers’ni tekshiring.
6. Oddiy/biznes follow’lari alohida ekanini tekshiring.
7. Orders, Service Orders va order chat ishlashini tekshiring.
8. Read-only probe:

```bash
python scripts/mvp_load_probe.py --base-url https://koprik.uz
```

Qabul mezoni: server error `0`, p95 `< 1000 ms`. Aks holda release
to‘xtatiladi va bottleneck o‘lchanadi.

## 6. Monitoring va backup

- Har deploydan oldin `migration_check.py`.
- `/healthz` va `/readyz`ni tashqi monitor bilan kuzating.
- Backup `.sqlite3` va `.manifest.json` juftligini tekshiring.
- `admin_audit_log` append-only; audit yozuvlarini qo‘lda o‘zgartirmang.
- “database is locked” yoki p95 chegarasi buzilsa PostgreSQL migratsiyasini
  release blocker sifatida oching.

## 7. Rollback

1. Railway’da oldingi deploymentni tanlang.
2. Migratsiyadan oldingi backupni **alohida yangi pathda** ochib
   `PRAGMA integrity_check` bajaring.
3. Xizmatni vaqtincha to‘xtating.
4. Joriy DBni timestamp bilan saqlab qo‘ying — ustidan yozmang.
5. Tekshirilgan backupni explicit `DB_PATH`ga restore qiling.
6. Oldingi release’ni ishga tushiring.
7. `/readyz`ni tekshiring.
8. Yangi jadvallarni qo‘lda `DROP` qilmang; rollback ma’lumotni yo‘qotmasin.

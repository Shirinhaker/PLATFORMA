# Phase 3C V8 final write-freeze

Bu hujjat final production snapshot oldidan v1656 source bazaga yangi yozuv kelishini
to‘liq to‘xtatish uchun ishlatiladi.

## Muhim qoida

`PROJECT_ACCESS_RESTRICTED=1` final write-freeze uchun yetarli emas: privileged
Telegram akkauntlar kirishi mumkin va legacy `/webhook` alohida ochiq qoladi.
Final snapshot uchun `KOPRIK_MIGRATION_MAINTENANCE=1` ishlatiladi.

`web` Railway start command `cutover_app:app` orqali ishga tushadi. Flag o‘chiq
bo‘lsa wrapper barcha scope'larni v1656 `main:app` ga o‘zgarishsiz uzatadi.
Flag yoqilgan bo‘lsa `main` umuman import/start qilinmaydi; legacy lifespan,
Telegram webhook va background outbox/push workerlar source SQLite'ga yoza olmaydi.

## 1. Maintenance/write-freeze ni yoqish

Railway `melodious-emotion` loyihasidagi production `web` servisida:

```text
KOPRIK_MIGRATION_MAINTENANCE=1
```

qiymatini bering va shu servis redeploy bo‘lsin.

Deploydan keyin quyidagilar majburiy:

- `GET /readyz` -> HTTP 200 va `writes_frozen: true`;
- `/` -> HTTP 503 maintenance sahifasi;
- `/maintenance.html` -> HTTP 200, `Texnik ishlar olib borilmoqda`;
- `/api/...` mutationlar -> HTTP 503 `migration_maintenance`;
- `/webhook` POST -> HTTP 503 `migration_maintenance`.

Shu tekshiruvlar o‘tmaguncha final archive/snapshot olinmaydi.

## 2. Final source archive

Write-freeze tasdiqlangandan keyin final SQLite backup va source archive olinadi.
Archive SHA-256 saqlanadi. Shu archive V8 final staging rehearsal uchun yagona
source hisoblanadi.

V8 staging skripti arxivni vaqtinchalik ish katalogiga chiqaradi va snapshotdan
OLDIN `app.legacy_migration.demo_prune` ni ishlatadi. Shuning uchun v1616 demo
akkauntlari va ularga tegishli demo biznes/listing/itemlar modular candidate
snapshotga kirmaydi.

Muhim: `demo_prune` live v1656 SQLite faylini o‘chirmaydi yoki tahrirlamaydi.
Demo yozuvlar eski source bazada rollback dalili sifatida qolishi mumkin, ammo
final modular candidate va productionga ko‘chirilmaydi.

## 3. Abort/rollback — routing hali almashtirilmagan bo‘lsa

Agar final rehearsal yoki promotion to‘xtatilsa va v1656 ni yana ochish kerak bo‘lsa:

```text
KOPRIK_MIGRATION_MAINTENANCE=0
```

qilib `web` servisni redeploy qiling. So‘ng `/readyz` normal v1656 readiness
javobiga qaytganini va sayt yana ochilganini tekshiring.

Maintenance davomida olingan SQLite backup, source archive, snapshot, manifest
va migration run dalillarini do not delete — qayta urinish va audit uchun saqlang.

# Phase 3C production cutover va rollback

Production migratsiyasi PR merge bilan avtomatik bajarilmaydi. Approved staging run, bir xil schema version va kelishilgan maintenance oynasi majburiy.

## Cutover

1. Approved staging run ID, barcha PASS gate’lar va maintenance oynasini ikki mas’ul bilan tasdiqlang.
2. Foydalanuvchi routingini `/maintenance.html` ga o‘tkazing.
3. Monolith’ga barcha write endpoint va worker yozuvlarini to‘xtating; yangi yozuv kelmayotganini tekshiring.
4. Yakuniy SQLite backup, immutable snapshot va media manifest yarating; SHA-256 fingerprintlarni yozing.
5. Typed environment, snapshot hash, maintenance flag va approved staging run ID bilan production migratsiyasini boshlang:

   ```bash
   koprik-migrate-legacy run \
     --snapshot /data/migration/final/platforma.snapshot.db \
     --environment production \
     --confirm-environment production \
     --confirm-snapshot-sha256 SNAPSHOT_SHA256 \
     --maintenance-enabled \
     --approved-staging-run-id STAGING_RUN_ID
   ```

6. Har bir verification gate PASS bo‘lishini talab qiling. Bitta FAIL ham cutover’ni to‘xtatadi.
7. Maintenance routing faol holda API va frontend smoke-testlarini bajaring.
8. Routingni yangi backend va frontendga o‘tkazing.
9. `/maintenance.html` routingini olib tashlang.
10. Eski foydalanuvchi bir marta qayta kiradi; qayta ro‘yxatdan o‘tmaydi.

## Rollback

1. Routingni yana `/maintenance.html` ga o‘tkazing.
2. `KOPRIK_PHASE3C_PUBLIC_ENABLED=false` qiling.
3. Routingni o‘zgarmagan v1656 monolith’ga qaytaring.
4. Monolith write endpoint va workerlarini qayta yoqing.
5. PostgreSQL’dagi partial yozuvlarni `migration_run_id` bilan izolyatsiyada qoldiring.
6. Do not delete SQLite, R2 objects, legacy media yoki partial target rows. Ular rollback dalili va idempotent retry uchun saqlanadi.
7. Xatoni tuzating va aynan o‘sha snapshot bilan idempotent qayta ishga tushiring.

Rollback’dan keyin ham foydalanuvchi ma’lumoti o‘chirilmaydi. Production ochilmaguncha monolith yagona yozish manbai bo‘lib qoladi.


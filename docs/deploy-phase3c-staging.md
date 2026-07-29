# Phase 3C staging migratsiyasi

Bu runbook faqat staging uchun. Production va ishlab turgan v1656 monolith o‘zgarmaydi.

## Old shartlar

- PostgreSQL va Redis staging xizmatlari sog‘lom.
- R2 staging bucket alohida va yozishga tayyor.
- `KOPRIK_PHASE3C_PUBLIC_ENABLED=false`.
- Monolith SQLite bazasi hamda eski media o‘chirilmaydi.

## Bajarish tartibi

1. PostgreSQL’ga `0003_phase3c_content` revisionini qo‘llang:

   ```bash
   cd backend
   python -m alembic upgrade 0003_phase3c_content
   ```

2. Immutable snapshot va media manifest yarating; chiqqan SHA-256 qiymatlarini deploy jurnaliga yozing:

   ```bash
   koprik-migrate-legacy snapshot \
     --source /data/platforma.db \
     --output /data/migration/phase3c \
     --media-root /data/uploads
   ```

3. Migratsiyani `verify` bosqichigacha bajaring:

   ```bash
   koprik-migrate-legacy run \
     --snapshot /data/migration/phase3c/platforma.snapshot.db \
     --environment staging
   ```

4. Aynan shu snapshot bilan ikkinchi idempotent ishga tushirishni bajaring. Har import bosqichida `created=0` bo‘lishi shart.

5. JSON va Markdown reportlarni oching. Ular faqat count, numeric legacy ID va safe issue code saqlashini tekshiring:

   ```bash
   koprik-migrate-legacy report --run-id RUN_ID --format json
   koprik-migrate-legacy report --run-id RUN_ID --format markdown
   ```

6. Barcha takrorlangan telefon/Telegram identity conflictlarini administrator bilan hal qiling. Unresolved identity conflict `0` bo‘lishi shart.

7. Reconciliation countlari teng, media `failed=0`, copied checksum gate PASS va barcha verification gate PASS bo‘lishini talab qiling.

8. Faqat staging’da `KOPRIK_PHASE3C_PUBLIC_ENABLED=true` qilib yangi backend/frontend deploy qiling.

9. Health/readiness, profil, product, service, location filter, “Egasi hali akkauntini bog‘lamagan” warning, disabled order/chat, reklamalar va yopiq `/api/v1/public/listings` endpointini smoke-test qiling.

10. Redis’ni vaqtincha uzib, public catalog/search PostgreSQL fallback bilan ishlashini tekshiring.

11. Telefon, planshet va desktop ekranlarda katalog kartalari, mobile/desktop banner va placeholder rasmni tekshiring.

12. Deploy jurnaliga approved staging run ID, snapshot SHA-256, manifest SHA-256, gate natijalari, entity/media countlari va unresolved issue countini yozing.

Staging gate’dan bittasi yiqilsa feature flagni o‘chiring, yangi public routingni qaytaring va snapshotdan idempotent qayta ishlang. Monolith, SQLite va legacy media o‘chirilmaydi.


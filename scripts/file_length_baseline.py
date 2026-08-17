"""Fayl uzunligi qarzi — `check_file_length.py` uchun.

Bu ro'yxatni qo'lda tahrirlamang. Faylni bo'lgach:

    python scripts/check_file_length.py --update
"""

BASELINE: dict[str, int] = {
    "backend/app/admin/moderation_service.py": 566,
    "backend/app/admin/router.py": 535,
    "backend/app/business_online/service.py": 834,
    "backend/app/cash_register/service.py": 676,
    "backend/app/documents/service.py": 530,
    "backend/app/education/cabinet_service.py": 605,
    "backend/app/education/management_repository.py": 546,
    "backend/app/education/model.py": 562,
    "backend/app/legacy_migration/media_stage.py": 515,
    "backend/app/legacy_migration/profile_parity_v7.py": 829,
    "backend/app/legacy_migration/reconcile.py": 845,
    "backend/app/legacy_migration/reconcile_v6.py": 722,
    "backend/app/legacy_migration/verify.py": 537,
    "backend/app/notifications/repository.py": 655,
    "backend/app/notifications/service.py": 544,
    "backend/app/payments/service.py": 688,
    "backend/app/queues/repository.py": 619,
    "backend/app/staff/service.py": 646,
    "backend/app/stories/service.py": 521,
    "frontend/src/profiles/business-profile-config.ts": 1036,
}

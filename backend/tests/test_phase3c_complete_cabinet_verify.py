from app.legacy_migration.verify import (
    VerificationInput,
    _inspect_cabinet_value,
    evaluate_gates,
)


def clean_values(**overrides) -> VerificationInput:
    values = {
        "source_rows": 7,
        "mapped_rows": 7,
        "source_catalog_kinds": {"product": 1, "service": 1},
        "target_catalog_kinds": {"product": 1, "service": 1},
        "source_listings": 1,
        "target_listings": 1,
        "source_advertisements": 1,
        "target_advertisements": 1,
        "broken_foreign_keys": 0,
        "identity_conflicts": 0,
        "source_media_references": 2,
        "media_copied": 2,
        "media_missing": 0,
        "media_invalid": 0,
        "media_failed": 0,
        "copied_media_unverified": 0,
        "idempotency_created": 0,
        "forbidden_public_fields": (),
        "cabinet_demo_rows": 0,
        "cabinet_sensitive_fields": 0,
    }
    values.update(overrides)
    return VerificationInput(**values)


def test_clean_complete_cabinet_passes_all_gates():
    report = evaluate_gates(clean_values())

    assert report.passed is True
    assert {gate.code for gate in report.gates} >= {
        "cabinet_demo_rows",
        "cabinet_sensitive_fields",
        "identity_conflicts",
        "idempotency",
    }


def test_demo_or_sensitive_cabinet_payload_fails_verify():
    report = evaluate_gates(
        clean_values(
            cabinet_demo_rows=2,
            cabinet_sensitive_fields=3,
        )
    )
    failed = {gate.code for gate in report.gates if not gate.passed}

    assert report.passed is False
    assert failed == {"cabinet_demo_rows", "cabinet_sensitive_fields"}


def test_nested_payload_inspection_detects_demo_and_secrets():
    demo_rows, sensitive_fields = _inspect_cabinet_value(
        {
            "orders": [
                {
                    "id": 1,
                    "title": "Haqiqiy",
                    "items": [{"id": 2, "name": "Muhr"}],
                },
                {
                    "id": 3,
                    "title": "Demo",
                    "is_demo": 1,
                },
            ],
            "staff": [
                {
                    "id": 4,
                    "name": "Kassir",
                    "pass_hash": "must-not-leak",
                }
            ],
            "payment": {
                "token_hash": "must-not-leak",
            },
        }
    )

    assert demo_rows == 1
    assert sensitive_fields == 2

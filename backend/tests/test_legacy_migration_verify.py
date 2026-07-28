from app.legacy_migration.verify import (
    VerificationInput,
    evaluate_gates,
)


def valid_input(**changes):
    values = {
        "source_rows": 20,
        "mapped_rows": 20,
        "source_catalog_kinds": {"product": 5, "service": 3},
        "target_catalog_kinds": {"product": 5, "service": 3},
        "source_listings": 4,
        "target_listings": 4,
        "source_advertisements": 2,
        "target_advertisements": 2,
        "broken_foreign_keys": 0,
        "identity_conflicts": 0,
        "source_media_references": 6,
        "media_copied": 4,
        "media_missing": 1,
        "media_invalid": 1,
        "media_failed": 0,
        "copied_media_unverified": 0,
        "idempotency_created": 0,
        "forbidden_public_fields": (),
    }
    values.update(changes)
    return VerificationInput(**values)


def test_all_exact_gates_pass_for_consistent_migration():
    report = evaluate_gates(valid_input())

    assert report.passed is True
    assert all(gate.passed for gate in report.gates)


def test_failed_media_and_identity_conflicts_block_gate():
    report = evaluate_gates(
        valid_input(media_failed=1, identity_conflicts=2)
    )

    assert report.passed is False
    failed = {gate.code for gate in report.gates if not gate.passed}
    assert failed == {"identity_conflicts", "media_failed"}


def test_listing_and_advertisement_counts_are_not_mixed():
    report = evaluate_gates(valid_input(target_advertisements=4))

    assert report.passed is False
    failed = {gate.code for gate in report.gates if not gate.passed}
    assert "advertisement_count" in failed
    assert "listing_count" not in failed


def test_idempotency_and_public_schema_leaks_block_gate():
    report = evaluate_gates(
        valid_input(
            idempotency_created=1,
            forbidden_public_fields=("business_account_id",),
        )
    )

    assert report.passed is False
    failed = {gate.code for gate in report.gates if not gate.passed}
    assert failed == {"idempotency", "public_schema_leak"}

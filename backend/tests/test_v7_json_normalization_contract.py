from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_business_online_service_stops_using_profile_json_as_primary_store():
    source = (
        ROOT / "app" / "business_online" / "service_relational.py"
    ).read_text(encoding="utf-8")
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "CabinetRecordRepository" in source
    assert "profile.cabinet_payload = payload" not in source
    assert "service_relational import BusinessOnlineService" in main


def test_v7_normalization_migration_and_verify_exist():
    migration = ROOT / "migrations" / "versions" / "0006_v7_normalized_cabinet_records.py"
    assert migration.exists()
    text = migration.read_text(encoding="utf-8")
    assert "cabinet_resources" in text
    assert "value_kind" in text
    assert "cabinet_records" in text
    assert "cabinet_record_fields" in text
    assert "cabinet_normalization_runs" in text

    verify = ROOT / "app" / "cabinet_records" / "verify.py"
    assert verify.exists()
    verify_text = verify.read_text(encoding="utf-8")
    assert "verify_payload_parity" in verify_text
    assert "source_digest" in verify_text
    assert "target_digest" in verify_text


def test_profile_json_cleanup_is_not_part_of_initial_backfill():
    migration = (
        ROOT / "migrations" / "versions" / "0006_v7_normalized_cabinet_records.py"
    )
    assert migration.exists()
    text = migration.read_text(encoding="utf-8")
    assert "UPDATE business_profiles SET cabinet_payload" not in text
    assert "UPDATE user_profiles SET cabinet_payload" not in text

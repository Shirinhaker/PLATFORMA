from pathlib import Path


def test_taxi_migration_follows_ai_domain_and_has_active_ride_guards():
    path = Path(__file__).parents[1] / "migrations/versions/0041_taxi_driver_domain.py"
    source = path.read_text(encoding="utf-8")

    assert 'down_revision = "0040_ai_assistant_domain"' in source
    assert '"taxi_drivers"' in source
    assert '"taxi_rides"' in source
    assert '"uq_taxi_rides_active_customer"' in source
    assert '"uq_taxi_rides_active_driver"' in source
    assert "FROM drivers" not in source
    assert "FROM rides" not in source


def test_complete_cabinet_migration_runs_typed_taxi_import():
    root = Path(__file__).parents[1] / "app"
    profile_source = (root / "legacy_migration/profile_parity_v7.py").read_text(
        encoding="utf-8",
    )
    runner_source = (root / "legacy_migration/runner_v6.py").read_text(
        encoding="utf-8",
    )

    assert "import_taxi_domain" in profile_source
    assert 'MIGRATION_SCHEMA_VERSION = "0008_phase3c_taxi_v1"' in runner_source

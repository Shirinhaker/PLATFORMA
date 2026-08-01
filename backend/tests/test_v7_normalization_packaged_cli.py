from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent


def test_v7_normalization_cli_is_packaged_with_the_backend_app():
    cli = BACKEND / "app" / "cabinet_records" / "cli.py"
    assert cli.exists()
    text = cli.read_text(encoding="utf-8")
    assert "execute_backfill_batches" in text
    assert "verify_existing_normalization" in text
    assert "DATABASE_WRITES=0" in text


def test_staging_ops_script_invokes_the_packaged_module():
    script = REPOSITORY / "scripts" / "Koprik-V7-Normalize-Cabinet-JSON.ps1"
    text = script.read_text(encoding="utf-8")
    assert "python -m app.cabinet_records.cli" in text
    assert "scripts/backfill_v7_cabinet_records.py" not in text

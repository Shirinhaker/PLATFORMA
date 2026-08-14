from pathlib import Path


def test_active_runtime_does_not_import_legacy_migration_package() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    migration_only = {
        app_root / "db" / "all_models.py",
    }
    offenders: list[str] = []
    for path in app_root.rglob("*.py"):
        if "legacy_migration" in path.parts:
            continue
        if path.name == "legacy_import.py" or path in migration_only:
            continue
        text = path.read_text(encoding="utf-8")
        if "app.legacy_migration" in text:
            offenders.append(str(path.relative_to(app_root.parent)))
    assert offenders == [], (
        "Active runtime legacy_migration paketiga bog‘langan: "
        + ", ".join(sorted(offenders))
    )

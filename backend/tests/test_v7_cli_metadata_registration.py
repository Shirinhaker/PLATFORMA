from app.cabinet_records import cli  # noqa: F401
from app.cabinet_records.model import CabinetResource
from app.db.base import Base


def test_standalone_v7_cli_registers_foreign_key_metadata() -> None:
    assert "accounts" in Base.metadata.tables
    assert "user_profiles" in Base.metadata.tables
    assert "business_profiles" in Base.metadata.tables
    assert "cabinet_resources" in Base.metadata.tables

    foreign_keys = list(CabinetResource.__table__.c.account_id.foreign_keys)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].column.table.name == "accounts"
    assert foreign_keys[0].column.name == "id"

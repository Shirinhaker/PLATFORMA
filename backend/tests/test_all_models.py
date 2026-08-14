"""Barcha modellar bitta joydan yuklanishi kerak.

V8 staging runi shu sababdan yiqilgan edi:

    sqlalchemy.exc.NoReferencedTableError: Foreign key associated with
    column 'stories.created_by_staff_id' could not find table
    'staff_members'

Ilova ishlaganda muammo ko'rinmaydi — `app.main` hamma modelni import
qiladi. Migratsiya CLI'si esa faqat o'ziga keraklarini yuklardi va
domenlararo tashqi kalitlar yechilmay qolardi.
"""

import pathlib
import re

from sqlalchemy import inspect as sa_inspect

from app.db import all_models
from app.db.base import Base


BACKEND = pathlib.Path(__file__).resolve().parent.parent


def _model_modules() -> set[str]:
    """`app/*/model.py` va `app/*/*_model.py` fayllari."""
    found = set()
    for path in BACKEND.glob("app/*/model.py"):
        if path.parent.name == "legacy_migration":
            # Offline compatibility module only re-exports neutral ORM
            # definitions and must not be imported by runtime startup.
            continue
        found.add(f"app.{path.parent.name}.model")
    for path in BACKEND.glob("app/*/*_model.py"):
        found.add(f"app.{path.parent.name}.{path.stem}")
    return found


def _imported_modules() -> set[str]:
    source = pathlib.Path(all_models.__file__).read_text(encoding="utf-8")
    return {
        f"app.{package}.{module}"
        for package, module in re.findall(
            r"from app\.([a-z_]+) import ([a-z_]+) as ", source
        )
    }


def test_every_model_module_is_registered():
    """Yangi domen qo'shilsa, u ham ro'yxatga tushishi shart."""
    missing = sorted(_model_modules() - _imported_modules())
    assert not missing, (
        "app/db/all_models.py ga qo'shilmagan modullar: " + ", ".join(missing)
    )


def test_registry_has_no_stale_entries():
    stale = sorted(_imported_modules() - _model_modules())
    assert not stale, "mavjud bo'lmagan modullar: " + ", ".join(stale)


def test_alembic_env_registers_every_model_module():
    """Alembic ham to'liq metama'lumot bilan ishlashi kerak.

    `env.py` da `cabinet_records`, `outbox` va `taxi` yetishmayotgan edi —
    autogenerate ularni "o'chirilgan jadval" deb ko'rishi mumkin edi.
    """
    source = (BACKEND / "migrations" / "env.py").read_text(encoding="utf-8")
    imported = {
        f"app.{package}.{module}"
        for package, module in re.findall(
            r"from app\.([a-z_]+) import ([a-z_]+) as ", source
        )
    }
    missing = sorted(_model_modules() - imported)
    assert not missing, (
        "migrations/env.py ga qo'shilmagan modullar: " + ", ".join(missing)
    )


def test_cross_domain_foreign_keys_resolve():
    """Domenlararo kalitlar yechilmasa `sorted_tables` yiqiladi."""
    tables = Base.metadata.sorted_tables
    assert len(tables) > 80

    names = {table.name for table in tables}
    # Aynan V8 ni yiqitgan bog'lanishlar.
    assert {"stories", "staff_members", "orders", "debtors"} <= names


def test_story_staff_foreign_key_points_at_staff_members():
    column = Base.metadata.tables["stories"].c.created_by_staff_id
    targets = {key.target_fullname for key in column.foreign_keys}
    assert targets == {"staff_members.id"}


def test_migration_cli_alone_resolves_every_foreign_key():
    """CLI'ni yolg'iz import qilish yetarli bo'lishi kerak.

    Ilgari CLI atigi 26 ta jadval yuklardi va tashqi kalit yechilmasdi.
    """
    from app.legacy_migration import cli  # noqa: F401

    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            for key in column.foreign_keys:
                # `.column` yechilmasa NoReferencedTableError chiqadi.
                assert key.column is not None

    assert sa_inspect(Base.metadata.tables["stories"]) is not None

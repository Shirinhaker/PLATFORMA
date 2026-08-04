from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db.base import Base
from app.accounts import model as accounts_model  # noqa: F401
from app.advertisements import model as advertisements_model  # noqa: F401
from app.auth import model as auth_model  # noqa: F401
from app.catalog import model as catalog_model  # noqa: F401
from app.cash_register import model as cash_register_model  # noqa: F401
from app.debt_ledger import model as debt_ledger_model  # noqa: F401
from app.expenses import model as expenses_model  # noqa: F401
from app.inventory import model as inventory_model  # noqa: F401
from app.legacy_migration import model as legacy_migration_model  # noqa: F401
from app.listings import model as listings_model  # noqa: F401
from app.notifications import model as notifications_model  # noqa: F401
from app.orders import model as orders_model  # noqa: F401
from app.profiles import model as profiles_model  # noqa: F401
from app.queues import model as queues_model  # noqa: F401
from app.staff import model as staff_model  # noqa: F401


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())

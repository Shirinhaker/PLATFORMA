"""Alembic migratsiyasini replica-safe advisory lock bilan ishga tushiradi."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings


LOCK_NAME = "koprik-alembic-migration"


async def _alembic_upgrade() -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        "upgrade",
        "head",
    )
    code = await process.wait()
    if code != 0:
        raise SystemExit(code)


async def migrate() -> None:
    settings = Settings()
    if not settings.database_url.startswith("postgresql"):
        await _alembic_upgrade()
        return
    engine = create_async_engine(settings.database_url, pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT pg_advisory_lock(hashtext(:name))"),
                {"name": LOCK_NAME},
            )
            try:
                await _alembic_upgrade()
            finally:
                await connection.execute(
                    text("SELECT pg_advisory_unlock(hashtext(:name))"),
                    {"name": LOCK_NAME},
                )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(migrate())


if __name__ == "__main__":
    main()

from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


NORMALIZATION_ADVISORY_LOCK_KEY = 0x4B4F5052  # "KOPR"


class NormalizationAlreadyRunning(RuntimeError):
    pass


@asynccontextmanager
async def normalization_lock(session: AsyncSession):
    acquired = await session.scalar(
        text("SELECT pg_try_advisory_lock(:key)"),
        {"key": NORMALIZATION_ADVISORY_LOCK_KEY},
    )
    if not acquired:
        raise NormalizationAlreadyRunning("cabinet_normalization_already_running")
    try:
        yield
    finally:
        try:
            await session.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": NORMALIZATION_ADVISORY_LOCK_KEY},
            )
        finally:
            await session.rollback()

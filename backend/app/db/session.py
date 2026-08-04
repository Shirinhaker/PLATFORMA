from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    def __init__(
        self,
        url: str,
        *,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 3,
    ) -> None:
        self.url = url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.engine: AsyncEngine | None = None
        self._sessions: async_sessionmaker[AsyncSession] | None = None

    async def start(self) -> None:
        self.engine = create_async_engine(
            self.url,
            pool_pre_ping=True,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
        )
        self._sessions = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

    async def stop(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
        self.engine = None
        self._sessions = None

    async def ready(self) -> bool:
        if self.engine is None:
            return False
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessions is None:
            raise RuntimeError("Database.start() chaqirilmagan.")
        async with self._sessions() as session:
            yield session

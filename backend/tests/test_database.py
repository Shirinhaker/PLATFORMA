import os

import pytest
from sqlalchemy import text

from app.db.session import Database


DATABASE_URL = os.environ.get("KOPRIK_TEST_DATABASE_URL", "")


@pytest.mark.skipif(not DATABASE_URL, reason="KOPRIK_TEST_DATABASE_URL required")
async def test_database_pool_and_readiness():
    database = Database(DATABASE_URL, pool_size=5, max_overflow=5)
    await database.start()
    assert await database.ready() is True
    async with database.session() as session:
        assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
    await database.stop()

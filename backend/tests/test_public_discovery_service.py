from contextlib import asynccontextmanager
import asyncio

import fakeredis.aioredis

from app.core.config import Settings
from app.public_discovery.schemas import (
    PublicSearchItem,
    PublicSearchParams,
    PublicSearchResponse,
)
from app.public_discovery.service import PublicDiscoveryService


class FakeDatabase:
    def __init__(self):
        self.rollbacks = 0

    @asynccontextmanager
    async def session(self):
        database = self

        class Session:
            async def rollback(self):
                database.rollbacks += 1

        yield Session()


class BrokenRedis:
    async def get(self, key):
        raise RuntimeError("redis unavailable")

    async def set(self, key, value, *, ex):
        raise RuntimeError("redis unavailable")


async def test_public_search_uses_short_redis_cache():
    database = FakeDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    reads = 0

    async def loader(session, params):
        nonlocal reads
        reads += 1
        return PublicSearchResponse(
            items=[
                PublicSearchItem(
                    kind="business",
                    public_id="b_public",
                    name="Koprik Savdo",
                )
            ],
            page=params.page,
            page_size=params.page_size,
            total=1,
        )

    service = PublicDiscoveryService(
        database.session,
        redis,
        Settings(environment="test"),
        search_loader=loader,
    )
    try:
        first = await service.search(PublicSearchParams(q="savdo"))
        second = await service.search(PublicSearchParams(q="  savdo  "))
        ttl = await redis.ttl(service.cache_key(PublicSearchParams(q="savdo")))
    finally:
        await redis.aclose()

    assert first == second
    assert reads == 1
    assert database.rollbacks == 1
    assert 0 < ttl <= 30


async def test_public_search_falls_back_to_database_when_redis_fails():
    database = FakeDatabase()

    async def loader(session, params):
        return PublicSearchResponse(
            items=[],
            page=params.page,
            page_size=params.page_size,
            total=0,
        )

    service = PublicDiscoveryService(
        database.session,
        BrokenRedis(),
        Settings(environment="test"),
        search_loader=loader,
    )

    response = await service.search(PublicSearchParams())

    assert response.items == []
    assert database.rollbacks == 1


async def test_concurrent_identical_searches_share_one_database_load():
    database = FakeDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    reads = 0
    release = asyncio.Event()

    async def loader(session, params):
        nonlocal reads
        reads += 1
        await release.wait()
        return PublicSearchResponse(
            items=[],
            page=params.page,
            page_size=params.page_size,
            total=0,
        )

    service = PublicDiscoveryService(
        database.session,
        redis,
        Settings(environment="test"),
        search_loader=loader,
    )
    try:
        first = asyncio.create_task(
            service.search(PublicSearchParams(q="savdo"))
        )
        second = asyncio.create_task(
            service.search(PublicSearchParams(q="savdo"))
        )
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)
    finally:
        await redis.aclose()

    assert reads == 1
    assert database.rollbacks == 1


def test_public_search_cache_key_changes_with_filters_and_pagination():
    first = PublicDiscoveryService.cache_key(
        PublicSearchParams(q="savdo", page=1)
    )
    second = PublicDiscoveryService.cache_key(
        PublicSearchParams(q="savdo", page=2)
    )
    third = PublicDiscoveryService.cache_key(
        PublicSearchParams(q="xizmat", page=1)
    )

    assert len({first, second, third}) == 3
    assert "savdo" not in first
    assert first.startswith("public:search:v2:")

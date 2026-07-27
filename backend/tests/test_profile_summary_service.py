import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import fakeredis.aioredis
import pytest

from app.accounts.model import AccountType
from app.core.config import Settings
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile, UserProfile
from app.profiles.summary_service import ProfileSummaryService


class CountingDatabase:
    def __init__(self):
        self.reads = 0
        self.rollbacks = 0
        self.profiles = {
            (UserProfile, 1): SimpleNamespace(
                account_id=1,
                name="Ali",
                phone="+998901112233",
            ),
            (BusinessProfile, 2): SimpleNamespace(
                account_id=2,
                name="Koprik Savdo",
                phone="+998907770000",
                direction="Savdo",
                address="Toshkent",
            ),
        }

    @asynccontextmanager
    async def session(self):
        database = self

        class Session:
            async def get(self, model, account_id):
                database.reads += 1
                await asyncio.sleep(0.01)
                return database.profiles.get((model, account_id))

            async def rollback(self):
                database.rollbacks += 1

        yield Session()


class PausedDatabase(CountingDatabase):
    def __init__(self):
        super().__init__()
        self.read_started = asyncio.Event()
        self.allow_read_to_finish = asyncio.Event()

    @asynccontextmanager
    async def session(self):
        database = self

        class Session:
            async def get(self, model, account_id):
                database.reads += 1
                profile = database.profiles.get((model, account_id))
                snapshot = SimpleNamespace(**vars(profile))
                database.read_started.set()
                await database.allow_read_to_finish.wait()
                return snapshot

            async def rollback(self):
                database.rollbacks += 1

        yield Session()


class BrokenRedis:
    async def get(self, key):
        raise RuntimeError("redis read unavailable")

    async def set(self, key, value, *, ex):
        raise RuntimeError("redis write unavailable")

    async def delete(self, key):
        raise RuntimeError("redis delete unavailable")


async def test_repeated_profile_summary_uses_redis_after_one_database_read():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        first = await service.resolve(AccountType.USER, 1)
        second = await service.resolve(AccountType.USER, 1)
    finally:
        await redis.aclose()

    assert first == second
    assert first.model_dump(mode="json") == {
        "account_id": 1,
        "account_type": "user",
        "name": "Ali",
        "profile_complete": True,
    }
    assert database.reads == 1
    assert database.rollbacks == 1


async def test_parallel_cache_misses_share_one_database_read():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        summaries = await asyncio.gather(
            *(
                service.resolve(AccountType.USER, 1)
                for _ in range(50)
            )
        )
    finally:
        await redis.aclose()

    assert all(summary == summaries[0] for summary in summaries)
    assert database.reads == 1


async def test_user_and_business_profile_summaries_use_separate_keys():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        user = await service.resolve(AccountType.USER, 1)
        business = await service.resolve(AccountType.BUSINESS, 2)
        keys = {
            key async for key in redis.scan_iter("profile:me:v1:*")
        }
    finally:
        await redis.aclose()

    assert user.profile_complete is True
    assert business.profile_complete is True
    assert keys == {
        "profile:me:v1:user:1",
        "profile:me:v1:business:2",
    }


async def test_missing_profile_preserves_profile_not_found_error():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        with pytest.raises(ApiError) as raised:
            await service.resolve(AccountType.USER, 999)
        missing_cache = await redis.get("profile:me:v1:user:999")
    finally:
        await redis.aclose()

    assert raised.value.status_code == 404
    assert raised.value.code == "profile_not_found"
    assert missing_cache is None


async def test_invalid_cached_json_is_deleted_and_reloaded_from_database():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("profile:me:v1:user:1", "{broken-json")
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        summary = await service.resolve(AccountType.USER, 1)
        cached = await redis.get("profile:me:v1:user:1")
    finally:
        await redis.aclose()

    assert summary.name == "Ali"
    assert database.reads == 1
    assert cached is not None
    assert "{broken-json" not in cached


async def test_invalidate_deletes_only_the_selected_account_cache():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        await service.resolve(AccountType.USER, 1)
        await service.resolve(AccountType.BUSINESS, 2)
        await service.invalidate(AccountType.USER, 1)
        user_cache = await redis.get("profile:me:v1:user:1")
        business_cache = await redis.get(
            "profile:me:v1:business:2"
        )
    finally:
        await redis.aclose()

    assert user_cache is None
    assert business_cache is not None


async def test_invalidation_prevents_inflight_read_from_repopulating_cache():
    database = PausedDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        stale_read = asyncio.create_task(
            service.resolve(AccountType.USER, 1)
        )
        await database.read_started.wait()
        database.profiles[(UserProfile, 1)].name = "Yangi Ali"
        await service.invalidate(AccountType.USER, 1)
        database.allow_read_to_finish.set()
        stale = await stale_read
        cached_after_stale_read = await redis.get(
            "profile:me:v1:user:1"
        )
        fresh = await service.resolve(AccountType.USER, 1)
    finally:
        await redis.aclose()

    assert stale.name == "Ali"
    assert cached_after_stale_read is None
    assert fresh.name == "Yangi Ali"
    assert database.reads == 2


async def test_redis_failure_falls_back_to_database_and_invalidation_survives():
    database = CountingDatabase()
    service = ProfileSummaryService(
        database.session,
        BrokenRedis(),
        Settings(environment="test"),
    )

    summary = await service.resolve(AccountType.USER, 1)
    await service.invalidate(AccountType.USER, 1)

    assert summary.name == "Ali"
    assert database.reads == 1

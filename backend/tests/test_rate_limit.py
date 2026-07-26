import fakeredis.aioredis

from app.cache.rate_limit import consume_rate_limit


async def test_rate_limit_is_shared_and_atomic():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    first = await consume_rate_limit(redis, "search:user:42", 2, 60)
    second = await consume_rate_limit(redis, "search:user:42", 2, 60)
    third = await consume_rate_limit(redis, "search:user:42", 2, 60)

    assert (first.allowed, first.remaining) == (True, 1)
    assert (second.allowed, second.remaining) == (True, 0)
    assert (third.allowed, third.remaining) == (False, 0)
    assert third.retry_after_seconds >= 1

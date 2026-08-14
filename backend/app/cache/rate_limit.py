from dataclasses import dataclass
import time

from redis.asyncio import Redis


SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""
WEIGHTED_SCRIPT = """
local count = redis.call('INCRBY', KEYS[1], ARGV[2])
if count == tonumber(ARGV[2]) then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


def _result(count: int, ttl: int, limit: int) -> RateLimitResult:
    return RateLimitResult(
        allowed=count <= limit,
        remaining=max(0, limit - count),
        retry_after_seconds=max(1, ttl),
    )


async def consume_rate_limit(
    redis: Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> RateLimitResult:
    bucket = int(time.time()) // window_seconds
    count, ttl = await redis.eval(
        SCRIPT,
        1,
        f"rate:{key}:{bucket}",
        window_seconds,
    )
    return _result(int(count), int(ttl), limit)


async def consume_weighted_rate_limit(
    redis: Redis,
    key: str,
    *,
    cost: int,
    limit: int,
    window_seconds: int,
) -> RateLimitResult:
    if cost <= 0:
        raise ValueError("rate_limit_cost_must_be_positive")
    bucket = int(time.time()) // window_seconds
    count, ttl = await redis.eval(
        WEIGHTED_SCRIPT,
        1,
        f"rate:{key}:{bucket}",
        window_seconds,
        cost,
    )
    return _result(int(count), int(ttl), limit)

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


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


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
    count = int(count)
    ttl = max(1, int(ttl))
    return RateLimitResult(
        allowed=count <= limit,
        remaining=max(0, limit - count),
        retry_after_seconds=ttl,
    )

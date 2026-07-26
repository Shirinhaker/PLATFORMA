from redis.asyncio import Redis


class RedisClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self.client: Redis | None = None

    async def start(self) -> None:
        self.client = Redis.from_url(self.url, decode_responses=True)

    async def stop(self) -> None:
        if self.client is not None:
            await self.client.aclose()
        self.client = None

    async def ready(self) -> bool:
        if self.client is None:
            return False
        try:
            return bool(await self.client.ping())
        except Exception:
            return False

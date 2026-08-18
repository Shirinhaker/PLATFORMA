from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis


class RedisClient:
    def __init__(self, url: str, *, max_connections: int = 100) -> None:
        self.url = url
        self.max_connections = max_connections
        self.client: Redis | None = None

    async def start(self) -> None:
        # Chegara aniq belgilanmasa, yuqori yukda ulanishlar soni
        # nazoratsiz o'sadi va Redis ularni rad eta boshlaydi.
        self.client = Redis.from_url(
            self.url,
            decode_responses=True,
            max_connections=self.max_connections,
        )

    async def stop(self) -> None:
        if self.client is not None:
            await self.client.aclose()
        self.client = None

    async def ready(self) -> bool:
        if self.client is None:
            return False
        try:
            # redis-py stublari sync va async klientni bitta klass bilan
            # tasvirlaydi, shuning uchun `Awaitable[bool] | bool` chiqadi.
            # Bu yerda klient aniq async — `redis.asyncio.Redis`.
            return bool(await cast(Awaitable[bool], self.client.ping()))
        except Exception:
            return False

import logging
from typing import Any


logger = logging.getLogger(__name__)
CATALOG_CACHE_EPOCH_KEY = "public:catalog:epoch:v1"


class CatalogCacheEpoch:
    """Katalog o‘zgarganda eski qidiruv keshlarini kalit orqali chetlab o‘tadi."""

    def __init__(self, redis: Any) -> None:
        self._redis = redis
        self._local_epoch = 0

    async def current(self) -> int:
        connection = self._connection()
        if connection is None:
            return self._local_epoch
        try:
            value = int(await connection.get(CATALOG_CACHE_EPOCH_KEY) or 0)
            self._local_epoch = max(self._local_epoch, value)
        except Exception:
            logger.warning("Catalog cache epoch read failed; using local epoch.")
        return self._local_epoch

    async def bump(self) -> int:
        self._local_epoch += 1
        connection = self._connection()
        if connection is None:
            return self._local_epoch
        try:
            value = int(await connection.incr(CATALOG_CACHE_EPOCH_KEY))
            self._local_epoch = max(self._local_epoch, value)
        except Exception:
            logger.warning("Catalog cache epoch bump failed; using local epoch.")
        return self._local_epoch

    def _connection(self):
        client = getattr(self._redis, "client", None)
        if client is not None and not callable(client):
            return client
        if callable(getattr(self._redis, "get", None)):
            return self._redis
        return None

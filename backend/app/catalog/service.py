from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
import asyncio
import hashlib
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.repository import (
    ImageUrlProvider,
    get_public_catalog,
    list_public_catalog,
)
from app.catalog.schemas import (
    PublicCatalogItem,
    PublicCatalogParams,
    PublicCatalogResponse,
)
from app.core.config import Settings


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
CatalogLoader = Callable[
    [AsyncSession, PublicCatalogParams, ImageUrlProvider],
    Awaitable[PublicCatalogResponse],
]
CatalogDetailLoader = Callable[
    [AsyncSession, str, ImageUrlProvider],
    Awaitable[PublicCatalogItem | None],
]

logger = logging.getLogger(__name__)
_CACHE_PREFIX = "public:catalog:v1:"


class CatalogService:
    def __init__(
        self,
        session_factory: SessionFactory,
        redis: Any,
        settings: Settings,
        image_url_provider: ImageUrlProvider,
        *,
        list_loader: CatalogLoader = list_public_catalog,
        detail_loader: CatalogDetailLoader = get_public_catalog,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._settings = settings
        self._image_url_provider = image_url_provider
        self._list_loader = list_loader
        self._detail_loader = detail_loader
        self._tasks: dict[str, asyncio.Task] = {}

    async def list_items(
        self,
        params: PublicCatalogParams,
    ) -> PublicCatalogResponse:
        key = self._cache_key("list", params.model_dump(mode="json"))
        cached = await self._read(key, PublicCatalogResponse)
        if cached is not None:
            return cached
        return await self._single_flight(
            key,
            lambda: self._load_list(key, params),
        )

    async def get_item(self, public_id: str) -> PublicCatalogItem | None:
        key = self._cache_key("detail", {"public_id": public_id})
        cached = await self._read(key, PublicCatalogItem)
        if cached is not None:
            return cached
        return await self._single_flight(
            key,
            lambda: self._load_detail(key, public_id),
        )

    async def _load_list(self, key, params):
        async with self._session_factory() as session:
            value = await self._list_loader(
                session,
                params,
                self._image_url_provider,
            )
            await session.rollback()
        await self._write(key, value)
        return value

    async def _load_detail(self, key, public_id):
        async with self._session_factory() as session:
            value = await self._detail_loader(
                session,
                public_id,
                self._image_url_provider,
            )
            await session.rollback()
        if value is not None:
            await self._write(key, value)
        return value

    async def _single_flight(self, key, factory):
        task = self._tasks.get(key)
        if task is None:
            task = asyncio.create_task(factory())
            self._tasks[key] = task
            task.add_done_callback(
                lambda done: (
                    self._tasks.pop(key, None)
                    if self._tasks.get(key) is done
                    else None
                )
            )
        return await asyncio.shield(task)

    async def _read(self, key, model):
        redis = self._connection()
        if redis is None:
            return None
        try:
            payload = await redis.get(key)
            return model.model_validate_json(payload) if payload else None
        except Exception:
            logger.warning("Catalog cache read failed; using database.")
            return None

    async def _write(self, key, value):
        redis = self._connection()
        if redis is None:
            return
        try:
            await redis.set(
                key,
                value.model_dump_json(),
                ex=self._settings.public_search_cache_ttl_seconds,
            )
        except Exception:
            logger.warning("Catalog cache write failed; continuing.")

    def _connection(self):
        client = getattr(self._redis, "client", None)
        if client is not None and not callable(client):
            return client
        return self._redis if callable(getattr(self._redis, "get", None)) else None

    @staticmethod
    def _cache_key(scope: str, payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        return f"{_CACHE_PREFIX}{scope}:{digest}"


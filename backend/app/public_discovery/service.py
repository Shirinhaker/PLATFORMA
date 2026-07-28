from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
import asyncio
import hashlib
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.public_discovery.repository import search_public_profiles
from app.public_discovery.schemas import PublicSearchParams, PublicSearchResponse
from app.public_discovery.schemas import PublicResultType


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
SearchLoader = Callable[
    [AsyncSession, PublicSearchParams],
    Awaitable[PublicSearchResponse],
]

logger = logging.getLogger(__name__)
_CACHE_PREFIX = "public:search:v2:"


class PublicDiscoveryService:
    def __init__(
        self,
        session_factory: SessionFactory,
        redis: Any,
        settings: Settings,
        *,
        search_loader: SearchLoader | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._settings = settings
        if search_loader is None:
            async def configured_loader(session, params):
                if (
                    not settings.phase3c_public_enabled
                    and params.result_type
                    in (
                        PublicResultType.PRODUCT,
                        PublicResultType.SERVICE,
                    )
                ):
                    return PublicSearchResponse(
                        items=[],
                        page=params.page,
                        page_size=params.page_size,
                        total=0,
                    )
                return await search_public_profiles(
                    session,
                    params,
                    include_content=settings.phase3c_public_enabled,
                )

            self._search_loader = configured_loader
        else:
            self._search_loader = search_loader
        self._search_tasks: dict[str, asyncio.Task[PublicSearchResponse]] = {}

    async def search(
        self,
        params: PublicSearchParams,
    ) -> PublicSearchResponse:
        cache_key = self.cache_key(params)
        cached = await self._read_cache(cache_key)
        if cached is not None:
            return cached

        task = self._search_tasks.get(cache_key)
        if task is None:
            task = asyncio.create_task(self._load_and_cache(cache_key, params))
            self._search_tasks[cache_key] = task

            def clear_completed(
                completed: asyncio.Task[PublicSearchResponse],
            ) -> None:
                if self._search_tasks.get(cache_key) is completed:
                    self._search_tasks.pop(cache_key, None)

            task.add_done_callback(clear_completed)

        return await asyncio.shield(task)

    async def _load_and_cache(
        self,
        cache_key: str,
        params: PublicSearchParams,
    ) -> PublicSearchResponse:
        async with self._session_factory() as session:
            response = await self._search_loader(session, params)
            await session.rollback()

        if self._search_tasks.get(cache_key) is asyncio.current_task():
            await self._write_cache(cache_key, response)
        return response

    async def _read_cache(
        self,
        cache_key: str,
    ) -> PublicSearchResponse | None:
        redis = self._redis_connection()
        if redis is None:
            return None
        try:
            payload = await redis.get(cache_key)
        except Exception:
            logger.warning("Public search cache read failed; using database.")
            return None
        if payload is None:
            return None
        try:
            return PublicSearchResponse.model_validate(json.loads(payload))
        except (TypeError, ValueError, json.JSONDecodeError):
            try:
                await redis.delete(cache_key)
            except Exception:
                pass
            return None

    async def _write_cache(
        self,
        cache_key: str,
        response: PublicSearchResponse,
    ) -> None:
        redis = self._redis_connection()
        if redis is None:
            return
        payload = json.dumps(
            response.model_dump(mode="json"),
            separators=(",", ":"),
            sort_keys=True,
        )
        try:
            await redis.set(
                cache_key,
                payload,
                ex=self._settings.public_search_cache_ttl_seconds,
            )
        except Exception:
            logger.warning(
                "Public search cache write failed; continuing without cache."
            )

    def _redis_connection(self):
        client = getattr(self._redis, "client", None)
        if client is not None and not callable(client):
            return client
        if callable(getattr(self._redis, "get", None)):
            return self._redis
        return None

    @staticmethod
    def cache_key(params: PublicSearchParams) -> str:
        canonical = json.dumps(
            params.model_dump(mode="json"),
            separators=(",", ":"),
            sort_keys=True,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{_CACHE_PREFIX}{digest}"

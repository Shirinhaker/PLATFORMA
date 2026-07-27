import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.core.config import Settings
from app.profiles.repository import get_business_profile, get_user_profile
from app.profiles.schemas import MeRead


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

logger = logging.getLogger(__name__)

_CACHE_MISS = object()
_PROFILE_SUMMARY_CACHE_PREFIX = "profile:me:v1:"


class ProfileSummaryService:
    def __init__(
        self,
        session_factory: SessionFactory,
        redis: Any,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._settings = settings
        self._resolution_tasks: dict[str, asyncio.Task[MeRead]] = {}

    async def resolve(
        self,
        account_type: AccountType,
        account_id: int,
    ) -> MeRead:
        cache_key = self.cache_key(account_type, account_id)
        cached = await self._read_cached_summary(cache_key)
        if cached is not _CACHE_MISS:
            return cached

        task = self._resolution_tasks.get(cache_key)
        if task is None:
            task = asyncio.create_task(
                self._load_and_cache(account_type, account_id)
            )
            self._resolution_tasks[cache_key] = task

            def clear_completed(completed: asyncio.Task[MeRead]) -> None:
                if self._resolution_tasks.get(cache_key) is completed:
                    self._resolution_tasks.pop(cache_key, None)

            task.add_done_callback(clear_completed)

        return await asyncio.shield(task)

    async def invalidate(
        self,
        account_type: AccountType,
        account_id: int,
    ) -> None:
        cache_key = self.cache_key(account_type, account_id)
        self._resolution_tasks.pop(cache_key, None)
        redis = self._redis_connection()
        if redis is None:
            return
        try:
            await redis.delete(cache_key)
        except Exception:
            logger.warning(
                "Profile summary cache invalidation failed; TTL fallback remains."
            )

    async def _load_and_cache(
        self,
        account_type: AccountType,
        account_id: int,
    ) -> MeRead:
        cache_key = self.cache_key(account_type, account_id)
        async with self._session_factory() as session:
            if account_type is AccountType.USER:
                profile = await get_user_profile(session, account_id)
                profile_complete = bool(
                    profile.name.strip() and profile.phone.strip()
                )
            else:
                profile = await get_business_profile(session, account_id)
                profile_complete = all(
                    value.strip()
                    for value in (
                        profile.name,
                        profile.phone,
                        profile.direction,
                        profile.address,
                    )
                )

            summary = MeRead(
                account_id=profile.account_id,
                account_type=account_type,
                name=profile.name,
                profile_complete=profile_complete,
            )
            await session.rollback()

        if self._resolution_tasks.get(cache_key) is asyncio.current_task():
            await self._write_cached_summary(cache_key, summary)
        return summary

    async def _read_cached_summary(self, cache_key: str) -> MeRead | object:
        redis = self._redis_connection()
        if redis is None:
            return _CACHE_MISS

        try:
            payload = await redis.get(cache_key)
        except Exception:
            logger.warning("Profile summary cache read failed; using database.")
            return _CACHE_MISS

        if payload is None:
            return _CACHE_MISS

        try:
            return MeRead.model_validate(json.loads(payload))
        except (TypeError, ValueError, json.JSONDecodeError):
            try:
                await redis.delete(cache_key)
            except Exception:
                pass
            return _CACHE_MISS

    async def _write_cached_summary(
        self,
        cache_key: str,
        summary: MeRead,
    ) -> None:
        redis = self._redis_connection()
        if redis is None:
            return

        payload = json.dumps(
            summary.model_dump(mode="json"),
            separators=(",", ":"),
            sort_keys=True,
        )
        try:
            await redis.set(
                cache_key,
                payload,
                ex=self._settings.profile_summary_cache_ttl_seconds,
            )
        except Exception:
            logger.warning(
                "Profile summary cache write failed; continuing without cache."
            )

    def _redis_connection(self):
        client = getattr(self._redis, "client", None)
        if client is not None and not callable(client):
            return client
        if callable(getattr(self._redis, "get", None)):
            return self._redis
        return None

    @staticmethod
    def cache_key(account_type: AccountType, account_id: int) -> str:
        return (
            f"{_PROFILE_SUMMARY_CACHE_PREFIX}"
            f"{account_type.value}:{account_id}"
        )

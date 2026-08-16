"""Seans: yaratish, o'qish, bekor qilish.

Redis keshi va bazadagi yozuv bir joyda — kesh yiqilsa baza
zaxira bo'ladi.
"""

from __future__ import annotations

import asyncio
import json
import math
from datetime import datetime

from app.auth.repository import (
    lock_session,
)
from app.auth.repository import (
    resolve_session as resolve_stored_session,
)
from app.auth.schemas import (
    Authenticated,
    SessionIdentity,
)
from app.auth.security import (
    derive_csrf,
    sha256_token,
)
from app.auth.service_parts.base import AuthServiceBase
from app.auth.service_parts.helpers import (
    _CACHE_MISS,
    _CACHE_SESSION_SCRIPT,
    _REVOKE_CACHED_SESSION_SCRIPT,
    _SESSION_CACHE_PREFIX,
    _SESSION_REVOKED_PREFIX,
    _SESSION_TOUCH_INTERVAL,
    logger,
)


class SessionsMixin(AuthServiceBase):
    async def resolve_session(
        self,
        raw_token: str,
        now: datetime,
    ) -> SessionIdentity | None:
        cached = await self._read_cached_session(raw_token, now)
        if cached is not _CACHE_MISS:
            return cached

        cache_key = self._session_cache_key(raw_token)
        task = self._session_resolution_tasks.get(cache_key)
        if task is None:
            task = asyncio.create_task(
                self._resolve_session_from_database(raw_token, now)
            )
            self._session_resolution_tasks[cache_key] = task

            def clear_completed(completed):
                if self._session_resolution_tasks.get(cache_key) is completed:
                    self._session_resolution_tasks.pop(cache_key, None)

            task.add_done_callback(clear_completed)
        return await asyncio.shield(task)

    async def _resolve_session_from_database(
        self,
        raw_token: str,
        now: datetime,
    ) -> SessionIdentity | None:
        async with self._session_factory() as session:
            stored = await resolve_stored_session(session, raw_token, now)
            if stored is None:
                await session.rollback()
                return None
            auth_session, account = stored
            identity = SessionIdentity(
                account_id=account.id,
                account_type=account.account_type,
                login=account.login,
                csrf_token=derive_csrf(
                    raw_token,
                    self._settings.csrf_secret,
                ),
                expires_at=auth_session.expires_at,
            )
            if auth_session.last_used_at <= now - _SESSION_TOUCH_INTERVAL:
                auth_session.last_used_at = now
                await session.commit()
            else:
                await session.rollback()
        await self._cache_session(
            raw_token,
            identity,
            now,
            last_used_at=auth_session.last_used_at,
        )
        return identity

    async def revoke_session(
        self,
        raw_token: str,
        now: datetime,
    ) -> None:
        async with self._session_factory() as session:
            try:
                auth_session = await lock_session(session, raw_token)
                if auth_session is not None and auth_session.revoked_at is None:
                    auth_session.revoked_at = now
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        await self._revoke_cached_session(raw_token)

    async def _cache_authenticated_session(
        self,
        authenticated: Authenticated,
        now: datetime,
    ) -> None:
        if authenticated.login is None:
            return
        await self._cache_session(
            authenticated.session_token,
            SessionIdentity(
                account_id=authenticated.account_id,
                account_type=authenticated.account_type,
                login=authenticated.login,
                csrf_token=authenticated.csrf_token,
                expires_at=authenticated.expires_at,
            ),
            now,
            last_used_at=now,
        )

    async def _read_cached_session(
        self,
        raw_token: str,
        now: datetime,
    ) -> SessionIdentity | None | object:
        redis = self._redis_connection()
        if redis is None:
            return _CACHE_MISS

        cache_key = self._session_cache_key(raw_token)
        revoked_key = self._session_revoked_key(raw_token)
        try:
            payload, revoked = await redis.mget(cache_key, revoked_key)
        except Exception:
            logger.warning("Session cache read failed; using database.")
            return _CACHE_MISS

        if revoked is not None:
            return None
        if payload is None:
            return _CACHE_MISS

        try:
            cached = json.loads(payload)
            last_used_at = datetime.fromisoformat(cached.pop("last_used_at"))
            cached["csrf_token"] = derive_csrf(
                raw_token,
                self._settings.csrf_secret,
            )
            identity = SessionIdentity.model_validate(cached)
        except (TypeError, ValueError, json.JSONDecodeError):
            try:
                await redis.delete(cache_key)
            except Exception:
                pass
            return _CACHE_MISS

        if identity.expires_at <= now:
            try:
                await redis.delete(cache_key)
            except Exception:
                pass
            return None
        if last_used_at <= now - _SESSION_TOUCH_INTERVAL:
            try:
                await redis.delete(cache_key)
            except Exception:
                pass
            return _CACHE_MISS
        return identity

    async def _cache_session(
        self,
        raw_token: str,
        identity: SessionIdentity,
        now: datetime,
        *,
        last_used_at: datetime,
    ) -> None:
        redis = self._redis_connection()
        if redis is None:
            return

        remaining_seconds = math.ceil((identity.expires_at - now).total_seconds())
        if remaining_seconds <= 0:
            return
        ttl_seconds = min(
            self._settings.session_cache_ttl_seconds,
            remaining_seconds,
        )
        cached = identity.model_dump(
            mode="json",
            exclude={"csrf_token"},
        )
        cached["last_used_at"] = last_used_at.isoformat()
        payload = json.dumps(
            cached,
            separators=(",", ":"),
            sort_keys=True,
        )
        try:
            await redis.eval(
                _CACHE_SESSION_SCRIPT,
                2,
                self._session_cache_key(raw_token),
                self._session_revoked_key(raw_token),
                payload,
                ttl_seconds,
            )
        except Exception:
            logger.warning("Session cache write failed; continuing without cache.")

    async def _revoke_cached_session(self, raw_token: str) -> None:
        redis = self._redis_connection()
        if redis is None:
            return
        revoked_ttl_seconds = max(
            60,
            self._settings.session_cache_ttl_seconds * 2,
        )
        try:
            await redis.eval(
                _REVOKE_CACHED_SESSION_SCRIPT,
                2,
                self._session_revoked_key(raw_token),
                self._session_cache_key(raw_token),
                revoked_ttl_seconds,
            )
        except Exception:
            logger.warning(
                "Session cache invalidation failed; database session is revoked."
            )

    def _redis_connection(self):
        client = getattr(self._redis, "client", None)
        if client is not None and not callable(client):
            return client
        if callable(getattr(self._redis, "mget", None)):
            return self._redis
        return None

    @staticmethod
    def _session_cache_key(raw_token: str) -> str:
        return f"{_SESSION_CACHE_PREFIX}{sha256_token(raw_token)}"

    @staticmethod
    def _session_revoked_key(raw_token: str) -> str:
        return f"{_SESSION_REVOKED_PREFIX}{sha256_token(raw_token)}"

"""Media manbasi: lokal disk yoki Telegram."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePosixPath

import httpx

from app.legacy_migration.media.constants import (
    MediaResolution,
)
from app.legacy_migration.media.reading import (
    _read_async_media,
    _read_local_media,
)
from app.legacy_migration.model import (
    MediaMigration,
)


class LocalMediaResolver:
    def __init__(
        self,
        roots: Iterable[Path],
        *,
        max_bytes: int = 100 * 1024 * 1024,
    ) -> None:
        self.roots = tuple(Path(root).resolve() for root in roots)
        self.max_bytes = max_bytes

    async def resolve(self, reference: str) -> MediaResolution:
        path = self._resolve_path(reference)
        if path is None:
            return MediaResolution(None, "media.path_outside_roots")
        if not path.is_file():
            return MediaResolution(None, "media.missing")
        return _read_local_media(path, max_bytes=self.max_bytes)

    def _resolve_path(self, reference: str) -> Path | None:
        normalized = reference.replace("\\", "/").lstrip("/")
        relative = PurePosixPath(normalized)
        if not normalized or relative.is_absolute() or ".." in relative.parts:
            return None

        for root in self.roots:
            parts = relative.parts
            if parts and parts[0] == root.name:
                parts = parts[1:]
            candidate = root.joinpath(*parts).resolve()
            if candidate == root or root in candidate.parents:
                return candidate
        return None


class TelegramMediaResolver:
    def __init__(
        self,
        bot_token: str,
        *,
        max_bytes: int = 100 * 1024 * 1024,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.bot_token = bot_token
        self.max_bytes = max_bytes
        self.client = client

    async def resolve(self, reference: str) -> MediaResolution:
        if not self.bot_token or not reference:
            return MediaResolution(None, "media.telegram_unavailable")
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=30)
        try:
            response = await client.get(
                f"https://api.telegram.org/bot{self.bot_token}/getFile",
                params={"file_id": reference},
            )
            response.raise_for_status()
            payload = response.json()
            file_path = (payload.get("result") or {}).get("file_path")
            if not payload.get("ok") or not file_path:
                return MediaResolution(None, "media.missing")
            async with client.stream(
                "GET",
                f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}",
            ) as download:
                download.raise_for_status()
                return await _read_async_media(
                    download.aiter_bytes(),
                    max_bytes=self.max_bytes,
                )
        except (httpx.HTTPError, ValueError, TypeError):
            return MediaResolution(None, "media.telegram_failed")
        finally:
            if owns_client:
                await client.aclose()


def _resolver_for_reference(
    record: MediaMigration,
    reference: str,
    *,
    local,
    telegram,
):
    if record.entity_type not in {"listing_media"}:
        return local
    normalized = reference.replace("\\", "/")
    if normalized.startswith("/") or "/" in normalized:
        return local
    return telegram


def _media_roots(value: str) -> tuple[Path, ...]:
    return tuple(Path(item.strip()) for item in value.split(",") if item.strip())

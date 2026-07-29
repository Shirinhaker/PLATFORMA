from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from pathlib import Path, PurePosixPath
import sqlite3
from tempfile import SpooledTemporaryFile
from typing import BinaryIO

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.advertisements.model import Advertisement
from app.catalog.model import CatalogItem
from app.core.config import Settings
from app.legacy_migration.model import (
    LegacyIdMap,
    MediaMigration,
    MediaMigrationState,
    MigrationRun,
)
from app.legacy_migration.reconcile import StageResult
from app.listings.model import ListingMedia
from app.media.storage import R2Storage


CONTENT_TYPE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
}


@dataclass(frozen=True)
class ResolvedMedia:
    stream: BinaryIO
    content_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class MediaResolution:
    media: ResolvedMedia | None
    code: str


def sniff_media_type(header: bytes) -> str | None:
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if (
        len(header) >= 12
        and header.startswith(b"RIFF")
        and header[8:12] == b"WEBP"
    ):
        return "image/webp"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "video/mp4"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    return None


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


def _read_local_media(path: Path, *, max_bytes: int) -> MediaResolution:
    with path.open("rb") as source:
        return _read_chunks(iter(lambda: source.read(1024 * 1024), b""), max_bytes)


async def _read_async_media(chunks, *, max_bytes: int) -> MediaResolution:
    stream = SpooledTemporaryFile(max_size=min(max_bytes, 8 * 1024 * 1024))
    digest = hashlib.sha256()
    header = b""
    size = 0
    async for chunk in chunks:
        size += len(chunk)
        if size > max_bytes:
            stream.close()
            return MediaResolution(None, "media.too_large")
        if len(header) < 16:
            header += chunk[: 16 - len(header)]
        digest.update(chunk)
        stream.write(chunk)
    return _finished_media(stream, header, size, digest.hexdigest())


def _read_chunks(chunks, max_bytes: int) -> MediaResolution:
    stream = SpooledTemporaryFile(max_size=min(max_bytes, 8 * 1024 * 1024))
    digest = hashlib.sha256()
    header = b""
    size = 0
    for chunk in chunks:
        size += len(chunk)
        if size > max_bytes:
            stream.close()
            return MediaResolution(None, "media.too_large")
        if len(header) < 16:
            header += chunk[: 16 - len(header)]
        digest.update(chunk)
        stream.write(chunk)
    return _finished_media(stream, header, size, digest.hexdigest())


def _finished_media(
    stream: BinaryIO,
    header: bytes,
    size: int,
    digest: str,
) -> MediaResolution:
    content_type = sniff_media_type(header)
    if content_type is None:
        stream.close()
        return MediaResolution(None, "media.invalid_type")
    stream.seek(0)
    return MediaResolution(
        ResolvedMedia(stream, content_type, size, digest),
        "",
    )


async def migrate_media(
    session: AsyncSession,
    source: sqlite3.Connection,
    storage: R2Storage,
    settings: Settings,
    run: MigrationRun,
    *,
    local_resolver=None,
    telegram_resolver=None,
) -> StageResult:
    local = local_resolver or LocalMediaResolver(
        _media_roots(settings.legacy_media_roots),
        max_bytes=settings.legacy_media_max_bytes,
    )
    telegram = telegram_resolver or TelegramMediaResolver(
        settings.telegram_bot_token,
        max_bytes=settings.legacy_media_max_bytes,
    )
    counters = {"created": 0, "reused": 0, "updated": 0}
    records = (
        await session.scalars(
            select(MediaMigration)
            .where(MediaMigration.migration_run_id == run.id)
            .order_by(MediaMigration.id)
        )
    ).all()
    for record in records:
        if record.state is MediaMigrationState.COPIED:
            verified = storage.verify_object(
                record.destination_object_key,
                expected_size=record.size_bytes,
                expected_sha256=record.sha256,
                expected_content_type=record.content_type,
            )
            if verified:
                await _set_target_object_key(
                    session,
                    record,
                    record.destination_object_key,
                )
                counters["reused"] += 1
                continue
            record.attempts += 1
            record.updated_at = datetime.now(UTC)
            _mark_failure(
                record,
                MediaMigrationState.FAILED,
                "media.r2_verification_failed",
            )
            counters["updated"] += 1
            continue
        record.attempts += 1
        record.updated_at = datetime.now(UTC)
        reference = _source_reference(source, record)
        if not reference:
            _mark_failure(record, MediaMigrationState.MISSING, "media.missing")
            continue
        resolver = _resolver_for_reference(
            record,
            reference,
            local=local,
            telegram=telegram,
        )
        resolution = await resolver.resolve(reference)
        if resolution.media is None:
            state = (
                MediaMigrationState.MISSING
                if resolution.code == "media.missing"
                else MediaMigrationState.INVALID
                if resolution.code
                in {"media.path_outside_roots", "media.too_large", "media.invalid_type"}
                else MediaMigrationState.FAILED
            )
            _mark_failure(record, state, resolution.code)
            continue
        await _copy_media(session, storage, run, record, resolution.media)
        if record.state is MediaMigrationState.COPIED:
            counters["created"] += 1
        else:
            counters["updated"] += 1
    await session.flush()
    return StageResult(**counters)


async def _copy_media(
    session: AsyncSession,
    storage: R2Storage,
    run: MigrationRun,
    record: MediaMigration,
    media: ResolvedMedia,
) -> None:
    stored = storage.put_migration_object(
        stream=media.stream,
        run_id=run.id,
        entity_type=record.entity_type,
        legacy_id=record.legacy_id,
        slot=record.slot,
        sha256=media.sha256,
        content_type=media.content_type,
        size_bytes=media.size_bytes,
        suffix=CONTENT_TYPE_SUFFIXES[media.content_type],
    )
    verified = storage.verify_object(
        stored.object_key,
        expected_size=media.size_bytes,
        expected_sha256=media.sha256,
        expected_content_type=media.content_type,
    )
    if not verified:
        _mark_failure(
            record,
            MediaMigrationState.FAILED,
            "media.r2_verification_failed",
        )
        return
    record.destination_object_key = stored.object_key
    record.sha256 = media.sha256
    record.content_type = media.content_type
    record.size_bytes = media.size_bytes
    record.state = MediaMigrationState.COPIED
    record.last_error_code = ""
    await _set_target_object_key(session, record, stored.object_key)


def _mark_failure(
    record: MediaMigration,
    state: MediaMigrationState,
    code: str,
) -> None:
    record.state = state
    record.last_error_code = code


async def _set_target_object_key(
    session: AsyncSession,
    record: MediaMigration,
    object_key: str,
) -> None:
    mapping = (
        await session.scalars(
            select(LegacyIdMap).where(
                LegacyIdMap.entity_type == record.entity_type,
                LegacyIdMap.legacy_id == record.legacy_id,
            )
        )
    ).one_or_none()
    if mapping is None or mapping.target_id is None:
        return
    if record.entity_type == "catalog_item":
        target = await session.get(CatalogItem, mapping.target_id)
        if target is not None:
            target.image_object_key = object_key
    elif record.entity_type == "listing_media":
        target = await session.get(ListingMedia, mapping.target_id)
        if target is not None:
            target.object_key = object_key
            target.migration_state = "copied"
    elif record.entity_type == "advertisement":
        target = await session.get(Advertisement, mapping.target_id)
        if target is not None:
            field = (
                "mobile_image_object_key"
                if record.slot == "mobile"
                else "desktop_image_object_key"
            )
            setattr(target, field, object_key)


def _source_reference(
    source: sqlite3.Connection,
    record: MediaMigration,
) -> str:
    table, column = {
        ("catalog_item", "primary"): ("items", "photo_file"),
        ("listing_media", "primary"): ("listing_media", "tg_file_id"),
        ("advertisement", "desktop"): ("advertisements", "image_file"),
        ("advertisement", "mobile"): (
            "advertisements",
            "mobile_image_file",
        ),
    }.get((record.entity_type, record.slot), ("", ""))
    if not table:
        return ""
    try:
        row = source.execute(
            f"SELECT {column} FROM {table} WHERE id = ?",
            (record.legacy_id,),
        ).fetchone()
    except sqlite3.Error:
        return ""
    if row is None:
        return ""
    value = row[0]
    return str(value).strip() if value is not None else ""


def _resolver_for_reference(
    record: MediaMigration,
    reference: str,
    *,
    local,
    telegram,
):
    if record.entity_type != "listing_media":
        return local
    normalized = reference.replace("\\", "/")
    if normalized.startswith("/") or "/" in normalized:
        return local
    return telegram


def _media_roots(value: str) -> tuple[Path, ...]:
    return tuple(Path(item.strip()) for item in value.split(",") if item.strip())

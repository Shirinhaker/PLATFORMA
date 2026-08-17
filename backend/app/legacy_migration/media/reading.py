"""Fayl o'qish va media turini aniqlash."""

from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import BinaryIO

from app.legacy_migration.media.constants import (
    MediaResolution,
    ResolvedMedia,
)


def sniff_media_type(header: bytes) -> str | None:
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "video/mp4"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    return None


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

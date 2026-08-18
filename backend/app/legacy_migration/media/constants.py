"""Media havolasi va yechim natijasi shakllari."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

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

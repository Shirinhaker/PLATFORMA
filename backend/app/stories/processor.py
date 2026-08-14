from __future__ import annotations

import asyncio
from dataclasses import dataclass
import math
from pathlib import Path
import subprocess
import tempfile

from app.accounts.model import AccountType
from app.media.storage import R2Storage


STORY_TTL_SECONDS = 24 * 60 * 60
MAX_ACTIVE_STORIES = 10
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 100 * 1024 * 1024
MAX_VIDEO_SECONDS = 60.0
MAX_CAPTION_LENGTH = 200

IMAGE_MIMES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
VIDEO_MIMES = {"video/mp4", "video/quicktime", "video/webm"}


class StoryValidationError(ValueError):
    """Foydalanuvchiga ko‘rsatiladigan v1656 validatsiya xatosi."""


@dataclass(frozen=True)
class ValidatedStoryMedia:
    media_type: str
    mime_type: str
    caption: str
    duration_seconds: float


@dataclass(frozen=True)
class ProcessedStoryMedia:
    media_type: str
    media_object_key: str
    thumbnail_object_key: str
    mime_type: str
    caption: str
    duration_seconds: float


def sniff_media_type(data: bytes) -> str:
    head = bytes(data or b"")[:32]
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "video/mp4"
    return ""


def validate_story_upload(
    *,
    claimed_type: str,
    actual_type: str,
    size_bytes: int,
    duration_seconds: float,
    caption: str,
) -> ValidatedStoryMedia:
    claimed = (claimed_type or "").split(";", 1)[0].strip().lower()
    actual = (actual_type or "").strip().lower()
    clean_caption = (caption or "").strip()
    if len(clean_caption) > MAX_CAPTION_LENGTH:
        raise StoryValidationError("Istoriya matni 200 belgidan oshmasin.")
    if claimed.startswith("image/") and not actual.startswith("image/"):
        raise StoryValidationError("Tanlangan fayl rasm formatiga mos emas.")
    if claimed.startswith("video/") and not actual.startswith("video/"):
        raise StoryValidationError("Tanlangan fayl video formatiga mos emas.")
    if actual in IMAGE_MIMES:
        if size_bytes <= 0 or size_bytes > MAX_IMAGE_BYTES:
            raise StoryValidationError("Rasm hajmi 10 MB dan oshmasin.")
        return ValidatedStoryMedia(
            media_type="image",
            mime_type="image/jpeg" if actual == "image/jpg" else actual,
            caption=clean_caption,
            duration_seconds=0.0,
        )
    if actual in VIDEO_MIMES:
        if size_bytes <= 0 or size_bytes > MAX_VIDEO_BYTES:
            raise StoryValidationError("Video hajmi 100 MB dan oshmasin.")
        try:
            seconds = float(duration_seconds)
        except (TypeError, ValueError):
            seconds = 0.0
        if not math.isfinite(seconds) or seconds <= 0 or seconds > MAX_VIDEO_SECONDS:
            raise StoryValidationError("Video 60 soniyadan oshmasin.")
        return ValidatedStoryMedia(
            media_type="video",
            mime_type=actual,
            caption=clean_caption,
            duration_seconds=seconds,
        )
    raise StoryValidationError(
        "Istoriya uchun JPG, PNG, WEBP, MP4, MOV yoki WEBM fayl tanlang."
    )


def probe_video_seconds(path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        seconds = float(result.stdout.strip())
    except (FileNotFoundError, subprocess.SubprocessError, ValueError) as exc:
        raise StoryValidationError(
            "Video tekshirilmadi. Serverda FFmpeg sozlamasini tekshiring."
        ) from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise StoryValidationError("Video davomiyligi aniqlanmadi.")
    return seconds


def transcode_video(source: Path, output: Path, thumbnail: Path) -> None:
    try:
        subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-y", "-i", str(source),
                "-t", "60", "-vf",
                "scale=720:-2:force_original_aspect_ratio=decrease",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
                "-c:a", "aac", "-movflags", "+faststart", str(output),
            ],
            capture_output=True,
            timeout=180,
            check=True,
        )
        subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-y", "-ss", "0", "-i",
                str(output), "-frames:v", "1", "-vf", "scale=480:-2",
                str(thumbnail),
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        raise StoryValidationError(
            "Video qayta ishlanmadi. Serverda FFmpeg sozlamasini tekshiring."
        ) from exc


class StoryMediaProcessor:
    def __init__(self, storage: R2Storage) -> None:
        self._storage = storage

    async def process(
        self,
        *,
        owner_type: AccountType,
        owner_id: int,
        object_key: str,
        claimed_type: str,
        claimed_size: int,
        caption: str,
    ) -> ProcessedStoryMedia:
        expected = f"private/{owner_type.value}/{owner_id}/story_"
        if not object_key.startswith(expected):
            raise StoryValidationError("Bu media obyekti akkauntga tegishli emas.")
        return await asyncio.to_thread(
            self._process_sync,
            owner_type,
            owner_id,
            object_key,
            claimed_type,
            claimed_size,
            caption,
        )

    def _process_sync(
        self,
        owner_type: AccountType,
        owner_id: int,
        object_key: str,
        claimed_type: str,
        claimed_size: int,
        caption: str,
    ) -> ProcessedStoryMedia:
        with tempfile.TemporaryDirectory(prefix="koprik-story-") as folder:
            root = Path(folder)
            source = root / "source"
            info = self._storage.download_to_file(object_key, source)
            if info.size_bytes != claimed_size:
                raise StoryValidationError("Yuklangan fayl hajmi mos kelmadi.")
            with source.open("rb") as stream:
                actual_type = sniff_media_type(stream.read(32))
            duration = (
                probe_video_seconds(source)
                if actual_type.startswith("video/")
                else 0.0
            )
            validated = validate_story_upload(
                claimed_type=claimed_type,
                actual_type=actual_type,
                size_bytes=info.size_bytes,
                duration_seconds=duration,
                caption=caption,
            )
            if validated.media_type == "image":
                return ProcessedStoryMedia(
                    media_type="image",
                    media_object_key=object_key,
                    thumbnail_object_key=object_key,
                    mime_type=validated.mime_type,
                    caption=validated.caption,
                    duration_seconds=0,
                )

            output = root / "story.mp4"
            thumbnail = root / "story.jpg"
            transcode_video(source, output, thumbnail)
            media_key = ""
            thumbnail_key = ""
            try:
                media_key = self._storage.put_story_file(
                    owner_type=owner_type,
                    owner_id=owner_id,
                    purpose="story_video_processed",
                    path=output,
                    content_type="video/mp4",
                    suffix=".mp4",
                )
                thumbnail_key = self._storage.put_story_file(
                    owner_type=owner_type,
                    owner_id=owner_id,
                    purpose="story_thumbnail",
                    path=thumbnail,
                    content_type="image/jpeg",
                    suffix=".jpg",
                )
            except Exception:
                for key in {media_key, thumbnail_key}:
                    if key:
                        try:
                            self._storage.delete_object(key)
                        except Exception:
                            pass
                raise
            self._storage.delete_object(object_key)
            return ProcessedStoryMedia(
                media_type="video",
                media_object_key=media_key,
                thumbnail_object_key=thumbnail_key,
                mime_type="video/mp4",
                caption=validated.caption,
                duration_seconds=validated.duration_seconds,
            )

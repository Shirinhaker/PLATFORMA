from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import secrets
from typing import Literal

import boto3

from app.accounts.model import AccountType
from app.core.config import Settings


PROFILE_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
LISTING_IMAGE_TYPES = {
    **PROFILE_IMAGE_TYPES,
    "image/heic": ".heic",
    "image/heif": ".heif",
}
LISTING_VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-m4v": ".m4v",
}
STORY_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_PROFILE_IMAGE_BYTES = 8 * 1024 * 1024
MAX_LISTING_IMAGE_BYTES = 10 * 1024 * 1024
MAX_LISTING_VIDEO_BYTES = 50 * 1024 * 1024
MAX_STORY_IMAGE_BYTES = 10 * 1024 * 1024
MAX_STORY_VIDEO_BYTES = 100 * 1024 * 1024
MAX_SPECIALIST_PORTFOLIO_BYTES = 30 * 1024 * 1024
PENDING_UPLOAD_TTL = timedelta(hours=24)

MediaPurpose = Literal[
    "avatar", "logo", "payment_qr", "listing_photo", "listing_video",
    "order_chat_image", "chat_image", "payment_receipt", "advertisement_image",
    "story_image", "story_video", "specialist_credential", "specialist_offer_image",
    "specialist_portfolio_image", "specialist_portfolio_video",
]


class UploadRejected(ValueError):
    pass


@dataclass(frozen=True)
class UploadGrant:
    object_key: str
    pending_object_key: str
    purpose: str
    upload_url: str
    method: str
    headers: dict[str, str]
    expires_in_seconds: int


@dataclass(frozen=True)
class StoredObject:
    object_key: str
    size_bytes: int
    sha256: str
    content_type: str


@dataclass(frozen=True)
class DownloadedObject:
    size_bytes: int
    content_type: str


def _upload_rule(
    owner_type: AccountType,
    purpose: MediaPurpose,
    content_type: str,
    size_bytes: int,
) -> tuple[str, int]:
    profile_purpose = (
        owner_type is AccountType.USER and purpose == "avatar"
    ) or (
        owner_type is AccountType.BUSINESS
        and purpose in {"logo", "payment_qr"}
    )
    general_purpose = purpose in {
        "listing_photo", "listing_video", "order_chat_image", "chat_image",
        "story_image", "story_video", "payment_receipt", "advertisement_image",
    }
    specialist_purpose = (
        owner_type is AccountType.USER
        and purpose in {
            "specialist_credential", "specialist_offer_image",
            "specialist_portfolio_image", "specialist_portfolio_video",
        }
    )
    if not profile_purpose and not general_purpose and not specialist_purpose:
        raise UploadRejected("Bu media turi akkauntga mos emas.")

    if purpose in {
        "specialist_credential", "specialist_offer_image",
        "specialist_portfolio_image",
    }:
        if content_type not in STORY_IMAGE_TYPES:
            raise UploadRejected("JPG, PNG yoki WEBP fayl tanlang.")
        maximum = (
            MAX_SPECIALIST_PORTFOLIO_BYTES
            if purpose == "specialist_portfolio_image"
            else MAX_PROFILE_IMAGE_BYTES
        )
        if not 1 <= size_bytes <= maximum:
            limit = 30 if purpose == "specialist_portfolio_image" else 8
            raise UploadRejected(f"Fayl hajmi {limit} MB dan oshmasin.")
        return STORY_IMAGE_TYPES[content_type], maximum

    if purpose == "specialist_portfolio_video":
        if content_type not in LISTING_VIDEO_TYPES:
            raise UploadRejected("MP4, WEBM yoki MOV fayl tanlang.")
        if not 1 <= size_bytes <= MAX_SPECIALIST_PORTFOLIO_BYTES:
            raise UploadRejected("Fayl hajmi 30 MB dan oshmasin.")
        return LISTING_VIDEO_TYPES[content_type], MAX_SPECIALIST_PORTFOLIO_BYTES

    if purpose in {
        "listing_photo", "order_chat_image", "chat_image", "payment_receipt",
        "advertisement_image", "story_image",
    }:
        allowed_images = (
            STORY_IMAGE_TYPES if purpose == "story_image" else LISTING_IMAGE_TYPES
        )
        if content_type not in allowed_images:
            if purpose == "story_image":
                raise UploadRejected("JPG, PNG yoki WEBP fayl tanlang.")
            raise UploadRejected("JPG, PNG, WEBP, GIF yoki HEIC fayl tanlang.")
        maximum = (
            MAX_PROFILE_IMAGE_BYTES
            if purpose in {"order_chat_image", "chat_image", "payment_receipt"}
            else (
                MAX_STORY_IMAGE_BYTES
                if purpose == "story_image"
                else MAX_LISTING_IMAGE_BYTES
            )
        )
        if not 1 <= size_bytes <= maximum:
            limit = 8 if purpose in {"order_chat_image", "chat_image", "payment_receipt"} else 10
            raise UploadRejected(f"Fayl hajmi {limit} MB dan oshmasin.")
        return allowed_images[content_type], maximum

    if purpose in {"listing_video", "story_video"}:
        if content_type not in LISTING_VIDEO_TYPES:
            raise UploadRejected("MP4, WEBM yoki MOV fayl tanlang.")
        maximum = (
            MAX_STORY_VIDEO_BYTES
            if purpose == "story_video"
            else MAX_LISTING_VIDEO_BYTES
        )
        if not 1 <= size_bytes <= maximum:
            limit = 100 if purpose == "story_video" else 50
            raise UploadRejected(f"Fayl hajmi {limit} MB dan oshmasin.")
        return LISTING_VIDEO_TYPES[content_type], maximum

    if content_type not in PROFILE_IMAGE_TYPES:
        raise UploadRejected("Rasm turi ruxsat etilmagan.")
    if not 1 <= size_bytes <= MAX_PROFILE_IMAGE_BYTES:
        raise UploadRejected("Rasm hajmi 8 MB dan oshmasin.")
    return PROFILE_IMAGE_TYPES[content_type], MAX_PROFILE_IMAGE_BYTES


class R2Storage:
    def __init__(self, client, *, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def create_upload_grant(
        self,
        *,
        owner_type: AccountType,
        owner_id: int,
        purpose: MediaPurpose,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> UploadGrant:
        del filename
        suffix, _maximum = _upload_rule(
            owner_type,
            purpose,
            content_type,
            size_bytes,
        )
        token = secrets.token_hex(16)
        basename = f"{token}{suffix}"
        object_key = (
            f"private/{owner_type.value}/{owner_id}/{purpose}/{basename}"
        )
        pending_object_key = (
            f"pending/{owner_type.value}/{owner_id}/{purpose}/{basename}"
        )
        return self._presigned_put(
            object_key=object_key,
            pending_object_key=pending_object_key,
            purpose=purpose,
            content_type=content_type,
            size_bytes=size_bytes,
            expires_in=300,
        )

    def finalize_upload(
        self,
        *,
        owner_type: AccountType,
        owner_id: int,
        purpose: MediaPurpose,
        pending_object_key: str,
        object_key: str,
    ) -> str:
        pending_prefix = f"pending/{owner_type.value}/{owner_id}/{purpose}/"
        final_prefix = f"private/{owner_type.value}/{owner_id}/{purpose}/"
        if not pending_object_key.startswith(pending_prefix):
            raise UploadRejected("Vaqtinchalik media kaliti akkauntga tegishli emas.")
        if not object_key.startswith(final_prefix):
            raise UploadRejected("Media kaliti akkauntga tegishli emas.")
        pending_name = pending_object_key.removeprefix(pending_prefix)
        final_name = object_key.removeprefix(final_prefix)
        if not pending_name or pending_name != final_name or "/" in pending_name:
            raise UploadRejected("Media kaliti noto‘g‘ri.")

        response = self.client.head_object(
            Bucket=self.bucket,
            Key=pending_object_key,
        )
        actual_size = int(response.get("ContentLength") or 0)
        actual_type = str(response.get("ContentType") or "").split(";", 1)[0].strip().lower()
        suffix, _maximum = _upload_rule(
            owner_type,
            purpose,
            actual_type,
            actual_size,
        )
        if not pending_name.endswith(suffix):
            raise UploadRejected("Media kengaytmasi fayl turiga mos emas.")

        self.client.copy_object(
            Bucket=self.bucket,
            CopySource={"Bucket": self.bucket, "Key": pending_object_key},
            Key=object_key,
            ContentType=actual_type,
            MetadataDirective="REPLACE",
            Metadata={"validated": "1"},
        )
        try:
            self.client.delete_object(Bucket=self.bucket, Key=pending_object_key)
        except Exception:
            # Worker stale pending obyektni keyin tozalaydi.
            pass
        return object_key

    def ready(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False

    def cleanup_pending_uploads(
        self,
        *,
        now: datetime | None = None,
        max_delete: int = 500,
    ) -> int:
        stamp = now or datetime.now(UTC)
        cutoff = stamp - PENDING_UPLOAD_TTL
        continuation: str | None = None
        deleted = 0
        while deleted < max_delete:
            kwargs = {
                "Bucket": self.bucket,
                "Prefix": "pending/",
                "MaxKeys": min(1000, max_delete - deleted),
            }
            if continuation:
                kwargs["ContinuationToken"] = continuation
            response = self.client.list_objects_v2(**kwargs)
            for row in response.get("Contents") or []:
                modified = row.get("LastModified")
                key = str(row.get("Key") or "")
                if key and modified is not None and modified <= cutoff:
                    self.client.delete_object(Bucket=self.bucket, Key=key)
                    deleted += 1
                    if deleted >= max_delete:
                        break
            if not response.get("IsTruncated") or deleted >= max_delete:
                break
            continuation = str(response.get("NextContinuationToken") or "") or None
            if continuation is None:
                break
        return deleted

    def put_migration_object(
        self,
        *,
        stream,
        run_id: int,
        entity_type: str,
        legacy_id: int,
        slot: str,
        sha256: str,
        content_type: str,
        size_bytes: int,
        suffix: str,
    ) -> StoredObject:
        object_key = (
            f"migration/{run_id}/{entity_type}/{legacy_id}/{slot}/"
            f"{sha256}{suffix}"
        )
        self.client.upload_fileobj(
            stream,
            self.bucket,
            object_key,
            ExtraArgs={
                "ContentType": content_type,
                "Metadata": {"sha256": sha256},
            },
        )
        return StoredObject(
            object_key=object_key,
            size_bytes=size_bytes,
            sha256=sha256,
            content_type=content_type,
        )

    def verify_object(
        self,
        object_key: str,
        *,
        expected_size: int,
        expected_sha256: str,
        expected_content_type: str,
    ) -> bool:
        response = self.client.head_object(
            Bucket=self.bucket,
            Key=object_key,
        )
        metadata = response.get("Metadata") or {}
        return (
            response.get("ContentLength") == expected_size
            and response.get("ContentType") == expected_content_type
            and metadata.get("sha256") == expected_sha256
        )

    def create_download_url(
        self,
        object_key: str,
        *,
        expires_in: int = 900,
    ) -> str:
        if not object_key:
            return ""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )

    def download_to_file(self, object_key: str, path: Path) -> DownloadedObject:
        response = self.client.head_object(Bucket=self.bucket, Key=object_key)
        size = int(response.get("ContentLength") or 0)
        if size <= 0 or size > MAX_STORY_VIDEO_BYTES:
            raise UploadRejected("Istoriya fayli hajmi ruxsat etilmagan.")
        self.client.download_file(self.bucket, object_key, str(path))
        return DownloadedObject(
            size_bytes=size,
            content_type=str(response.get("ContentType") or ""),
        )

    def put_story_file(
        self,
        *,
        owner_type: AccountType,
        owner_id: int,
        purpose: Literal["story_video_processed", "story_thumbnail"],
        path: Path,
        content_type: str,
        suffix: str,
    ) -> str:
        object_key = (
            f"private/{owner_type.value}/{owner_id}/{purpose}/"
            f"{secrets.token_hex(16)}{suffix}"
        )
        self.client.upload_file(
            str(path),
            self.bucket,
            object_key,
            ExtraArgs={"ContentType": content_type},
        )
        return object_key

    def delete_object(self, object_key: str) -> None:
        if object_key:
            self.client.delete_object(Bucket=self.bucket, Key=object_key)

    def _presigned_put(
        self,
        *,
        object_key: str,
        pending_object_key: str,
        purpose: str,
        content_type: str,
        size_bytes: int,
        expires_in: int,
    ) -> UploadGrant:
        upload_url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": pending_object_key,
                "ContentType": content_type,
                "ContentLength": size_bytes,
            },
            ExpiresIn=expires_in,
        )
        return UploadGrant(
            object_key=object_key,
            pending_object_key=pending_object_key,
            purpose=purpose,
            upload_url=upload_url,
            method="PUT",
            headers={"Content-Type": content_type},
            expires_in_seconds=expires_in,
        )


def build_r2_storage(settings: Settings) -> R2Storage:
    client = boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )
    return R2Storage(client, bucket=settings.r2_bucket)

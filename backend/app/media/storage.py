from dataclasses import dataclass
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


class UploadRejected(ValueError):
    pass


@dataclass(frozen=True)
class UploadGrant:
    object_key: str
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


class R2Storage:
    def __init__(self, client, *, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def create_upload_grant(
        self,
        *,
        owner_type: AccountType,
        owner_id: int,
        purpose: Literal[
            "avatar", "logo", "payment_qr", "listing_photo", "listing_video",
            "order_chat_image", "payment_receipt", "advertisement_image",
            "story_image", "story_video",
        ],
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> UploadGrant:
        profile_purpose = (
            owner_type is AccountType.USER and purpose == "avatar"
        ) or (
            owner_type is AccountType.BUSINESS
            and purpose in {"logo", "payment_qr"}
        )
        listing_purpose = purpose in {
            "listing_photo", "listing_video", "order_chat_image",
            "story_image", "story_video",
        }
        # To'lov kvitansiyasini ikkala akkaunt turi ham yuklaydi:
        # e'lon va reklama uchun oddiy foydalanuvchi ham to'laydi.
        if purpose in {"payment_receipt", "advertisement_image"}:
            listing_purpose = True
        if not profile_purpose and not listing_purpose:
            raise UploadRejected("Bu rasm turi akkauntga mos emas.")
        if purpose in {
            "listing_photo", "order_chat_image", "payment_receipt",
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
                if purpose in {"order_chat_image", "payment_receipt"}
                else (
                    MAX_STORY_IMAGE_BYTES
                    if purpose == "story_image"
                    else MAX_LISTING_IMAGE_BYTES
                )
            )
            if not 1 <= size_bytes <= maximum:
                limit = 8 if purpose == "order_chat_image" else 10
                raise UploadRejected(f"Fayl hajmi {limit} MB dan oshmasin.")
            suffix = allowed_images[content_type]
        elif purpose in {"listing_video", "story_video"}:
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
            suffix = LISTING_VIDEO_TYPES[content_type]
        else:
            if content_type not in PROFILE_IMAGE_TYPES:
                raise UploadRejected("Rasm turi ruxsat etilmagan.")
            if not 1 <= size_bytes <= MAX_PROFILE_IMAGE_BYTES:
                raise UploadRejected("Rasm hajmi 8 MB dan oshmasin.")
            suffix = PROFILE_IMAGE_TYPES[content_type]
        object_key = (
            f"private/{owner_type.value}/{owner_id}/{purpose}/"
            f"{secrets.token_hex(16)}{suffix}"
        )
        return self._presigned_put(
            object_key,
            content_type,
            expires_in=900,
        )

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
        object_key: str,
        content_type: str,
        *,
        expires_in: int,
    ) -> UploadGrant:
        upload_url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
        return UploadGrant(
            object_key=object_key,
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

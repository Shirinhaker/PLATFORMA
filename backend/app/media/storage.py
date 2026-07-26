from dataclasses import dataclass
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
MAX_PROFILE_IMAGE_BYTES = 8 * 1024 * 1024


class UploadRejected(ValueError):
    pass


@dataclass(frozen=True)
class UploadGrant:
    object_key: str
    upload_url: str
    method: str
    headers: dict[str, str]
    expires_in_seconds: int


class R2Storage:
    def __init__(self, client, *, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def create_upload_grant(
        self,
        *,
        owner_type: AccountType,
        owner_id: int,
        purpose: Literal["avatar", "logo"],
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> UploadGrant:
        allowed_purpose = (
            owner_type is AccountType.USER and purpose == "avatar"
        ) or (
            owner_type is AccountType.BUSINESS and purpose == "logo"
        )
        if not allowed_purpose:
            raise UploadRejected("Bu rasm turi akkauntga mos emas.")
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

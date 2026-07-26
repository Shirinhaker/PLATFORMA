from dataclasses import dataclass
import secrets

import boto3

from app.core.config import Settings


ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "application/pdf": ".pdf",
}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


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
        actor_id: int,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> UploadGrant:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise UploadRejected("Fayl turi ruxsat etilmagan.")
        if size_bytes < 1 or size_bytes > MAX_UPLOAD_BYTES:
            raise UploadRejected("Fayl hajmi ruxsat etilgan chegaradan tashqarida.")
        suffix = ALLOWED_CONTENT_TYPES[content_type]
        object_key = (
            f"private/uploads/{actor_id}/"
            f"{secrets.token_hex(16)}{suffix}"
        )
        upload_url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=900,
        )
        return UploadGrant(
            object_key=object_key,
            upload_url=upload_url,
            method="PUT",
            headers={"Content-Type": content_type},
            expires_in_seconds=900,
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

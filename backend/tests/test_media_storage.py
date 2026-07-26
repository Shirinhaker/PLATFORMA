import pytest

from app.accounts.model import AccountType
from app.media.storage import R2Storage, UploadRejected


def test_upload_grant_uses_private_profile_prefix(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    grant = storage.create_upload_grant(
        owner_type=AccountType.USER,
        owner_id=42,
        purpose="avatar",
        filename="me.png",
        content_type="image/png",
        size_bytes=1024,
    )
    assert grant.object_key.startswith("private/user/42/avatar/")
    assert grant.object_key.endswith(".png")
    assert grant.method == "PUT"
    assert grant.headers == {"Content-Type": "image/png"}
    assert grant.expires_in_seconds == 900


def test_executable_upload_is_rejected(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    with pytest.raises(UploadRejected, match="Rasm turi ruxsat etilmagan"):
        storage.create_upload_grant(
            owner_type=AccountType.USER,
            owner_id=42,
            purpose="avatar",
            filename="bad.exe",
            content_type="application/octet-stream",
            size_bytes=1024,
        )


def test_profile_image_is_limited_to_eight_mebibytes(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    with pytest.raises(UploadRejected, match="8 MB"):
        storage.create_upload_grant(
            owner_type=AccountType.BUSINESS,
            owner_id=84,
            purpose="logo",
            filename="large.webp",
            content_type="image/webp",
            size_bytes=8 * 1024 * 1024 + 1,
        )


def test_user_cannot_create_logo_grant(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    with pytest.raises(UploadRejected, match="akkauntga mos emas"):
        storage.create_upload_grant(
            owner_type=AccountType.USER,
            owner_id=42,
            purpose="logo",
            filename="logo.gif",
            content_type="image/gif",
            size_bytes=1024,
        )

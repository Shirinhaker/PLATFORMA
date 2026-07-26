import pytest

from app.media.storage import R2Storage, UploadRejected


def test_upload_grant_uses_private_actor_prefix(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    grant = storage.create_upload_grant(
        actor_id=42,
        filename="logo.png",
        content_type="image/png",
        size_bytes=1024,
    )
    assert grant.object_key.startswith("private/uploads/42/")
    assert grant.object_key.endswith(".png")
    assert grant.method == "PUT"
    assert grant.headers == {"Content-Type": "image/png"}


def test_executable_upload_is_rejected(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    with pytest.raises(UploadRejected, match="Fayl turi ruxsat etilmagan"):
        storage.create_upload_grant(
            actor_id=42,
            filename="bad.exe",
            content_type="application/octet-stream",
            size_bytes=1024,
        )

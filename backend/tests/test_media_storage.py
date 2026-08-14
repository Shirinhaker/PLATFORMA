import pytest
from io import BytesIO

from app.accounts.model import AccountType
from app.media.storage import R2Storage, StoredObject, UploadRejected


def test_r2_readiness_performs_a_real_bucket_probe():
    class Healthy:
        def __init__(self):
            self.calls = 0

        def head_bucket(self, *, Bucket):
            self.calls += 1
            assert Bucket == "koprik-test"

    class Broken:
        def head_bucket(self, **_kwargs):
            raise RuntimeError("r2 unavailable")

    healthy = Healthy()
    assert R2Storage(healthy, bucket="koprik-test").ready() is True
    assert healthy.calls == 1
    assert R2Storage(Broken(), bucket="koprik-test").ready() is False


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


def test_profile_attachment_verifies_real_r2_bytes_and_type():
    class Body:
        def read(self, size):
            assert size == 32
            return b"\x89PNG\r\n\x1a\n" + b"0" * 24

        def close(self):
            return None

    class Client:
        def head_object(self, *, Bucket, Key):
            return {"ContentLength": 1024, "ContentType": "image/png"}

        def get_object(self, *, Bucket, Key, Range):
            assert Range == "bytes=0-31"
            return {"Body": Body()}

    result = R2Storage(Client(), bucket="koprik-test").verify_profile_image(
        "private/user/42/avatar/image.png"
    )
    assert result.size_bytes == 1024
    assert result.content_type == "image/png"


def test_profile_attachment_rejects_spoofed_content_type():
    class Body:
        def read(self, size):
            return b"MZ" + b"0" * 30

        def close(self):
            return None

    class Client:
        def head_object(self, *, Bucket, Key):
            return {"ContentLength": 1024, "ContentType": "image/png"}

        def get_object(self, **kwargs):
            return {"Body": Body()}

    with pytest.raises(UploadRejected, match="haqiqiy fayl turi"):
        R2Storage(Client(), bucket="koprik-test").verify_profile_image(
            "private/user/42/avatar/fake.png"
        )


def test_order_chat_image_grant_uses_private_owner_prefix_and_eight_mb_limit(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    grant = storage.create_upload_grant(
        owner_type=AccountType.BUSINESS,
        owner_id=84,
        purpose="order_chat_image",
        filename="receipt.heic",
        content_type="image/heic",
        size_bytes=1024,
    )
    assert grant.object_key.startswith(
        "private/business/84/order_chat_image/"
    )
    assert grant.object_key.endswith(".heic")

    with pytest.raises(UploadRejected, match="8 MB"):
        storage.create_upload_grant(
            owner_type=AccountType.USER,
            owner_id=42,
            purpose="order_chat_image",
            filename="large.webp",
            content_type="image/webp",
            size_bytes=8 * 1024 * 1024 + 1,
        )


def test_general_chat_image_grant_uses_its_own_private_prefix(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    grant = storage.create_upload_grant(
        owner_type=AccountType.USER,
        owner_id=42,
        purpose="chat_image",
        filename="photo.webp",
        content_type="image/webp",
        size_bytes=1024,
    )

    assert grant.object_key.startswith("private/user/42/chat_image/")
    assert grant.object_key.endswith(".webp")


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


def test_specialist_media_uses_exact_v1656_formats_and_limits(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    credential = storage.create_upload_grant(
        owner_type=AccountType.USER,
        owner_id=42,
        purpose="specialist_credential",
        filename="diplom.webp",
        content_type="image/webp",
        size_bytes=1024,
    )
    assert credential.object_key.startswith(
        "private/user/42/specialist_credential/"
    )
    video = storage.create_upload_grant(
        owner_type=AccountType.USER,
        owner_id=42,
        purpose="specialist_portfolio_video",
        filename="work.mp4",
        content_type="video/mp4",
        size_bytes=30 * 1024 * 1024,
    )
    assert video.object_key.startswith(
        "private/user/42/specialist_portfolio_video/"
    )
    with pytest.raises(UploadRejected, match="30 MB"):
        storage.create_upload_grant(
            owner_type=AccountType.USER,
            owner_id=42,
            purpose="specialist_portfolio_video",
            filename="large.mp4",
            content_type="video/mp4",
            size_bytes=30 * 1024 * 1024 + 1,
        )
    with pytest.raises(UploadRejected, match="JPG, PNG yoki WEBP"):
        storage.create_upload_grant(
            owner_type=AccountType.USER,
            owner_id=42,
            purpose="specialist_offer_image",
            filename="animated.gif",
            content_type="image/gif",
            size_bytes=1024,
        )


def test_migration_upload_sets_checksum_metadata_and_verifies_head():
    class RecordingClient:
        def __init__(self):
            self.upload = None

        def upload_fileobj(self, stream, bucket, key, ExtraArgs):
            self.upload = {
                "bytes": stream.read(),
                "bucket": bucket,
                "key": key,
                "extra": ExtraArgs,
            }

        def head_object(self, *, Bucket, Key):
            assert Bucket == "koprik-test"
            assert Key == self.upload["key"]
            return {
                "ContentLength": len(self.upload["bytes"]),
                "ContentType": "image/png",
                "Metadata": {"sha256": "a" * 64},
            }

    client = RecordingClient()
    storage = R2Storage(client, bucket="koprik-test")

    stored = storage.put_migration_object(
        stream=BytesIO(b"png-bytes"),
        run_id=42,
        entity_type="catalog_item",
        legacy_id=8,
        slot="primary",
        sha256="a" * 64,
        content_type="image/png",
        size_bytes=9,
        suffix=".png",
    )

    assert isinstance(stored, StoredObject)
    assert stored.object_key == (
        "migration/42/catalog_item/8/primary/" + "a" * 64 + ".png"
    )
    assert client.upload["extra"] == {
        "ContentType": "image/png",
        "Metadata": {"sha256": "a" * 64},
    }
    assert storage.verify_object(
        stored.object_key,
        expected_size=9,
        expected_sha256="a" * 64,
        expected_content_type="image/png",
    ) is True

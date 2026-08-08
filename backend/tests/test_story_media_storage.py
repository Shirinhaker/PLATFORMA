import pytest

from app.accounts.model import AccountType
from app.media.storage import R2Storage, UploadRejected


def test_story_upload_grants_keep_v1656_limits(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    image = storage.create_upload_grant(
        owner_type=AccountType.USER,
        owner_id=42,
        purpose="story_image",
        filename="story.webp",
        content_type="image/webp",
        size_bytes=10 * 1024 * 1024,
    )
    video = storage.create_upload_grant(
        owner_type=AccountType.BUSINESS,
        owner_id=84,
        purpose="story_video",
        filename="story.mov",
        content_type="video/quicktime",
        size_bytes=100 * 1024 * 1024,
    )

    assert image.object_key.startswith("private/user/42/story_image/")
    assert video.object_key.startswith("private/business/84/story_video/")
    with pytest.raises(UploadRejected, match="100 MB"):
        storage.create_upload_grant(
            owner_type=AccountType.USER,
            owner_id=42,
            purpose="story_video",
            filename="large.mp4",
            content_type="video/mp4",
            size_bytes=100 * 1024 * 1024 + 1,
        )
    with pytest.raises(UploadRejected, match="JPG, PNG yoki WEBP"):
        storage.create_upload_grant(
            owner_type=AccountType.USER,
            owner_id=42,
            purpose="story_image",
            filename="animated.gif",
            content_type="image/gif",
            size_bytes=1024,
        )

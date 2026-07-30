from types import SimpleNamespace

import pytest

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.media.storage import R2Storage
from app.profiles.router import require_profile_object_key
from app.profiles.schemas import (
    BusinessPaymentQrAttachment,
    BusinessProfileRead,
)


class RecordingS3:
    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        return (
            f"https://media.example/{operation}/"
            f"{Params['Key']}?expires={ExpiresIn}"
        )


def business_profile(**overrides):
    values = {
        "account_id": 7,
        "name": "Muhr",
        "phone": "912377784",
        "description": "",
        "public_username": "muhr1",
        "direction": "Savdo",
        "activity_type": "Oziq-ovqat do'koni",
        "address": "Qumqo‘rg‘on",
        "latitude": 37.8,
        "longitude": 67.5,
        "work_hours": {"from": "09:00", "to": "20:00"},
        "pay_card": "5614681918687751",
        "pay_holder": "BUNYOD ASHUROV",
        "pay_qr_object_key": "private/business/7/payment_qr/" + "a" * 32 + ".png",
        "director": "",
        "tax_id": "",
        "logo_object_key": "private/business/7/logo/" + "b" * 32 + ".png",
        "logo_x": 50,
        "logo_y": 50,
        "logo_zoom": 1,
        "followers_count": 0,
        "following_count": 1,
        "rating_sum": 0,
        "rating_count": 0,
        "map_visible": True,
        "dashboard_snapshot": {},
        "recent_activity": [],
        "cabinet_payload": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_business_profile_read_accepts_signed_media_urls():
    value = BusinessProfileRead.model_validate(business_profile()).model_copy(
        update={
            "logo_url": "https://media.example/logo.png",
            "pay_qr_url": "https://media.example/payment.png",
        }
    )

    assert value.logo_url == "https://media.example/logo.png"
    assert value.pay_qr_url == "https://media.example/payment.png"
    assert value.work_hours == {"from": "09:00", "to": "20:00"}


def test_business_can_request_payment_qr_upload_grant():
    storage = R2Storage(RecordingS3(), bucket="koprik-test")

    grant = storage.create_upload_grant(
        owner_type=AccountType.BUSINESS,
        owner_id=7,
        purpose="payment_qr",
        filename="pay.png",
        content_type="image/png",
        size_bytes=1024,
    )

    assert grant.object_key.startswith("private/business/7/payment_qr/")
    assert grant.object_key.endswith(".png")
    assert grant.headers == {"Content-Type": "image/png"}


def test_payment_qr_object_must_belong_to_current_business():
    valid = "private/business/7/payment_qr/" + "a" * 32 + ".webp"
    require_profile_object_key(
        valid,
        account_type=AccountType.BUSINESS,
        account_id=7,
        purpose="payment_qr",
    )

    with pytest.raises(ApiError) as captured:
        require_profile_object_key(
            "private/business/8/payment_qr/" + "a" * 32 + ".webp",
            account_type=AccountType.BUSINESS,
            account_id=7,
            purpose="payment_qr",
        )

    assert captured.value.code == "media_object_forbidden"


def test_payment_qr_attachment_allows_explicit_removal():
    assert BusinessPaymentQrAttachment(object_key="").object_key == ""

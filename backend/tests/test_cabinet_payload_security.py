import pytest

from app.cabinet_records.security import (
    SensitiveCabinetFieldError,
    assert_payload_safe,
)


@pytest.mark.parametrize(
    "payload",
    [
        {"messages": [{"id": 1, "token": "secret"}]},
        {"staff": [{"id": 1, "password_hash": "hash"}]},
        {"nested": {"private_key": "key"}},
        {"auth": [{"otp_hash": "hash"}]},
    ],
)
def test_sensitive_fields_stop_normalization(payload):
    with pytest.raises(SensitiveCabinetFieldError):
        assert_payload_safe(payload)


def test_normal_migrated_cabinet_payload_is_allowed():
    assert_payload_safe({
        "orders": [{"id": 1, "status": "new", "items": []}],
        "documents": [{"id": 2, "title": "Shartnoma"}],
    })

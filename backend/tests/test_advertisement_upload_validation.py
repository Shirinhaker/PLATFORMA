from types import SimpleNamespace
from typing import Any

import pytest

from app.accounts.model import AccountType
from app.advertisements.authoring_router import verify_advertisement_image
from app.auth.dependencies import CurrentAccount
from app.core.errors import ApiError


def _current() -> CurrentAccount:
    return CurrentAccount(
        account_id=7,
        account_type=AccountType.BUSINESS,
        session_token="session",
    )


def _request(storage: Any) -> Any:
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(r2=storage)),
    )


async def test_advertisement_image_must_belong_to_the_current_account():
    storage = SimpleNamespace(verify_profile_image=lambda _key: None)

    with pytest.raises(ApiError) as failure:
        await verify_advertisement_image(
            _request(storage),
            _current(),
            "private/business/99/advertisement_image/banner.webp",
        )

    assert failure.value.status_code == 400
    assert failure.value.code == "advertisement_image_invalid"


async def test_uploaded_advertisement_image_is_verified_in_r2():
    checked = []
    storage = SimpleNamespace(
        verify_profile_image=lambda key: checked.append(key),
    )
    object_key = "private/business/7/advertisement_image/banner.webp"

    await verify_advertisement_image(
        _request(storage),
        _current(),
        object_key,
    )

    assert checked == [object_key]


async def test_missing_advertisement_image_returns_a_retryable_user_error():
    def missing(_key):
        raise RuntimeError("R2 object not found")

    with pytest.raises(ApiError) as failure:
        await verify_advertisement_image(
            _request(SimpleNamespace(verify_profile_image=missing)),
            _current(),
            "private/business/7/advertisement_image/banner.webp",
        )

    assert failure.value.status_code == 400
    assert failure.value.code == "advertisement_image_missing"
    assert "R2" not in failure.value.message

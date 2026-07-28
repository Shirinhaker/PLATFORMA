import pytest
from pydantic import ValidationError

from app.public_discovery.schemas import (
    PublicResultKind,
    PublicResultType,
    PublicSearchItem,
    PublicSearchParams,
    PublicSearchResponse,
)


def test_public_search_item_contains_only_the_public_contract():
    item = PublicSearchItem(
        kind=PublicResultKind.BUSINESS,
        public_id="business:42",
        name="Koprik Savdo",
        public_username="koprik_savdo",
        description="Mahalliy savdo nuqtasi",
        direction="Savdo",
        activity_type="Do‘kon",
        region="",
        district="",
        mahalla="",
        image_url="",
    )

    assert item.model_dump(mode="json") == {
        "kind": "business",
        "public_id": "business:42",
        "name": "Koprik Savdo",
        "public_username": "koprik_savdo",
        "description": "Mahalliy savdo nuqtasi",
        "direction": "Savdo",
        "activity_type": "Do‘kon",
        "region": "",
        "district": "",
        "mahalla": "",
        "image_url": "",
    }


@pytest.mark.parametrize(
    "private_field",
    [
        "phone",
        "login",
        "password_hash",
        "telegram_user_id",
        "latitude",
        "longitude",
        "address",
        "tax_id",
        "director",
        "object_key",
    ],
)
def test_public_search_item_rejects_private_fields(private_field):
    payload = {
        "kind": "user",
        "public_id": "user:7",
        "name": "Ali",
        private_field: "secret",
    }

    with pytest.raises(ValidationError):
        PublicSearchItem.model_validate(payload)


def test_public_search_params_normalize_filters_and_limit_pagination():
    params = PublicSearchParams(
        q="  Savdo  ",
        result_type="business",
        direction="  Chakana savdo ",
        region="  Toshkent ",
        page=2,
        page_size=50,
    )

    assert params.q == "Savdo"
    assert params.direction == "Chakana savdo"
    assert params.region == "Toshkent"
    assert params.result_type is PublicResultType.BUSINESS
    assert params.offset == 50

    with pytest.raises(ValidationError):
        PublicSearchParams(page_size=51)


def test_public_search_params_accept_all_result_types():
    assert PublicSearchParams().result_type is PublicResultType.ALL
    assert (
        PublicSearchParams(result_type="all").result_type
        is PublicResultType.ALL
    )


def test_public_search_response_has_stable_page_metadata():
    response = PublicSearchResponse(
        items=[],
        page=3,
        page_size=20,
        total=41,
    )

    assert response.pages == 3

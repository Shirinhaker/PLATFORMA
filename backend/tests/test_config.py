import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_origins_are_normalized_to_exact_https_origins():
    settings = Settings(
        cors_origins=(
            " https://frontend-one.up.railway.app/,"
            "https://frontend-two.up.railway.app "
        )
    )

    assert settings.cors_origins == (
        "https://frontend-one.up.railway.app,"
        "https://frontend-two.up.railway.app"
    )
    assert settings.cors_origin_list == [
        "https://frontend-one.up.railway.app",
        "https://frontend-two.up.railway.app",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "*",
        "http://frontend-staging.up.railway.app",
        "https://frontend-staging.up.railway.app/path",
    ],
)
def test_cors_origins_reject_wildcards_http_and_paths(value):
    with pytest.raises(ValidationError):
        Settings(cors_origins=value)

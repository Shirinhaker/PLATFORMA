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


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_deployed_environments_require_auth_and_telegram_secrets(environment):
    with pytest.raises(ValidationError):
        Settings(environment=environment)


def test_staging_accepts_complete_auth_and_telegram_secrets():
    settings = Settings(
        environment="staging",
        telegram_bot_token="bot-token",
        telegram_bot_username="koprik_test_bot",
        telegram_webhook_secret="webhook-secret",
        otp_secret="otp-secret",
        csrf_secret="csrf-secret",
        outbox_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    )

    assert settings.auth_cookie_name == "koprik_session"
    assert settings.session_ttl_seconds == 30 * 24 * 60 * 60
    assert settings.session_cache_ttl_seconds == 30
    assert settings.profile_summary_cache_ttl_seconds == 30
    assert settings.public_search_cache_ttl_seconds == 30


def test_profile_summary_cache_ttl_defaults_to_thirty_seconds():
    settings = Settings(environment="test")

    assert settings.profile_summary_cache_ttl_seconds == 30


def test_public_search_cache_ttl_defaults_to_thirty_seconds():
    settings = Settings(environment="test")

    assert settings.public_search_cache_ttl_seconds == 30


def test_phase3c_media_settings_are_safe_by_default():
    settings = Settings(environment="test")

    assert settings.legacy_media_roots == ""
    assert settings.legacy_media_max_bytes == 100 * 1024 * 1024
    assert settings.legacy_snapshot_root == ""
    assert settings.listings_enabled is False
    assert settings.phase3c_public_enabled is False


@pytest.mark.parametrize("value", [4, 301])
def test_profile_summary_cache_ttl_rejects_values_outside_bounds(value):
    with pytest.raises(ValidationError):
        Settings(
            environment="test",
            profile_summary_cache_ttl_seconds=value,
        )


@pytest.mark.parametrize("value", [4, 301])
def test_public_search_cache_ttl_rejects_values_outside_bounds(value):
    with pytest.raises(ValidationError):
        Settings(
            environment="test",
            public_search_cache_ttl_seconds=value,
        )


def test_staging_rejects_invalid_outbox_encryption_key():
    with pytest.raises(ValidationError):
        Settings(
            environment="staging",
            telegram_bot_token="bot-token",
            telegram_bot_username="koprik_test_bot",
            telegram_webhook_secret="webhook-secret",
            otp_secret="otp-secret",
            csrf_secret="csrf-secret",
            outbox_encryption_key="not-a-fernet-key",
        )

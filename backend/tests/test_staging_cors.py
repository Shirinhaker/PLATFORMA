import re

from app.core.config import Settings
from app.main import STAGING_RAILWAY_ORIGIN_REGEX, _cors_origin_regex


def settings(environment: str) -> Settings:
    return Settings(
        environment=environment,
        telegram_bot_username="koprik_test_bot",
        telegram_bot_token="test-token",
        telegram_webhook_secret="test-webhook-secret",
        otp_secret="test-otp-secret",
        csrf_secret="test-csrf-secret",
        outbox_encryption_key=(
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        ),
    )


def test_staging_accepts_railway_https_frontend_origins():
    pattern = _cors_origin_regex(settings("staging"))

    assert pattern == STAGING_RAILWAY_ORIGIN_REGEX
    assert re.fullmatch(pattern, "https://web-production-aed95.up.railway.app")
    assert re.fullmatch(pattern, "https://humble-acceptance.up.railway.app")
    assert not re.fullmatch(pattern, "http://web-production.up.railway.app")
    assert not re.fullmatch(pattern, "https://up.railway.app.evil.example")


def test_production_does_not_enable_railway_wildcard_origin():
    assert _cors_origin_regex(settings("production")) is None

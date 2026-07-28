from functools import lru_cache
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KOPRIK_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "koprik-api"
    environment: str = "development"
    legacy_build: str = "v1656"
    database_url: str = "postgresql+asyncpg://koprik:koprik@localhost:5432/koprik"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = ""
    r2_endpoint_url: str = "https://example.r2.cloudflarestorage.com"
    r2_bucket: str = "koprik-development"
    r2_access_key_id: str = Field(default="")
    r2_secret_access_key: str = Field(default="")
    telegram_bot_token: str = Field(default="")
    telegram_bot_username: str = Field(default="")
    telegram_webhook_secret: str = Field(default="")
    otp_secret: str = Field(default="")
    csrf_secret: str = Field(default="")
    outbox_encryption_key: str = Field(default="")
    auth_cookie_name: str = "koprik_session"
    session_ttl_seconds: int = 30 * 24 * 60 * 60
    session_cache_ttl_seconds: int = Field(default=30, ge=5, le=300)
    profile_summary_cache_ttl_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
    )
    public_search_cache_ttl_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
    )
    telegram_link_ttl_seconds: int = 10 * 60
    telegram_code_ttl_seconds: int = 5 * 60
    telegram_resend_seconds: int = 60
    telegram_max_attempts: int = 5

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [
            origin.strip().rstrip("/")
            for origin in value.split(",")
            if origin.strip()
        ]

        for origin in origins:
            parsed = urlsplit(origin)
            if (
                origin == "*"
                or parsed.scheme != "https"
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS origin to‘liq va xavfsiz HTTPS origin bo‘lishi kerak."
                )

        return ",".join(dict.fromkeys(origins))

    @property
    def cors_origin_list(self) -> list[str]:
        return self.cors_origins.split(",") if self.cors_origins else []

    @model_validator(mode="after")
    def validate_auth_secrets(self) -> "Settings":
        if self.environment not in {"staging", "production"}:
            return self

        required = {
            "telegram_bot_token": self.telegram_bot_token,
            "telegram_bot_username": self.telegram_bot_username,
            "telegram_webhook_secret": self.telegram_webhook_secret,
            "otp_secret": self.otp_secret,
            "csrf_secret": self.csrf_secret,
            "outbox_encryption_key": self.outbox_encryption_key,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(
                "Staging va production uchun auth sirlari to‘liq bo‘lishi kerak: "
                + ", ".join(missing)
            )

        try:
            Fernet(self.outbox_encryption_key.encode("ascii"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "outbox_encryption_key Fernet kaliti bo‘lishi kerak."
            ) from exc

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

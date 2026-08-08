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
    # Har API nusxasi shuncha ulanish ochadi. PostgreSQL'ning `max_connections`
    # chegarasi barcha nusxalar uchun umumiy, shuning uchun nusxalar soni
    # oshganda bu qiymatlar muhitdan pasaytiriladi (yoki PgBouncer qo'yiladi).
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    # Pool bo'shashini uzoq kutish yiqilishni butun tizimga tarqatadi —
    # tez rad etib, yukni orqaga qaytargan ma'qul.
    db_pool_timeout_seconds: int = Field(default=3, ge=1, le=60)
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = Field(default=100, ge=1, le=1000)
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
    legacy_media_roots: str = ""
    legacy_media_max_bytes: int = Field(
        default=100 * 1024 * 1024,
        ge=1,
    )
    legacy_snapshot_root: str = ""
    listings_enabled: bool = False
    stories_enabled: bool = False
    phase3c_public_enabled: bool = False
    telegram_link_ttl_seconds: int = 10 * 60
    telegram_code_ttl_seconds: int = 5 * 60
    telegram_resend_seconds: int = 60
    telegram_max_attempts: int = 5

    # Admin paneli. Ro'yxat bo'sh bo'lsa hech kim kira olmaydi — v1656da
    # standart qiymatga ikkita Telegram ID yozilgan edi, bu xavfli.
    admin_telegram_ids: str = ""
    admin_cookie_name: str = "koprik_admin_session"
    admin_challenge_ttl_seconds: int = 5 * 60
    admin_challenge_max_attempts: int = 5
    admin_session_ttl_seconds: int = 8 * 60 * 60
    # Bo'sh turgan admin sessiyasi shu muddatdan keyin yopiladi.
    admin_session_idle_seconds: int = 30 * 60
    # Audit jurnalidagi IP xeshi uchun. Berilmasa `csrf_secret` ishlatiladi.
    admin_audit_ip_secret: str = ""

    @property
    def admin_telegram_id_set(self) -> frozenset[int]:
        result: set[int] = set()
        for raw in self.admin_telegram_ids.split(","):
            try:
                value = int(raw.strip())
            except (TypeError, ValueError):
                continue
            if value > 0:
                result.add(value)
        return frozenset(result)

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

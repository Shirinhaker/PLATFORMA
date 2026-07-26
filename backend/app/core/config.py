from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, field_validator
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


@lru_cache
def get_settings() -> Settings:
    return Settings()

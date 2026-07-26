from functools import lru_cache

from pydantic import Field
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
    r2_endpoint_url: str = "https://example.r2.cloudflarestorage.com"
    r2_bucket: str = "koprik-development"
    r2_access_key_id: str = Field(default="")
    r2_secret_access_key: str = Field(default="")


@lru_cache
def get_settings() -> Settings:
    return Settings()

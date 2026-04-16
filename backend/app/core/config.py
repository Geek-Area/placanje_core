from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    env: Literal["dev", "test", "prod"] = "dev"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"
    cors_allowed_origins: list[str] = Field(default_factory=list)
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None
    bank_webhook_secret: str | None = None
    public_share_link_ttl_days: int = Field(default=30, ge=1, le=365)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_cors_allowed_origins(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if raw == "":
                return []
            return [item.strip() for item in raw.split(",") if item.strip()]
        raise ValueError("CORS_ALLOWED_ORIGINS must be a comma-separated string or a list.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

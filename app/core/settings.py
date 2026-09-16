from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="IPMS_",
        extra="ignore",
    )

    app_name: str = "Investment Portfolio Management System"
    version: str = "0.1.0"
    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    database_url: str = "postgresql+psycopg://ipms:ipms@localhost:5432/ipms"
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_timeout_seconds: int = Field(default=30, ge=1)

    auth_secret_key: str = "change-me"
    auth_token_ttl_minutes: int = Field(default=60, ge=1)

    batch_commit_interval: int = Field(default=1000, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()

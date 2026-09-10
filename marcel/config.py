from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated environment configuration for Marcel Arch."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "Marcel Arch"
    app_version: str = "1.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    database_url: str = "sqlite+aiosqlite:///./marcel_arch.db"
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=100)

    redis_url: str = "redis://localhost:6379/0"
    redis_socket_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    redis_health_check_interval_seconds: int = Field(default=30, ge=1, le=300)

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "marcel-arch"
    jwt_audience: str = "marcel-arch-clients"
    jwt_expiry_seconds: int = Field(default=900, ge=60, le=86400)

    audit_hmac_key: SecretStr = Field(min_length=32)
    approval_timeout_seconds: int = Field(default=900, ge=30, le=86400)
    max_request_body_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        allowed_prefixes = ("sqlite+aiosqlite://", "postgresql+asyncpg://")
        if not value.startswith(allowed_prefixes):
            raise ValueError("database_url must use sqlite+aiosqlite or postgresql+asyncpg")
        return value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        parsed = AnyUrl(value)
        if parsed.scheme not in {"redis", "rediss"}:
            raise ValueError("redis_url must use redis or rediss")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("cors_origins must contain at least one origin")
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    jwt_secret: SecretStr
    jwt_issuer: str = Field(default="chess-api", min_length=1, max_length=200)
    jwt_audience: str = Field(default="chess-web", min_length=1, max_length=200)
    access_token_seconds: int = Field(default=300, ge=30, le=900)
    refresh_token_days: int = Field(default=30, ge=1, le=90)
    bcrypt_rounds: int = Field(default=12, ge=4, le=14)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"], min_length=1)

    @property
    def secure_cookies(self) -> bool:
        return self.app_env == "production"

    @property
    def refresh_cookie_name(self) -> str:
        return "__Host-chess_refresh" if self.secure_cookies else "chess_refresh"

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 bytes; generate a random secret")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            if url.drivername in {"postgres", "postgresql"}:
                url = url.set(drivername="postgresql+psycopg")
            if url.drivername != "postgresql+psycopg":
                raise ValueError("Use a PostgreSQL URL with the psycopg driver")
            if not url.host or not url.database or not url.username:
                raise ValueError("Database URL requires host, database, and username")
        except (ArgumentError, ValueError) as exc:
            raise ValueError("Invalid PostgreSQL database URL") from exc
        return SecretStr(url.render_as_string(hide_password=False))

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            try:
                parsed = urlsplit(origin)
                port = parsed.port
            except ValueError as exc:
                raise ValueError("Invalid CORS origin") from exc
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or (port is not None and port < 1)
                or "*" in origin
                or any(character.isspace() for character in origin)
            ):
                raise ValueError("CORS entries must be exact HTTP origins without a path")
        return list(dict.fromkeys(origins))

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.app_env != "test" and self.bcrypt_rounds < 12:
            raise ValueError("bcrypt_rounds must be at least 12 outside tests")
        if self.app_env == "production" and any(
            not origin.startswith("https://") for origin in self.cors_origins
        ):
            raise ValueError("Production CORS origins must use HTTPS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

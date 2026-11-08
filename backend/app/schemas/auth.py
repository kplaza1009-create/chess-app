from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from app.db.models import Speed


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    email: EmailStr = Field(max_length=254)
    password: SecretStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if not password or len(password.encode("utf-8")) > 72 or "\x00" in password:
            raise ValueError("Password must contain 1–72 UTF-8 bytes and no null characters")
        return value


class RegisterRequest(LoginRequest):
    username: str = Field(min_length=3, max_length=24, pattern=r"^[a-z0-9_]+$")

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def require_password_length(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 12:
            raise ValueError("Use at least 12 characters")
        return value


class RatingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    speed: Speed
    rating: int
    wins: int
    losses: int
    draws: int


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    avatar_key: str | None
    created_at: datetime
    ratings: list[RatingResponse]


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    session_id: UUID
    user: UserResponse


class CsrfResponse(BaseModel):
    csrf_token: str


class MessageResponse(BaseModel):
    message: str

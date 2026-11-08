import hashlib
import hmac
import re
import secrets
import time
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

import bcrypt
import jwt
from anyio import CapacityLimiter, to_thread
from pydantic import BaseModel, ConfigDict, ValidationError

from app.config import Settings


class AuthError(Exception):
    def __init__(self, status: int, detail: str, *, clear_cookie: bool = False) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.clear_cookie = clear_cookie


class Claims(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sub: UUID
    sid: UUID
    jti: UUID
    token_type: Literal["access", "refresh"]
    exp: int
    iat: int
    nbf: int


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Security:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.key = settings.jwt_secret.get_secret_value()
        self.csrf_key = hmac.digest(self.key.encode(), b"chess:csrf:v1", "sha256")
        self.password_slots = CapacityLimiter(4)
        self.dummy_hash = ""

    async def initialize(self) -> None:
        self.dummy_hash = await self.hash_password(secrets.token_hex(24))

    async def hash_password(self, password: str) -> str:
        def calculate() -> str:
            salt = bcrypt.gensalt(rounds=self.settings.bcrypt_rounds)
            return bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")

        return await to_thread.run_sync(calculate, limiter=self.password_slots)

    async def verify_password(self, password: str, encoded_hash: str) -> bool:
        def calculate() -> bool:
            try:
                return bcrypt.checkpw(password.encode("utf-8"), encoded_hash.encode("ascii"))
            except (ValueError, UnicodeError):
                return False

        return await to_thread.run_sync(calculate, limiter=self.password_slots)

    def encode(
        self,
        user_id: UUID,
        family_id: UUID,
        kind: Literal["access", "refresh"],
        expires_at: datetime,
        token_id: UUID | None = None,
    ) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "sub": str(user_id),
                "sid": str(family_id),
                "jti": str(token_id or uuid4()),
                "token_type": kind,
                "iss": self.settings.jwt_issuer,
                "aud": self.settings.jwt_audience,
                "iat": now,
                "nbf": now,
                "exp": int(expires_at.timestamp()),
            },
            self.key,
            algorithm="HS256",
        )

    def decode(self, token: str, kind: Literal["access", "refresh"]) -> Claims:
        if not token or len(token) > 4096:
            raise AuthError(401, "Authentication required")
        try:
            payload = jwt.decode(
                token,
                self.key,
                algorithms=["HS256"],
                issuer=self.settings.jwt_issuer,
                audience=self.settings.jwt_audience,
                options={
                    "require": [
                        "sub",
                        "sid",
                        "jti",
                        "token_type",
                        "exp",
                        "iat",
                        "nbf",
                        "iss",
                        "aud",
                    ],
                    "strict_aud": True,
                },
            )
            claims = Claims.model_validate(payload)
            if claims.token_type != kind:
                raise ValueError("Wrong token type")
            return claims
        except (jwt.InvalidTokenError, ValidationError, ValueError) as exc:
            raise AuthError(401, "Authentication required") from exc

    def csrf_token(self, refresh_token: str) -> str:
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        message = f"{token_hash(refresh_token)}:{timestamp}:{nonce}"
        signature = hmac.new(self.csrf_key, message.encode(), hashlib.sha256).hexdigest()
        return f"{timestamp}.{nonce}.{signature}"

    def verify_csrf(self, value: str, refresh_token: str) -> None:
        try:
            if re.fullmatch(r"[0-9]{1,12}\.[0-9a-f]{32}\.[0-9a-f]{64}", value) is None:
                raise ValueError("Invalid CSRF format")
            timestamp, nonce, signature = value.split(".")
            age = int(time.time()) - int(timestamp)
            if not 0 <= age <= 3600 or len(nonce) != 32 or len(signature) != 64:
                raise ValueError("Invalid CSRF format")
            message = f"{token_hash(refresh_token)}:{timestamp}:{nonce}"
            expected = hmac.new(self.csrf_key, message.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("Invalid CSRF signature")
        except (ValueError, UnicodeError) as exc:
            raise AuthError(403, "Security check failed. Refresh the page and try again.") from exc

    def throttle_key(self, scope: str, identifier: str) -> str:
        return hmac.new(
            self.key.encode(), f"rate:{scope}:{identifier}".encode(), hashlib.sha256
        ).hexdigest()


def utc_now() -> datetime:
    return datetime.now(UTC)

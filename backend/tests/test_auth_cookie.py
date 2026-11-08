from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import Response
from pydantic import SecretStr

from app.api.auth import set_refresh_cookie
from app.config import Settings
from app.schemas.auth import AuthResponse, UserResponse
from app.services.auth import IssuedSession
from app.services.security import Security


@pytest.mark.parametrize("zone", ["UTC", "America/New_York", "Asia/Kathmandu"])
@pytest.mark.parametrize("month", [1, 7])
def test_cookie_expiration_preserves_instant(
    zone: str, month: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, month, 15, 12, tzinfo=UTC)
    expires = (now + timedelta(days=1)).astimezone(ZoneInfo(zone))
    monkeypatch.setattr("app.api.auth.utc_now", lambda: now)
    security = Security(
        Settings(
            database_url=SecretStr("postgresql+psycopg://test:test@localhost/chess_test"),
            app_env="test",
            _env_file=None,
        )
    )
    issued = IssuedSession(
        AuthResponse(
            access_token="test-access",
            expires_in=300,
            session_id=uuid4(),
            user=UserResponse(
                id=uuid4(),
                username="kevin",
                email="kevin@example.com",
                avatar_key=None,
                created_at=now,
                ratings=[],
            ),
        ),
        "test-refresh",
        expires,
    )
    response = Response()
    set_refresh_cookie(response, security, issued)
    cookies: SimpleCookie[str] = SimpleCookie()
    cookies.load(response.headers["set-cookie"])
    refresh = cookies["chess_refresh"]
    assert refresh["expires"].endswith(" GMT")
    assert parsedate_to_datetime(refresh["expires"]) == now + timedelta(days=1)
    assert refresh["max-age"] == "86400"
    assert refresh["httponly"] and refresh["samesite"] == "lax"

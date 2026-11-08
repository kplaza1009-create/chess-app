import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import create_engine, text

from app.services.security import utc_now

ACCOUNT = {"username": "Kevin", "email": "Kevin@example.com", "password": "a safe passphrase 2026"}


def mutation(client: TestClient, action: str, data: dict[str, str] | None = None) -> Response:
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200
    return client.post(
        f"/api/v1/auth/{action}",
        json=data,
        headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
    )


def register(client: TestClient) -> dict[str, Any]:
    response = mutation(client, "register", ACCOUNT)
    assert response.status_code == 201, response.text
    return dict(response.json())


def me(client: TestClient, access_token: str) -> Response:
    return client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})


def set_cookie(client: TestClient, token: str) -> None:
    client.cookies.clear()
    client.cookies.set("chess_refresh", token)


def test_registration_normalizes_and_creates_ratings(auth_client: TestClient) -> None:
    result = register(auth_client)
    assert result["user"]["username"] == "kevin"
    assert result["user"]["email"] == "kevin@example.com"
    assert {item["speed"] for item in result["user"]["ratings"]} == {"bullet", "blitz", "rapid"}
    assert all(item["rating"] == 1200 for item in result["user"]["ratings"])
    assert "password_hash" not in result["user"]
    response = me(auth_client, result["access_token"])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


def test_logout_revokes_access_immediately(auth_client: TestClient) -> None:
    result = register(auth_client)
    assert mutation(auth_client, "logout").status_code == 200
    assert not auth_client.cookies.get("chess_refresh")
    assert me(auth_client, result["access_token"]).status_code == 401
    assert mutation(auth_client, "logout").status_code == 200


def test_login_and_generic_failure(auth_client: TestClient) -> None:
    register(auth_client)
    mutation(auth_client, "logout")
    wrong = mutation(auth_client, "login", {"email": ACCOUNT["email"], "password": "wrong"})
    missing = mutation(auth_client, "login", {"email": "absent@example.com", "password": "wrong"})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
    success = mutation(
        auth_client, "login", {"email": ACCOUNT["email"], "password": ACCOUNT["password"]}
    )
    assert success.status_code == 200


@pytest.mark.parametrize("field", ["email", "username"])
def test_duplicate_accounts(auth_client: TestClient, field: str) -> None:
    register(auth_client)
    second = {**ACCOUNT, "username": "another", "email": "another@example.com"}
    second[field] = ACCOUNT[field].upper()
    assert mutation(auth_client, "register", second).status_code == 409


@pytest.mark.parametrize("password", ["short", "😀" * 19, "a" * 73, "contains\x00nulls"])
def test_invalid_passwords_are_not_echoed(auth_client: TestClient, password: str) -> None:
    response = mutation(auth_client, "register", {**ACCOUNT, "password": password})
    assert response.status_code == 422
    assert all("input" not in error for error in response.json()["detail"])


def test_csrf_missing_forged_and_wrong_origin(auth_client: TestClient) -> None:
    assert auth_client.post("/api/v1/auth/register", json=ACCOUNT).status_code == 403
    assert (
        auth_client.post(
            "/api/v1/auth/register", json=ACCOUNT, headers={"X-CSRF-Token": "forged"}
        ).status_code
        == 403
    )
    csrf = auth_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    for origin in ["https://attacker.example", "null", "http://localhost:5173.attacker.example"]:
        assert (
            auth_client.post(
                "/api/v1/auth/register",
                json=ACCOUNT,
                headers={"X-CSRF-Token": csrf, "Origin": origin},
            ).status_code
            == 403
        )


def test_refresh_rotation_and_reuse_revokes_family(auth_client: TestClient) -> None:
    first = register(auth_client)
    original_cookie = auth_client.cookies["chess_refresh"]
    second = mutation(auth_client, "refresh")
    assert second.status_code == 200
    rotated_cookie = auth_client.cookies["chess_refresh"]
    assert rotated_cookie != original_cookie
    assert second.json()["session_id"] == first["session_id"]
    assert mutation(auth_client, "refresh").status_code == 200
    newest_cookie = auth_client.cookies["chess_refresh"]
    set_cookie(auth_client, original_cookie)
    assert mutation(auth_client, "refresh").status_code == 401
    assert me(auth_client, second.json()["access_token"]).status_code == 401
    set_cookie(auth_client, newest_cookie)
    assert mutation(auth_client, "refresh").status_code == 401


@pytest.mark.parametrize("auth_client", ["America/New_York", "Asia/Kathmandu"], indirect=True)
def test_refresh_cookie_with_non_utc_database_timezone(auth_client: TestClient) -> None:
    first = register(auth_client)
    application = auth_client.app

    async def read_expiry() -> datetime:
        async with application.state.database.sessions() as session:
            timezone = await session.scalar(text("SHOW timezone"))
            assert timezone in ("America/New_York", "Asia/Kathmandu")
            expiry = await session.scalar(text("SELECT expires_at FROM refresh_sessions LIMIT 1"))
            assert isinstance(expiry, datetime)
            assert expiry.utcoffset() != timedelta(0)
            return expiry

    assert auth_client.portal is not None
    expires = auth_client.portal.call(read_expiry)
    original_token = auth_client.cookies["chess_refresh"]
    for _ in range(2):
        before = utc_now()
        response = mutation(auth_client, "refresh")
        after = utc_now()
        assert response.status_code == 200, response.text
        assert response.json()["session_id"] == first["session_id"]
        cookie: SimpleCookie[str] = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        refresh = cookie["chess_refresh"]
        assert refresh["expires"].endswith(" GMT")
        assert parsedate_to_datetime(refresh["expires"]) == expires.astimezone(UTC)
        assert (
            int((expires - after).total_seconds())
            <= int(refresh["max-age"])
            <= int((expires - before).total_seconds())
        )
        claims = jwt.decode(refresh.value, options={"verify_signature": False})
        assert claims["exp"] == int(expires.timestamp())
        assert me(auth_client, response.json()["access_token"]).status_code == 200
    assert auth_client.cookies["chess_refresh"] != original_token
    assert auth_client.portal.call(read_expiry) == expires


def test_concurrent_refresh_reuse_revokes_the_family(auth_client: TestClient) -> None:
    register(auth_client)
    cookie = auth_client.cookies["chess_refresh"]
    csrf = auth_client.get("/api/v1/auth/csrf").json()["csrf_token"]

    def rotate() -> Response:
        return auth_client.post(
            "/api/v1/auth/refresh",
            headers={"Cookie": f"chess_refresh={cookie}", "X-CSRF-Token": csrf},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(rotate) for _ in range(2)]
        responses = [request.result(timeout=15) for request in pending]
    assert sorted(response.status_code for response in responses) == [200, 401]
    issued = next(response for response in responses if response.status_code == 200)
    assert me(auth_client, issued.json()["access_token"]).status_code == 401


def test_csrf_is_bound_to_current_refresh_cookie(auth_client: TestClient) -> None:
    register(auth_client)
    csrf = auth_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    assert mutation(auth_client, "refresh").status_code == 200
    assert (
        auth_client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf}).status_code == 403
    )


def test_access_and_refresh_are_not_interchangeable(auth_client: TestClient) -> None:
    result = register(auth_client)
    assert me(auth_client, auth_client.cookies["chess_refresh"]).status_code == 401
    set_cookie(auth_client, result["access_token"])
    assert mutation(auth_client, "refresh").status_code == 401


@pytest.mark.parametrize("claim", ["exp", "iss", "aud", "sub", "token_type"])
def test_invalid_jwt_claims(auth_client: TestClient, claim: str) -> None:
    result = register(auth_client)
    # Decode without verification only to construct deliberately invalid test tokens.
    payload = jwt.decode(result["access_token"], options={"verify_signature": False})
    payload[claim] = (
        int((utc_now() - timedelta(minutes=1)).timestamp()) if claim == "exp" else "wrong"
    )
    token = jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
    assert me(auth_client, token).status_code == 401


def test_unsigned_and_missing_claim_tokens(auth_client: TestClient) -> None:
    assert me(auth_client, jwt.encode({"sub": "x"}, "", algorithm="none")).status_code == 401
    token = jwt.encode({"sub": "x"}, os.environ["JWT_SECRET"], algorithm="HS256")
    assert me(auth_client, token).status_code == 401


def test_login_rate_limit(auth_client: TestClient) -> None:
    credentials = {"email": "absent@example.com", "password": "wrong"}
    for _ in range(10):
        assert mutation(auth_client, "login", credentials).status_code == 401
    response = mutation(auth_client, "login", credentials)
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_body_limit(auth_client: TestClient) -> None:
    assert (
        auth_client.post(
            "/api/v1/auth/register",
            content="x" * 16_385,
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )


def test_cookie_flags_and_secret_storage(auth_client: TestClient) -> None:
    csrf = auth_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = auth_client.post(
        "/api/v1/auth/register", json=ACCOUNT, headers={"X-CSRF-Token": csrf}
    )
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    with engine.connect() as connection:
        password_hash = connection.scalar(text("SELECT password_hash FROM users"))
        stored_token = connection.scalar(text("SELECT token_hash FROM refresh_sessions"))
    engine.dispose()
    assert password_hash.startswith("$2b$") and password_hash != ACCOUNT["password"]
    assert len(stored_token) == 64 and stored_token != auth_client.cookies["chess_refresh"]


def test_new_login_replaces_current_cookie_session(auth_client: TestClient) -> None:
    first = register(auth_client)
    second = mutation(
        auth_client, "login", {"email": ACCOUNT["email"], "password": ACCOUNT["password"]}
    )
    assert second.status_code == 200
    assert second.json()["session_id"] != first["session_id"]
    assert me(auth_client, first["access_token"]).status_code == 401
    assert me(auth_client, second.json()["access_token"]).status_code == 200


def test_disabled_user_cannot_access_or_refresh(auth_client: TestClient) -> None:
    result = register(auth_client)
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    with engine.begin() as connection:
        connection.execute(text("UPDATE users SET is_active = false"))
    engine.dispose()
    assert me(auth_client, result["access_token"]).status_code == 401
    assert mutation(auth_client, "refresh").status_code == 401


@pytest.mark.parametrize("auth_client", ["production"], indirect=True)
def test_production_cookie_is_secure_and_host_only(auth_client: TestClient) -> None:
    response = mutation(auth_client, "register", ACCOUNT)
    assert response.status_code == 201
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-chess_refresh=")
    assert "Secure" in cookie and "HttpOnly" in cookie and "Path=/" in cookie
    assert "Domain=" not in cookie
    assert auth_client.get("/docs").status_code == 404

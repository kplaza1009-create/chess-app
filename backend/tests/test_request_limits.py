import asyncio

import pytest
from starlette.types import Message, Receive, Scope, Send

from app.middleware import SecurityHeadersMiddleware


@pytest.mark.parametrize("advertised", [b"16385", b"9" * 5000, None])
async def test_rejects_large_auth_body_before_endpoint(advertised: bytes | None) -> None:
    reached_endpoint = False
    received_body = False
    sent: list[Message] = []

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal reached_endpoint
        reached_endpoint = True

    async def receive() -> Message:
        nonlocal received_body
        received_body = True
        return {"type": "http.request", "body": b"x" * 16_385, "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http", "method": "POST", "path": "/api/v1/auth/register",
        "headers": [(b"content-length", advertised)] if advertised is not None else [],
    }
    await SecurityHeadersMiddleware(application)(scope, receive, send)
    assert not reached_endpoint
    assert received_body is (advertised is None)
    assert sent[0]["status"] == 413
    assert (b"cache-control", b"no-store") in sent[0]["headers"]


async def test_slow_auth_body_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.middleware.AUTH_BODY_TIMEOUT", 0.01)
    sent: list[Message] = []

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        pytest.fail("An incomplete request must not reach the endpoint")

    async def receive() -> Message:
        await asyncio.Event().wait()
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http", "method": "POST", "path": "/api/v1/auth/login", "headers": [],
    }
    await asyncio.wait_for(SecurityHeadersMiddleware(application)(scope, receive, send), timeout=1)
    assert sent[0]["status"] == 408

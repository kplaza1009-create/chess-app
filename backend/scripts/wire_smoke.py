"""Exercise a running local server over real HTTP and WebSocket connections.

Creates two test accounts and one unrated game. Use only a development database.
Run from backend: python scripts/wire_smoke.py
"""

import json
import os
from http.cookiejar import CookieJar
from typing import Any
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

from websockets.sync.client import connect

BASE = os.getenv("SMOKE_API_URL", "http://127.0.0.1:8000")
ORIGIN = "http://localhost:5173"


def account(name: str) -> str:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    with opener.open(BASE + "/api/v1/auth/csrf", timeout=10) as response:
        csrf = json.load(response)["csrf_token"]
    data = json.dumps(
        {"username": name, "email": f"{name}@example.com", "password": "Smoke-password-12345"}
    ).encode()
    request = Request(
        BASE + "/api/v1/auth/register",
        data=data,
        headers={
            "Origin": ORIGIN,
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
        },
    )
    with opener.open(request, timeout=10) as response:
        return str(json.load(response)["access_token"])


def main() -> None:
    suffix = uuid4().hex[:12]
    white, black = account("w_" + suffix), account("b_" + suffix)
    request = Request(
        BASE + "/api/v1/games",
        data=json.dumps({"opponent": "b_" + suffix}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {white}"},
    )
    with build_opener().open(request, timeout=10) as response:
        game_id = json.load(response)["id"]
    url = (
        BASE.replace("http://", "ws://").replace("https://", "wss://")
        + f"/api/v1/games/{game_id}/ws"
    )

    def state(ws: Any) -> dict[str, Any]:
        while True:
            result = json.loads(ws.recv(timeout=10))
            if result["type"] != "heartbeat":
                assert result["type"] == "state", result
                return dict(result)

    with connect(url, origin=ORIGIN, proxy=None) as w, connect(url, origin=ORIGIN, proxy=None) as b:
        w.send(json.dumps({"type": "auth", "token": white}))
        b.send(json.dumps({"type": "auth", "token": black}))
        assert state(w)["version"] == state(b)["version"] == 0
        for version, uci in enumerate(["f2f3", "e7e5", "g2g4", "d8h4"]):
            (w if version % 2 == 0 else b).send(
                json.dumps(
                    {
                        "type": "move",
                        "version": version,
                        "request_id": str(uuid4()),
                        "uci": uci,
                    }
                )
            )
            latest = state(w)
            assert latest["version"] == state(b)["version"] == version + 1
        assert latest["result"] == "0-1"
        assert latest["moves"][-1]["san"] == "Qh4#"
    with connect(url, origin=ORIGIN, proxy=None) as ws:
        ws.send(json.dumps({"type": "auth", "token": white}))
        assert state(ws)["version"] == 4
    print("Wire checks passed: HTTP auth, two WebSockets, synchronized moves, SAN mate, reconnect.")


if __name__ == "__main__":
    main()

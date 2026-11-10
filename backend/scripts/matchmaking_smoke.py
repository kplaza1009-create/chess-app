"""Create two local accounts, pair them, and settle a rated game over real sockets."""

import json
import os
from typing import Any
from urllib.request import Request, urlopen
from uuid import uuid4

from websockets.sync.client import ClientConnection, connect
from wire_smoke import BASE, ORIGIN, account

PEER = os.getenv("SMOKE_PEER_URL", BASE)


def api(
    base: str, path: str, token: str, method: str = "GET", data: dict[str, str] | None = None
) -> dict[str, Any]:
    request = Request(
        f"{base}/api/v1{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
        data=json.dumps(data).encode() if data is not None else None,
    )
    with urlopen(request, timeout=10) as response:
        return dict(json.load(response))


def socket_url(base: str, game_id: str) -> str:
    return base.replace("http", "ws", 1) + f"/api/v1/games/{game_id}/ws"


def state(ws: ClientConnection) -> dict[str, Any]:
    while True:
        message = json.loads(ws.recv(timeout=10))
        if message["type"] != "heartbeat":
            assert message["type"] == "state", message
            return dict(message)


def main() -> None:
    suffix = uuid4().hex[:12]
    a_token, b_token = account("a_" + suffix), account("b_" + suffix)
    path = "/matchmaking"
    control = {"time_control": "3+2"}
    waiting = api(BASE, path, a_token, "POST", control)
    assert waiting["state"] == "queued"
    assert api(BASE, f"{path}/{waiting['ticket_id']}", a_token, "DELETE") == {"state": "idle"}
    waiting = api(BASE, path, a_token, "POST", control)
    match = api(PEER, path, b_token, "POST", control)
    assert match["state"] == "matched"
    assert api(BASE, f"{path}/{waiting['ticket_id']}", a_token, "PUT") == match

    with (
        connect(socket_url(BASE, match["game_id"]), origin=ORIGIN, proxy=None) as a,
        connect(socket_url(PEER, match["game_id"]), origin=ORIGIN, proxy=None) as b,
    ):
        a.send(json.dumps({"type": "auth", "token": a_token}))
        b.send(json.dumps({"type": "auth", "token": b_token}))
        first, second = state(a), state(b)
        assert first["rated"] and second["rated"]
        assert first["color"] != second["color"]
        white, black = (a, b) if first["color"] == "w" else (b, a)
        for version, uci in enumerate(["f2f3", "e7e5", "g2g4", "d8h4"]):
            message = {"type": "move", "version": version, "request_id": str(uuid4()), "uci": uci}
            (white if version % 2 == 0 else black).send(json.dumps(message))
            w_state, b_state = state(white), state(black)
            assert w_state["version"] == b_state["version"] == version + 1
        assert w_state["result"] == b_state["result"] == "0-1"
        assert w_state["rating_change"] == {"before": 1200, "after": 1184}
        assert b_state["rating_change"] == {"before": 1200, "after": 1216}
        black.send(json.dumps(message))
        assert state(black)["rating_change"] == b_state["rating_change"]
    assert api(BASE, path, a_token) == api(PEER, path, b_token) == {"state": "idle"}
    ratings = [
        next(
            row["rating"]
            for row in api(base, "/auth/me", token)["ratings"]
            if row["speed"] == "blitz"
        )
        for base, token in ((BASE, a_token), (PEER, b_token))
    ]
    assert sorted(ratings) == [1184, 1216]
    print("Rated wire checks passed: cancel, pairing, synchronized mate, ratings, duplicate move.")


if __name__ == "__main__":
    main()

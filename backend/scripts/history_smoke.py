"""Real HTTP/WebSocket history round trip. Creates disposable development accounts.

Run from backend with the local app running: python scripts/history_smoke.py
"""

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, build_opener
from uuid import uuid4

from websockets.sync.client import connect
from wire_smoke import BASE, ORIGIN, account


def request(path: str, token: str, data: dict[str, str] | None = None) -> Any:
    message = Request(
        BASE + "/api/v1" + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with build_opener().open(message, timeout=15) as response:
        return json.load(response)


def state(ws: Any) -> dict[str, Any]:
    while True:
        message = json.loads(ws.recv(timeout=10))
        if message["type"] != "heartbeat":
            assert message["type"] == "state", message
            return dict(message)


def main() -> None:
    suffix = uuid4().hex[:10]
    first, second = account("hw_" + suffix), account("hb_" + suffix)
    game_id = request("/games", first, {"opponent": "hb_" + suffix})["id"]
    url = BASE.replace("http", "ws", 1) + f"/api/v1/games/{game_id}/ws"
    with (
        connect(url, origin=ORIGIN, proxy=None) as white,
        connect(url, origin=ORIGIN, proxy=None) as black,
    ):
        white.send(json.dumps({"type": "auth", "token": first}))
        black.send(json.dumps({"type": "auth", "token": second}))
        state(white)
        state(black)
        for version, uci in enumerate(("f2f3", "e7e5", "g2g4", "d8h4")):
            (white if version % 2 == 0 else black).send(
                json.dumps(
                    {
                        "type": "move",
                        "version": version,
                        "request_id": str(uuid4()),
                        "uci": uci,
                    }
                )
            )
            latest = state(white)
            assert latest["version"] == state(black)["version"] == version + 1
    detail = request(f"/history/online/{game_id}", first)
    assert detail["moves"][-1]["fen_after"] == latest["position"]["fen"]
    assert detail["pgn"].endswith("1. f3 e5 2. g4 Qh4# 0-1\n")
    for token in (first, second):
        listing = request("/history", token)
        assert listing["items"][0]["id"] == game_id
    imported = request("/history/import", first, {"pgn": detail["pgn"]})
    assert imported["moves"] == detail["moves"]
    assert imported["result"] == detail["result"]
    assert request(f"/history/import/{imported['id']}", first) == imported
    try:
        request(f"/history/import/{imported['id']}", second)
        raise AssertionError("Another account accessed a private import")
    except HTTPError as exc:
        assert exc.code == 404
    print("History wire checks passed: two players, checkmate, history, PGN round trip, privacy.")


if __name__ == "__main__":
    main()

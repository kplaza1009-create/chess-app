"""Real WebSocket latency and expiry checks. Development database only.

Start two workers on 8000 and 8001, with ACCESS_TOKEN_SECONDS=30.
Run python scripts/delivery_smoke.py; creates disposable accounts and a game.
"""

import json
import os
import random
import statistics
import time
from typing import Any
from urllib.request import Request, build_opener
from uuid import uuid4

from websockets.sync.client import connect
from wire_smoke import BASE, ORIGIN, account


def state(ws: Any, version: int) -> dict[str, Any]:
    while True:
        result = json.loads(ws.recv(timeout=10))
        assert result["type"] != "error", result
        if result["type"] == "state" and result["version"] >= version:
            return dict(result)


def main() -> None:
    suffix = uuid4().hex[:10]
    white, black = account("w_" + suffix), account("b_" + suffix)
    request = Request(
        BASE + "/api/v1/games",
        data=json.dumps({"opponent": "b_" + suffix}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {white}"},
    )
    with build_opener().open(request, timeout=10) as response:
        game_id = json.load(response)["id"]
    url = BASE.replace("http", "ws", 1) + f"/api/v1/games/{game_id}/ws"
    peer = (
        os.getenv("SMOKE_PEER_URL", BASE).replace("http", "ws", 1) + f"/api/v1/games/{game_id}/ws"
    )
    samples = []
    rng = random.Random(17)
    with (
        connect(url, origin=ORIGIN, proxy=None) as w,
        connect(peer, origin=ORIGIN, proxy=None) as b,
    ):
        w.send(json.dumps({"type": "auth", "token": white}))
        b.send(json.dumps({"type": "auth", "token": black}))
        latest = state(w, 0)
        state(b, 0)
        for version in range(30):
            assert latest["result"] == "*", latest
            mover, opponent = (w, b) if version % 2 == 0 else (b, w)
            move = rng.choice(latest["position"]["legal_moves"])
            start = time.perf_counter()
            mover.send(
                json.dumps(
                    {"type": "move", "version": version, "request_id": str(uuid4()), "uci": move}
                )
            )
            latest = state(opponent, version + 1)
            samples.append((time.perf_counter() - start) * 1000)
            state(mover, version + 1)
        print(
            f"Opponent delivery: n=30 mean={statistics.mean(samples):.1f}ms "
            f"max={max(samples):.1f}ms",
            flush=True,
        )
        assert max(samples) < 100, samples
        if os.getenv("SMOKE_WAIT_EXPIRY") == "1":
            time.sleep(31)
            w.send(
                json.dumps(
                    {
                        "type": "move",
                        "version": 30,
                        "request_id": str(uuid4()),
                        "uci": latest["position"]["legal_moves"][0],
                    }
                )
            )
            assert state(b, 31)["version"] == 31
            assert state(w, 31)["version"] == 31
            print("Both existing sockets survived 30-second token expiry and accepted a move.")


if __name__ == "__main__":
    main()

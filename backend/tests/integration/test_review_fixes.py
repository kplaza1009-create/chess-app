import os
import time
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from starlette.websockets import WebSocketDisconnect

from app.services.security import utc_now
from tests.integration.test_games import ORIGIN, room


def test_first_moves_start_clocks_and_names(auth_client: TestClient) -> None:
    game_id, white, black = room(auth_client)
    with (
        auth_client.websocket_connect(
            f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
        ) as w,
        auth_client.websocket_connect(
            f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
        ) as b,
    ):
        w.send_json({"type": "auth", "token": white})
        state = w.receive_json()
        assert state["opponent"] == "blackplayer"
        assert not state["clock"]["running"]
        assert 0 < state["clock"]["first_move_ms"] <= 30000
        b.send_json({"type": "auth", "token": black})
        assert b.receive_json()["opponent"] == "whiteplayer"
        for version, uci in enumerate(["e2e4", "e7e5"]):
            (w if version == 0 else b).send_json(
                {"type": "move", "version": version, "request_id": str(uuid4()), "uci": uci}
            )
            state = w.receive_json()
            assert b.receive_json()["version"] == version + 1
            assert state["clock"]["running"] == (version == 1)
            assert state["clock"]["black_ms"] == 600000
            assert state["clock"]["white_ms"] > 599000


@pytest.mark.parametrize("white_moved", [False, True])
def test_missing_first_move_aborts_unrated(auth_client: TestClient, white_moved: bool) -> None:
    game_id, white, _ = room(auth_client)
    with auth_client.websocket_connect(
        f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
    ) as ws:
        ws.send_json({"type": "auth", "token": white})
        ws.receive_json()
        if white_moved:
            ws.send_json({"type": "move", "version": 0, "request_id": str(uuid4()), "uci": "e2e4"})
            ws.receive_json()
        engine = create_engine(os.environ["TEST_DATABASE_URL"])
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE games SET rated=true, "
                        "first_move_deadline=clock_timestamp()-interval '1 second' WHERE id=:id"
                    ),
                    {"id": game_id},
                )
            state = ws.receive_json()
            assert state["status"] == "aborted" and state["result"] == "*"
            assert state["position"]["legal_moves"] == []
            with engine.connect() as connection:
                assert (
                    connection.execute(
                        text("SELECT rated FROM games WHERE id=:id"), {"id": game_id}
                    ).scalar()
                    is False
                )
                assert (
                    connection.execute(
                        text("SELECT count(*) FROM rating_changes WHERE game_id=:id"),
                        {"id": game_id},
                    ).scalar()
                    == 0
                )
            with pytest.raises(IntegrityError), engine.begin() as connection:
                connection.execute(
                    text("UPDATE games SET rated=true WHERE id=:id"), {"id": game_id}
                )
        finally:
            engine.dispose()
    assert auth_client.app.state.game_connections == {}
    assert auth_client.app.state.game_notifications.subscribers == {}


def test_socket_survives_token_expiry_but_new_handshake_fails(auth_client: TestClient) -> None:
    game_id, white, _ = room(auth_client)
    security = auth_client.app.state.security
    claims = security.decode(white, "access")
    short = security.encode(claims.sub, claims.sid, "access", utc_now() + timedelta(seconds=2))
    path = f"/api/v1/games/{game_id}/ws"
    with auth_client.websocket_connect(path, headers={"Origin": ORIGIN}) as ws:
        ws.send_json({"type": "auth", "token": short})
        ws.receive_json()
        time.sleep(2.1)
        ws.send_json({"type": "move", "version": 0, "request_id": str(uuid4()), "uci": "e2e4"})
        assert ws.receive_json()["version"] == 1
        with auth_client.websocket_connect(path, headers={"Origin": ORIGIN}) as expired:
            expired.send_json({"type": "auth", "token": short})
            with pytest.raises(WebSocketDisconnect):
                expired.receive_json()

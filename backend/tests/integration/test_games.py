import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.websockets import WebSocketDisconnect

from app.services.games import TERMINATIONS

ORIGIN = "http://localhost:5173"


def register(client: TestClient, name: str) -> str:
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/register",
        headers={"X-CSRF-Token": csrf},
        json={"username": name, "email": f"{name}@example.com", "password": "Long-password-123"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["access_token"])


def room(client: TestClient) -> tuple[str, str, str]:
    white = register(client, "whiteplayer")
    client.cookies.clear()
    black = register(client, "blackplayer")
    response = client.post(
        "/api/v1/games",
        json={"opponent": "blackplayer"},
        headers={"Authorization": f"Bearer {white}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], white, black


def test_socket_moves_reconnect_and_duplicate(auth_client: TestClient) -> None:
    game_id, white, black = room(auth_client)
    url = f"/api/v1/games/{game_id}/ws"
    with auth_client.websocket_connect(url, headers={"Origin": ORIGIN}) as w:
        w.send_json({"type": "auth", "token": white})
        assert w.receive_json()["version"] == 0
        with auth_client.websocket_connect(url, headers={"Origin": ORIGIN}) as b:
            b.send_json({"type": "auth", "token": black})
            assert b.receive_json()["color"] == "b"
            b.send_json({"type": "move", "version": 0, "request_id": str(uuid4()), "uci": "e7e5"})
            assert b.receive_json()["type"] == "error"
            assert b.receive_json()["version"] == 0
            message = {"type": "move", "version": 0, "request_id": str(uuid4()), "uci": "e2e4"}
            w.send_json(message)
            assert w.receive_json()["moves"][0]["san"] == "e4"
            assert b.receive_json()["version"] == 1
            w.send_json(message)
            assert w.receive_json()["version"] == 1
            b.send_json({"type": "move", "version": 0, "request_id": str(uuid4()), "uci": "e7e5"})
            assert b.receive_json()["type"] == "error"
            assert b.receive_json()["version"] == 1
            b.send_json({"type": "move", "version": 1, "request_id": str(uuid4()), "uci": "e7e5"})
            assert b.receive_json()["version"] == 2
            assert w.receive_json()["version"] == 2
    with auth_client.websocket_connect(url, headers={"Origin": ORIGIN}) as ws:
        ws.send_json({"type": "auth", "token": white})
        state = ws.receive_json()
        assert state["version"] == 2
        assert [m["san"] for m in state["moves"]] == ["e4", "e5"]


def test_socket_origin_auth_membership(auth_client: TestClient) -> None:
    game_id, white, _ = room(auth_client)
    url = f"/api/v1/games/{game_id}/ws"
    with pytest.raises(WebSocketDisconnect):
        with auth_client.websocket_connect(url, headers={"Origin": "https://evil.example"}):
            pass
    with auth_client.websocket_connect(url, headers={"Origin": ORIGIN}) as ws:
        ws.send_json({"type": "auth", "token": "invalid"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    auth_client.cookies.clear()
    outsider = register(auth_client, "outsider")
    assert (
        auth_client.get(
            f"/api/v1/games/{game_id}/ticket", headers={"Authorization": f"Bearer {outsider}"}
        ).status_code
        == 404
    )
    assert (
        auth_client.get(
            f"/api/v1/games/{game_id}/ticket", headers={"Authorization": f"Bearer {white}"}
        ).status_code
        == 200
    )


def test_auto_repetition_persisted(auth_client: TestClient) -> None:
    game_id, white, black = room(auth_client)
    with auth_client.websocket_connect(
        f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
    ) as w:
        w.send_json({"type": "auth", "token": white})
        w.receive_json()
        with auth_client.websocket_connect(
            f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
        ) as b:
            b.send_json({"type": "auth", "token": black})
            b.receive_json()
            for version, uci in enumerate(["g1f3", "g8f6", "f3g1", "f6g8"] * 2):
                (w if version % 2 == 0 else b).send_json(
                    {"type": "move", "version": version, "request_id": str(uuid4()), "uci": uci}
                )
                state = w.receive_json()
                assert b.receive_json()["version"] == version + 1
            assert state["result"] == "1/2-1/2"
            assert state["position"]["ending"] == "repetition"
            assert state["position"]["legal_moves"] == []


@pytest.mark.parametrize("reason", list(TERMINATIONS))
def test_all_engine_terminations_fit_database(auth_client: TestClient, reason: str) -> None:
    game_id, _, _ = room(auth_client)
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE games SET status='finished', result=:result, "
                    "termination=:reason, ended_at=now() WHERE id=:id"
                ),
                {
                    "id": game_id,
                    "reason": TERMINATIONS[reason],
                    "result": "1-0" if reason == "checkmate" else "1/2-1/2",
                },
            )
    finally:
        engine.dispose()


def test_two_connections_race_same_move(auth_client: TestClient) -> None:
    game_id, white, _ = room(auth_client)
    message = {"type": "move", "version": 0, "request_id": str(uuid4()), "uci": "e2e4"}

    def send() -> int:
        with auth_client.websocket_connect(
            f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
        ) as ws:
            ws.send_json({"type": "auth", "token": white})
            ws.receive_json()
            ws.send_json(message)
            return int(ws.receive_json()["version"])

    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(lambda _: send(), range(2))) == [1, 1]
    assert auth_client.app.state.game_connections == {}
    assert auth_client.app.state.game_notifications.subscribers == {}


@pytest.mark.parametrize("send_move", [False, True])
def test_socket_teardown_releases_slots_and_subscriptions(
    auth_client: TestClient, send_move: bool
) -> None:
    game_id, white, _ = room(auth_client)
    with auth_client.websocket_connect(
        f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
    ) as ws:
        ws.send_json({"type": "auth", "token": white})
        assert ws.receive_json()["version"] == 0
        if send_move:
            ws.send_json({"type": "move", "version": 0, "request_id": str(uuid4()), "uci": "e2e4"})
            # Exit immediately, without waiting for a move acknowledgement.
    assert auth_client.app.state.game_connections == {}
    assert auth_client.app.state.game_notifications.subscribers == {}


@pytest.mark.parametrize("binary", [False, True])
def test_bad_frames_close_cleanly(auth_client: TestClient, binary: bool) -> None:
    game_id, white, _ = room(auth_client)
    with auth_client.websocket_connect(
        f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
    ) as ws:
        ws.send_json({"type": "auth", "token": white})
        ws.receive_json()
        if binary:
            ws.send_bytes(b"invalid")
        else:
            ws.send_text("x" * 1025)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1008


def test_revoked_session_disconnects(auth_client: TestClient) -> None:
    game_id, _, black = room(auth_client)
    with auth_client.websocket_connect(
        f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
    ) as ws:
        ws.send_json({"type": "auth", "token": black})
        ws.receive_json()
        csrf = auth_client.get("/api/v1/auth/csrf").json()["csrf_token"]
        assert (
            auth_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code
            == 200
        )
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4401


def test_fifty_move_draw_after_accepted_move(auth_client: TestClient) -> None:
    game_id, white, _ = room(auth_client)
    # Seed a legal pre-game fixture; public room creation never accepts custom FEN.
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    fen = "4k3/8/8/8/8/8/R7/4K3 w - - 99 1"
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE games SET initial_fen=:fen, current_fen=:fen WHERE id=:id"),
                {"fen": fen, "id": game_id},
            )
    finally:
        engine.dispose()
    with auth_client.websocket_connect(
        f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
    ) as ws:
        ws.send_json({"type": "auth", "token": white})
        ws.receive_json()
        ws.send_json({"type": "move", "version": 0, "request_id": str(uuid4()), "uci": "a2a3"})
        state = ws.receive_json()
        assert state["result"] == "1/2-1/2"
        assert state["position"]["ending"] == "fifty_move"


def test_failed_commit_does_not_poison_engine_cache(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import games

    game_id, white, _ = room(auth_client)
    url = f"/api/v1/games/{game_id}/ws"

    async def fail_notification(*args: object) -> None:
        # play() has already advanced the engine and flushed the move row here.
        raise SQLAlchemyError("Simulated failure before commit")

    with monkeypatch.context() as scoped:
        scoped.setattr(games, "notify_transaction", fail_notification)
        with auth_client.websocket_connect(url, headers={"Origin": ORIGIN}) as ws:
            ws.send_json({"type": "auth", "token": white})
            assert ws.receive_json()["version"] == 0
            ws.send_json({"type": "move", "version": 0, "request_id": str(uuid4()), "uci": "e2e4"})
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_json()
            assert closed.value.code == 1013
    with auth_client.websocket_connect(url, headers={"Origin": ORIGIN}) as ws:
        ws.send_json({"type": "auth", "token": white})
        state = ws.receive_json()
        assert state["version"] == 0
        assert state["moves"] == []
        ws.send_json({"type": "move", "version": 0, "request_id": str(uuid4()), "uci": "d2d4"})
        state = ws.receive_json()
        assert state["version"] == 1
        assert [move["uci"] for move in state["moves"]] == ["d2d4"]

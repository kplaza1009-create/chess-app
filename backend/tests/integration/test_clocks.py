import os
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

from app.db.models import Game
from app.services.clocks import database_now, expire
from app.services.games import play
from tests.integration.test_games import ORIGIN, room


def update(game_id: str, assignment: str) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(text(f"UPDATE games SET {assignment} WHERE id=:id"), {"id": game_id})
    finally:
        engine.dispose()


def test_increment_persistence_and_duplicate(auth_client: TestClient) -> None:
    game_id, white, _ = room(auth_client)
    update(
        game_id,
        "increment_ms=2000, white_remaining_ms=60000, "
        "turn_started_at=clock_timestamp() - interval '5 seconds'",
    )
    with auth_client.websocket_connect(
        f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
    ) as ws:
        ws.send_json({"type": "auth", "token": white})
        assert ws.receive_json()["clock"]["white_ms"] <= 55000
        move = {"type": "move", "version": 0, "request_id": str(uuid4()), "uci": "e2e4"}
        ws.send_json(move)
        first = ws.receive_json()
        assert 54000 < first["clock"]["white_ms"] <= 57000
        ws.send_json(move)
        assert ws.receive_json()["clock"]["white_ms"] == first["clock"]["white_ms"]
    with auth_client.websocket_connect(
        f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
    ) as ws:
        ws.send_json({"type": "auth", "token": white})
        restored = ws.receive_json()
        assert restored["clock"]["white_ms"] == first["clock"]["white_ms"]
        assert restored["clock"]["black_ms"] <= first["clock"]["black_ms"]


def test_expired_game_settles_without_connections(auth_client: TestClient) -> None:
    game_id, white, _ = room(auth_client)
    update(
        game_id, "white_remaining_ms=1000, turn_started_at=clock_timestamp() - interval '2 seconds'"
    )
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with engine.connect() as connection:
                result = connection.execute(
                    text("SELECT result FROM games WHERE id=:id"), {"id": game_id}
                ).scalar()
            if result == "0-1":
                break
            time.sleep(0.05)
        assert result == "0-1"
    finally:
        engine.dispose()
    with auth_client.websocket_connect(
        f"/api/v1/games/{game_id}/ws", headers={"Origin": ORIGIN}
    ) as ws:
        ws.send_json({"type": "auth", "token": white})
        state = ws.receive_json()
        assert state["clock"]["white_ms"] == 0
        assert not state["clock"]["running"]
        ws.send_json(
            {"type": "move", "version": state["version"], "request_id": str(uuid4()), "uci": "e2e4"}
        )
        assert ws.receive_json()["type"] == "error"
        assert ws.receive_json()["moves"] == []


def test_invalid_time_control(auth_client: TestClient) -> None:
    _, white, _ = room(auth_client)
    assert (
        auth_client.post(
            "/api/v1/games",
            headers={"Authorization": f"Bearer {white}"},
            json={"opponent": "blackplayer", "time_control": "-1+10000"},
        ).status_code
        == 422
    )


def test_timeout_race_cannot_insert_move(auth_client: TestClient) -> None:
    game_id, _, _ = room(auth_client)
    update(
        game_id, "white_remaining_ms=1000, turn_started_at=clock_timestamp() - interval '2 seconds'"
    )

    async def contend(move: bool) -> None:
        async with auth_client.app.state.database.sessions() as session, session.begin():
            game = await session.scalar(
                select(Game).where(Game.id == UUID(game_id)).with_for_update()
            )
            assert game is not None
            if move and game.status == "active":
                assert game.white_user_id is not None
                await play(session, game, game.white_user_id, game.version, uuid4(), "e2e4")
            else:
                expire(game, await database_now(session))

    def run(move: bool) -> None:
        assert auth_client.portal is not None
        auth_client.portal.call(contend, move)

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(run, [True, False]))
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT result, version, ply_count FROM games WHERE id=:id"), {"id": game_id}
            ).one()
            assert tuple(result) == ("0-1", 1, 0)
    finally:
        engine.dispose()

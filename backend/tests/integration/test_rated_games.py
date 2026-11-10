import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from app.db.models import Game
from app.services import games
from app.services.clocks import database_now
from app.services.ratings import settle_ratings
from tests.integration.test_games import ORIGIN
from tests.integration.test_matchmaking import bearer, execute, player, queue


def ranked_room(client: TestClient, control: str = "3+2") -> tuple[str, str, str]:
    first, second = (player(client, name) for name in ("first_player", "second_player"))
    assert queue(client, first, control)["state"] == "queued"
    match = queue(client, second, control)
    assert match["state"] == "matched"
    return match["game_id"], first, second


@contextmanager
def sockets(
    client: TestClient, room: tuple[str, str, str]
) -> Iterator[tuple[WebSocketTestSession, WebSocketTestSession]]:
    game_id, first, second = room
    path = f"/api/v1/games/{game_id}/ws"
    with (
        client.websocket_connect(path, headers={"Origin": ORIGIN}) as a,
        client.websocket_connect(path, headers={"Origin": ORIGIN}) as b,
    ):
        a.send_json({"type": "auth", "token": first})
        b.send_json({"type": "auth", "token": second})
        a_state, b_state = a.receive_json(), b.receive_json()
        assert a_state["rated"] and b_state["rated"]
        assert a_state["color"] != b_state["color"]
        yield (a, b) if a_state["color"] == "w" else (b, a)


def moves(
    white: WebSocketTestSession, black: WebSocketTestSession, ucis: list[str]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    white_state: dict[str, Any] = {}
    black_state: dict[str, Any] = {}
    message: dict[str, Any] = {}
    for version, uci in enumerate(ucis):
        message = {"type": "move", "version": version, "request_id": str(uuid4()), "uci": uci}
        (white if version % 2 == 0 else black).send_json(message)
        white_state, black_state = white.receive_json(), black.receive_json()
        assert white_state["version"] == black_state["version"] == version + 1
    return white_state, black_state, message


def rating_rows(speed: str = "blitz") -> list[tuple[Any, ...]]:
    return execute(
        "SELECT rating, wins, losses, draws FROM user_ratings WHERE speed=:speed ORDER BY rating",
        speed=speed,
    )


def test_rated_checkmate_settles_once_and_exposes_result(auth_client: TestClient) -> None:
    room = ranked_room(auth_client)
    game_id, first, second = room
    with sockets(auth_client, room) as (white, black):
        a, b, final_move = moves(white, black, ["f2f3", "e7e5", "g2g4", "d8h4"])
        assert a["result"] == b["result"] == "0-1"
        assert a["rating_change"] == {"before": 1200, "after": 1184}
        assert b["rating_change"] == {"before": 1200, "after": 1216}
        black.send_json(final_move)
        assert black.receive_json()["rating_change"] == b["rating_change"]

    async def settle_again() -> None:
        async with auth_client.app.state.database.sessions() as session, session.begin():
            game = await session.get(Game, UUID(game_id), with_for_update=True)
            assert game is not None
            await settle_ratings(session, game)

    assert auth_client.portal is not None
    auth_client.portal.call(settle_again)
    assert rating_rows() == [(1184, 0, 1, 0), (1216, 1, 0, 0)]
    assert rating_rows("rapid") == [(1200, 0, 0, 0)] * 2
    assert execute("SELECT count(*) FROM rating_changes WHERE game_id=:id", id=game_id) == [(2,)]
    assert queue(auth_client, first, method="GET") == {"state": "idle"}
    ratings = [
        next(
            row["rating"]
            for row in auth_client.get("/api/v1/auth/me", headers=bearer(token)).json()["ratings"]
            if row["speed"] == "blitz"
        )
        for token in (first, second)
    ]
    assert sorted(ratings) == [1184, 1216]


def test_uneven_rated_draw_transfers_points_in_one_pool(auth_client: TestClient) -> None:
    first, second = (player(auth_client, name) for name in ("first_player", "second_player"))
    execute(
        "UPDATE user_ratings SET rating=1300 WHERE speed='rapid' "
        "AND user_id=(SELECT id FROM users WHERE username='second_player')"
    )
    queue(auth_client, first, "10+0")
    game_id = queue(auth_client, second, "10+0")["game_id"]
    with sockets(auth_client, (game_id, first, second)) as (white, black):
        a, b, _ = moves(white, black, ["g1f3", "g8f6", "f3g1", "f6g8"] * 2)
        assert a["result"] == b["result"] == "1/2-1/2"
        assert a["position"]["ending"] == b["position"]["ending"] == "repetition"
    assert rating_rows("rapid") == [(1204, 0, 0, 1), (1296, 0, 0, 1)]
    assert rating_rows() == [(1200, 0, 0, 0)] * 2


def test_mate_and_ratings_rollback_together(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    room = ranked_room(auth_client)
    game_id = room[0]

    async def fail_notification(*args: object) -> None:
        raise SQLAlchemyError("Simulated transaction failure")

    with sockets(auth_client, room) as (white, black):
        moves(white, black, ["f2f3", "e7e5", "g2g4"])
        with monkeypatch.context() as scoped:
            scoped.setattr(games, "notify_transaction", fail_notification)
            black.send_json(
                {"type": "move", "version": 3, "request_id": str(uuid4()), "uci": "d8h4"}
            )
            with pytest.raises(WebSocketDisconnect) as closed:
                black.receive_json()
            assert closed.value.code == 1013
    assert execute("SELECT status, ply_count FROM games WHERE id=:id", id=game_id) == [
        ("active", 3)
    ]
    assert execute("SELECT count(*) FROM rating_changes") == [(0,)]
    assert rating_rows() == [(1200, 0, 0, 0)] * 2


@pytest.mark.parametrize("opening_abort", [False, True])
def test_clock_worker_settles_timeout_but_never_rates_an_abort(
    auth_client: TestClient, opening_abort: bool
) -> None:
    game_id, first, _ = ranked_room(auth_client, "1+0")
    if opening_abort:
        execute(
            "UPDATE games SET first_move_deadline=clock_timestamp()-interval '1 second' "
            "WHERE id=:id",
            id=game_id,
        )
    else:
        execute(
            "UPDATE games SET first_move_deadline=NULL, "
            "turn_started_at=clock_timestamp()-interval '61 seconds' WHERE id=:id",
            id=game_id,
        )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        rows = execute("SELECT status, rated, result FROM games WHERE id=:id", id=game_id)
        if rows[0][0] != "active":
            break
        time.sleep(0.05)
    if opening_abort:
        assert rows == [("aborted", False, "*")]
        assert rating_rows("bullet") == [(1200, 0, 0, 0)] * 2
        assert execute("SELECT count(*) FROM rating_changes") == [(0,)]
    else:
        assert rows == [("finished", True, "0-1")]
        assert rating_rows("bullet") == [(1184, 0, 1, 0), (1216, 1, 0, 0)]
        assert execute("SELECT count(*) FROM rating_changes") == [(2,)]
    assert queue(auth_client, first, method="GET") == {"state": "idle"}


def test_move_after_flag_settles_rated_result_without_inserting_move(
    auth_client: TestClient,
) -> None:
    game_id, _, _ = ranked_room(auth_client)

    async def submit_late_move() -> None:
        async with auth_client.app.state.database.sessions() as session, session.begin():
            game = await session.get(Game, UUID(game_id), with_for_update=True)
            assert game is not None and game.white_user_id is not None
            # Stage the expiry while holding the same row lock as a real move.
            game.first_move_deadline = None
            game.turn_started_at = await database_now(session) - timedelta(minutes=4)
            await games.play(session, game, game.white_user_id, 0, uuid4(), "e2e4")

    assert auth_client.portal is not None
    auth_client.portal.call(submit_late_move)
    assert execute("SELECT result, termination, ply_count FROM games") == [("0-1", "timeout", 0)]
    assert execute("SELECT count(*) FROM moves") == [(0,)]
    assert rating_rows() == [(1184, 0, 1, 0), (1216, 1, 0, 0)]

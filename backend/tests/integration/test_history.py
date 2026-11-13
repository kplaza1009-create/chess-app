import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.chess.pgn import parse_pgn
from tests.integration.test_matchmaking import bearer, execute, player
from tests.integration.test_rated_games import moves, ranked_room, sockets

PATH = "/api/v1/history"
PGN = '[White "Outside White"] [Black "Outside Black"]\n1. f3 e5 2. g4 Qh4 0-1'


def test_import_is_private_persistent_unrated_and_replayable(auth_client: TestClient) -> None:
    alice, bob = (player(auth_client, name) for name in ("alice", "bobby"))
    response = auth_client.post(f"{PATH}/import", headers=bearer(alice), json={"pgn": PGN})
    assert response.status_code == 201, response.text
    data = response.json()
    game_id = data["id"]
    assert data["moves"][-1]["san"] == "Qh4#"
    assert auth_client.get(f"{PATH}/import/{game_id}", headers=bearer(alice)).json() == data
    listing = auth_client.get(PATH, headers=bearer(alice)).json()
    assert listing["page"] == 1 and not listing["has_more"]
    assert listing["items"][0]["white"] == "Outside White"
    assert listing["items"][0]["rated"] is False
    assert listing["items"][0]["rating_after"] is None
    assert auth_client.get(PATH, headers=bearer(bob)).json()["items"] == []
    for suffix in ("", "/pgn"):
        assert (
            auth_client.get(f"{PATH}/import/{game_id}{suffix}", headers=bearer(bob)).status_code
            == 404
        )
    assert execute("SELECT count(*) FROM games") == [(0,)]
    assert execute("SELECT count(*) FROM rating_changes") == [(0,)]
    assert execute("SELECT DISTINCT rating,wins,losses,draws FROM user_ratings") == [
        (1200, 0, 0, 0)
    ]
    export = auth_client.get(f"{PATH}/import/{game_id}/pgn", headers=bearer(alice))
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/x-chess-pgn")
    assert export.headers["cache-control"] == "no-store"
    assert ".pgn" in export.headers["content-disposition"]
    assert parse_pgn(export.text).moves[-1].san == "Qh4#"


@pytest.mark.parametrize("auth_client", ["America/New_York"], indirect=True)
def test_rated_history_exports_actual_result_positions_and_historical_elo(
    auth_client: TestClient,
) -> None:
    room = ranked_room(auth_client)
    game_id, first, second = room
    execute("UPDATE games SET created_at='2026-11-02T00:30:00Z' WHERE id=:id", id=game_id)
    stranger = player(auth_client, "stranger")
    # Live rooms cannot be read through the archive as a spectator shortcut.
    assert auth_client.get(f"{PATH}/online/{game_id}", headers=bearer(first)).status_code == 404
    assert auth_client.get(PATH, headers=bearer(first)).json()["items"] == []
    with sockets(auth_client, room) as (white, black):
        final, _, _ = moves(white, black, ["f2f3", "e7e5", "g2g4", "d8h4"])
    # Keep the archive independent from players' subsequent rating changes.
    execute("UPDATE user_ratings SET rating=rating+100")
    for token in (first, second):
        item = auth_client.get(PATH, headers=bearer(token)).json()["items"][0]
        assert item["rated"] and item["time_control"] == "3+2"
        assert item["rating_before"] == 1200
        assert item["rating_after"] in (1184, 1216)
        detail = auth_client.get(f"{PATH}/online/{game_id}", headers=bearer(token)).json()
        assert detail["result"] == "0-1" and detail["termination"] == "checkmate"
        assert detail["moves"][-1]["fen_after"] == final["position"]["fen"]
        assert detail["headers"]["WhiteElo"] == detail["headers"]["BlackElo"] == "1200"
        assert detail["headers"]["Date"] == "2026.11.02"
        imported = parse_pgn(detail["pgn"])
        assert [move.uci for move in imported.moves] == ["f2f3", "e7e5", "g2g4", "d8h4"]
        assert imported.result == "0-1"
    for suffix in ("", "/pgn"):
        assert (
            auth_client.get(
                f"{PATH}/online/{game_id}{suffix}", headers=bearer(stranger)
            ).status_code
            == 404
        )
    imported = auth_client.post(
        PATH + "/import", headers=bearer(first), json={"pgn": detail["pgn"]}
    )
    assert imported.status_code == 201
    combined = auth_client.get(PATH, headers=bearer(first)).json()["items"]
    assert [item["source"] for item in combined] == ["import", "online"]


@pytest.mark.parametrize("legacy_untimed", [False, True])
def test_aborted_games_remain_unrated_in_history_and_pgn(
    auth_client: TestClient,
    legacy_untimed: bool,
) -> None:
    game_id, first, _ = ranked_room(auth_client)
    execute(
        "UPDATE games SET status='aborted',rated=false,termination='aborted',"
        "ended_at=clock_timestamp(),first_move_deadline=NULL WHERE id=:id",
        id=game_id,
    )
    if legacy_untimed:
        execute("UPDATE games SET turn_started_at=NULL WHERE id=:id", id=game_id)
    item = auth_client.get(PATH, headers=bearer(first)).json()["items"][0]
    assert item["status"] == "aborted" and item["rated"] is False
    assert item["rating_before"] is item["rating_after"] is None
    detail = auth_client.get(f"{PATH}/online/{game_id}", headers=bearer(first)).json()
    assert detail["headers"]["Termination"] == "abandoned"
    assert parse_pgn(detail["pgn"]).moves == ()
    assert detail["result"] == "*"
    assert item["time_control"] == (None if legacy_untimed else "3+2")
    assert detail["headers"]["TimeControl"] == ("-" if legacy_untimed else "180+2")


def test_history_pagination_filters_and_deterministic_ties(auth_client: TestClient) -> None:
    token = player(auth_client, "collector")
    # Seed validated imports, avoiding API rate-limit bypasses in the application.
    for _ in range(23):
        execute(
            "INSERT INTO imported_games(id,owner_id,headers,initial_fen,moves,result,"
            "ply_count,pgn,created_at) "
            "SELECT :id,id,'{}',:fen,'[]','*',0,:pgn,'2026-11-01T10:00:00Z' "
            "FROM users WHERE username='collector'",
            id=uuid4(),
            fen=parse_pgn("*").initial_fen,
            pgn=parse_pgn("*").export(),
        )
    one = auth_client.get(PATH, headers=bearer(token)).json()
    two = auth_client.get(PATH + "?page=2", headers=bearer(token)).json()
    assert len(one["items"]) == 20 and one["has_more"]
    assert len(two["items"]) == 3 and not two["has_more"]
    assert not ({item["id"] for item in one["items"]} & {item["id"] for item in two["items"]})
    assert auth_client.get(PATH, headers=bearer(token)).json() == one
    assert auth_client.get(PATH + "?source=online", headers=bearer(token)).json()["items"] == []
    assert (
        len(auth_client.get(PATH + "?source=import", headers=bearer(token)).json()["items"]) == 20
    )
    for query in ("?page=0", "?page=501", "?source=other"):
        assert auth_client.get(PATH + query, headers=bearer(token)).status_code == 422


def test_import_limits_validation_and_no_partial_writes(auth_client: TestClient) -> None:
    token = player(auth_client, "collector")
    for pgn in ("1. e4 e5 2. e4 *", "a" * 65537, "\ud800", "{" + "é" * 32768 + "} *"):
        result = auth_client.post(
            PATH + "/import",
            headers={**bearer(token), "Content-Type": "application/json"},
            content=json.dumps({"pgn": pgn}),
        )
        assert result.status_code == 422, result.text
    assert execute("SELECT count(*) FROM imported_games") == [(0,)]
    assert (
        auth_client.post(PATH + "/import", headers=bearer(token), json={"pgn": "*"}).status_code
        == 201
    )
    assert execute("SELECT count(*) FROM imported_games") == [(1,)]


def test_import_rate_limit_is_shared_and_bounded(auth_client: TestClient) -> None:
    token = player(auth_client, "collector")
    for _ in range(5):
        response = auth_client.post(PATH + "/import", headers=bearer(token), json={"pgn": "*"})
        assert response.status_code == 201
    limited = auth_client.post(PATH + "/import", headers=bearer(token), json={"pgn": "*"})
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0
    assert execute("SELECT count(*) FROM imported_games") == [(5,)]


def test_auth_required_and_revoked_sessions_cannot_read_history(auth_client: TestClient) -> None:
    assert auth_client.get(PATH).status_code == 401
    assert auth_client.post(PATH + "/import", json={"pgn": "*"}).status_code == 401
    token = player(auth_client, "collector")
    execute("UPDATE refresh_sessions SET revoked_at=clock_timestamp()")
    assert auth_client.get(PATH, headers=bearer(token)).status_code == 401


def test_import_body_limit_is_scoped_and_unknown_ids_do_not_leak(auth_client: TestClient) -> None:
    token = player(auth_client, "collector")
    # More than auth's 16 KiB is permitted for a PGN comment.
    pgn = "{" + "a" * 20000 + "} 1. e4 *"
    assert (
        auth_client.post(PATH + "/import", headers=bearer(token), json={"pgn": pgn}).status_code
        == 201
    )
    assert (
        auth_client.post(PATH + "/import", headers=bearer(token), content="a" * 524289).status_code
        == 413
    )
    assert auth_client.post("/api/v1/auth/login", content="a" * 20000).status_code == 413
    assert auth_client.get(f"{PATH}/import/{uuid4()}", headers=bearer(token)).status_code == 404
    assert auth_client.get(f"{PATH}/bogus/{uuid4()}", headers=bearer(token)).status_code == 422
    assert auth_client.get(f"{PATH}/online/not-a-uuid", headers=bearer(token)).status_code == 422

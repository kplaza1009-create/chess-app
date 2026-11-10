import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.main import create_app
from tests.integration.test_games import ORIGIN, register

PATH = "/api/v1/matchmaking"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def player(client: TestClient, name: str) -> str:
    client.cookies.clear()
    return register(client, name)


def queue(
    client: TestClient, token: str, control: str = "3+2", *, method: str = "POST", ticket: str = ""
) -> dict[str, Any]:
    response = client.request(
        method,
        PATH + (f"/{ticket}" if ticket else ""),
        headers=bearer(token),
        json={"time_control": control} if method == "POST" else None,
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def execute(sql: str, **parameters: object) -> list[tuple[Any, ...]]:
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with engine.begin() as connection:
            result = connection.execute(text(sql), parameters)
            return [tuple(row) for row in result] if result.returns_rows else []
    finally:
        engine.dispose()


def test_queue_requires_auth_and_accepts_only_presets(auth_client: TestClient) -> None:
    assert auth_client.get(PATH).status_code == 401
    token = player(auth_client, "queue_user")
    for data in ({"time_control": "3+3"}, {"time_control": "3+2", "rated": False}):
        assert auth_client.post(PATH, headers=bearer(token), json=data).status_code == 422
    assert auth_client.put(f"{PATH}/not-a-uuid", headers=bearer(token)).status_code == 422
    assert queue(auth_client, token, method="GET") == {"state": "idle"}


def test_queue_pairing_is_atomic_across_two_apps(auth_client: TestClient) -> None:
    alice, bob = (player(auth_client, name) for name in ("alice", "bobby"))
    settings = auth_client.app.state.security.settings
    with TestClient(create_app(settings), headers={"Origin": ORIGIN}) as other:
        with ThreadPoolExecutor(4) as pool:
            results = list(
                pool.map(
                    lambda args: queue(*args),
                    [(auth_client, alice), (other, alice), (auth_client, bob), (other, bob)],
                )
            )
        match = queue(other, alice, method="GET")
        assert match["state"] == "matched"
        assert queue(auth_client, bob, "1+0") == match
        assert all(row == match for row in results if row["state"] == "matched")
    with TestClient(create_app(settings)) as restarted:
        assert queue(restarted, alice, method="GET") == match
    assert execute("SELECT rated, speed, initial_time_ms, increment_ms FROM games") == [
        (True, "blitz", 180000, 2000)
    ]
    assert execute("SELECT count(*) FROM matchmaking_tickets") == [(0,)]


def test_same_speed_different_controls_and_stale_cancellation(auth_client: TestClient) -> None:
    alice, bob = (player(auth_client, name) for name in ("alice", "bobby"))
    first = queue(auth_client, alice)
    assert queue(auth_client, alice, "5+0") == first
    assert queue(auth_client, bob, "5+0")["state"] == "queued"
    assert execute("SELECT count(*) FROM games") == [(0,)]
    assert queue(auth_client, alice, method="DELETE", ticket=first["ticket_id"]) == {
        "state": "idle"
    }
    new = queue(auth_client, alice, "1+0")
    assert new["ticket_id"] != first["ticket_id"]
    assert queue(auth_client, alice, method="DELETE", ticket=first["ticket_id"]) == new
    assert queue(auth_client, bob, method="DELETE", ticket=new["ticket_id"])["state"] == "queued"


def test_cancellation_and_pairing_have_one_winner(auth_client: TestClient) -> None:
    alice, bob = (player(auth_client, name) for name in ("alice", "bobby"))
    first = queue(auth_client, alice)
    with ThreadPoolExecutor(2) as pool:
        cancel = pool.submit(queue, auth_client, alice, method="DELETE", ticket=first["ticket_id"])
        join = pool.submit(queue, auth_client, bob)
        canceled, joined = cancel.result(), join.result()
    if canceled["state"] == "idle":
        assert joined["state"] == "queued"
        assert execute("SELECT count(*) FROM games") == [(0,)]
    else:
        assert canceled == joined == queue(auth_client, alice, method="GET")
        assert canceled["state"] == "matched"
        assert execute("SELECT count(*) FROM games") == [(1,)]


def test_oldest_eligible_opponent_is_picked(auth_client: TestClient) -> None:
    alice, bob, carol = (player(auth_client, name) for name in ("alice", "bobby", "carol"))
    execute(
        "UPDATE user_ratings SET rating=CASE WHEN users.username='bobby' THEN 1380 ELSE 1290 END "
        "FROM users WHERE users.id=user_ratings.user_id AND speed='blitz' "
        "AND users.username IN ('bobby', 'carol')"
    )
    queue(auth_client, alice)
    queue(auth_client, bob)
    match = queue(auth_client, carol)
    assert match["state"] == "matched"
    assert queue(auth_client, alice, method="GET") == match
    assert queue(auth_client, bob, method="GET")["state"] == "queued"


@pytest.mark.parametrize(("gap", "expected"), [(175, "matched"), (401, "queued")])
def test_both_rating_windows_must_widen(auth_client: TestClient, gap: int, expected: str) -> None:
    alice, bob = (player(auth_client, name) for name in ("alice", "bobby"))
    execute(
        "UPDATE user_ratings SET rating=:rating WHERE speed='blitz' "
        "AND user_id=(SELECT id FROM users WHERE username='bobby')",
        rating=1200 + gap,
    )
    first = queue(auth_client, alice)
    execute("UPDATE matchmaking_tickets SET joined_at=clock_timestamp() - interval '35 seconds'")
    assert queue(auth_client, bob)["state"] == "queued"
    execute("UPDATE matchmaking_tickets SET joined_at=clock_timestamp() - interval '35 seconds'")
    match = queue(auth_client, alice, method="PUT", ticket=first["ticket_id"])
    assert match["state"] == expected
    if expected == "matched":
        assert queue(auth_client, bob, method="GET") == match
        assert queue(auth_client, alice, method="DELETE", ticket=first["ticket_id"]) == match


def test_expired_search_is_not_renewed_or_paired(auth_client: TestClient) -> None:
    alice, bob = (player(auth_client, name) for name in ("alice", "bobby"))
    first = queue(auth_client, alice)
    execute(
        "UPDATE matchmaking_tickets SET joined_at=clock_timestamp()-interval '30 seconds', "
        "expires_at=clock_timestamp()-interval '1 second'"
    )
    assert queue(auth_client, alice, method="PUT", ticket=first["ticket_id"]) == {"state": "idle"}
    assert queue(auth_client, bob)["state"] == "queued"
    assert queue(auth_client, alice)["state"] == "matched"


def test_logout_makes_a_ticket_ineligible(auth_client: TestClient) -> None:
    bob, alice = (player(auth_client, name) for name in ("bobby", "alice"))
    queue(auth_client, alice)
    csrf = auth_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    assert (
        auth_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    )
    assert auth_client.get(PATH, headers=bearer(alice)).status_code == 401
    assert queue(auth_client, bob)["state"] == "queued"


def test_database_enforces_one_search_per_user_and_valid_lease(auth_client: TestClient) -> None:
    token = player(auth_client, "alice")
    queue(auth_client, token)
    with pytest.raises(IntegrityError, match="pk_matchmaking_tickets"):
        execute(
            "INSERT INTO matchmaking_tickets "
            "SELECT user_id, session_id, gen_random_uuid(), time_control, joined_at, expires_at "
            "FROM matchmaking_tickets"
        )
    with pytest.raises(IntegrityError, match="lease_after_join"):
        execute("UPDATE matchmaking_tickets SET expires_at=joined_at")

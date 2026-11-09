import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.board import limit_board_requests, router
from app.chess import START_FEN, Position

app = FastAPI()
app.include_router(router)
# Pure rule/response tests; real throttling is exercised against PostgreSQL.
app.dependency_overrides[limit_board_requests] = lambda: None
client = TestClient(app)


def test_start_and_move() -> None:
    response = client.post("/api/v1/board/position", json={})
    assert response.status_code == 200
    assert len(response.json()["legal_moves"]) == 20
    assert response.json()["board"][0] == "R"
    response = client.post("/api/v1/board/position", json={"move": "e2e4"})
    assert response.status_code == 200
    assert response.json()["fen"] == Position.start().play("e2e4").fen()


@pytest.mark.parametrize(
    "data",
    [
        {"fen": "invalid"},
        {"fen": "x" * 121},
        {"move": "e2e5"},
        {"move": "a0a9"},
        {"unexpected": True},
        {"fen": 1},
    ],
)
def test_invalid_input(data: dict[str, object]) -> None:
    assert client.post("/api/v1/board/position", json=data).status_code == 422


@pytest.mark.parametrize(
    ("fen", "move"),
    [
        ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1"),
        ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "e5d6"),
        ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8n"),
    ],
)
def test_special_moves(fen: str, move: str) -> None:
    result = client.post("/api/v1/board/position", json={"fen": fen, "move": move})
    assert result.status_code == 200
    assert result.json()["fen"] == Position.from_fen(fen).play(move).fen()


def test_checkmate_has_no_destinations() -> None:
    position = Position.start()
    for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
        position = position.play(move)
    result = client.post("/api/v1/board/position", json={"fen": position.fen()}).json()
    assert result["check"] is True
    assert result["ending"] == "checkmate"
    assert result["legal_moves"] == []
    assert client.post("/api/v1/board/position", json={"fen": START_FEN}).status_code == 200

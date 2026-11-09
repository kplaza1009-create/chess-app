from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.chess import Position
from app.db.models import START_FEN, Game, GameStatus
from app.services.clocks import expire, has_mating_material, remaining

NOW = datetime(2026, 11, 8, tzinfo=UTC)


def game() -> Game:
    return Game(
        current_fen=START_FEN,
        white_remaining_ms=1000,
        black_remaining_ms=2000,
        turn_started_at=NOW,
        status=GameStatus.ACTIVE,
        version=0,
        result="*",
    )


def test_balance_and_exact_deadline() -> None:
    item = game()
    assert remaining(item, NOW + timedelta(milliseconds=999)) == (1, 2000)
    assert not expire(item, NOW + timedelta(milliseconds=999))
    assert expire(item, NOW + timedelta(seconds=1))
    assert item.result == "0-1" and item.version == 1
    assert not expire(item, NOW + timedelta(seconds=10))
    assert item.version == 1


def test_timezone_backward_clock_and_legacy() -> None:
    item = game()
    assert remaining(item, NOW.astimezone(timezone(timedelta(hours=-5)))) == (1000, 2000)
    assert remaining(item, NOW - timedelta(seconds=1)) == (1000, 2000)
    item.turn_started_at = None
    assert not expire(item, NOW + timedelta(days=1))


def test_first_move_deadline_does_not_charge_clock_and_aborts_exactly() -> None:
    item = game()
    item.first_move_deadline = NOW + timedelta(seconds=30)
    item.rated = True
    assert remaining(item, NOW + timedelta(seconds=29)) == (1000, 2000)
    assert not expire(item, NOW + timedelta(milliseconds=29999))
    assert expire(item, NOW + timedelta(seconds=30))
    assert item.status == GameStatus.ABORTED
    assert item.result == "*" and item.rated is False


@pytest.mark.parametrize(
    ("fen", "color", "expected"),
    [
        ("4k3/8/8/8/8/8/R7/4K3 w - - 0 1", "b", False),
        ("4k3/8/8/8/8/8/R7/4K3 w - - 0 1", "w", True),
        ("4k3/8/8/8/8/8/N7/4K3 w - - 0 1", "w", False),
        ("4k3/8/8/8/8/8/NN6/4K3 w - - 0 1", "w", True),
        ("4k3/p7/8/8/8/8/N7/4K3 w - - 0 1", "w", True),
        ("4k3/8/8/8/8/8/B7/4K3 w - - 0 1", "w", False),
        ("4k3/8/8/8/8/8/BB6/4K3 w - - 0 1", "w", True),
        ("4k3/8/8/8/8/8/B1B5/4K3 w - - 0 1", "w", False),
    ],
)
def test_one_sided_material(fen: str, color: str, expected: bool) -> None:
    assert has_mating_material(Position.from_fen(fen), color) is expected


def test_timeout_draw_when_winner_has_only_king() -> None:
    item = game()
    item.current_fen = "4k3/8/8/8/8/8/R7/4K3 w - - 0 1"
    assert expire(item, NOW + timedelta(seconds=1))
    assert item.result == "1/2-1/2"

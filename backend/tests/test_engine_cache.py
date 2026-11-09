from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.chess import Game, Position
from app.services.engine_cache import EngineCache

START = Position.start().fen()
CYCLE = ("g1f3", "g8f6", "f3g1", "f6g8")


def test_cache_only_replays_committed_suffix() -> None:
    cache, game_id = EngineCache(), uuid4()
    cache.restore(game_id, 2, START, ("e2e4", "e7e5"))
    original_push = Game.push
    with patch.object(Game, "push", autospec=True, side_effect=original_push) as push:
        state = cache.restore(game_id, 3, START, ("e2e4", "e7e5", "g1f3"))
        assert push.call_count == 1
        assert push.call_args.args[1] == "g1f3"
        assert state.position.turn == "b"


def test_pending_move_does_not_mutate_cached_history() -> None:
    cache, game_id = EngineCache(), uuid4()
    pending = cache.restore(game_id, 1, START, ("e2e4",))
    pending.push("e7e5")
    # Simulate a failed transaction: the database still has just White's move.
    restored = cache.restore(game_id, 1, START, ("e2e4",))
    assert len(restored.moves) == 1
    restored.push("c7c5")
    assert restored.moves[-1].uci() == "c7c5"


@pytest.mark.parametrize(("version", "moves"), [(1, ("e2e4",)), (2, ("d2d4", "d7d5"))])
def test_older_or_replaced_history_rebuilds(version: int, moves: tuple[str, ...]) -> None:
    cache, game_id = EngineCache(), uuid4()
    cache.restore(game_id, 2, START, ("e2e4", "e7e5"))
    restored = cache.restore(game_id, version, START, moves)
    expected = Game()
    for move in moves:
        expected.push(move)
    assert restored.position == expected.position
    assert restored.moves == expected.moves


def test_initial_position_change_rebuilds() -> None:
    cache, game_id = EngineCache(), uuid4()
    cache.restore(game_id, 0, START, ())
    fen = "4k3/8/8/8/8/8/R7/4K3 w - - 0 1"
    assert cache.restore(game_id, 0, fen, ()).position.fen() == fen


def test_eviction_is_bounded_and_reconstructs_history() -> None:
    cache = EngineCache(capacity=1)
    first, second = uuid4(), uuid4()
    cache.restore(first, 4, START, CYCLE)
    cache.restore(second, 0, START, ())
    original_push = Game.push
    with patch.object(Game, "push", autospec=True, side_effect=original_push) as push:
        restored = cache.restore(first, 8, START, CYCLE * 2)
        assert push.call_count == 8
    assert restored.claimable_draws() == ("threefold_repetition",)


def test_concurrent_restores_do_not_share_mutable_history() -> None:
    cache, game_id = EngineCache(), uuid4()

    def branch(move: str) -> str:
        engine = cache.restore(game_id, 0, START, ())
        engine.push(move)
        assert len(engine.moves) == 1
        return engine.moves[0].uci()

    with ThreadPoolExecutor(4) as pool:
        assert list(pool.map(branch, ["e2e4", "d2d4"] * 8)) == ["e2e4", "d2d4"] * 8
    assert cache.restore(game_id, 0, START, ()).moves == ()


def test_invalid_capacity() -> None:
    with pytest.raises(ValueError):
        EngineCache(0)

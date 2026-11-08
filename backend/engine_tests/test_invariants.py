"""Deterministic metamorphic tests supplement the independent reference counts."""

from random import Random

import pytest

from app.chess import Game, Position

from .test_rules import mirror, mirror_uci


@pytest.mark.parametrize("seed", range(10))
def test_color_symmetry_and_reversible_play(seed: int) -> None:
    random = Random(seed)
    game = Game()
    for _ in range(60):
        if game.outcome() is not None:
            break
        before = game.position
        legal = before.legal_moves()
        assert len(legal) == len(set(legal))
        flipped = mirror(before)
        flipped.validate()
        assert {m.uci() for m in flipped.legal_moves()} == {mirror_uci(m.uci()) for m in legal}
        move = random.choice(legal)
        after = game.push(move)
        assert not after.is_check(before.turn)
        assert Position.from_fen(after.fen()) == after
        assert len(game.positions) == len(game.moves) + 1
        assert game.pop() == move
        assert game.position == before
        assert game.push(move) == after
    while game.moves:
        game.pop()
    assert game.position == Position.start()
    assert game.claimable_draws() == ()

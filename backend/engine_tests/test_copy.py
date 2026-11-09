from app.chess import Game


def test_copy_preserves_repetition_and_independent_undo() -> None:
    game = Game()
    for move in ("g1f3", "g8f6", "f3g1", "f6g8") * 2:
        game.push(move)
    clone = game.copy()
    clone.pop()
    assert game.claimable_draws() == ("threefold_repetition",)
    assert clone.claimable_draws() == ()
    assert len(game.moves) == 8
    assert len(clone.moves) == 7
    clone.push("f6g8")
    clone.claim_draw("threefold_repetition")
    assert game.outcome() is None
    assert clone.outcome() is not None


def test_copy_preserves_claimed_outcome() -> None:
    game = Game()
    for move in ("g1f3", "g8f6", "f3g1", "f6g8") * 2:
        game.push(move)
    game.claim_draw("threefold_repetition")
    clone = game.copy()
    assert clone.outcome() == game.outcome()
    clone.pop()
    assert clone.outcome() is None
    assert game.outcome() is not None

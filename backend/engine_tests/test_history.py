from dataclasses import replace

import pytest

from app.chess import ChessError, Game, Position

CYCLE = ("g1f3", "g8f6", "f3g1", "f6g8")


@pytest.mark.parametrize("halfmove", [0, 98, 99, 100, 149, 150, 151])
def test_exact_draw_thresholds(halfmove: int) -> None:
    game = Game(Position.from_fen(f"7k/8/8/8/8/8/8/KR6 w - - {halfmove} 80"))
    if halfmove >= 150:
        outcome = game.outcome()
        assert outcome is not None and outcome.reason == "seventy_five_moves"
        assert game.claimable_draws() == ()
    else:
        assert game.outcome() is None
        expected = ("fifty_moves",) if halfmove >= 100 else ()
        assert game.claimable_draws() == expected
        expected_next = ("fifty_moves",) if halfmove >= 99 else ()
        assert game.claimable_draws("b1b2") == expected_next


@pytest.mark.parametrize(
    ("fen", "move"),
    [
        ("7k/8/8/8/8/8/P7/KR6 w - - 99 80", "a2a3"),
        ("7k/8/8/8/8/8/1n6/KR6 w - - 99 80", "b1b2"),
    ],
)
def test_irreversible_move_prevents_fifty_move_claim(fen: str, move: str) -> None:
    game = Game(Position.from_fen(fen))
    assert game.claimable_draws(move) == ()
    game.push(move)
    assert game.position.halfmove_clock == 0
    assert game.claimable_draws() == ()


def test_repetition_undo_branch_and_replay() -> None:
    game = Game()
    for move in CYCLE * 2:
        game.push(move)
    assert game.claimable_draws() == ("threefold_repetition",)
    game.pop()
    game.push("f6h5")
    assert game.claimable_draws() == ()
    game.pop()
    game.push("f6g8")
    assert game.claimable_draws() == ("threefold_repetition",)
    replay = Game(game.positions[0])
    for move in game.moves:
        replay.push(move)
    assert replay.positions == game.positions
    assert replay.claimable_draws() == game.claimable_draws()
    loaded_fen = Game(Position.from_fen(game.position.fen()))
    assert loaded_fen.claimable_draws() == ()


def test_two_games_have_independent_history() -> None:
    first, second = Game(), Game()
    for move in CYCLE * 2:
        first.push(move)
    assert first.claimable_draws() == ("threefold_repetition",)
    assert second.claimable_draws() == ()
    assert second.moves == ()


def test_claim_and_failed_actions_are_atomic() -> None:
    game = Game()
    for move in CYCLE * 2:
        game.push(move)
    before = game.positions
    with pytest.raises(ChessError):
        game.claim_draw("fifty_moves")
    with pytest.raises(ChessError):
        game.claimable_draws("e2e5")
    assert game.positions == before and game.outcome() is None
    result = game.claim_draw("threefold_repetition")
    assert game.outcome() == result
    assert game.positions == before
    with pytest.raises(ChessError):
        game.push("e2e4")
    with pytest.raises(ChessError):
        game.claim_draw("threefold_repetition")
    game.pop()
    assert game.outcome() is None


def test_repetition_key_fields() -> None:
    position = Position.start()
    key = position.repetition_key()
    assert replace(position, halfmove_clock=80, fullmove_number=100).repetition_key() == key
    assert replace(position, turn="b").repetition_key() != key
    assert replace(position, castling="KQ").repetition_key() != key
    after = position.play("e2e4")
    assert after.repetition_key() == replace(after, en_passant=None).repetition_key()


@pytest.mark.parametrize(
    "fen",
    [
        "7k/8/8/8/8/8/8/KN6 w - - 100 80",
        "7k/8/8/8/8/8/8/KB6 w - - 150 80",
        "7k/5Q2/6K1/8/8/8/8/8 b - - 150 80",
        "7k/6Q1/6K1/8/8/8/8/8 b - - 150 80",
    ],
)
def test_terminal_games_have_no_claims_or_continuation(fen: str) -> None:
    game = Game(Position.from_fen(fen))
    before = game.positions
    assert game.outcome() is not None
    assert game.claimable_draws() == ()
    with pytest.raises(ChessError):
        game.push("a1a2")
    assert game.positions == before

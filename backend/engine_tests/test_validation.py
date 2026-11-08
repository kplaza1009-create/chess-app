"""Validate public inputs, immutable snapshots, and FEN invariants."""

from dataclasses import FrozenInstanceError, replace

import pytest

from app.chess import ChessError, Game, Move, Position, square, square_name


@pytest.mark.parametrize("index", range(64))
def test_square_round_trip(index: int) -> None:
    name = chr(97 + index % 8) + str(1 + index // 8)
    assert square_name(index) == name
    assert square(name) == index


@pytest.mark.parametrize("value", [None, True, 2, "", "a0", "a9", "i1", "A1", " a1", "a11"])
def test_invalid_square(value: object) -> None:
    with pytest.raises(ChessError):
        square(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [-1, 64, True, 1.0, "1", None])
def test_invalid_square_index(value: object) -> None:
    with pytest.raises(ChessError):
        square_name(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("uci", ["a1h8", "h8a1", "a7b8q", "h2h1r", "b7b8b", "a2b1n"])
def test_move_round_trip(uci: str) -> None:
    assert Move.from_uci(uci).uci() == uci


@pytest.mark.parametrize(
    ("source", "target", "promotion"),
    [
        (-1, 1, None),
        (0, 64, None),
        (True, 2, None),
        (0, 0, None),
        (0, 1, "Q"),
        (0, 1, "p"),
        (0, 1, ""),
    ],
)
def test_invalid_move_constructor(source: int, target: int, promotion: str | None) -> None:
    with pytest.raises(ChessError):
        Move(source, target, promotion)


@pytest.mark.parametrize(
    "fen",
    [
        None,
        42,
        "x" * 201,
        "7k/8/8/8/8/8/8/K7 w - - 0",
        "7k/8/8/8/8/8/K7 w - - 0 1",
        "7k/8/8/8/8/8/8/K8 w - - 0 1",
        "7k/8/8/8/8/8/8/K6X w - - 0 1",
        "7k/8/8/8/8/8/8/K7 w - - 0.5 1",
        "7k/8/8/8/8/8/8/K7 w - - 0 +1",
        "7k/8/8/8/8/8/8/K7 w KK - 0 1",
        "7k/8/8/8/8/8/8/K7 w qK - 0 1",
        "7k/8/8/8/8/8/8/K7 w z - 0 1",
        "7k/8/8/8/8/8/8/KK6 w - - 0 1",
        "7k/8/8/8/8/8/PPPPPPPP/KP6 w - - 0 1",
        "7k/8/8/8/8/RRRRRRRR/PPPPPPPP/K7 w - - 0 1",
        "7k/8/8/8/8/8/8/K6R w - - 0 1",
        "7k/8/8/3pP3/8/8/8/K7 w - d3 0 1",
        "7k/8/3N4/3pP3/8/8/8/K7 w - d6 0 1",
        "7k/3n4/8/3pP3/8/8/8/K7 w - d6 0 1",
        "7k/8/8/3pP3/8/8/8/K7 w - d6 1 1",
    ],
)
def test_fen_rejects_inconsistent_inputs(fen: object) -> None:
    with pytest.raises(ChessError):
        Position.from_fen(fen)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("board", (".",)),
        ("board", ["."] * 64),
        ("board", ("x",) * 64),
        ("turn", "x"),
        ("castling", "KK"),
        ("castling", None),
        ("en_passant", -1),
        ("halfmove_clock", -1),
        ("halfmove_clock", True),
        ("fullmove_number", 0),
        ("fullmove_number", False),
    ],
)
def test_position_constructor_checks(field: str, value: object) -> None:
    with pytest.raises(ChessError):
        replace(Position.start(), **{field: value})


def test_frozen_values_and_history_snapshots() -> None:
    game = Game()
    position = game.position
    history = game.positions
    moves = game.moves
    with pytest.raises(FrozenInstanceError):
        position.turn = "b"  # type: ignore[misc]
    move = Move.from_uci("e2e4")
    with pytest.raises(FrozenInstanceError):
        move.target = square("e5")  # type: ignore[misc]
    game.push(move)
    assert history == (Position.start(),)
    assert moves == ()
    assert game.position != position


@pytest.mark.parametrize("value", [None, 1, {}, "a1a8", "e7e5", "e2e4q", "e2e3n"])
def test_invalid_play_preserves_position(value: object) -> None:
    game = Game()
    before = game.positions
    with pytest.raises(ChessError):
        game.push(value)  # type: ignore[arg-type]
    assert game.positions == before and game.moves == ()


def test_invalid_game_and_colors() -> None:
    with pytest.raises(ChessError):
        Game("bad")  # type: ignore[arg-type]
    with pytest.raises(ChessError):
        Position.start().is_check("x")  # type: ignore[arg-type]
    with pytest.raises(ChessError):
        Position.start().attacked(0, "x")  # type: ignore[arg-type]


def test_game_validates_direct_initial_position() -> None:
    with pytest.raises(ChessError):
        Game(replace(Position.start(), en_passant=square("e3")))

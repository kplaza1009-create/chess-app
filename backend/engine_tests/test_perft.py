"""Independent published counts from https://www.chessprogramming.org/Perft_Results.

Depths 0–3 run routinely; deeper trees are explicit slow cases. Counts are
literal reference data and never computed from this implementation.
"""

import pytest

from app.chess import START_FEN, ChessError, Game, Position, divide, perft

REFERENCES = (
    ("start", START_FEN, (1, 20, 400, 8902, 197281, 4865609)),
    (
        "kiwipete",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        (1, 48, 2039, 97862, 4085603),
    ),
    ("position3", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", (1, 14, 191, 2812, 43238, 674624)),
    (
        "position4",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
        (1, 6, 264, 9467, 422333),
    ),
    (
        "position4_mirror",
        "r2q1rk1/pP1p2pp/Q4n2/bbp1p3/Np6/1B3NBn/pPPP1PPP/R3K2R b KQ - 0 1",
        (1, 6, 264, 9467, 422333),
    ),
    (
        "position5",
        "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
        (1, 44, 1486, 62379, 2103487),
    ),
    (
        "position6",
        "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
        (1, 46, 2079, 89890, 3894594),
    ),
)


@pytest.mark.parametrize(
    ("fen", "depth", "expected"),
    [
        pytest.param(
            fen, depth, count, id=f"{name}-d{depth}", marks=pytest.mark.slow if depth >= 4 else ()
        )
        for name, fen, counts in REFERENCES
        for depth, count in enumerate(counts)
    ],
)
def test_reference_tree(fen: str, depth: int, expected: int) -> None:
    position = Position.from_fen(fen)
    actual = perft(position, depth)
    assert actual == expected, (
        f"FEN={fen}, depth={depth}, expected={expected}, actual={actual}, "
        f"branches={divide(position, depth) if depth else {}}"
    )
    assert position.fen() == fen


def test_start_divide_depth_three() -> None:
    # Each value counts replies and continuations after this first move.
    expected = {
        "a2a3": 380,
        "a2a4": 420,
        "b1a3": 400,
        "b1c3": 440,
        "b2b3": 420,
        "b2b4": 421,
        "c2c3": 420,
        "c2c4": 441,
        "d2d3": 539,
        "d2d4": 560,
        "e2e3": 599,
        "e2e4": 600,
        "f2f3": 380,
        "f2f4": 401,
        "g1f3": 440,
        "g1h3": 400,
        "g2g3": 420,
        "g2g4": 421,
        "h2h3": 380,
        "h2h4": 420,
    }
    actual = divide(Position.start(), 3)
    assert actual == expected
    assert list(actual) == sorted(actual)
    assert sum(actual.values()) == 8902


@pytest.mark.parametrize(
    "fen",
    [
        "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1",
        "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1",
    ],
)
def test_terminal_tree(fen: str) -> None:
    position = Position.from_fen(fen)
    assert perft(position, 0) == 1
    assert perft(position, 1) == perft(position, 2) == 0
    assert divide(position, 2) == {}


def test_perft_ignores_adjudicated_draws() -> None:
    position = Position.from_fen("7k/8/8/8/8/8/8/K7 w - - 150 80")
    assert Game(position).outcome() is not None
    assert perft(position, 1) == 3
    assert divide(position, 1) == {"a1a2": 1, "a1b1": 1, "a1b2": 1}


@pytest.mark.parametrize("depth", [-1, True, 1.5, "2", None])
def test_invalid_depth(depth: object) -> None:
    with pytest.raises(ChessError):
        perft(Position.start(), depth)  # type: ignore[arg-type]
    with pytest.raises(ChessError):
        divide(Position.start(), depth)  # type: ignore[arg-type]


def test_divide_requires_first_ply() -> None:
    with pytest.raises(ChessError):
        divide(Position.start(), 0)

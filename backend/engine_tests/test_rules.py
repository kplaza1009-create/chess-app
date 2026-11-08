"""Explicit move expectations, repeated with colors and ranks reversed."""

import pytest

from app.chess import Game, Move, Position, square


def mirror(position: Position) -> Position:
    rights = position.castling.swapcase()
    return Position(
        tuple(position.board[i ^ 56].swapcase() for i in range(64)),
        "b" if position.turn == "w" else "w",
        "".join(right for right in "KQkq" if right in rights),
        None if position.en_passant is None else position.en_passant ^ 56,
        position.halfmove_clock,
        position.fullmove_number,
    )


def mirror_uci(uci: str) -> str:
    move = Move.from_uci(uci)
    return Move(move.source ^ 56, move.target ^ 56, move.promotion).uci()


@pytest.mark.parametrize("flipped", [False, True], ids=["white", "black"])
@pytest.mark.parametrize(
    ("piece", "targets"),
    [
        ("N", "b3 b5 c2 c6 e2 e6 f3 f5"),
        ("B", "a1 b2 c3 e5 f6 g7 h8 a7 b6 c5 e3 f2 g1"),
        ("R", "d1 d2 d3 d5 d6 d7 d8 a4 b4 c4 e4 f4 g4 h4"),
        ("Q", "a1 b2 c3 e5 f6 g7 h8 a7 b6 c5 e3 f2 g1 d1 d2 d3 d5 d6 d7 d8 a4 b4 c4 e4 f4 g4 h4"),
        ("P", "d5"),
    ],
)
def test_unblocked_piece_moves(piece: str, targets: str, flipped: bool) -> None:
    position = Position.from_fen(f"k7/8/8/8/3{piece}4/8/8/7K w - - 0 1")
    expected = {"d4" + target for target in targets.split()}
    source = square("d4")
    if flipped:
        position = mirror(position)
        source ^= 56
        expected = {mirror_uci(move) for move in expected}
    assert {move.uci() for move in position.legal_moves() if move.source == source} == expected


@pytest.mark.parametrize("flipped", [False, True])
@pytest.mark.parametrize(
    ("fen", "source", "expected"),
    [
        (
            "k7/8/3p4/8/3R4/8/3P4/7K w - - 0 1",
            "d4",
            "d4d3 d4d5 d4d6 d4a4 d4b4 d4c4 d4e4 d4f4 d4g4 d4h4",
        ),
        ("k7/8/8/8/8/3n4/3P4/7K w - - 0 1", "d2", ""),
        ("k7/8/8/8/3n4/8/3P4/7K w - - 0 1", "d2", "d2d3"),
        ("k7/8/8/8/8/2p1p3/3P4/7K w - - 0 1", "d2", "d2d3 d2d4 d2c3 d2e3"),
        ("k7/8/8/8/8/8/8/N6K w - - 0 1", "a1", "a1b3 a1c2"),
        ("k7/8/8/8/8/8/8/7K w - - 0 1", "h1", "h1g1 h1g2 h1h2"),
    ],
)
def test_blockers_captures_and_edges(fen: str, source: str, expected: str, flipped: bool) -> None:
    position = Position.from_fen(fen)
    index = square(source)
    expected_set = set(expected.split())
    if flipped:
        position = mirror(position)
        index ^= 56
        expected_set = {mirror_uci(move) for move in expected_set}
    assert {m.uci() for m in position.legal_moves() if m.source == index} == expected_set


@pytest.mark.parametrize("flipped", [False, True])
@pytest.mark.parametrize(
    ("fen", "move", "allowed"),
    [
        ("k3r3/8/8/8/8/8/8/4K2R w K - 0 1", "e1g1", False),
        ("k7/8/8/8/8/8/8/4KB1R w K - 0 1", "e1g1", False),
        ("7k/8/8/8/8/8/8/RN2K3 w Q - 0 1", "e1c1", False),
        ("k7/8/8/8/8/8/8/4K2R w - - 0 1", "e1g1", False),
        ("k5r1/8/8/8/8/8/8/4K2R w K - 0 1", "e1g1", False),
        ("k7/8/8/8/8/8/6p1/4K2R w K - 0 1", "e1g1", False),
        ("k6r/8/8/8/8/8/8/4K2R w K - 0 1", "e1g1", True),
        ("r6k/8/8/8/8/8/8/R3K3 w Q - 0 1", "e1c1", True),
    ],
)
def test_castling_boundaries(fen: str, move: str, allowed: bool, flipped: bool) -> None:
    position = Position.from_fen(fen)
    if flipped:
        position = mirror(position)
        move = mirror_uci(move)
    assert (move in {m.uci() for m in position.legal_moves()}) is allowed


@pytest.mark.parametrize("flipped", [False, True])
@pytest.mark.parametrize("promotion", list("qrbn"))
@pytest.mark.parametrize("target", ["a8", "b8"])
def test_every_promotion_and_undo(flipped: bool, promotion: str, target: str) -> None:
    position = Position.from_fen("1r5k/P7/8/8/8/8/8/7K w - - 9 20")
    uci = "a7" + target + promotion
    if flipped:
        position = mirror(position)
        uci = mirror_uci(uci)
    game = Game(position)
    after = game.push(uci)
    piece = promotion if flipped else promotion.upper()
    assert after.board[Move.from_uci(uci).target] == piece
    assert after.halfmove_clock == 0
    assert after.en_passant is None
    assert game.pop().uci() == uci
    assert game.position == position


def test_pinned_piece_still_attacks_king_destination() -> None:
    position = Position.from_fen("4k3/4n3/8/6K1/8/8/8/4R3 w - - 0 1")
    assert position.attacked(square("f5"), "b")
    assert "g5f5" not in {m.uci() for m in position.legal_moves()}


def test_pawn_attacks_are_not_forward_moves() -> None:
    position = Position.from_fen("k7/8/8/8/3P4/8/8/7K w - - 0 1")
    assert position.attacked(square("c5"), "w")
    assert position.attacked(square("e5"), "w")
    assert not position.attacked(square("d5"), "w")
    assert not position.attacked(square("c3"), "w")

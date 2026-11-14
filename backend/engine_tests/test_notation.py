import pytest

from app.chess import ChessError, Position
from app.chess.notation import parse_san, san


@pytest.mark.parametrize(
    ("fen", "uci", "notation"),
    [
        (Position.start().fen(), "e2e4", "e4"),
        ("4k3/8/8/8/8/8/8/1N2KN2 w - - 0 1", "b1d2", "Nbd2"),
        ("4k3/8/8/8/8/R7/8/R3K3 w - - 0 1", "a1a2", "R1a2"),
        ("7k/8/8/8/8/1N6/8/1N2KN2 w - - 0 1", "b1d2", "Nb1d2"),
        ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1", "O-O"),
        ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1c1", "O-O-O"),
        ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8q", "a8=Q+"),
        ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "e5d6", "exd6"),
        ("1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7b8n", "axb8=N"),
    ],
)
def test_san_roundtrip(fen: str, uci: str, notation: str) -> None:
    position = Position.from_fen(fen)
    assert san(position, uci) == notation
    assert parse_san(position, notation).uci() == uci


def test_checkmate_and_invalid_notation() -> None:
    position = Position.start()
    for uci in ("f2f3", "e7e5", "g2g4"):
        position = position.play(uci)
    assert san(position, "d8h4") == "Qh4#"
    assert parse_san(position, "Qh4#").uci() == "d8h4"
    assert parse_san(position, "Qh4").uci() == "d8h4"
    for notation in ("Qh4+", "Qz9", "", "a" * 17):
        with pytest.raises(ChessError):
            parse_san(position, notation)
    with pytest.raises(ChessError):
        san(position, "e7e5")


def test_ambiguous_san_rejected() -> None:
    position = Position.from_fen("4k3/8/8/8/8/8/8/1N2KN2 w - - 0 1")
    with pytest.raises(ChessError):
        parse_san(position, "Nd2")

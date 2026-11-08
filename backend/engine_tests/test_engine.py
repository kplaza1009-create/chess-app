"""Phase 3 acceptance checks. The comprehensive perft suite follows in Phase 4."""

import pytest

from app.chess import START_FEN, ChessError, Game, Move, Position, perft, square


def moves(fen: str) -> set[str]:
    return {m.uci() for m in Position.from_fen(fen).legal_moves()}


def test_start_and_round_trip() -> None:
    position = Position.start()
    assert position.fen() == START_FEN
    assert perft(position, 0) == 1
    assert perft(position, 3) == 8902
    assert position.fen() == START_FEN
    game = Game()
    for move in ("e2e4", "e7e5", "g1f3", "b8c6"):
        game.push(move)
        assert Position.from_fen(game.position.fen()) == game.position
    for _ in range(4):
        game.pop()
    assert game.position == position
    assert game.moves == ()


def test_kiwipete() -> None:
    position = Position.from_fen(
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
    )
    assert perft(position, 2) == 2039


def test_mate_and_stalemate() -> None:
    game = Game()
    for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
        game.push(move)
    outcome = game.outcome()
    assert outcome is not None and (outcome.result, outcome.reason) == ("0-1", "checkmate")
    with pytest.raises(ChessError):
        game.push("a2a3")
    game.pop()
    assert game.outcome() is None
    outcome = Game(Position.from_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")).outcome()
    assert outcome is not None and outcome.reason == "stalemate"


def test_castling_and_rights() -> None:
    position = Position.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    assert {"e1g1", "e1c1"} <= {m.uci() for m in position.legal_moves()}
    next_position = position.play("e1c1")
    assert next_position.board[square("c1")] == "K"
    assert next_position.board[square("d1")] == "R"
    assert next_position.castling == "kq"
    assert position.play("a1a8").castling == "Kk"
    assert "e1g1" not in moves("k4r2/8/8/8/8/8/8/4K2R w K - 0 1")
    assert "e1g1" not in moves("k5r1/8/8/8/8/8/8/4K2R w K - 0 1")
    assert "e1c1" in moves("1r5k/8/8/8/8/8/8/R3K3 w Q - 0 1")


def test_en_passant_and_repetition_identity() -> None:
    legal = Position.from_fen("7k/8/8/3pP3/8/8/8/K7 w - d6 0 1")
    after = legal.play("e5d6")
    assert after.board[square("d5")] == "."
    assert after.board[square("d6")] == "P"
    assert after.halfmove_clock == 0
    pinned = Position.from_fen("k3r3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    assert "e5d6" not in {m.uci() for m in pinned.legal_moves()}
    assert (
        pinned.repetition_key()
        == Position.from_fen(pinned.fen().replace("d6", "-")).repetition_key()
    )
    assert (
        legal.repetition_key() != Position.from_fen(legal.fen().replace("d6", "-")).repetition_key()
    )
    horizontal = Position.from_fen("7k/8/8/r4pPK/8/8/8/8 w - f6 0 1")
    assert "g5f6" not in {m.uci() for m in horizontal.legal_moves()}
    game = Game()
    for move in ("e2e4", "a7a6", "e4e5", "d7d5", "h2h3", "a6a5"):
        game.push(move)
    with pytest.raises(ChessError):
        game.push("e5d6")


def test_promotions_and_pin() -> None:
    position = Position.from_fen("1r5k/P7/8/8/8/8/8/7K w - - 0 1")
    legal = {m.uci() for m in position.legal_moves()}
    assert {"a7a8" + p for p in "qrbn"} <= legal
    assert {"a7b8" + p for p in "qrbn"} <= legal
    assert position.play("a7b8n").board[square("b8")] == "N"
    with pytest.raises(ChessError):
        position.play("a7a8")
    assert "e2f2" not in moves("k3r3/8/8/8/8/8/4R3/4K3 w - - 0 1")


@pytest.mark.parametrize(
    ("fen", "expected"),
    [
        ("7k/8/8/8/8/8/8/K7 w - - 0 1", True),
        ("7k/8/8/8/8/8/8/KN6 w - - 0 1", True),
        ("7k/8/8/8/8/8/8/KB6 w - - 0 1", True),
        ("7k/8/8/8/8/8/8/KNN5 w - - 0 1", False),
        ("7k/8/8/8/8/8/8/KB1B4 w - - 0 1", True),
        ("7k/8/8/8/8/8/8/KBB5 w - - 0 1", False),
    ],
)
def test_material(fen: str, expected: bool) -> None:
    assert Position.from_fen(fen).insufficient_material() is expected


def test_repetition_claim_and_automatic_draw() -> None:
    game = Game()
    cycle = ("g1f3", "g8f6", "f3g1", "f6g8")
    for move in cycle + cycle[:3]:
        game.push(move)
    before = game.positions
    assert game.claimable_draws() == ()
    assert game.claimable_draws("f6g8") == ("threefold_repetition",)
    assert game.positions == before
    assert game.claim_draw("threefold_repetition", "f6g8").result == "1/2-1/2"
    assert game.positions == before
    with pytest.raises(ChessError):
        game.push("f6g8")
    game = Game()
    for move in cycle * 4:
        game.push(move)
    outcome = game.outcome()
    assert outcome is not None and outcome.reason == "fivefold_repetition"
    game.pop()
    assert game.outcome() is None


def test_move_count_claims_and_mate_precedence() -> None:
    game = Game(Position.from_fen("7k/8/8/8/8/8/8/KR6 w - - 99 50"))
    assert game.claimable_draws() == ()
    assert game.claimable_draws("b1b2") == ("fifty_moves",)
    game.push("b1b2")
    assert game.claimable_draws() == ("fifty_moves",)
    assert game.claim_draw("fifty_moves").reason == "fifty_moves"
    game = Game(Position.from_fen("7k/8/8/8/8/8/8/KR6 w - - 149 75"))
    game.push("b1b2")
    outcome = game.outcome()
    assert outcome is not None and outcome.reason == "seventy_five_moves"
    game = Game(Position.from_fen("7k/8/5KQ1/8/8/8/8/8 w - - 149 75"))
    game.push("g6g7")
    outcome = game.outcome()
    assert outcome is not None and outcome.reason == "checkmate"


@pytest.mark.parametrize(
    "fen",
    [
        "",
        "8/8/8/8/8/8/8/8 w - - 0 1",
        "7k/8/8/8/8/8/8/K7 x - - 0 1",
        "7k/8/8/8/8/8/8/K7 w K - 0 1",
        "7k/8/8/8/8/8/8/K7 w - e6 0 1",
        "7k/8/8/8/8/8/8/K7 w - - -1 1",
        "7k/8/8/8/8/8/8/K7 w - - 0 0",
        "7k/8/8/8/8/8/8/K6P w - - 0 1",
        "7k/6K1/8/8/8/8/8/8 w - - 0 1",
        "7k/8/8/8/8/8/8/K34 w - - 0 1",
    ],
)
def test_invalid_fen(fen: str) -> None:
    with pytest.raises(ChessError):
        Position.from_fen(fen)


@pytest.mark.parametrize("uci", ["", "e2e9", "e2e2", "e7e8k", "e2-e4", "E2E4"])
def test_invalid_uci(uci: str) -> None:
    with pytest.raises(ChessError):
        Move.from_uci(uci)


def test_failed_action_is_atomic() -> None:
    game = Game()
    original = game.positions
    with pytest.raises(ChessError):
        game.push("e2e5")
    with pytest.raises(ChessError):
        game.claim_draw("fifty_moves")
    with pytest.raises(ChessError):
        game.pop()
    assert game.positions == original
    assert game.moves == ()
    assert game.outcome() is None


def test_black_special_moves() -> None:
    position = Position.from_fen("r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1")
    after = position.play("e8g8")
    assert after.board[square("g8")] == "k"
    assert after.board[square("f8")] == "r"
    assert after.castling == "KQ"
    assert after.fullmove_number == 2
    position = Position.from_fen("7k/8/8/8/3Pp3/8/8/K7 b - d3 0 1")
    assert position.play("e4d3").board[square("d4")] == "."
    position = Position.from_fen("7k/8/8/8/8/8/p7/1R5K b - - 0 1")
    assert position.play("a2b1n").board[square("b1")] == "n"


def test_double_check_only_allows_king_moves() -> None:
    position = Position.from_fen("k3r3/8/8/8/1b6/8/6R1/4K3 w - - 0 1")
    assert position.is_check()
    assert position.legal_moves()
    assert all(move.source == square("e1") for move in position.legal_moves())


def test_en_passant_can_remove_checking_pawn() -> None:
    position = Position.from_fen("7k/8/8/3pP3/4K3/8/8/8 w - d6 0 1")
    assert position.is_check()
    assert not position.play("e5d6").is_check("w")


def test_castling_rights_never_return() -> None:
    game = Game(Position.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"))
    original_key = game.position.repetition_key()
    for move in ("h1h2", "h8h7", "h2h1", "h7h8"):
        game.push(move)
    assert game.position.castling == "Qq"
    assert game.position.repetition_key() != original_key


def test_seeded_play_round_trip_and_complete_undo() -> None:
    from random import Random

    random = Random(20261107)
    for _ in range(5):
        game = Game()
        for _ in range(80):
            if game.outcome() is not None:
                break
            previous = game.position
            game.push(random.choice(previous.legal_moves()))
            assert not game.position.is_check(previous.turn)
            assert Position.from_fen(game.position.fen()) == game.position
        while game.moves:
            game.pop()
        assert game.position == Position.start()
        assert game.claimable_draws() == ()

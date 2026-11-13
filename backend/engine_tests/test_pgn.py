import pytest

from app.chess import START_FEN, ChessError, Position, notation, parse_san
from app.chess.pgn import MAX_PGN_BYTES, export_pgn, parse_pgn

MATE = '[White "Ada"]\n[Black "Grace"]\n[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1'


def test_import_export_preserves_every_position_and_result() -> None:
    game = parse_pgn(MATE)
    assert [move.uci for move in game.moves] == ["f2f3", "e7e5", "g2g4", "d8h4"]
    assert game.moves[-1].san == "Qh4#"
    assert game.result == "0-1"
    exported = game.export()
    assert exported.startswith('[Event "?"]\n[Site "?"]\n[Date "????.??.??"]')
    assert exported.endswith("1. f3 e5 2. g4 Qh4# 0-1\n")
    restored = parse_pgn(exported)
    assert restored.moves == game.moves
    assert restored.initial_fen == START_FEN
    assert restored.result == game.result


def test_comments_variations_glyphs_bom_and_attached_numbers() -> None:
    game = parse_pgn(
        '\ufeff% engine note\n{leading} [Event "Practice"]\n'
        "1.e4! {main line} (1.d4 d5 (1...Nf6)) e5$1\n"
        "; ignore this line\n2.Nf3?! Nc6 * {end}"
    )
    assert [move.san for move in game.moves] == ["e4", "e5", "Nf3", "Nc6"]
    assert "main line" not in game.export()
    assert "d4" not in game.export()


def test_escaped_tags_and_unicode_roundtrip() -> None:
    game = parse_pgn('[White "Zoë \\"Q\\" \\\\ club"]\n1. e4 *')
    assert game.headers["White"] == 'Zoë "Q" \\ club'
    assert parse_pgn(game.export()).headers["White"] == game.headers["White"]


@pytest.mark.parametrize(
    ("fen", "text", "uci", "canonical"),
    [
        ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a8Q", "a7a8q", "a8=Q+"),
        ("1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1", "axb8N", "a7b8n", "axb8=N"),
        ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "0-0", "e1g1", "O-O"),
        ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "exd6", "e5d6", "exd6"),
    ],
)
def test_custom_starts_special_moves_and_tolerant_san(
    fen: str,
    text: str,
    uci: str,
    canonical: str,
) -> None:
    game = parse_pgn(f'[SetUp "1"]\n[FEN "{fen}"]\n1. {text} *')
    assert game.moves[0].uci == uci
    assert game.moves[0].san == canonical
    assert parse_pgn(game.export()).moves == game.moves
    assert '[SetUp "1"]' in game.export()


def test_black_to_move_and_non_one_fullmove_number() -> None:
    fen = "4k3/8/8/8/8/8/7p/4K3 b - - 0 23"
    game = parse_pgn(f'[FEN "{fen}"]\n23...h1Q+ 24. Kd2 *')
    assert "23... h1=Q+ 24. Kd2 *" in game.export()
    assert parse_pgn(game.export()).moves == game.moves


def test_import_does_not_automatically_claim_threefold_draws() -> None:
    game = parse_pgn("1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. Ng1 Ng8 5. e4 *")
    assert len(game.moves) == 9


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        "1. e9 *",
        "1. e4 e5 2. e4 *",
        "1. e4# *",
        "1. e4 {unclosed",
        "1. e4 (1. d4 *",
        "1. e4 ) *",
        "1. e4 } *",
        "1. e4 $999 *",
        "1. e4 $1234 *",
        "1. e4 $ *",
        '[Event "a"] [Event "b"] *',
        '[Event "unterminated] *',
        '[SetUp "1"] *',
        '[SetUp "2"] *',
        '[SetUp "0"] [FEN "bad"] *',
        '[Variant "Chess960"] *',
        '[Result "win"] *',
        '[Result "1-0"] 1. e4 0-1',
        "1. e4 * 1. d4 *",
        '1. e4 * [Event "Second"] *',
        "2. e4 *",
        "1.. e4 *",
        "1... e4 *",
        "1. " + "a" * 33,
        "1. e4\x00 *",
        "(" * 33 + ")" * 33,
        MATE.replace('"0-1"', '"1-0"').replace("# 0-1", "# 1-0"),
        MATE.replace("# 0-1", "# 3. e4 0-1"),
    ],
)
def test_bad_pgn_is_rejected(text: str) -> None:
    with pytest.raises(ChessError):
        parse_pgn(text)


def test_size_limits_and_exact_failure_ply() -> None:
    with pytest.raises(ChessError, match="64 KiB"):
        parse_pgn("{" + "é" * (MAX_PGN_BYTES // 2) + "} *")
    with pytest.raises(ChessError, match="ply 3: e4"):
        parse_pgn("1. e4 e5 2. e4 *")
    with pytest.raises(ChessError, match="header"):
        parse_pgn('[White "' + "a" * 257 + '"] *')


def test_result_can_describe_resignation_or_agreed_draw() -> None:
    assert parse_pgn("1. e4 1-0").result == "1-0"
    assert parse_pgn('[Result "1/2-1/2"] 1. e4').result == "1/2-1/2"
    assert parse_pgn("*").moves == ()


def test_published_opera_game_with_castling_captures_and_disambiguation() -> None:
    game = parse_pgn(
        '[White "Paul Morphy"] [Black "Duke Karl / Count Isouard"] '
        '[Date "1858.??.??"] [Result "1-0"]\n'
        "1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 "
        "6. Bc4 Nf6 7. Qb3 Qe7 8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 "
        "11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7 14. Rd1 Qe6 "
        "15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0"
    )
    assert len(game.moves) == 33
    assert game.moves[-1].uci == "d1d8"
    assert game.moves[-1].san == "Rd8#"
    position = Position.from_fen(game.moves[-1].fen_after)
    assert position.is_check() and not position.legal_moves()
    assert parse_pgn(game.export()).moves == game.moves


def test_ply_tag_and_counter_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.chess import pgn

    monkeypatch.setattr(pgn, "MAX_PGN_PLIES", 2)
    assert len(parse_pgn("1. e4 e5 *").moves) == 2
    with pytest.raises(ChessError, match="plies"):
        parse_pgn("1. e4 e5 2. Nf3 *")
    with pytest.raises(ChessError, match="header"):
        parse_pgn(" ".join(f'[Tag{i} "x"]' for i in range(65)) + " *")
    with pytest.raises(ChessError, match="counters"):
        parse_pgn('[FEN "4k3/8/8/8/8/8/7p/4K3 b - - 0 1000001"] *')
    with pytest.raises(ChessError, match="Unicode"):
        parse_pgn("\ud800")


def test_export_wraps_and_does_not_mutate_headers() -> None:
    headers = {"Result": "*", "Event": "Test"}
    text = export_pgn(headers, START_FEN, ["Nf3", "Nf6", "Ng1", "Ng8"] * 10)
    assert all(len(line) <= 79 for line in text.splitlines()[8:])
    assert headers == {"Result": "*", "Event": "Test"}
    with pytest.raises(ChessError):
        export_pgn({"Result": "bad"}, START_FEN, [])
    with pytest.raises(ChessError):
        export_pgn({"Result": "*", "White": "bad\nheader"}, START_FEN, [])


def test_san_formats_only_matching_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    original = notation._san
    calls = []

    def tracked(*args: object) -> str:
        calls.append(args)
        return original(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(notation, "_san", tracked)
    assert parse_san(Position.start(), "e4").uci() == "e2e4"
    assert len(calls) == 1

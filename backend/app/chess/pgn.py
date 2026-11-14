"""Bounded standard-chess PGN mainline import and canonical export.

Comments, NAGs and variations are accepted but intentionally not archived.
No chess library is used. Uploaded results are metadata, never rated results.
"""

import re
import textwrap
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from app.chess.engine import START_FEN, ChessError, Game, Position
from app.chess.notation import parse_san, san

MAX_PGN_BYTES = 65_536
MAX_PGN_PLIES = 1_000
RESULTS = ("*", "1-0", "0-1", "1/2-1/2")
ROSTER = ("Event", "Site", "Date", "Round", "White", "Black", "Result")
TAG = re.compile(r'\[([A-Za-z][A-Za-z0-9_]*)\s+"((?:[^"\\\r\n]|\\["\\])*)"\s*\]')


@dataclass(frozen=True)
class PGNMove:
    uci: str
    san: str
    fen_after: str


@dataclass(frozen=True)
class PGNGame:
    headers: dict[str, str]
    initial_fen: str
    moves: tuple[PGNMove, ...]

    @property
    def result(self) -> str:
        return self.headers["Result"]

    def export(self) -> str:
        return export_pgn(self.headers, self.initial_fen, [move.san for move in self.moves])


def _tokens(text: str) -> Iterator[str]:
    """Linear scanner: validate delimiters even inside skipped variations."""
    offset, depth = 0, 0
    while offset < len(text):
        char = text[offset]
        if char.isspace():
            offset += 1
        elif char == ";" or (char == "%" and (offset == 0 or text[offset - 1] == "\n")):
            end = text.find("\n", offset)
            offset = len(text) if end == -1 else end + 1
        elif char == "{":
            end = text.find("}", offset + 1)
            if end == -1:
                raise ChessError("Unclosed PGN comment.")
            offset = end + 1
        elif char == "(":
            depth += 1
            if depth > 32:
                raise ChessError("PGN variations are nested too deeply.")
            offset += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ChessError("Unexpected closing variation.")
            offset += 1
        elif char in "[]}":
            raise ChessError("Unexpected PGN delimiter; import one game at a time.")
        elif char == "$":
            match = re.match(r"\$([0-9]{1,3})(?![0-9])", text[offset:])
            if match is None or int(match[1]) > 255:
                raise ChessError("Invalid PGN annotation glyph.")
            offset += len(match[0])
        else:
            end = offset
            while end < len(text) and not text[end].isspace() and text[end] not in "{}();$[]":
                end += 1
            if depth == 0:
                token = text[offset:end]
                if len(token) > 32:
                    raise ChessError("PGN move token is too long.")
                yield token
            offset = end
    if depth:
        raise ChessError("Unclosed PGN variation.")


def parse_pgn(text: str) -> PGNGame:
    if not isinstance(text, str) or not text.strip():
        raise ChessError("Paste a PGN or choose a PGN file.")
    try:
        byte_count = len(text.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ChessError("PGN must contain valid Unicode text.") from exc
    if byte_count > MAX_PGN_BYTES:
        raise ChessError("PGN must be at most 64 KiB.")
    if any(ord(char) < 32 and char not in "\r\n\t" for char in text):
        raise ChessError("PGN contains unsupported control characters.")
    text = text.lstrip("\ufeff")
    headers: dict[str, str] = {}
    offset = 0
    # Leading comments and escape lines are common in downloaded PGNs.
    while True:
        trivia = re.match(r"(?:\s+|;[^\n]*(?:\n|$)|%[^\n]*(?:\n|$)|\{[^}]*\})*", text[offset:])
        assert trivia is not None
        offset += len(trivia[0])
        if offset >= len(text) or text[offset] != "[":
            break
        match = TAG.match(text, offset)
        if match is None:
            raise ChessError("Malformed PGN header.")
        name, value = match.groups()
        value = re.sub(r'\\(["\\])', r"\1", value)
        if len(headers) >= 64 or len(name) > 64 or len(value) > 256 or name in headers:
            raise ChessError("Duplicate or oversized PGN header.")
        headers[name] = value
        offset = match.end()
    if headers.get("Variant", "Standard").lower() not in ("standard", "chess"):
        raise ChessError("Only standard chess PGNs are supported.")
    if headers.get("SetUp", "0") not in ("0", "1"):
        raise ChessError("SetUp must be 0 or 1.")
    if headers.get("SetUp") == "1" and "FEN" not in headers:
        raise ChessError("SetUp 1 requires a FEN header.")
    if headers.get("SetUp") == "0" and "FEN" in headers:
        raise ChessError("SetUp 0 contradicts the FEN header.")
    initial = Position.from_fen(headers.get("FEN", START_FEN))
    if initial.fullmove_number > 1_000_000 or initial.halfmove_clock > 1_000_000:
        raise ChessError("PGN FEN move counters must not exceed 1,000,000.")
    game = Game(initial)
    moves: list[PGNMove] = []
    marker: str | None = None
    for token in _tokens(text[offset:]):
        if marker is not None:
            raise ChessError("Unexpected content after the result; import one game at a time.")
        numbered = re.match(r"^([0-9]+)(\.{1,3})", token)
        if numbered:
            number, dots = numbered.groups()
            if int(number) != game.position.fullmove_number or len(dots) == 2:
                raise ChessError("Incorrect PGN move number.")
            if len(dots) == 3 and game.position.turn != "b":
                raise ChessError("Black move number used on White's turn.")
            token = token[len(numbered[0]) :]
        if not token or token == "...":
            continue
        if token in RESULTS:
            marker = token
            continue
        token = re.sub(r"(?:!!|\?\?|!\?|\?!|!|\?)$", "", token)
        if len(moves) >= MAX_PGN_PLIES:
            raise ChessError("PGN may contain at most 1,000 plies.")
        try:
            move = parse_san(game.position, token)
            notation = san(game.position, move)
            game.push(move)
        except ChessError as exc:
            raise ChessError(f"Invalid move at ply {len(moves) + 1}: {token}. {exc}") from exc
        moves.append(PGNMove(move.uci(), notation, game.position.fen()))
    result = headers.get("Result", marker or "*")
    if result not in RESULTS or (marker is not None and marker != result):
        raise ChessError("PGN header and movetext results must agree.")
    outcome = game.outcome()
    if outcome and result != "*" and outcome.result != result:
        raise ChessError("PGN result contradicts the final board position.")
    headers["Result"] = result
    return PGNGame(headers, initial.fen(), tuple(moves))


def export_pgn(headers: Mapping[str, str], initial_fen: str, moves: Sequence[str]) -> str:
    """Export already-validated SAN; callers must not pass arbitrary movetext."""
    initial = Position.from_fen(initial_fen)
    tags = {name: headers.get(name, "????.??.??" if name == "Date" else "?") for name in ROSTER}
    tags.update(headers)
    if tags.get("Result") not in RESULTS:
        raise ChessError("Invalid PGN result.")
    if initial_fen != START_FEN:
        tags.update(SetUp="1", FEN=initial.fen())
    else:
        tags.pop("SetUp", None)
        tags.pop("FEN", None)
    lines = []
    for key in (*ROSTER, *sorted(set(tags) - set(ROSTER))):
        value = tags[key]
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", key) is None or any(
            ord(character) < 32 for character in value
        ):
            raise ChessError("Invalid PGN header.")
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'[{key} "{escaped}"]')
    words = []
    offset = 0 if initial.turn == "w" else 1
    for index, notation in enumerate(moves):
        number = initial.fullmove_number + (index + offset) // 2
        if (index + offset) % 2 == 0:
            words.append(f"{number}.")
        elif index == 0:
            words.append(f"{number}...")
        words.append(notation)
    words.append(tags["Result"])
    return "\n".join(lines) + "\n\n" + textwrap.fill(" ".join(words), width=79) + "\n"

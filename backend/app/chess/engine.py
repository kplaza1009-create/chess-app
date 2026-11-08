"""Orthodox chess rules. Squares run a1=0 through h8=63; no I/O or global state."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

Color = Literal["w", "b"]
DrawReason = Literal["threefold_repetition", "fifty_moves"]
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
KNIGHT_STEPS = ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1))
DIAGONALS = ((1, 1), (1, -1), (-1, 1), (-1, -1))
ORTHOGONALS = ((1, 0), (-1, 0), (0, 1), (0, -1))
KING_STEPS = DIAGONALS + ORTHOGONALS
ROOK_RIGHTS = {0: "Q", 7: "K", 56: "q", 63: "k"}


class ChessError(ValueError):
    """Invalid position, illegal move, or unavailable game action."""


def opposite(color: Color) -> Color:
    return "b" if color == "w" else "w"


def square(name: str) -> int:
    if not isinstance(name, str) or re.fullmatch(r"[a-h][1-8]", name) is None:
        raise ChessError("A square must be a1 through h8.")
    return (int(name[1]) - 1) * 8 + ord(name[0]) - ord("a")


def square_name(index: int) -> str:
    if type(index) is not int or not 0 <= index < 64:
        raise ChessError("Square index must be an integer from 0 through 63.")
    return chr(ord("a") + index % 8) + str(index // 8 + 1)


def color_of(piece: str) -> Color:
    return "w" if piece.isupper() else "b"


@dataclass(frozen=True, slots=True)
class Move:
    source: int
    target: int
    promotion: str | None = None

    def __post_init__(self) -> None:
        square_name(self.source)
        square_name(self.target)
        if self.source == self.target or self.promotion not in (None, "q", "r", "b", "n"):
            raise ChessError("Invalid move or promotion piece.")

    @classmethod
    def from_uci(cls, text: str) -> Move:
        if not isinstance(text, str) or re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", text) is None:
            raise ChessError("Use UCI notation, for example e2e4 or a7a8q.")
        return cls(square(text[:2]), square(text[2:4]), text[4] if len(text) == 5 else None)

    def uci(self) -> str:
        return square_name(self.source) + square_name(self.target) + (self.promotion or "")


@dataclass(frozen=True, slots=True)
class Position:
    """Use from_fen/start to import positions; internal transitions use _apply."""

    board: tuple[str, ...]
    turn: Color
    castling: str
    en_passant: int | None
    halfmove_clock: int
    fullmove_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.board, tuple) or len(self.board) != 64:
            raise ChessError("Board must be an immutable tuple of 64 squares.")
        if any(
            p not in (".", "P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k")
            for p in self.board
        ):
            raise ChessError("Unknown piece.")
        if self.turn not in ("w", "b"):
            raise ChessError("Invalid side to move.")
        if not isinstance(self.castling, str) or self.castling != "".join(
            c for c in "KQkq" if c in self.castling
        ):
            raise ChessError("Castling rights must be unique and ordered KQkq.")
        if self.en_passant is not None:
            square_name(self.en_passant)
        if type(self.halfmove_clock) is not int or self.halfmove_clock < 0:
            raise ChessError("Halfmove clock must be nonnegative.")
        if type(self.fullmove_number) is not int or self.fullmove_number < 1:
            raise ChessError("Fullmove number must be positive.")
        if self.board.count("K") != 1 or self.board.count("k") != 1:
            raise ChessError("Exactly one king of each color is required.")

    @classmethod
    def start(cls) -> Position:
        return cls.from_fen(START_FEN)

    @classmethod
    def from_fen(cls, fen: str) -> Position:
        if not isinstance(fen, str) or len(fen) > 200:
            raise ChessError("FEN must be a string of at most 200 characters.")
        fields = fen.split()
        if len(fields) != 6:
            raise ChessError("FEN requires six fields.")
        placement, turn, rights, ep, half, full = fields
        rows = placement.split("/")
        if len(rows) != 8 or turn not in ("w", "b"):
            raise ChessError("Invalid FEN ranks or turn.")
        board: list[str] = []
        for row in reversed(rows):
            expanded: list[str] = []
            previous_digit = False
            for token in row:
                if token in "12345678":
                    if previous_digit:
                        raise ChessError("Consecutive empty-square counts are invalid.")
                    expanded.extend("." * int(token))
                    previous_digit = True
                elif token in "PNBRQKpnbrqk":
                    expanded.append(token)
                    previous_digit = False
                else:
                    raise ChessError("Invalid FEN piece.")
            if len(expanded) != 8:
                raise ChessError("Every FEN rank must contain eight squares.")
            board.extend(expanded)
        if re.fullmatch(r"[0-9]+", half) is None or re.fullmatch(r"[0-9]+", full) is None:
            raise ChessError("Invalid FEN move counters.")
        position = cls(
            tuple(board),
            "w" if turn == "w" else "b",
            "" if rights == "-" else rights,
            None if ep == "-" else square(ep),
            int(half),
            int(full),
        )
        position.validate()
        return position

    def validate(self) -> None:
        """Reject inconsistent setups; this does not prove historical reachability."""
        if any(p.lower() == "p" for p in self.board[:8] + self.board[56:]):
            raise ChessError("Pawns cannot occupy the first or last rank.")
        for color in ("w", "b"):
            pieces = [p for p in self.board if p != "." and color_of(p) == color]
            if len(pieces) > 16 or sum(p.lower() == "p" for p in pieces) > 8:
                raise ChessError("Too many pieces or pawns.")
        for rook, right in ROOK_RIGHTS.items():
            if right in self.castling:
                king = 4 if right.isupper() else 60
                if self.board[rook] != ("R" if right.isupper() else "r") or self.board[king] != (
                    "K" if right.isupper() else "k"
                ):
                    raise ChessError("Castling rights require the original king and rook squares.")
        if self.is_check(opposite(self.turn)):
            raise ChessError("The player who just moved cannot remain in check.")
        if self.en_passant is not None:
            ep = self.en_passant
            direction = 8 if self.turn == "w" else -8
            pawn = "p" if self.turn == "w" else "P"
            if (
                ep // 8 != (5 if self.turn == "w" else 2)
                or self.board[ep] != "."
                or self.board[ep - direction] != pawn
                or self.board[ep + direction] != "."
                or self.halfmove_clock != 0
            ):
                raise ChessError("Inconsistent en passant target or halfmove clock.")

    def fen(self) -> str:
        rows: list[str] = []
        for rank in range(7, -1, -1):
            row = ""
            empty = 0
            for piece in self.board[rank * 8 : rank * 8 + 8]:
                if piece == ".":
                    empty += 1
                else:
                    if empty:
                        row += str(empty)
                        empty = 0
                    row += piece
            rows.append(row + (str(empty) if empty else ""))
        ep = "-" if self.en_passant is None else square_name(self.en_passant)
        return (
            f"{'/'.join(rows)} {self.turn} {self.castling or '-'} {ep} "
            f"{self.halfmove_clock} {self.fullmove_number}"
        )

    def attacked(self, target: int, by: Color) -> bool:
        """Geometric attacks include pinned pieces, as required for king safety."""
        square_name(target)
        if by not in ("w", "b"):
            raise ChessError("Invalid attacking color.")
        tx, ty = target % 8, target // 8
        for dx, dy in KING_STEPS:
            x, y = tx + dx, ty + dy
            distance = 1
            while 0 <= x < 8 and 0 <= y < 8:
                piece = self.board[y * 8 + x]
                if piece != ".":
                    if color_of(piece) == by:
                        kind = piece.lower()
                        if kind == "q" or kind == ("b" if dx and dy else "r"):
                            return True
                        if distance == 1 and kind == "k":
                            return True
                        if distance == 1 and kind == "p" and dx and dy == (-1 if by == "w" else 1):
                            return True
                    break
                x += dx
                y += dy
                distance += 1
        knight = "N" if by == "w" else "n"
        return any(
            0 <= tx + dx < 8 and 0 <= ty + dy < 8 and self.board[(ty + dy) * 8 + tx + dx] == knight
            for dx, dy in KNIGHT_STEPS
        )

    def is_check(self, color: Color | None = None) -> bool:
        side = self.turn if color is None else color
        if side not in ("w", "b"):
            raise ChessError("Invalid king color.")
        return self.attacked(self.board.index("K" if side == "w" else "k"), opposite(side))

    def _pawn_moves(self, source: int) -> Iterator[Move]:
        step = 8 if self.turn == "w" else -8
        rank = source // 8
        target = source + step
        if 0 <= target < 64 and self.board[target] == ".":
            yield from self._promotions(source, target)
            if rank == (1 if self.turn == "w" else 6) and self.board[target + step] == ".":
                yield Move(source, target + step)
        for dx in (-1, 1):
            target = source + step + dx
            if not 0 <= source % 8 + dx < 8 or not 0 <= target < 64:
                continue
            victim = self.board[target]
            if victim != "." and color_of(victim) != self.turn and victim.lower() != "k":
                yield from self._promotions(source, target)
            elif (
                target == self.en_passant
                and victim == "."
                and self.board[target - step] == ("p" if self.turn == "w" else "P")
            ):
                yield Move(source, target)

    @staticmethod
    def _promotions(source: int, target: int) -> Iterator[Move]:
        if target // 8 in (0, 7):
            for piece in "qrbn":
                yield Move(source, target, piece)
        else:
            yield Move(source, target)

    def _castles(self, source: int) -> Iterator[Move]:
        home = 4 if self.turn == "w" else 60
        if source != home or self.is_check():
            return
        for right, offset, rook_offset, empty_offsets in (
            ("K", 2, 3, (1, 2)),
            ("Q", -2, -4, (-1, -2, -3)),
        ):
            flag = right if self.turn == "w" else right.lower()
            if flag not in self.castling or self.board[home + rook_offset] != (
                "R" if self.turn == "w" else "r"
            ):
                continue
            if any(self.board[home + gap] != "." for gap in empty_offsets):
                continue
            transit = self._apply(Move(home, home + (1 if offset > 0 else -1)))
            if not transit.is_check(self.turn):
                yield Move(home, home + offset)

    def _pseudo_legal_moves(self) -> Iterator[Move]:
        for source, piece in enumerate(self.board):
            if piece == "." or color_of(piece) != self.turn:
                continue
            kind = piece.lower()
            if kind == "p":
                yield from self._pawn_moves(source)
                continue
            directions = {
                "n": KNIGHT_STEPS,
                "k": KING_STEPS,
                "b": DIAGONALS,
                "r": ORTHOGONALS,
                "q": KING_STEPS,
            }[kind]
            for dx, dy in directions:
                x, y = source % 8 + dx, source // 8 + dy
                while 0 <= x < 8 and 0 <= y < 8:
                    target = y * 8 + x
                    victim = self.board[target]
                    if victim != "." and (color_of(victim) == self.turn or victim.lower() == "k"):
                        break
                    yield Move(source, target)
                    if victim != "." or kind in ("n", "k"):
                        break
                    x += dx
                    y += dy
            if kind == "k":
                yield from self._castles(source)

    def legal_moves(self) -> tuple[Move, ...]:
        return tuple(
            move for move in self._pseudo_legal_moves() if not self._apply(move).is_check(self.turn)
        )

    def play(self, move: Move | str) -> Position:
        candidate = Move.from_uci(move) if isinstance(move, str) else move
        if not isinstance(candidate, Move) or candidate not in self.legal_moves():
            raise ChessError("Illegal move.")
        return self._apply(candidate)

    def _apply(self, move: Move) -> Position:
        """Internal transition, called only for generated or validated moves."""
        board = list(self.board)
        piece, victim = board[move.source], board[move.target]
        board[move.source] = "."
        board[move.target] = piece
        pawn = piece.lower() == "p"
        if pawn and move.target == self.en_passant and victim == ".":
            board[move.target + (-8 if self.turn == "w" else 8)] = "."
            victim = "p"
        if move.promotion:
            board[move.target] = move.promotion.upper() if self.turn == "w" else move.promotion
        if piece.lower() == "k" and abs(move.target - move.source) == 2:
            rook_source = move.source + (3 if move.target > move.source else -4)
            rook_target = (move.source + move.target) // 2
            board[rook_target], board[rook_source] = board[rook_source], "."
        removed = ROOK_RIGHTS.get(move.source, "") + ROOK_RIGHTS.get(move.target, "")
        if piece.lower() == "k":
            removed += "KQ" if self.turn == "w" else "kq"
        rights = "".join(c for c in self.castling if c not in removed)
        ep = (
            (move.source + move.target) // 2
            if pawn and abs(move.target - move.source) == 16
            else None
        )
        return Position(
            tuple(board),
            opposite(self.turn),
            rights,
            ep,
            0 if pawn or victim != "." else self.halfmove_clock + 1,
            self.fullmove_number + (self.turn == "b"),
        )

    def repetition_key(self) -> tuple[tuple[str, ...], Color, str, int | None]:
        ep = None
        if self.en_passant is not None:
            for move in self.legal_moves():
                if (
                    move.target == self.en_passant
                    and self.board[move.source].lower() == "p"
                    and move.source % 8 != move.target % 8
                ):
                    ep = self.en_passant
                    break
        return self.board, self.turn, self.castling, ep

    def insufficient_material(self) -> bool:
        pieces = [(i, p.lower()) for i, p in enumerate(self.board) if p not in (".", "K", "k")]
        if not pieces:
            return True
        if len(pieces) == 1:
            return pieces[0][1] in ("b", "n")
        # All bishops must occupy the same square color, including promoted bishops.
        return (
            all(p == "b" for _, p in pieces) and len({(i // 8 + i % 8) % 2 for i, _ in pieces}) == 1
        )


@dataclass(frozen=True, slots=True)
class Outcome:
    result: Literal["1-0", "0-1", "1/2-1/2"]
    reason: str


class Game:
    """Owns move history and draw claims. One caller must serialize mutations."""

    def __init__(self, initial: Position | None = None) -> None:
        position = Position.start() if initial is None else initial
        if not isinstance(position, Position):
            raise ChessError("Initial state must be a Position.")
        position.validate()
        self._positions = [position]
        self._moves: list[Move] = []
        self._counts = Counter({position.repetition_key(): 1})
        self._claimed: Outcome | None = None

    @property
    def position(self) -> Position:
        return self._positions[-1]

    @property
    def moves(self) -> tuple[Move, ...]:
        return tuple(self._moves)

    @property
    def positions(self) -> tuple[Position, ...]:
        return tuple(self._positions)

    def outcome(self) -> Outcome | None:
        if self._claimed is not None:
            return self._claimed
        position = self.position
        if not position.legal_moves():
            if position.is_check():
                return Outcome("0-1" if position.turn == "w" else "1-0", "checkmate")
            return Outcome("1/2-1/2", "stalemate")
        if position.insufficient_material():
            return Outcome("1/2-1/2", "insufficient_material")
        if self._counts[position.repetition_key()] >= 5:
            return Outcome("1/2-1/2", "fivefold_repetition")
        if position.halfmove_clock >= 150:
            return Outcome("1/2-1/2", "seventy_five_moves")
        return None

    def push(self, move: Move | str) -> Position:
        if self.outcome() is not None:
            raise ChessError("The game has ended.")
        candidate = Move.from_uci(move) if isinstance(move, str) else move
        next_position = self.position.play(candidate)
        key = next_position.repetition_key()
        self._positions.append(next_position)
        self._moves.append(candidate)
        self._counts[key] += 1
        return next_position

    def pop(self) -> Move:
        """Undo for analysis/replay. Server authorization belongs outside this engine."""
        if not self._moves:
            raise ChessError("No move to undo.")
        self._counts[self.position.repetition_key()] -= 1
        self._positions.pop()
        self._claimed = None
        return self._moves.pop()

    def claimable_draws(self, intended_move: Move | str | None = None) -> tuple[DrawReason, ...]:
        if self.outcome() is not None:
            return ()
        position = self.position
        count = self._counts[position.repetition_key()]
        if intended_move is not None:
            position = position.play(intended_move)
            count = self._counts[position.repetition_key()] + 1
        reasons: list[DrawReason] = []
        if count >= 3:
            reasons.append("threefold_repetition")
        if position.halfmove_clock >= 100:
            reasons.append("fifty_moves")
        return tuple(reasons)

    def claim_draw(self, reason: DrawReason, intended_move: Move | str | None = None) -> Outcome:
        if reason not in self.claimable_draws(intended_move):
            raise ChessError("This draw cannot be claimed.")
        self._claimed = Outcome("1/2-1/2", reason)
        return self._claimed


def perft(position: Position, depth: int) -> int:
    """Count legal paths of exactly depth plies, ignoring game draw adjudication."""
    if type(depth) is not int or depth < 0:
        raise ChessError("Depth must be a nonnegative integer.")
    if depth == 0:
        return 1
    moves = position.legal_moves()
    if depth == 1:
        return len(moves)
    return sum(perft(position._apply(move), depth - 1) for move in moves)


def divide(position: Position, depth: int) -> dict[str, int]:
    """Return perft leaves by first UCI move, in deterministic order."""
    if type(depth) is not int or depth < 1:
        raise ChessError("Divide depth must be a positive integer.")
    return {
        move.uci(): perft(position._apply(move), depth - 1)
        for move in sorted(position.legal_moves(), key=Move.uci)
    }

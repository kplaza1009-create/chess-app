"""Canonical SAN output and deliberately tolerant, unambiguous SAN input."""

import re

from app.chess.engine import ChessError, Move, Position, square, square_name


def san(position: Position, move: Move | str) -> str:
    move = Move.from_uci(move) if isinstance(move, str) else move
    legal = position.legal_moves()
    if move not in legal:
        raise ChessError("Illegal move.")
    return _san(position, move, legal)


def _san(position: Position, move: Move, legal: tuple[Move, ...]) -> str:
    """The caller has already generated legal moves and validated membership."""
    piece = position.board[move.source].upper()
    source, target = square_name(move.source), square_name(move.target)
    capture = position.board[move.target] != "." or (piece == "P" and source[0] != target[0])
    if piece == "K" and abs(move.target - move.source) == 2:
        text = "O-O" if move.target > move.source else "O-O-O"
    else:
        prefix = "" if piece == "P" else piece
        if piece == "P" and capture:
            prefix = source[0]
        others = [
            m
            for m in legal
            if m != move
            and m.target == move.target
            and position.board[m.source] == position.board[move.source]
        ]
        if piece != "P" and others:
            if all(m.source % 8 != move.source % 8 for m in others):
                prefix += source[0]
            elif all(m.source // 8 != move.source // 8 for m in others):
                prefix += source[1]
            else:
                prefix += source
        text = prefix + ("x" if capture else "") + target
        if move.promotion:
            text += "=" + move.promotion.upper()
    after = position._apply(move)
    if after.is_check():
        text += "+" if after.legal_moves() else "#"
    return text


def parse_san(position: Position, text: str) -> Move:
    """Accept omitted +/# and promotion =, but never guess ambiguous moves.

    A supplied check/mate suffix must be correct. Filter by destination, piece,
    promotion and origin before computing canonical SAN; do not format the
    entire legal move list for every imported ply.
    """
    if not isinstance(text, str) or not 1 <= len(text) <= 16:
        raise ChessError("Invalid SAN.")
    normalized = text.replace("0", "O")
    legal = position.legal_moves()
    if normalized.rstrip("+#") in ("O-O", "O-O-O"):
        offset = 2 if normalized.rstrip("+#") == "O-O" else -2
        candidates = [
            move
            for move in legal
            if position.board[move.source].upper() == "K" and move.target - move.source == offset
        ]
    else:
        match = re.fullmatch(
            r"([KQRBN]?)([a-h]?[1-8]?)(x?)([a-h][1-8])(?:=?([QRBN]))?([+#]?)", normalized
        )
        if match is None:
            raise ChessError("Invalid SAN.")
        piece, origin, _, destination, promotion, _ = match.groups()
        candidates = [
            move
            for move in legal
            if move.target == square(destination)
            and position.board[move.source].upper() == (piece or "P")
            and move.promotion == (promotion.lower() if promotion else None)
            and all(character in square_name(move.source) for character in origin)
        ]
    matches = []
    for move in candidates:
        canonical = _san(position, move, legal).replace("=", "")
        expected = canonical if normalized.endswith(("+", "#")) else canonical.rstrip("+#")
        if normalized.replace("=", "") == expected:
            matches.append(move)
    if len(matches) != 1:
        raise ChessError("Illegal, ambiguous, or incorrect SAN.")
    return matches[0]

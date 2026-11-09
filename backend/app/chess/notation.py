"""Canonical Standard Algebraic Notation, derived only from legal moves."""

from app.chess.engine import ChessError, Move, Position, square_name


def san(position: Position, move: Move | str) -> str:
    move = Move.from_uci(move) if isinstance(move, str) else move
    legal = position.legal_moves()
    if move not in legal:
        raise ChessError("Illegal move.")
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
    after = position.play(move)
    if after.is_check():
        text += "+" if after.legal_moves() else "#"
    return text


def parse_san(position: Position, text: str) -> Move:
    """Strict SAN; also accept the widespread zero-based castling spelling."""
    if not isinstance(text, str) or not 1 <= len(text) <= 16:
        raise ChessError("Invalid SAN.")
    normalized = text.replace("0", "O")
    matches = [move for move in position.legal_moves() if san(position, move) == normalized]
    if len(matches) != 1:
        raise ChessError("Illegal, ambiguous, or noncanonical SAN.")
    return matches[0]

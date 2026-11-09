"""Persistent clocks. Call mutations only while holding the game's write lock."""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.chess import Position
from app.db.models import Game, GameStatus
from app.db.session import Database

PRESETS = {
    "1+0": (60000, 0),
    "3+2": (180000, 2000),
    "5+0": (300000, 0),
    "10+0": (600000, 0),
    "15+10": (900000, 10000),
}


async def database_now(session: AsyncSession) -> datetime:
    value = await session.scalar(select(text("clock_timestamp()")))
    if not isinstance(value, datetime):
        raise RuntimeError("Database clock unavailable")
    return value


def remaining(game: Game, now: datetime) -> tuple[int, int]:
    white, black = game.white_remaining_ms, game.black_remaining_ms
    if game.turn_started_at is not None and game.status == GameStatus.ACTIVE:
        elapsed = max(0, int((now - game.turn_started_at).total_seconds() * 1000))
        if game.current_fen.split()[1] == "w":
            white = max(0, white - elapsed)
        else:
            black = max(0, black - elapsed)
    return white, black


def has_mating_material(position: Position, color: str) -> bool:
    """One-sided material test, including helpmates using enemy blockers.

    This is a material policy, not an exhaustive search of arbitrary locked
    positions. Two knights can mate cooperatively, though they cannot force it.
    """
    own = [
        (i, p.lower())
        for i, p in enumerate(position.board)
        if p != "." and p.isupper() == (color == "w") and p.lower() != "k"
    ]
    enemy = [
        p.lower()
        for p in position.board
        if p != "." and p.isupper() != (color == "w") and p.lower() != "k"
    ]
    if not own:
        return False
    if any(p in "pqr" for _, p in own):
        return True
    if any(p == "n" for _, p in own):
        return len(own) > 1 or any(p != "q" for p in enemy)
    colors = {(i // 8 + i % 8) % 2 for i, _ in own}
    all_bishops = {(i // 8 + i % 8) % 2 for i, p in enumerate(position.board) if p.lower() == "b"}
    return (
        len(colors) > 1 or any(p in "pn" for p in enemy) or (len(all_bishops) > 1 and bool(enemy))
    )


def expire(game: Game, now: datetime) -> bool:
    if game.turn_started_at is None or game.status != GameStatus.ACTIVE:
        return False
    white, black = remaining(game, now)
    turn = game.current_fen.split()[1]
    if (white if turn == "w" else black) > 0:
        return False
    winner = "b" if turn == "w" else "w"
    game.white_remaining_ms, game.black_remaining_ms = white, black
    game.result = (
        ("0-1" if winner == "b" else "1-0")
        if has_mating_material(Position.from_fen(game.current_fen), winner)
        else "1/2-1/2"
    )
    game.status = GameStatus.FINISHED
    game.termination = "timeout"
    game.ended_at = now
    game.version += 1
    return True


async def sweep_once(database: Database) -> None:
    async with database.sessions() as session, session.begin():
        # Bound each batch; SKIP LOCKED allows multiple workers without double results.
        games = (
            await session.scalars(
                select(Game)
                .where(
                    Game.status == GameStatus.ACTIVE,
                    Game.turn_started_at.is_not(None),
                    text(
                        "turn_started_at + (CASE WHEN split_part(current_fen, ' ', 2) = 'w' "
                        "THEN white_remaining_ms ELSE black_remaining_ms END) "
                        "* interval '1 millisecond' "
                        "<= clock_timestamp()"
                    ),
                )
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        ).all()
        now = await database_now(session)
        for game in games:
            expire(game, now)


async def clock_worker(database: Database) -> None:
    while True:
        try:
            await sweep_once(database)
        except SQLAlchemyError:
            logging.getLogger(__name__).warning("Clock sweep deferred: database unavailable")
        await asyncio.sleep(0.5)

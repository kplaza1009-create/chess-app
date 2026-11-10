"""Settle a rated result in the transaction that finishes its game."""

from math import pow

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Game, GameStatus, RatingChange, UserRating

K_FACTOR = 32
WHITE_SCORES = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}


def elo_delta(white: int, black: int, white_score: float) -> int:
    """Points transferred from Black to White, with a zero rating floor."""
    odds = pow(10.0, -abs(white - black) / 400)
    expected = (odds if white < black else 1) / (1 + odds)
    delta = round(K_FACTOR * (white_score - expected))
    return min(black, max(-white, delta))


async def settle_ratings(session: AsyncSession, game: Game) -> None:
    """Caller holds the game write lock. Commit the game and ledger together."""
    if not game.rated or game.status != GameStatus.FINISHED:
        return
    white_id, black_id = game.white_user_id, game.black_user_id
    if white_id is None or black_id is None:
        raise RuntimeError("Rated game is missing a player")
    player_ids = {white_id, black_id}
    # Also see any ledger rows inserted earlier in this transaction (autoflush is off).
    await session.flush()
    recorded = set(
        await session.scalars(select(RatingChange.user_id).where(RatingChange.game_id == game.id))
    )
    if recorded:
        if recorded != player_ids:
            raise RuntimeError("Incomplete rating ledger")
        return
    rows = {
        row.user_id: row
        for row in await session.scalars(
            select(UserRating)
            .where(UserRating.user_id.in_(player_ids), UserRating.speed == game.speed)
            .order_by(UserRating.user_id)
            .with_for_update()
        )
    }
    if rows.keys() != player_ids:
        raise RuntimeError("Rated game is missing a rating")
    white, black = rows[white_id], rows[black_id]
    score = WHITE_SCORES[game.result]
    delta = elo_delta(white.rating, black.rating, score)
    for row, change, actual in ((white, delta, score), (black, -delta, 1 - score)):
        session.add(
            RatingChange(
                game_id=game.id,
                user_id=row.user_id,
                speed=game.speed,
                rating_before=row.rating,
                rating_after=row.rating + change,
            )
        )
        row.rating += change
        if actual == 1:
            row.wins += 1
        elif actual == 0:
            row.losses += 1
        else:
            row.draws += 1

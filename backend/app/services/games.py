"""Durable game operations. Lock the game row before reading or writing its moves."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from anyio import to_thread
from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chess import Game as EngineGame
from app.chess import Position
from app.chess.notation import san
from app.db.models import Game, GameStatus, Move, RatingChange, User, UserRating
from app.services.clocks import database_now, expire, remaining
from app.services.engine_cache import EngineCache
from app.services.notifications import notify_transaction
from app.services.ratings import settle_ratings

TERMINATIONS = {
    "checkmate": "checkmate",
    "stalemate": "stalemate",
    "insufficient_material": "insufficient_material",
    "threefold_repetition": "repetition",
    "fivefold_repetition": "repetition",
    "fifty_moves": "fifty_move",
    "seventy_five_moves": "seventy_five_move",
}


async def locked_game(
    session: AsyncSession, game_id: UUID, user_id: UUID, *, write: bool = False
) -> Game:
    # Shared locks keep game and move rows in one snapshot while allowing both
    # players to reconnect concurrently. Applying a move takes an exclusive lock.
    statement = select(Game).where(Game.id == game_id).with_for_update(read=not write)
    game = await session.scalar(statement)
    if game is None or user_id not in (game.white_user_id, game.black_user_id):
        raise HTTPException(404, "Game not found")
    return game


async def snapshot(session: AsyncSession, game: Game, user_id: UUID) -> dict[str, Any]:
    def board() -> dict[str, Any]:
        position = Position.from_fen(game.current_fen)
        return {
            "fen": game.current_fen,
            "board": list(position.board),
            "turn": position.turn,
            "check": position.is_check(),
            "ending": game.termination,
            "legal_moves": [m.uci() for m in position.legal_moves()]
            if game.status == GameStatus.ACTIVE
            else [],
        }

    moves = (
        await session.scalars(select(Move).where(Move.game_id == game.id).order_by(Move.ply))
    ).all()
    now = await database_now(session)
    white, black = remaining(game, now)
    opponent_id = game.black_user_id if user_id == game.white_user_id else game.white_user_id
    player_ids = [player for player in (game.white_user_id, game.black_user_id) if player]
    players = {
        player_id: (username, rating)
        for player_id, username, rating in await session.execute(
            select(User.id, User.username, UserRating.rating)
            .outerjoin(
                UserRating,
                and_(UserRating.user_id == User.id, UserRating.speed == game.speed),
            )
            .where(User.id.in_(player_ids))
        )
    }
    rating_changes = (
        {
            change.user_id: change
            for change in await session.scalars(
                select(RatingChange).where(RatingChange.game_id == game.id)
            )
        }
        if game.rated and game.status == GameStatus.FINISHED
        else {}
    )

    def rating_for(player_id: UUID | None) -> int | None:
        if player_id is None:
            return None
        if change := rating_changes.get(player_id):
            return change.rating_after
        player = players.get(player_id)
        return player[1] if player else None

    opponent = players.get(opponent_id) if opponent_id is not None else None
    rating_change = rating_changes.get(user_id)
    return {
        "type": "state",
        "id": str(game.id),
        "version": game.version,
        "color": "w" if user_id == game.white_user_id else "b",
        "result": game.result,
        "status": game.status.value,
        "opponent": opponent[0] if opponent else None,
        "player_rating": rating_for(user_id),
        "opponent_rating": rating_for(opponent_id),
        "rated": game.rated,
        "rating_change": (
            {"before": rating_change.rating_before, "after": rating_change.rating_after}
            if rating_change is not None
            else None
        ),
        "clock": {
            "white_ms": white,
            "black_ms": black,
            "running": game.turn_started_at is not None
            and game.status == GameStatus.ACTIVE
            and game.first_move_deadline is None,
            "first_move_ms": max(0, int((game.first_move_deadline - now).total_seconds() * 1000))
            if game.first_move_deadline is not None and game.status == GameStatus.ACTIVE
            else None,
            "timed": game.turn_started_at is not None,
            "initial_ms": game.initial_time_ms,
            "increment_ms": game.increment_ms,
        },
        "position": await to_thread.run_sync(board),
        "moves": [
            {"uci": m.uci, "san": m.san, "request_id": str(m.client_request_id)} for m in moves
        ],
    }


async def play(
    session: AsyncSession,
    game: Game,
    user_id: UUID,
    version: int,
    request_id: UUID,
    uci: str,
    *,
    cache: EngineCache | None = None,
) -> None:
    moves = list(
        (
            await session.scalars(select(Move).where(Move.game_id == game.id).order_by(Move.ply))
        ).all()
    )
    for old in moves:
        if old.client_request_id == request_id:
            owner = game.white_user_id if old.ply % 2 else game.black_user_id
            if owner != user_id or old.uci != uci:
                raise HTTPException(409, "Request ID already used")
            return
    if game.status != GameStatus.ACTIVE:
        raise HTTPException(409, "Game has ended")
    if version != game.version:
        raise HTTPException(409, "Position changed; synchronized current state")
    owner = game.white_user_id if game.ply_count % 2 == 0 else game.black_user_id
    if owner != user_id:
        raise HTTPException(403, "It is not your turn")
    if len(moves) >= 20000:
        raise HTTPException(409, "Game move limit reached")
    now = await database_now(session)
    if expire(game, now):
        await settle_ratings(session, game)
        await session.flush()
        await notify_transaction(session, game.id)
        return

    def advance() -> tuple[EngineGame, str]:
        if cache is not None:
            engine = cache.restore(
                game.id, game.version, game.initial_fen, tuple(move.uci for move in moves)
            )
        else:
            engine = EngineGame(Position.from_fen(game.initial_fen))
            for previous in moves:
                engine.push(previous.uci)
        notation = san(engine.position, uci)
        engine.push(uci)
        if engine.outcome() is None and (claims := engine.claimable_draws()):
            engine.claim_draw(claims[0])
        return engine, notation

    engine, notation = await to_thread.run_sync(advance)
    if game.first_move_deadline is not None:
        game.turn_started_at = await database_now(session)
        game.first_move_deadline = (
            game.turn_started_at + timedelta(seconds=30) if game.ply_count == 0 else None
        )
    elif game.turn_started_at is not None:
        white, black = remaining(game, now)
        if game.current_fen.split()[1] == "w":
            white += game.increment_ms
        else:
            black += game.increment_ms
        game.white_remaining_ms, game.black_remaining_ms = white, black
        # Validation time is not charged to the opponent.
        game.turn_started_at = await database_now(session)
    game.current_fen = engine.position.fen()
    game.ply_count += 1
    game.version += 1
    outcome = engine.outcome()
    if outcome:
        game.status = GameStatus.FINISHED
        game.result = outcome.result
        game.termination = TERMINATIONS[outcome.reason]
        game.ended_at = await database_now(session)
    session.add(
        Move(
            game_id=game.id,
            ply=game.ply_count,
            client_request_id=request_id,
            uci=uci,
            san=notation,
            fen_after=game.current_fen,
            white_remaining_ms=game.white_remaining_ms,
            black_remaining_ms=game.black_remaining_ms,
        )
    )
    if outcome:
        await settle_ratings(session, game)
    await session.flush()
    await notify_transaction(session, game.id)

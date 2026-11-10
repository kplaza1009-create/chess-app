"""Pair live tickets on PostgreSQL so multiple API processes share one queue."""

from datetime import datetime, timedelta
from secrets import randbelow
from uuid import UUID, uuid4

from sqlalchemy import Select, delete, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Game,
    GameStatus,
    MatchmakingTicket,
    RefreshSession,
    TimeControl,
    User,
    UserRating,
)
from app.services.clocks import PRESETS, database_now, new_timed_game

LEASE = timedelta(seconds=20)
INITIAL_RANGE = 100
RANGE_STEP = 50
STEP_SECONDS = 5
MAX_RANGE = 400

type SearchState = MatchmakingTicket | UUID | None


async def lock_queue(session: AsyncSession) -> None:
    # A transaction lock also covers the case where a player's ticket does not exist.
    # All queue transitions take this lock. Game writes never acquire it.
    await session.execute(text("SET LOCAL lock_timeout = '2s'"))
    await session.execute(text("SELECT pg_advisory_xact_lock(83145, 8)"))


def live_tickets(now: datetime) -> Select[tuple[MatchmakingTicket]]:
    return (
        select(MatchmakingTicket)
        .join(User, User.id == MatchmakingTicket.user_id)
        .join(RefreshSession, RefreshSession.id == MatchmakingTicket.session_id)
        .where(
            MatchmakingTicket.expires_at > now,
            User.is_active.is_(True),
            RefreshSession.user_id == MatchmakingTicket.user_id,
            RefreshSession.family_id == RefreshSession.id,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > func.clock_timestamp(),
        )
    )


async def search_state(session: AsyncSession, user_id: UUID, now: datetime) -> SearchState:
    game_id = await session.scalar(
        select(Game.id)
        .where(
            Game.rated.is_(True),
            Game.status == GameStatus.ACTIVE,
            or_(Game.white_user_id == user_id, Game.black_user_id == user_id),
        )
        .order_by(Game.created_at.desc(), Game.id)
        .limit(1)
    )
    if game_id is not None:
        return game_id
    return (
        await session.scalars(live_tickets(now).where(MatchmakingTicket.user_id == user_id))
    ).first()


async def start_search(
    session: AsyncSession, user_id: UUID, session_id: UUID, control: TimeControl, now: datetime
) -> MatchmakingTicket:
    stale = (
        select(MatchmakingTicket.user_id)
        .where(MatchmakingTicket.expires_at <= now)
        .order_by(MatchmakingTicket.expires_at)
        .limit(100)
    )
    await session.execute(delete(MatchmakingTicket).where(MatchmakingTicket.user_id.in_(stale)))
    ticket = await session.get(MatchmakingTicket, user_id)
    if ticket is None:
        ticket = MatchmakingTicket(user_id=user_id)
        session.add(ticket)
    ticket.ticket_id = uuid4()
    ticket.session_id = session_id
    ticket.time_control = control
    ticket.joined_at = now
    ticket.expires_at = now + LEASE
    await session.flush()
    return ticket


async def renew_and_pair(
    session: AsyncSession, ticket: MatchmakingTicket, session_id: UUID, now: datetime
) -> SearchState:
    ticket.session_id = session_id
    ticket.expires_at = now + LEASE
    _, _, speed = PRESETS[ticket.time_control]
    rating = await session.scalar(
        select(UserRating.rating).where(
            UserRating.user_id == ticket.user_id, UserRating.speed == speed
        )
    )
    if rating is None:
        raise RuntimeError("Queued player is missing a rating")

    waited = max(0, int((now - ticket.joined_at).total_seconds()))
    own_range = min(MAX_RANGE, INITIAL_RANGE + waited // STEP_SECONDS * RANGE_STEP)
    other_wait = func.greatest(0, func.extract("epoch", literal(now) - MatchmakingTicket.joined_at))
    other_range = func.least(
        MAX_RANGE, INITIAL_RANGE + func.floor(other_wait / STEP_SECONDS) * RANGE_STEP
    )
    gap = func.abs(UserRating.rating - rating)
    opponent = await session.scalar(
        live_tickets(now)
        .join(UserRating, UserRating.user_id == MatchmakingTicket.user_id)
        .where(
            MatchmakingTicket.user_id != ticket.user_id,
            MatchmakingTicket.time_control == ticket.time_control,
            UserRating.speed == speed,
            gap <= own_range,
            gap <= other_range,
        )
        .order_by(MatchmakingTicket.joined_at, MatchmakingTicket.user_id)
        .limit(1)
        # Order matching against session revocation and account deactivation.
        .with_for_update(read=True, of=(User, RefreshSession))
    )
    if opponent is None:
        return ticket
    white, black = ticket.user_id, opponent.user_id
    if randbelow(2):
        white, black = black, white
    game = new_timed_game(
        white, black, ticket.time_control, await database_now(session), rated=True
    )
    session.add(game)
    await session.delete(ticket)
    await session.delete(opponent)
    await session.flush()
    return game.id

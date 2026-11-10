from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import AccessDep, SecurityDep, SessionDep, load_session_user
from app.db.models import MatchmakingTicket, TimeControl
from app.services.clocks import database_now
from app.services.matchmaking import (
    SearchState,
    lock_queue,
    renew_and_pair,
    search_state,
    start_search,
)
from app.services.rate_limit import enforce_rate_limit
from app.services.security import Claims, Security

router = APIRouter(prefix="/api/v1/matchmaking", tags=["matchmaking"])


class JoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time_control: TimeControl


class Idle(BaseModel):
    state: Literal["idle"] = "idle"


class Queued(BaseModel):
    state: Literal["queued"] = "queued"
    ticket_id: UUID
    time_control: TimeControl


class Matched(BaseModel):
    state: Literal["matched"] = "matched"
    game_id: UUID


type QueueResponse = Idle | Queued | Matched


def response(state: SearchState) -> QueueResponse:
    if isinstance(state, UUID):
        return Matched(game_id=state)
    if isinstance(state, MatchmakingTicket):
        return Queued(ticket_id=state.ticket_id, time_control=state.time_control)
    return Idle()


@asynccontextmanager
async def queue_transaction(
    session: AsyncSession, security: Security, claims: Claims
) -> AsyncIterator[tuple[datetime, SearchState]]:
    await enforce_rate_limit(session, security.throttle_key("matchmaking", str(claims.sub)), 90, 60)
    async with session.begin():
        await lock_queue(session)
        await load_session_user(session, claims, lock=True)
        now = await database_now(session)
        yield now, await search_state(session, claims.sub, now)


@router.get("")
async def status(session: SessionDep, security: SecurityDep, claims: AccessDep) -> QueueResponse:
    async with queue_transaction(session, security, claims) as (_, state):
        return response(state)


@router.post("")
async def join(
    data: JoinRequest, session: SessionDep, security: SecurityDep, claims: AccessDep
) -> QueueResponse:
    async with queue_transaction(session, security, claims) as (now, state):
        if isinstance(state, UUID):
            return response(state)
        ticket = state or await start_search(
            session, claims.sub, claims.sid, data.time_control, now
        )
        return response(await renew_and_pair(session, ticket, claims.sid, now))


@router.put("/{ticket_id}")
async def heartbeat(
    ticket_id: UUID, session: SessionDep, security: SecurityDep, claims: AccessDep
) -> QueueResponse:
    async with queue_transaction(session, security, claims) as (now, state):
        if isinstance(state, MatchmakingTicket) and state.ticket_id == ticket_id:
            state = await renew_and_pair(session, state, claims.sid, now)
        return response(state)


@router.delete("/{ticket_id}")
async def cancel(
    ticket_id: UUID, session: SessionDep, security: SecurityDep, claims: AccessDep
) -> QueueResponse:
    async with queue_transaction(session, security, claims) as (_, state):
        if isinstance(state, MatchmakingTicket) and state.ticket_id == ticket_id:
            await session.delete(state)
            return Idle()
        return response(state)

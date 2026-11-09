"""Participant-only, unrated rooms with persistent clocks."""

import asyncio
import json
import logging
import time
from datetime import timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from anyio import CancelScope
from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import SecurityDep, SessionDep, UserDep, current_user, session_user
from app.chess import ChessError
from app.db.models import Game, GameKind, Speed, User
from app.db.session import Database
from app.services.clocks import PRESETS, database_now
from app.services.games import locked_game, play, snapshot
from app.services.notifications import GameNotifications
from app.services.rate_limit import enforce_rate_limit
from app.services.security import AuthError, Security

router = APIRouter(prefix="/api/v1/games", tags=["games"])
logger = logging.getLogger(__name__)


async def _cancel_tasks(*tasks: asyncio.Task[Any]) -> None:
    # TestClient (and other AnyIO callers) can cancel us while gather is draining
    # a mixture of pending and already-cancelled children. Shield that drain so
    # gather cannot replace the caller's cancellation with a child's bare one.
    # Cancellation of the handler itself still propagates outside this scope.
    with CancelScope(shield=True):
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class CreateGame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opponent: Annotated[str, Field(pattern=r"^[a-z0-9_]{3,24}$")]
    time_control: Literal["1+0", "3+2", "5+0", "10+0", "15+10"] = "10+0"


class MoveMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["move"]
    version: Annotated[int, Field(ge=0)]
    request_id: UUID
    uci: Annotated[str, Field(pattern=r"^[a-h][1-8][a-h][1-8][qrbn]?$")]


@router.post("", status_code=201)
async def create_game(
    data: CreateGame, user: UserDep, session: SessionDep, security: SecurityDep
) -> dict[str, str]:
    await enforce_rate_limit(session, security.throttle_key("create-game", str(user.id)), 10, 3600)
    async with session.begin():
        opponent = await session.scalar(
            select(User).where(User.username == data.opponent, User.is_active.is_(True))
        )
        if opponent is None or opponent.id == user.id:
            raise HTTPException(422, "Choose another registered player")
        initial, increment = PRESETS[data.time_control]
        now = await database_now(session)
        game = Game(
            kind=GameKind.MULTIPLAYER,
            white_user_id=user.id,
            black_user_id=opponent.id,
            rated=False,
            speed=Speed.BULLET
            if initial < 180000
            else Speed.BLITZ
            if initial < 600000
            else Speed.RAPID,
            initial_time_ms=initial,
            increment_ms=increment,
            white_remaining_ms=initial,
            black_remaining_ms=initial,
            turn_started_at=now,
            first_move_deadline=now + timedelta(seconds=30),
        )
        session.add(game)
        await session.flush()
        return {"id": str(game.id)}


@router.get("/{game_id}/ticket")
async def socket_ticket(
    game_id: UUID,
    request: Request,
    response: Response,
    user: UserDep,
    session: SessionDep,
    security: SecurityDep,
) -> dict[str, str]:
    await enforce_rate_limit(session, security.throttle_key("game-ticket", str(user.id)), 60, 60)
    async with session.begin():
        await locked_game(session, game_id, user.id)
    # Reuse the short-lived access credential, sent only in the first WS frame.
    # No token in URLs, logs, localStorage, or new refresh-session semantics.
    response.headers["Cache-Control"] = "no-store"
    return {"token": request.headers["authorization"].split(" ", 1)[1]}


@router.websocket("/{game_id}/ws")
async def game_socket(ws: WebSocket, game_id: UUID) -> None:
    security: Security = ws.app.state.security
    database: Database = ws.app.state.database
    slots: dict[str, int] = ws.app.state.game_connections
    key: str | None = None
    accepted = False
    notifications: GameNotifications = ws.app.state.game_notifications
    changed: asyncio.Event | None = None
    receive_task: asyncio.Task[str] | None = None
    wake_task: asyncio.Task[bool] | None = None

    async def send(data: dict[str, Any]) -> None:
        async with asyncio.timeout(5):
            await ws.send_json(data)

    async def receive_text() -> str:
        message = await ws.receive()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message.get("code", 1000))
        value = message.get("text")
        if not isinstance(value, str):
            raise ValueError("Text messages required")
        return value

    try:
        if ws.headers.get("origin") not in security.settings.cors_origins:
            await ws.close(code=1008)
            return
        if sum(slots.values()) >= 128:
            await ws.close(code=1013)
            return
        key = "pending"
        slots[key] = slots.get(key, 0) + 1
        async with database.sessions() as session:
            address = ws.client.host if ws.client else "unknown"
            await enforce_rate_limit(session, security.throttle_key("ws-open", address), 60, 60)
        await ws.accept()
        accepted = True
        async with asyncio.timeout(5):
            raw = await receive_text()
        if len(raw) > 5000:
            raise ValueError("Oversized authentication frame")
        auth = json.loads(raw)
        if (
            not isinstance(auth, dict)
            or set(auth) != {"type", "token"}
            or auth["type"] != "auth"
            or not isinstance(auth["token"], str)
        ):
            raise ValueError("Invalid authentication frame")
        credential = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth["token"])
        claims = security.decode(auth["token"], "access")
        async with database.sessions() as session:
            user = await current_user(session, security, credential)
        user_key = str(user.id)
        if slots.get(user_key, 0) >= 4:
            await ws.close(code=1013)
            return
        slots[key] -= 1
        if slots[key] == 0:
            del slots[key]
        key = user_key
        slots[key] = slots.get(key, 0) + 1
        sent_version = -1
        heartbeat = time.monotonic()
        changed = notifications.subscribe(game_id)
        receive_task = asyncio.create_task(receive_text())
        while True:
            # Clear before reading: a commit during the read must wake the next pass.
            changed.clear()
            async with database.sessions() as session:
                user = await session_user(session, claims)
                async with session.begin():
                    game = await locked_game(session, game_id, user.id)
                    state = (
                        await snapshot(session, game, user.id)
                        if game.version != sent_version or time.monotonic() - heartbeat >= 15
                        else None
                    )
            if state is not None:
                await send(state)
                sent_version = state["version"]
            if time.monotonic() - heartbeat >= 15:
                await send({"type": "heartbeat"})
                heartbeat = time.monotonic()
            wake_task = asyncio.create_task(changed.wait())
            done, _ = await asyncio.wait(
                {receive_task, wake_task}, timeout=5, return_when=asyncio.FIRST_COMPLETED
            )
            await _cancel_tasks(wake_task)
            wake_task = None
            if receive_task not in done:
                continue
            raw = receive_task.result()
            receive_task = asyncio.create_task(receive_text())
            if len(raw) > 1024:
                raise ValueError("Oversized message")
            async with database.sessions() as session:
                await enforce_rate_limit(
                    session, security.throttle_key("ws-message", user_key), 120, 60
                )
                # Revalidate before every write, including after waiting for a frame.
                user = await session_user(session, claims)
                try:
                    message = MoveMessage.model_validate_json(raw)
                    async with session.begin():
                        game = await locked_game(session, game_id, user.id, write=True)
                        await play(
                            session,
                            game,
                            user.id,
                            message.version,
                            message.request_id,
                            message.uci,
                            cache=database.game_engines,
                        )
                    notifications.notify(game_id)
                    sent_version = -1
                except (ValidationError, ChessError, HTTPException) as exc:
                    detail = (
                        exc.detail if isinstance(exc, HTTPException) else "Invalid or illegal move"
                    )
                    await send({"type": "error", "message": detail})
                    sent_version = -1
    except WebSocketDisconnect:
        pass
    except AuthError:
        if accepted:
            await ws.close(code=4401)
    except HTTPException as exc:
        if accepted:
            await send({"type": "error", "message": exc.detail})
        await ws.close(code=1008)
    except (ValueError, TimeoutError):
        await ws.close(code=1008)
    except SQLAlchemyError:
        logger.warning("Game database operation unavailable")
        await ws.close(code=1013)
    finally:
        if changed is not None:
            notifications.unsubscribe(game_id, changed)
        # Release synchronous accounting even if the server cancels this handler
        # again during asynchronous teardown.
        if key is not None:
            slots[key] -= 1
            if slots[key] == 0:
                del slots[key]
        await _cancel_tasks(*(task for task in (receive_task, wake_task) if task is not None))

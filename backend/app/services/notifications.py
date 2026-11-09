"""Bounded wakeups, never game data: receivers reload committed database state."""

import asyncio
import logging
from uuid import UUID

import psycopg
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession


class GameNotifications:
    def __init__(self) -> None:
        self.subscribers: dict[UUID, set[asyncio.Event]] = {}
        self.ready = asyncio.Event()

    def subscribe(self, game_id: UUID) -> asyncio.Event:
        event = asyncio.Event()
        self.subscribers.setdefault(game_id, set()).add(event)
        return event

    def unsubscribe(self, game_id: UUID, event: asyncio.Event) -> None:
        listeners = self.subscribers.get(game_id)
        if listeners is not None:
            listeners.discard(event)
            if not listeners:
                del self.subscribers[game_id]

    def notify(self, game_id: UUID) -> None:
        for event in self.subscribers.get(game_id, ()):
            event.set()

    async def listen(self, url: str) -> None:
        dsn = make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    dsn, autocommit=True
                ) as connection:
                    await connection.execute("LISTEN chess_games")
                    self.ready.set()
                    # Resync after listener recovery; notifications are not durable.
                    for game_id in self.subscribers:
                        self.notify(game_id)
                    async for notification in connection.notifies():
                        try:
                            self.notify(UUID(notification.payload))
                        except ValueError:
                            continue
            except psycopg.Error:
                self.ready.clear()
                logging.getLogger(__name__).warning("Game notification listener reconnecting")
                await asyncio.sleep(1)


async def notify_transaction(session: AsyncSession, game_id: UUID) -> None:
    # PostgreSQL delivers this only on successful commit, not rollback.
    await session.execute(text("SELECT pg_notify('chess_games', :id)"), {"id": str(game_id)})

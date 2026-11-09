"""Bounded worker-local history cache. Database history always wins."""

from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from uuid import UUID

from app.chess import Game, Position


@dataclass(frozen=True)
class Entry:
    version: int
    initial_fen: str
    moves: tuple[str, ...]
    engine: Game


class EngineCache:
    def __init__(self, capacity: int = 128) -> None:
        if capacity < 1:
            raise ValueError("Cache capacity must be positive")
        self.capacity = capacity
        self._entries: OrderedDict[UUID, Entry] = OrderedDict()
        self._lock = Lock()

    def restore(
        self, game_id: UUID, version: int, initial_fen: str, moves: tuple[str, ...]
    ) -> Game:
        """Return an independent engine for history read under the DB game lock.

        Cache only the input history, never the caller's pending move. A worker
        can catch up from a prefix after another worker commits. Rollbacks,
        database resets, and replaced histories force reconstruction.
        """
        with self._lock:
            entry = self._entries.get(game_id)
        if (
            entry is not None
            and entry.version <= version
            and entry.initial_fen == initial_fen
            and moves[: len(entry.moves)] == entry.moves
        ):
            engine = entry.engine.copy()
            offset = len(entry.moves)
        else:
            engine = Game(Position.from_fen(initial_fen))
            offset = 0
        for move in moves[offset:]:
            engine.push(move)
        with self._lock:
            self._entries[game_id] = Entry(version, initial_fen, moves, engine.copy())
            self._entries.move_to_end(game_id)
            while len(self._entries) > self.capacity:
                self._entries.popitem(last=False)
        return engine

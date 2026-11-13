"""Participant-only online history and owner-only, unrated PGN imports."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from anyio import CapacityLimiter, to_thread
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, String, case, cast, func, literal, or_, select, union_all
from sqlalchemy.orm import aliased

from app.api.dependencies import SecurityDep, SessionDep, UserDep
from app.chess import ChessError
from app.chess.pgn import MAX_PGN_BYTES, export_pgn, parse_pgn
from app.db.models import Game, GameStatus, ImportedGame, Move, RatingChange, User
from app.services.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/api/v1/history", tags=["history and PGN"])
Source = Literal["online", "import"]


class HistoryItem(BaseModel):
    id: UUID
    source: Source
    white: str
    black: str
    result: str
    status: str
    rated: bool
    time_control: str | None
    ply_count: int
    created_at: datetime
    rating_before: int | None
    rating_after: int | None


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    page: int
    has_more: bool


class ReplayMove(BaseModel):
    uci: str
    san: str
    fen_after: str


class Replay(BaseModel):
    id: UUID
    source: Source
    headers: dict[str, str]
    initial_fen: str
    moves: list[ReplayMove]
    result: str
    termination: str | None
    pgn: str


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pgn: Annotated[str, Field(min_length=1, max_length=MAX_PGN_BYTES)]


@router.get("", response_model=HistoryPage)
async def history(
    user: UserDep,
    session: SessionDep,
    page: Annotated[int, Query(ge=1, le=500)] = 1,
    source: Literal["all", "online", "import"] = "all",
) -> HistoryPage:
    white, black = aliased(User), aliased(User)
    online = (
        select(
            Game.id,
            literal("online").label("source"),
            func.coalesce(white.username, "Computer").label("white"),
            func.coalesce(black.username, "Computer").label("black"),
            Game.result,
            cast(Game.status, String).label("status"),
            Game.rated,
            case(
                (Game.turn_started_at.is_(None), literal(None, String)),
                else_=(
                    cast(cast(Game.initial_time_ms / 60000, Integer), String)
                    + "+"
                    + cast(cast(Game.increment_ms / 1000, Integer), String)
                ),
            ).label("time_control"),
            Game.ply_count,
            Game.created_at,
            RatingChange.rating_before,
            RatingChange.rating_after,
        )
        .outerjoin(white, white.id == Game.white_user_id)
        .outerjoin(black, black.id == Game.black_user_id)
        .outerjoin(
            RatingChange, (RatingChange.game_id == Game.id) & (RatingChange.user_id == user.id)
        )
        .where(
            or_(Game.white_user_id == user.id, Game.black_user_id == user.id),
            Game.status != GameStatus.ACTIVE,
        )
    )
    imported = select(
        ImportedGame.id,
        literal("import").label("source"),
        func.coalesce(ImportedGame.headers["White"].astext, "?").label("white"),
        func.coalesce(ImportedGame.headers["Black"].astext, "?").label("black"),
        ImportedGame.result,
        literal("imported").label("status"),
        literal(False).label("rated"),
        literal(None, String).label("time_control"),
        ImportedGame.ply_count,
        ImportedGame.created_at,
        literal(None).label("rating_before"),
        literal(None).label("rating_after"),
    ).where(ImportedGame.owner_id == user.id)
    query = (
        union_all(online, imported)
        if source == "all"
        else online
        if source == "online"
        else imported
    ).subquery()
    async with session.begin():
        rows = (
            (
                await session.execute(
                    select(query)
                    .order_by(
                        query.c.created_at.desc(),
                        query.c.id.desc(),
                        query.c.source,
                    )
                    .limit(21)
                    .offset((page - 1) * 20)
                )
            )
            .mappings()
            .all()
        )
    return HistoryPage(
        items=[HistoryItem.model_validate(row) for row in rows[:20]],
        page=page,
        has_more=len(rows) > 20,
    )


@router.post("/import", status_code=201, response_model=Replay)
async def import_game(
    data: ImportRequest,
    request: Request,
    user: UserDep,
    session: SessionDep,
    security: SecurityDep,
) -> Replay:
    address = request.client.host if request.client else "unknown"
    await enforce_rate_limit(session, security.throttle_key("pgn-user", str(user.id)), 5, 60)
    await enforce_rate_limit(session, security.throttle_key("pgn-ip", address), 20, 60)
    # Do not hold a DB transaction/connection while parsing untrusted chess text.
    # Bounded worker concurrency keeps import work off the ASGI event loop.
    limiter: CapacityLimiter = request.app.state.pgn_limiter
    try:
        parsed = await to_thread.run_sync(parse_pgn, data.pgn, limiter=limiter)
        canonical = parsed.export()
    except ChessError as exc:
        raise HTTPException(422, str(exc)) from exc
    async with session.begin():
        archive = ImportedGame(
            owner_id=user.id,
            headers=parsed.headers,
            initial_fen=parsed.initial_fen,
            moves=[{"uci": m.uci, "san": m.san, "fen_after": m.fen_after} for m in parsed.moves],
            result=parsed.result,
            ply_count=len(parsed.moves),
            pgn=canonical,
        )
        session.add(archive)
        await session.flush()
        return imported_replay(archive)


def imported_replay(archive: ImportedGame) -> Replay:
    return Replay(
        id=archive.id,
        source="import",
        headers=archive.headers,
        initial_fen=archive.initial_fen,
        moves=[ReplayMove.model_validate(move) for move in archive.moves],
        result=archive.result,
        termination=None,
        pgn=archive.pgn,
    )


async def load_replay(session: SessionDep, user: UserDep, source: Source, game_id: UUID) -> Replay:
    async with session.begin():
        if source == "import":
            archive = await session.scalar(
                select(ImportedGame).where(
                    ImportedGame.id == game_id,
                    ImportedGame.owner_id == user.id,
                )
            )
            if archive is None:
                raise HTTPException(404, "Game not found")
            return imported_replay(archive)
        game = await session.scalar(
            select(Game).where(
                Game.id == game_id,
                Game.status != GameStatus.ACTIVE,
                or_(Game.white_user_id == user.id, Game.black_user_id == user.id),
            )
        )
        if game is None:
            raise HTTPException(404, "Game not found")
        names: dict[UUID | None, str] = {
            player_id: name
            for player_id, name in await session.execute(
                select(User.id, User.username).where(
                    User.id.in_(
                        [value for value in (game.white_user_id, game.black_user_id) if value]
                    )
                )
            )
        }
        moves = (
            await session.scalars(
                select(Move)
                .where(
                    Move.game_id == game.id,
                )
                .order_by(Move.ply)
            )
        ).all()
        date = game.created_at.astimezone(UTC).strftime("%Y.%m.%d")
        headers = {
            "Event": "Chess Room rated game" if game.rated else "Chess Room private game",
            "Site": "Chess Room",
            "Date": date,
            "Round": "-",
            "White": names.get(game.white_user_id, "Computer"),
            "Black": names.get(game.black_user_id, "Computer"),
            "Result": game.result,
            "TimeControl": f"{game.initial_time_ms // 1000}+{game.increment_ms // 1000}"
            if game.turn_started_at is not None
            else "-",
            "Termination": "abandoned"
            if game.status == GameStatus.ABORTED
            else "time forfeit"
            if game.termination == "timeout"
            else "normal",
        }
        changes = (
            await session.scalars(
                select(RatingChange).where(
                    RatingChange.game_id == game.id,
                )
            )
        ).all()
        for change in changes:
            color = "White" if change.user_id == game.white_user_id else "Black"
            headers[f"{color}Elo"] = str(change.rating_before)
        return Replay(
            id=game.id,
            source="online",
            headers=headers,
            initial_fen=game.initial_fen,
            moves=[ReplayMove(uci=m.uci, san=m.san, fen_after=m.fen_after) for m in moves],
            result=game.result,
            termination=game.termination,
            pgn=export_pgn(headers, game.initial_fen, [m.san for m in moves]),
        )


@router.get("/{source}/{game_id}", response_model=Replay)
async def replay(source: Source, game_id: UUID, user: UserDep, session: SessionDep) -> Replay:
    return await load_replay(session, user, source, game_id)


@router.get("/{source}/{game_id}/pgn", response_class=PlainTextResponse)
async def download(
    source: Source, game_id: UUID, user: UserDep, session: SessionDep
) -> PlainTextResponse:
    record = await load_replay(session, user, source, game_id)
    return PlainTextResponse(
        record.pgn,
        media_type="application/x-chess-pgn",
        headers={
            "Content-Disposition": f'attachment; filename="chess-room-{game_id}.pgn"',
        },
    )

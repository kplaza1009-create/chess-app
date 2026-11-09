"""Stateless practice positions; never writes games, clocks, ratings or history."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import SecurityDep, SessionDep
from app.chess import START_FEN, ChessError, Game, Position
from app.services.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/api/v1/board", tags=["practice board"])


class BoardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fen: Annotated[str, Field(min_length=1, max_length=120)] = START_FEN
    move: Annotated[str, Field(pattern=r"^[a-h][1-8][a-h][1-8][qrbn]?$")] | None = None


class BoardResponse(BaseModel):
    fen: str
    board: list[str]
    turn: Literal["w", "b"]
    legal_moves: list[str]
    check: bool
    ending: str | None


async def limit_board_requests(
    request: Request, session: SessionDep, security: SecurityDep
) -> None:
    # Use the ASGI peer address, never a caller-supplied forwarding header.
    # Production proxy trust must be explicitly configured at the server.
    address = request.client.host if request.client else "unknown"
    await enforce_rate_limit(session, security.throttle_key("board", address), 120, 60)


@router.post(
    "/position", response_model=BoardResponse, dependencies=[Depends(limit_board_requests)]
)
def inspect_position(data: BoardRequest) -> BoardResponse:
    # A synchronous route keeps CPU work off FastAPI's event loop. The bounded
    # input accepts one position and at most one move, never arbitrary searches.
    try:
        position = Position.from_fen(data.fen)
        game = Game(position)
        if data.move is not None:
            game.push(data.move)
        position = game.position
        outcome = game.outcome()
        return BoardResponse(
            fen=position.fen(),
            board=list(position.board),
            turn=position.turn,
            legal_moves=[] if outcome else [move.uci() for move in position.legal_moves()],
            check=position.is_check(),
            ending=outcome.reason if outcome else None,
        )
    except ChessError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import Settings
from app.db.models import START_FEN, Game, Move, RatingChange, Speed, User, UserRating
from app.db.session import get_session
from app.main import create_app

UNIT_DATABASE_URL = "postgresql+psycopg://test:test@127.0.0.1:1/chess_test"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=SecretStr(UNIT_DATABASE_URL), app_env="test", bcrypt_rounds=4, _env_file=None
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_liveness_does_not_require_database(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("available", [True, False])
def test_readiness(settings: Settings, available: bool) -> None:
    session = AsyncMock(spec=AsyncSession)
    if not available:
        session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("private"))

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    application = create_app(settings)
    application.dependency_overrides[get_session] = override_session
    with TestClient(application) as test_client:
        response = test_client.get("/health/ready")
    assert response.status_code == (200 if available else 503)
    assert "private" not in response.text


@pytest.mark.parametrize("url", ["sqlite:///db", "https://example.com", "postgresql://"])
def test_rejects_invalid_database_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=SecretStr(url), _env_file=None)


def test_normalizes_render_url() -> None:
    settings = Settings(
        database_url=SecretStr("postgres://user:pass@localhost/chess"), _env_file=None
    )
    assert settings.database_url.get_secret_value().startswith("postgresql+psycopg://")
    assert "user:pass" not in repr(settings)


@pytest.mark.parametrize("origin", ["*", "https://example.com/path", "https://user@example.com"])
def test_rejects_invalid_cors_origins(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=SecretStr(UNIT_DATABASE_URL), cors_origins=[origin], _env_file=None)


def test_production_requires_https() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url=SecretStr(UNIT_DATABASE_URL),
            app_env="production",
            cors_origins=["http://example.com"],
            _env_file=None,
        )


@pytest.mark.parametrize(
    "field, value", [("cors_origins", []), ("jwt_issuer", ""), ("jwt_audience", "")]
)
def test_rejects_unusable_auth_configuration(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({
            "database_url": UNIT_DATABASE_URL,
            "jwt_secret": "test-secret-that-is-at-least-thirty-two-bytes",
            field: value,
        })


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL or run the Compose test service")
    database_name = make_url(database_url).database
    if not database_name or not database_name.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must point to a database ending in _test")
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection, join_transaction_mode="create_savepoint"
                ) as test_session:
                    yield test_session
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


async def make_user(session: AsyncSession) -> UUID:
    identifier = uuid4()
    await session.execute(
        insert(User).values(
            id=identifier,
            username=f"u_{identifier.hex[:20]}",
            email=f"{identifier.hex}@example.test",
            password_hash="x" * 60,
        )
    )
    return identifier


async def game_values(session: AsyncSession) -> dict[str, object]:
    return {
        "id": uuid4(),
        "kind": "multiplayer",
        "white_user_id": await make_user(session),
        "black_user_id": await make_user(session),
        "speed": "blitz",
        "initial_time_ms": 180_000,
        "white_remaining_ms": 180_000,
        "black_remaining_ms": 180_000,
    }


async def test_persists_game_defaults(session: AsyncSession) -> None:
    values = await game_values(session)
    await session.execute(insert(Game).values(**values))
    game = await session.scalar(select(Game).where(Game.id == values["id"]))
    assert game is not None
    assert game.current_fen == START_FEN
    assert game.result == "*"
    assert game.created_at.tzinfo is not None
    assert game.ply_count == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"initial_time_ms": -1},
        {"white_remaining_ms": -1},
        {"status": "finished"},
        {"kind": "computer", "black_user_id": None, "ai_level": 2, "rated": True},
        {"kind": "computer", "black_user_id": None, "ai_level": None},
        {"white_user_id": None, "black_user_id": None},
        {"result": "1-0", "termination": "checkmate"},
    ],
)
async def test_rejects_invalid_games(session: AsyncSession, changes: dict[str, object]) -> None:
    values = await game_values(session)
    values.update(changes)
    with pytest.raises(IntegrityError), session.no_autoflush:
        async with session.begin_nested():
            await session.execute(insert(Game).values(**values))


async def test_rejects_self_match(session: AsyncSession) -> None:
    values = await game_values(session)
    values["black_user_id"] = values["white_user_id"]
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(insert(Game).values(**values))


@pytest.mark.parametrize("duplicate", ["ply", "request"])
async def test_rejects_duplicate_moves(session: AsyncSession, duplicate: str) -> None:
    game = await game_values(session)
    await session.execute(insert(Game).values(**game))
    move = {
        "game_id": game["id"],
        "ply": 1,
        "client_request_id": uuid4(),
        "uci": "e2e4",
        "san": "e4",
        "fen_after": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        "white_remaining_ms": 179_000,
        "black_remaining_ms": 180_000,
    }
    await session.execute(insert(Move).values(**move))
    if duplicate == "ply":
        move["client_request_id"] = uuid4()
    else:
        move["ply"] = 2
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(insert(Move).values(**move))


async def test_rejects_duplicate_rating_change(session: AsyncSession) -> None:
    game = await game_values(session)
    game.update(
        rated=True,
        status="finished",
        result="1-0",
        termination="resignation",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ended_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await session.execute(insert(Game).values(**game))
    await session.execute(
        insert(UserRating).values(user_id=game["white_user_id"], speed=Speed.BLITZ)
    )
    change = {
        "game_id": game["id"],
        "user_id": game["white_user_id"],
        "speed": Speed.BLITZ,
        "rating_before": 1200,
        "rating_after": 1216,
    }
    await session.execute(insert(RatingChange).values(**change))
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(insert(RatingChange).values(**change))

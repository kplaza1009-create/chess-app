import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.main import create_app


@pytest.fixture
def auth_client(request: pytest.FixtureRequest) -> Iterator[TestClient]:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL or run the Compose test service")
    database = make_url(url).database
    if not database or not database.endswith("_test"):
        pytest.fail("Authentication tests require a dedicated database ending in _test")
    # HTTP requests commit independently, so reset only the dedicated test database.
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE users CASCADE"))
        connection.execute(text("TRUNCATE TABLE auth_throttles"))
    engine.dispose()
    production = getattr(request, "param", "test") == "production"
    origin = "https://chess.example.com" if production else "http://localhost:5173"
    settings = Settings(
        database_url=SecretStr(url),
        app_env="production" if production else "test",
        bcrypt_rounds=12 if production else 4,
        cors_origins=[origin],
        _env_file=None,
    )
    with TestClient(
        create_app(settings),
        headers={"Origin": origin},
        base_url="https://testserver" if production else "http://testserver",
    ) as client:
        yield client

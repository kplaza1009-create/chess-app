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
    mode = getattr(request, "param", "test")
    production = mode == "production"
    if mode in ("America/New_York", "Asia/Kathmandu"):
        # Apply to every application connection, including pooled connections after
        # service commits. A SET on the cleanup connection would not affect the app.
        url = (
            make_url(url)
            .update_query_dict({"options": f"-c timezone={mode}"})
            .render_as_string(hide_password=False)
        )
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

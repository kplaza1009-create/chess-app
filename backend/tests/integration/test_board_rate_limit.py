from datetime import timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.security import utc_now


def test_board_limit_precedes_engine_and_recovers(auth_client: TestClient) -> None:
    now = utc_now()
    with patch("app.services.rate_limit.utc_now", return_value=now):
        for _ in range(120):
            assert auth_client.post("/api/v1/board/position", json={}).status_code == 200
        with patch("app.api.board.Position.from_fen") as parse:
            response = auth_client.post(
                "/api/v1/board/position", json={}, headers={"X-Forwarded-For": "192.0.2.42"}
            )
            assert response.status_code == 429
            assert response.headers["Retry-After"] == "60"
            parse.assert_not_called()
    with patch("app.services.rate_limit.utc_now", return_value=now + timedelta(seconds=61)):
        assert auth_client.post("/api/v1/board/position", json={}).status_code == 200

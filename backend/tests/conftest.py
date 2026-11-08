import pytest


@pytest.fixture(autouse=True)
def test_signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "unit-test-key-that-is-never-used-for-production-123456")

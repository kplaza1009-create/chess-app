import pytest

from app.services.ratings import elo_delta


@pytest.mark.parametrize(
    ("white", "black", "score", "expected"),
    [
        (1200, 1200, 1.0, 16),
        (1200, 1200, 0.0, -16),
        (1200, 1200, 0.5, 0),
        (1000, 1400, 1.0, 29),
        (1400, 1000, 1.0, 3),
        (1000, 1400, 0.5, 13),
        (1, 1, 0.0, -1),
        (1, 1, 1.0, 1),
        (0, 2_000_000_000, 1.0, 32),
    ],
)
def test_elo_transfer(white: int, black: int, score: float, expected: int) -> None:
    assert elo_delta(white, black, score) == expected
    assert elo_delta(black, white, 1 - score) == -expected

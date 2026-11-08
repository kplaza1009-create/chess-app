import subprocess
import sys

import pytest


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app.chess", *arguments],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (("--perft", "0"), "Perft: 1"),
        (("--perft", "3"), "Perft: 8902"),
        (("--divide", "2"), "Total: 400"),
        (
            ("--moves", "f2f3", "e7e5", "g2g4", "d8h4"),
            "Outcome: Outcome(result='0-1', reason='checkmate')",
        ),
        (("--fen", "7k/8/8/8/8/8/8/K7 w - - 0 1"), "insufficient_material"),
    ],
)
def test_cli_success(arguments: tuple[str, ...], expected: str) -> None:
    result = run_cli(*arguments)
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize(
    "arguments",
    [
        ("--fen", "bad"),
        ("--moves", "e2e5"),
        ("--moves", "a7a8k"),
        ("--perft", "-1"),
        ("--perft", "6"),
        ("--perft", "many"),
        ("--divide", "0"),
        ("--divide", "6"),
    ],
)
def test_cli_failure_is_readable(arguments: tuple[str, ...]) -> None:
    result = run_cli(*arguments)
    assert result.returncode == 2
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr

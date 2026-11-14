# Phase 4 — comprehensive engine tests and perft diagnostics

The updated snapshot also includes the pre-Phase-5 refresh-cookie timezone
fix. See `AUTH_TIMEZONE_FIX.md` for the change, timestamp audit, upgrade steps,
and the new 64-case backend verification results.

This snapshot contains Phases 1–4. The custom engine now has 313 pytest cases,
including the original 36 acceptance checks. Case counts include parameterized
examples, such as the 64 square coordinates and color-reversed rule positions.
The routine engine run executes 304 cases; nine deeper perft cases are opt-in.

## Run on your Mac

Keep your existing project and its Python 3.12 environment while trying this
snapshot. The ZIP contains the complete `chess-app` project. Extract it into a
separate location to avoid accidentally overwriting your own changes.

Open that new `chess-app` folder in your editor. In Terminal, enter its `backend`
directory. If this new folder has no environment, create one with Python 3.12
and install the locked development dependencies.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pytest engine_tests -q
```

If Python 3.12 was installed through uv and `python3.12` is not on your PATH,
use `uv venv --python 3.12 .venv` for the first command, then activate it and
use `uv pip install -r requirements-dev.lock` to install dependencies.
The regular test result is `304 passed, 9 skipped`. Those nine skips deliberately
leave the deeper trees for the extended command.

```bash
python -m pytest engine_tests --runslow -q
```

This runs all 313 engine cases. Allow several minutes, depending on your computer.
Tests compare counts rather than elapsed time, so a slower machine can still pass.
Keep the terminal open until pytest prints its final summary.

For an existing project, you can instead merge the new `backend/app/chess`,
`backend/engine_tests`, and `backend/pyproject.toml` into your working copy and
copy the updated project instructions. Preserve your `.venv`, `.env`, and database
volume. Compare any edits you made locally before replacing a file.

If you are using Claude Code, paste this after opening the new project folder.

```text
Read PHASE4.md. Use Python 3.12 in backend/.venv, install requirements-dev.lock
if needed, and run python -m pytest engine_tests --runslow -q from backend.
Report the final result. Do not change the project source files.
```

## Test coverage

| File under backend/engine_tests | What it verifies |
| --- | --- |
| test_engine.py | Original Phase 3 acceptance regressions |
| test_perft.py | Published move-tree totals, branch totals, terminal trees, depth validation |
| test_validation.py | FEN and UCI parsing, constructors, coordinates, invalid actions, immutability |
| test_rules.py | Piece geometry, blockers, captures, pins, castling and all promotions for both colors |
| test_history.py | Draw thresholds, claims, independent games, repetition, undo, branching, replay |
| test_invariants.py | Ten seeded games, color symmetry, FEN round trips, undo and replay of each move |
| test_cli.py | Actual command-line subprocesses, successful results and readable invalid-input errors |

Reference expectations are fixed published values. Symmetry and round-trip tests
supplement those references by checking relationships between positions. They
are useful for finding inconsistencies but cannot establish correctness alone.

## Understanding perft and divide

A ply is one move by one player. Perft at depth three explores a move, every
opponent reply, and every legal continuation, then counts the final leaves.
From the starting position the depth-three result is 8,902. Draw adjudication
is deliberately excluded from perft so repetition and move-count thresholds
do not stop the move tree. Separate Game tests verify those rules.

`divide` groups the leaves by the first move. Its values must sum to perft at
the same depth. It helps localize a mismatch when one move is missing or illegal.

```bash
python -m app.chess --divide 3
python -m app.chess --moves e2e4 --divide 2
```

The first prints one line per opening move and `Total: 8902`. The second explores
the branch after e2e4 and prints `Total: 600`. If a reference test fails, pytest
reports its FEN, depth, expected count, actual count, and branch counts.
The CLI accepts divide depths 1–5. The Python API is also available.

```python
from app.chess import Position, divide

branches = divide(Position.start(), 3)
assert branches["e2e4"] == 600
assert sum(branches.values()) == 8902
```

## Reference corpus

All lower depths down to zero are included for these positions.

| Position | Deepest tested depth | Expected leaves |
| --- | --- | --- |
| Starting position | 5 | 4,865,609 |
| Kiwipete | 4 | 4,085,603 |
| Position 3 | 5 | 674,624 |
| Position 4 | 4 | 422,333 |
| Position 4 with colors and ranks reversed | 4 | 422,333 |
| Position 5 | 4 | 2,103,487 |
| Position 6 | 4 | 3,894,594 |

The complete six-field FEN strings and literal counts live in test_perft.py.
They come from the Chess Programming Wiki reference page. No chess library
is used by the engine or tests.
https://www.chessprogramming.org/Perft_Results

## Checks and limits

Routine engine tests pass with 304 passed and nine deliberate slow skips.
The extended perft run tests all published counts above. The full ordinary
backend run has 322 passed and 47 skipped. Of those skips, nine are deeper
perft cases and 38 require PostgreSQL. Four configuration tests pass.
Ruff passes and strict mypy passes for 21 application files.

The routine engine suite measured 100% statement and branch coverage in
`app/chess/engine.py` using coverage.py. The CLI subprocess tests execute
separately and were outside that coverage measurement. Coverage shows which
code was exercised; it does not prove every possible chess position is correct.
Coverage.py was used for authoring verification and is not a new project dependency.

The new cases found no engine-rule defect requiring a behavior change. Production
code changes add the divide function, its public export, and its CLI option.
Two initial test setups accidentally left the non-moving king in check; FEN
validation rejected them, and the setups were corrected before delivery.

The Phase 3 boundary remains relevant. The material detector handles its documented
insufficient-material cases, while general blocked dead positions require broader
analysis. FEN validation does not prove historical reachability. PostgreSQL,
Docker startup, and Render deployment were not revalidated in this phase.

For the complete application checks, run from the project root.

```bash
docker compose --profile test run --build --rm test
docker compose --profile test run --build --rm frontend_test
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

## Human effort estimate

Approximately 12–24 focused hours for an experienced engineer, or 25–45 hours
for a student learning test design and perft diagnostics. Phase 5, the chessboard
UI with drag-and-drop and legal-move highlighting, is next.

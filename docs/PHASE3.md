# Phase 3 — custom Python chess engine

The engine lives in `backend/app/chess`. It uses the Python standard library
and is independent of FastAPI, SQLAlchemy, accounts, and network services.
No chess library is used. Phase 4 adds the comprehensive engine test suite.

## Run it

Use Python 3.12 from the extracted `chess-app` directory.
The command-line engine itself needs no installed dependencies.

```bash
cd backend
python3 -m app.chess --perft 3
python3 -m app.chess --moves e2e4 e7e5 g1f3
python3 -m app.chess --moves f2f3 e7e5 g2g4 d8h4
```

The first command reports 8,902 paths. The last reports checkmate and `0-1`.
Use `--fen 'six-field FEN'` to load a position. `--perft` accepts depths 0–5
because the number of paths grows rapidly. Invalid input exits with code 2
and a readable error. The Python `perft` function accepts nonnegative depths
and is intended for trusted local computation.

For the acceptance tests and static checks, still inside `backend`,

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pytest engine_tests -q
python -m ruff check app alembic tests engine_tests
python -m mypy
```

On Windows, activate with `.venv\Scripts\activate`.
The normal `pytest` configuration now includes `engine_tests` automatically.
Existing full-stack commands remain available from the project root.

```bash
python3 scripts/configure_env.py
docker compose up --build -d
docker compose --profile test run --build --rm test
docker compose --profile test run --build --rm frontend_test
```

## Board and move generation

`Position` is an immutable dataclass. Its 64-square tuple starts with `a1` at
index 0, `b1` at 1, and ends with `h8` at 63. Uppercase letters represent white
pieces, lowercase letters represent black pieces, and `.` marks an empty square.
A position also stores the side to move, castling rights, en passant target,
halfmove clock, and fullmove number. Piece locations alone cannot determine
all legal moves or draws.

Moves use UCI coordinates such as `e2e4` and `a7a8n`. Castling uses the king's
move, such as `e1g1`. Promotion must explicitly select queen, rook, bishop,
or knight. FEN import/export represents a position. FEN does not contain the
history needed to establish repetition.

The generator first follows piece movement patterns to produce candidate
moves. Sliding pieces walk a direction until blocked. Pawns have separate
forward movement and capture rules. Each candidate produces a new position,
and the engine rejects it if the moving player's king is attacked afterward.
The old position remains available unchanged.

Attack detection is geometric and includes attacks by pinned pieces. Calling
legal-move generation to determine attacks would introduce circular logic and
would mishandle king safety. Castling additionally checks the king's original,
transit, and final squares. En passant removes the captured pawn before checking
the king, which catches both vertical and horizontal discovered attacks.

The immutable representation favors clarity and safe branching for the future
minimax search. It allocates a new board per candidate. Measure search performance
in the AI phase before adding a mutable make/unmake optimization.

## Python API

```python
from app.chess import ChessError, Game, Position, perft

game = Game()
try:
    game.push("e2e4")
    game.push("e7e5")
    print(game.position.fen())
    print([move.uci() for move in game.position.legal_moves()])
    print(game.position.is_check())
    print(game.outcome())
    print(game.claimable_draws())
    game.pop()
except ChessError as error:
    print(error)

assert perft(Position.start(), 2) == 400
```

`Position.play` validates and applies a legal move without adjudicating game
termination. Use `Game.push` for actual games because it rejects moves after an
outcome. `Game.pop` supports analysis and reverses board state, rights, counters,
and repetition history. It clears a claimed result when a move is undone.
Failed moves and claims leave game state unchanged.

`game.moves` and `game.positions` expose immutable snapshots. Restore a game by
loading its initial FEN and replaying its stored moves through `Game.push`.
Starting a `Game` from the latest FEN begins a new repetition history. A stored
claimed outcome must also be restored explicitly by the later persistence layer.
Do not persist only the latest FEN when repetition claims matter.

The later server must serialize access to each mutable `Game`, authenticate the
acting player, enforce whose turn it is, and authorize any undo functionality.
The private `_apply` method assumes generated/validated moves. External callers
should use `Position.play` or `Game.push`. Import external positions through
`Position.from_fen`; `Game` also validates a supplied initial `Position`.

## Outcomes and claims

`Game.outcome()` returns `None` during play or an `Outcome(result, reason)`.
Results are `1-0`, `0-1`, or `1/2-1/2`.

| Condition | Behavior |
| --- | --- |
| Checkmate | Automatic win for the other side |
| Stalemate | Automatic draw |
| Recognized insufficient material | Automatic draw |
| Third occurrence | Claim available to the player to move |
| 100 halfmoves without pawn movement or capture | 50-move claim available |
| Fifth occurrence | Automatic draw |
| 150 halfmoves without pawn movement or capture | Automatic 75-move draw |

Checkmate takes precedence over the automatic 75-move draw. A pawn move or any
capture, including en passant, resets the halfmove clock.

`game.claimable_draws()` lists current valid claims. Supplying an intended legal
move, such as `game.claimable_draws("f6g8")`, evaluates whether that move would
establish a claim. `game.claim_draw("threefold_repetition", "f6g8")` records a
valid claim and ends the game. The intended move is examined without being played.
An invalid claim raises `ChessError`. Physical-board touch-move and arbiter
penalties are outside the online engine API.

Repetition compares piece placement, turn, castling rights, and an en passant
target only when a legal en passant capture exists. Move numbers and the halfmove
clock do not distinguish otherwise identical positions.

Insufficient material recognizes kings alone, king and one bishop or knight
against king, and bishop-only positions with every bishop on the same square
color. Two knights against a bare king are not automatically drawn because a
cooperative mating sequence can exist. General blocked dead positions are not
recognized by this material detector. FEN validation checks structure and key
position invariants but does not prove reachability from the starting position.

Rule reference — FIDE Laws of Chess, articles 3, 5, 9.2, 9.3, and 9.6.
https://handbook.fide.com/chapter/E012023

## What perft checks

Perft counts every legal move sequence of exactly a chosen number of plies.
A ply is one player's move. Depth 0 is one leaf, depth 1 from the initial
position is 20, and depth 2 is 400. A mismatch usually exposes a missing or
extra move in a branch. Perft deliberately ignores repetition and move-count
draws, so it tests move generation separately from game adjudication.

These deeper checks were run during implementation against published counts.
The focused acceptance suite retains start depth 3 and Kiwipete depth 2.
Phase 4 will organize the wider reference corpus and per-move diagnostics.

| Position | Depth | Expected and actual leaves |
| --- | --- | --- |
| Initial | 4 | 197,281 |
| Kiwipete | 3 | 97,862 |
| CPW position 3 | 4 | 43,238 |
| CPW position 4 | 3 | 9,467 |
| CPW position 5 | 3 | 62,379 |

Reference positions and counts — https://www.chessprogramming.org/Perft_Results

## Verification and boundaries

The 36 engine acceptance cases pass. They cover both colors, checkmate,
stalemate, castling through attack, rook-rights loss, underpromotion, pinned
en passant, removing a checking pawn en passant, repetition identity and
claims, move-count draws, mate precedence, invalid inputs, atomic failures,
and seeded legal play with FEN round trips and complete undo.
Ruff passes for all backend application, migration, and test files. Strict mypy
passes for 21 application source files. CLI start-position perft and Fool's Mate
were executed successfully. Four configuration-script tests also pass.

Database-dependent tests require TEST_DATABASE_URL or Docker Compose. They were
not revalidated against PostgreSQL in Phase 3. The prior Phase 2 evidence and its
limits remain recorded in PHASE2.md. Frontend code was not modified in Phase 3.

The engine is locally usable. UI board integration starts in Phase 5 and game
server integration in Phase 6. Phase 4 is the next planned unit of work.

## Human effort estimate

Approximately 20–40 focused hours for an experienced engineer implementing and
checking this engine from scratch, or 40–80 hours for a student learning move
generation along the way. The comprehensive Phase 4 suite is additional work.

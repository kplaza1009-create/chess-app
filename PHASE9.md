# Phase 9 — game history, replay, and PGN

Choose **History** after signing in. Completed and aborted online games appear
automatically. Choose **Replay**, or choose **Import PGN** to paste a game or
select a `.pgn` file. `examples/fools-mate.pgn` is a small file to try.

Replay supports First, Back, Next, Last, direct move selection, board flipping,
and a PGN download. Left/Right and Home/End work on replay controls. Replay
never changes the original game or sends WebSocket moves. A completed live
game also links directly to its replay.

## Upgrade on your Mac

1. From the old `chess-app` folder, stop the old services with
   `docker compose down`. Keep the database volume.
2. Extract the Phase 9 archive into a separate folder. Copy your existing
   `.env` into its `chess-app` folder. Preserve any local edits separately.
3. In Terminal, type `cd `, drag that new `chess-app` folder into Terminal,
   and press Return. Run these commands there:

```bash
docker compose up --build -d
docker compose ps
docker compose exec api alembic current
```

The migration service applies `0005`. It adds `imported_games`; existing
accounts, games, moves, and ratings are preserved. Use the same Compose project
name as before so Compose uses the existing database volume. If you previously
used `-p`, pass the same value on the new commands. Do not use `down -v`.

Open http://localhost:5173/history and sign in. For a completely fresh install,
run `python3 scripts/configure_env.py` before starting Compose. Existing users
should preserve their existing environment rather than generate new credentials.

## Data and permissions

Online history reads the existing game and ordered move rows. Each row already
stores canonical SAN and a complete post-move FEN. Replay uses those snapshots,
including the starting position at ply zero. No live-game lock, clock worker,
or repetition computation is needed when stepping through an archived game.
The browser decodes FEN only to draw pieces; it does not generate legal moves.

Online records remain visible only to their participants, and only once they
are finished or aborted. The archive is not a spectator route for active games.
History has twenty entries per page, filtered by online games or imports, ordered
by creation time with an ID tie-breaker. Pagination is capped at 500 pages per
filter. New records can shift offset-based pages while browsing.

Imported games live in a separate table owned by the importing user. They do
not create accounts for names in a PGN, create multiplayer games, settle Elo,
or modify rating statistics. Import results and Elo tags are untrusted metadata.
Completed online exports use the historical pre-game Elo from the settlement
ledger, rather than a player's subsequently changed rating. Dates in online
PGN exports are explicitly normalized to UTC. Legacy untimed games export an
untimed `TimeControl` value.

## PGN support and boundaries

The parser validates every main-line SAN move through our custom engine.
An invalid move reports its ply and token. Input accepts move numbers with or
without following spaces, zero-spelled castling, omitted check/mate suffixes,
and promotions without `=`. A supplied check or mate suffix must be correct;
ambiguous moves and incorrect captures remain errors. Output uses canonical SAN.

Headers, UTF-8 names, escaped quotes/backslashes, a UTF-8 BOM, brace/semicolon
comments, percent escape lines, numeric annotation glyphs, and nested
variations are accepted. Only the main line and headers are saved. Comments,
annotation glyphs and variations are discarded, as the import form explains.
This is a game replay feature, not a lossless analysis-tree editor.

Custom starts use FEN/SetUp tags, including Black to move and non-one move
numbers. Exports supply the seven standard roster headers and SetUp/FEN when
needed. Header and movetext results must agree; a stated final result cannot
contradict an automatic engine ending. `*` represents an unknown/unfinished
result. Results such as resignation or agreement need not be a board checkmate.
Imports preserve the engine's existing claim API rather than applying the
online server's automatic threefold/50-move policy to an outside game.

Import limits: one standard-chess game, 64 KiB of UTF-8 text, 1,000 plies,
64 tags, 256 characters per tag value, 32 variation levels, and FEN counters
at most 1,000,000. Other variants, multiple-game databases, LAN/UCI movetext,
and malformed structures are rejected. Five parse attempts per user per
minute and twenty per peer IP per minute use the existing shared PostgreSQL
limiter. Parsing runs in a worker thread, with two imports at a time per API
process, outside a database transaction. Only the import route permits a
larger, bounded JSON envelope; authentication retains its 16 KiB limit.

PGN reference used during implementation:
https://www.saremba.de/chessgml/standards/pgn/pgn-complete.htm

## API

All endpoints require an access token in the Authorization header.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/history?page=1&source=all` | Personal history (`all`, `online`, or `import`) |
| POST | `/api/v1/history/import` | Validate and save `{"pgn":"1. e4 e5 *"}` |
| GET | `/api/v1/history/online/{id}` | Completed online game's replay and canonical PGN |
| GET | `/api/v1/history/import/{id}` | Owner's imported replay and canonical PGN |
| GET | `/api/v1/history/{source}/{id}/pgn` | PGN attachment; `source` is `online` or `import` |

The UI downloads the already-authorized replay's PGN using a Blob URL. Tokens
never appear in download links. Private responses retain `Cache-Control: no-store`.

## Run tests

From `chess-app`:

```bash
docker compose --profile test run --build --rm test
docker compose --profile test run --build --rm frontend_test
docker compose exec api ruff check --no-cache app alembic tests engine_tests scripts
docker compose exec api mypy --cache-dir=/tmp/chess-mypy
docker compose exec api alembic check
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

With Python 3.12 and `backend/requirements-dev.lock` installed, the focused
engine tests can also run without PostgreSQL:

```bash
cd backend
python -m pytest engine_tests/test_notation.py engine_tests/test_pgn.py -q
```

The included network smoke requires a running development server and creates
two disposable accounts and one game. Run from `backend`:

```bash
python scripts/history_smoke.py
```

For the browser check, keep the app running and use a second Terminal window.
From `chess-app/frontend`:

```bash
npm ci
npx playwright install chromium
node scripts/history-smoke.mjs
```

This checks invalid input, file import, persistence, every replay control,
keyboard shortcuts, flipping, PGN download, widths from 320 to 1440 pixels,
controls above the fold in windows at least 720px high, and dark mode. It also
checks usable board/control dimensions in short portrait and landscape windows,
where vertical scrolling is allowed. It creates a disposable local account.

## Checks actually executed

PostgreSQL verification uses version 16.11 with
`America/New_York`, not a UTC-only substitute.

- Backend suite: 521 passed, nine opt-in deeper perft cases skipped.
- Frontend suite: 73 passed. TypeScript and Vite production build passed.
- Ruff, strict mypy, four environment-helper tests and Alembic drift check passed.
- Fresh migrations through 0005 passed. Downgrade to 0004 and re-upgrade
  preserved existing users, games, moves, ratings, and rating ledger rows.
  Downgrading intentionally removes PGN imports; normal upgrades preserve them.
- Real Uvicorn HTTP/WebSocket smokes passed for existing private rooms,
  two-process rated matchmaking, and online-history/export/import/privacy.
- Existing 30-move opponent-delivery acceptance test passed across two API
  processes: 21.1 ms mean, 25.9 ms maximum, against the unchanged 100 ms limit.
- A seeded 160-ply SAN parsing benchmark, median of three runs, measured
  3.008 s using the previous parser and 0.055 s with candidate filtering.
  A complete validated import of that PGN took 0.214 s. These are local
  authoring measurements, not production throughput guarantees.

A separate source reviewer found and rechecked four corrections: a 240px
minimum replay board in short viewports; history filter/page preservation when
opening and returning from replay; once-only focus on the asynchronously loaded
replay heading; and a Back control whose accessible name includes its visible
label. All four were scored resolved in the source verdict. No browser visual
pass is implied by that review.

Docker/Compose and Nginx runtime were not executed here. Chromium launch failed
because the environment blocks its required Unix socket. The browser smoke
was syntax-checked but was not run successfully. Consequently, visual fit,
contrast and actual browser download behavior remain unverified here. The
existing board/game browser scripts are preserved for local regression checks.

## Next phase and effort estimate

Phase 10 is the minimax opponent with alpha-beta pruning and three difficulty
levels. It is not implemented in this snapshot. AI search must run in a separate
process so it cannot block the WebSocket event loop.

Estimated human effort for Phase 9: roughly 12–24 focused hours for an experienced
full-stack engineer, or 25–45 hours for a student learning PGN and replay design.
This is an estimate, not elapsed authoring time.

# Phase 6 — durable multiplayer rooms

This archive includes Phases 1–6 and the corrected Phase 5 board. It adds
participant-only WebSocket games, synchronization, reconnect, SAN, and automatic
threefold/50-move draws. Games are unrated and untimed in this phase.
Clocks are Phase 7; matchmaking and ELO are Phase 8. Spectators and invitations
with acceptance UI are not implemented here. A room creator names a registered
opponent and shares the room URL; creation does not notify the opponent.

## Run on your Mac

Stop the previous Compose app from its folder with `docker compose down`.
Keep the existing database volume. Extract this ZIP into a new location and
copy your existing `.env` into the new `chess-app` root to preserve credentials.
If you do not have an environment file, run `python3 scripts/configure_env.py`.
The database schema remains at migration 0002; no destructive reset is needed.

From the NEW chess-app root (type `cd `, drag its folder into Terminal, Return):

```bash
docker compose up --build --force-recreate -d
docker compose ps
```

Open http://localhost:5173/games. Create two accounts in separate browser
profiles or Safari and Chrome. Ordinary tabs share the same login cookie and
are not two independent players. Sign in as White, enter Black's username,
and create a game. Copy the resulting URL into the other browser. The black
board is flipped automatically. Make moves from the correct browser, refresh,
and confirm the move list survives. Only these two users can view the room.
The localhost link works on this Mac only; sharing with another computer needs
an accessible deployment and configured origins, which is later deployment work.

## Run the checks

From the project root:

```bash
docker compose --profile test run --build --rm test
docker compose --profile test run --build --rm frontend_test
docker compose exec api ruff check app alembic tests engine_tests scripts
docker compose exec api mypy
```

With the local application running, test actual WebSockets (creates two test
accounts and a game in the development database):

```bash
docker compose exec api python scripts/wire_smoke.py
```

Real Chromium checks, from the root:

```bash
cd frontend
npm ci
npx playwright install chromium
node scripts/board-smoke.mjs
node scripts/game-smoke.mjs
```

The game script creates two disposable test accounts, plays from separate browser
contexts, reloads, simulates going offline, reconnects, and checks narrow widths.
Allow up to a minute for heartbeat-based offline detection. Do not run smoke
account creation against a production database. Repeated runs may reach the
registration limit of 10/hour/IP; wait for the limit rather than removing it.

The game page also listens for the browser's `offline` event and immediately
marks the socket as reconnecting. This matters because an existing localhost
WebSocket can otherwise remain open in Chromium after network emulation is
enabled, delaying both user feedback and deterministic browser testing.

## What the WebSocket does

HTTP starts the room. The browser then opens a persistent WebSocket and sends
its access credential in the first frame. Browser WebSocket constructors cannot
set a normal Authorization header, so an authenticated, no-store HTTP endpoint
provides the existing short-lived credential. It never appears in the URL.
The endpoint name `ticket` does not imply a one-use credential: it is the current
access JWT, with the existing expiry and refresh-family revocation rules.

The server checks Origin, JWT expiry, active user, refresh-family revocation,
and room membership. It rechecks identity during synchronization and immediately
before writes. A revoked or expired session closes with code 4401; the frontend
obtains a fresh credential through the existing AuthSession and reconnects.
Authorization/membership errors from the HTTP endpoint stop automatic retries.

Each move contains UCI, a UUID request ID, and the position version. The server
locks the game row, checks whose turn it is, replays stored moves, validates the
new move with the custom engine, generates SAN, and commits the move, resulting
FEN, version and outcome together. The browser shows only confirmed positions.
Retries of an already stored request ID and identical move by the same player
are idempotent. Reusing an ID for a different move/player is rejected.

A lost acknowledgement does not tell the client whether a move committed.
The frontend reconnects and reads a complete snapshot instead of blindly sending
the move again. Version numbers prevent an older snapshot from replacing newer
state. PostgreSQL is the durable source; process memory is not game storage.
Refresh/reconnect rebuilds the same board and SAN move list.

Each connection checks the committed version every 500ms, then sends snapshots
only when it changes. This supports separate workers without a broker, but adds
up to roughly 500ms of delivery latency and two polling cycles per socket per
second. Use LISTEN/NOTIFY or a broker when measured load justifies it. This is
an intentional initial-scale tradeoff, not a claim of high-scale performance.
Row locks keep game and move rows consistent, and are released before socket IO.
CPU rule evaluation runs in a worker thread. AI remains separate-process work
for Phase 10; long-game replay is linear in move count and needs profiling.

## Protocol

Connect to `/api/v1/games/{uuid}/ws`, then send:

```json
{"type":"auth","token":"YOUR_ACCESS_TOKEN"}
```

Move example (use a fresh random UUID):

```json
{"type":"move","version":0,"request_id":"38a98108-a632-4446-816b-cc6bd08c1f86","uci":"e2e4"}
```

The server sends `state` (id, version, color, result, position, moves), `error`
(message), and `heartbeat`. Heartbeats arrive every 15 seconds. A client detects
silence after 45 seconds and reconnects with exponential delay plus jitter,
capped at about 15.5 seconds. A pending move has a 10-second acknowledgement
deadline. Error rejection triggers a fresh state snapshot.

## SAN and endings

`from app.chess import san, parse_san` exposes canonical SAN. Generation uses
legal competitors for disambiguation, so pinned pieces do not create false
ambiguity. It handles file/rank/both disambiguation, captures including en
passant, all promotions, castles, and +/#. Parsing is strict; zero-based
castling spelling is also accepted. PGN tokenization, comments, variations and
annotations remain Phase 9; the SAN parser expects one cleaned move token.

Server termination mapping preserves existing DB constraints:

| Engine reason | Stored termination |
| --- | --- |
| threefold_repetition / fivefold_repetition | repetition |
| fifty_moves | fifty_move |
| seventy_five_moves | seventy_five_move |
| checkmate / stalemate / insufficient_material | unchanged |

After an accepted move, an automatic outcome takes precedence. Otherwise the
server immediately claims an available threefold/50-move draw, as requested.
The engine's claim API is unchanged. Every mapped engine ending has a real
PostgreSQL persistence test. These rooms never update ratings.

## Resource controls and deployment boundaries

- Shared PostgreSQL limits: room creation 10/hour/user, credential retrieval
  60/minute/user, WebSocket openings 60/minute/peer IP, messages 120/minute/user.
- Four authenticated sockets/user/worker and 128 total sockets/worker, including
  pending authentication. Multi-worker deployment multiplies these local caps.
- Five-second authentication and send deadlines. Text-only application frames;
  auth frame <=5000 characters and move frame <=1024 characters.
- Uvicorn transport maximum 8192 bytes and queue maximum 8 frames in both
  Compose and Docker startup. HTTP API POST bodies limited to 16 KiB/10 seconds.
- Practice still uses 120 requests/minute/peer IP. Caller-supplied forwarding
  headers are ignored by default via `--no-proxy-headers`.
- Configure trusted proxy addresses and ingress-wide connection/rate limits
  before exposing this publicly. Behind the bundled Nginx proxy, peer-based
  limits conservatively share the proxy IP until that deployment work is done.
  This snapshot is ready for local evaluation, not an approved public deployment.
- Nginx now forwards WebSocket upgrades; its production container was not run
  here. TLS/origin/proxy deployment remains Phase 16.

## Checks actually executed

- Full backend with Python 3.12 and real PostgreSQL 17.11, session timezone
  America/New_York: **406 passed, 9 deliberate slow perft skips**.
- **45 frontend tests passed**, including new socket auth/move/reconnect tests.
- Strict TypeScript/Vite build, Ruff and mypy (25 application files): passed.
- Alembic upgrade and drift check: passed, no new migration required.
- Real Uvicorn HTTP/WebSocket network smoke: passed account creation, two
  simultaneous sockets, move synchronization, Fool's Mate SAN/outcome and reconnect.
- Chromium game smoke attempted: browser launch failed with socket permission
  denial before any page navigation. No Phase 6 browser-pass claim is made.
- Phase 5 browser success is user-reported from the corrected ZIP. This phase
  changes navigation and adds a game page, so rerun both browser scripts locally.
- Docker/Compose builds, Nginx runtime, deep perft, coverage, multi-worker load,
  and long-duration network interruption were not executed in this environment.

The shipped game browser script and manual two-browser steps are the remaining
local acceptance checks. Review resource limits before production exposure.
Phase 7 is next after authorization. Estimated human effort for this phase:
roughly 4–7 focused working days including concurrency/reconnect testing.

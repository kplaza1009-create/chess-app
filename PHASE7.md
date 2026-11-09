# Phase 7 — persistent chess clocks

This snapshot contains Phases 1–7, including the Phase 6 browser-offline handler.
New rooms offer 1+0, 3+2, 5+0, 10+0 and 15+10. Games remain unrated.
The review patch gives White 30 seconds for the first move, then Black 30 seconds
for theirs. Both clocks stay paused during these opening moves; increments begin
on subsequent moves. Missing a deadline aborts the game, without a win or loss.
Existing games retain their prior clock policy. Migration 0003 adds the first-move
deadline and prevents aborted games from being rated. Never reset the database.

## Upgrade on your Mac

From the OLD chess-app folder, stop the app:

```bash
docker compose down
```

Extract the new ZIP. Copy the old hidden `.env` into the NEW inner chess-app
folder. Finder's Command+Shift+period shows hidden files. Preserve this file,
especially if you changed database passwords. Do not run `down -v`.

In Terminal type `cd ` (with a trailing space), drag the NEW inner chess-app
folder into Terminal and press Return. Do not put quotes around a path inserted
by dragging: Terminal already escapes its spaces. Confirm with `pwd` and `ls`.
The root contains `compose.yaml`, `backend`, `frontend`, and this document.
Only for a fresh installation without existing credentials, use
`python3 scripts/configure_env.py`.

```bash
docker compose up --build --force-recreate -d
docker compose ps
```

Open http://localhost:5173/games. Use Safari and Chrome with separate accounts.
Choose 3+2, create a room with the other account's username, and open the same
room URL in the other browser. Make the two opening moves before their deadlines.
White's time then counts down; after its next legal move it receives two seconds
and Black starts counting down. Refreshing must
preserve the position and elapsed time. Disconnecting does not pause clocks.
An existing untimed room will not acquire clocks: create a new room to test.

## Verification commands

From the new project root, with Docker running:

```bash
docker compose --profile test run --build --rm test
docker compose --profile test run --build --rm frontend_test
docker compose exec api ruff check app alembic tests engine_tests scripts
docker compose exec api mypy
docker compose exec api alembic check
docker compose exec api python scripts/wire_smoke.py
```

The last command creates disposable accounts in the development database.
Then test Chromium from the NEW frontend folder:

```bash
cd frontend
npm ci
npx playwright install chromium
node scripts/board-smoke.mjs
node scripts/game-smoke.mjs
```

The game smoke checks time-control selection, both clocks, synchronized moves,
reload, offline reconnect, and responsive widths. Repeated runs may hit the
10 registrations/hour/IP limit; wait for that limit instead of disabling it.
To manually test timeout, create a 1+0 room, play e4 and e5, and let White's minute expire.
Both players should receive Black wins — timeout, and moves should be disabled.

## Why the clocks work this way

A clock is a stored balance plus the timestamp when its turn began. The server
subtracts elapsed time when reading it; it does not write the database every
millisecond. PostgreSQL's clock_timestamp() supplies a common wall clock across
API processes. Aware datetime subtraction works in non-UTC database sessions.
The database host must maintain a synchronized system clock; large host-clock
jumps can affect deadlines. Negative elapsed time is clamped at zero.

The move transaction locks the game, checks the deadline, validates the move,
deducts time and adds the increment exactly once. Duplicate request IDs do not
earn another increment. The opponent's clock starts after validation finishes.
The admission time is sampled after acquiring the game lock: no client timestamp
or network-lag compensation is trusted. A late request cannot rescue an expired
clock. Invalid moves leave the stored clock unchanged, so elapsed time continues.

A lifespan worker checks expired games every half-second, including games with
no connected players. It processes up to 100 rows per batch with SKIP LOCKED;
multiple workers cannot finish the same game twice. Restarted workers settle
overdue games from persisted timestamps. Service downtime counts as elapsed
time. Timeouts and moves use the same row lock and increment the game version.

Snapshots carry remaining balances, time control, first-move deadline, opponent
name and running state. Commits wake local sockets immediately and publish a
transactional PostgreSQL NOTIFY for other API processes. Each process maintains
one dedicated LISTEN connection with reconnect and resync. Notifications contain
only game IDs; authorized readers load the committed state. Events coalesce,
so slow clients cannot create an unbounded broadcast queue. A five-second poll
is a recovery fallback, with shared snapshot locks rather than exclusive locks.
All game endings use database time. Snapshots also refresh every 15 seconds.
The browser estimates
elapsed time with performance.now(), not the user's adjustable wall clock.
Network latency can make the displayed estimate optimistic; only the server
decides the result. Local zero is not a result. Clocks use timer semantics with
live announcements disabled to avoid reading every tick aloud.

## Timeout draw policy and limits

The material check is one-sided: it examines the potential winner's pieces and
the opponent's possible blockers, not just whether both sides lack material.
A bare king cannot win on time. A lone minor against a bare king cannot win;
two knights can cooperatively mate and count as mating material. Bishop square
colors and opposing material are considered.

This is a material-based approximation, not a complete solver for all positions
where checkmate is unreachable. Locked pawn structures and forced continuations
can require position-specific analysis. Do not claim full FIDE dead-position
adjudication. FIDE article 6.9 describes the stronger possible-legal-sequence
standard: https://handbook.fide.com/chapter/e012023 .

Access-token expiry is checked at the authenticated handshake. Existing sockets
retain that verified identity and check the user's active status, family revocation
and refresh-session expiry before every move and at least every five seconds.
Expired credentials cannot open new sockets. Logout/revocation still disconnects
established sockets; a five-minute JWT expiry alone does not interrupt a game.

There is no ready/accept handshake, lag compensation, outage refund, or dedicated
clock service. The half-second worker scans active games; add a deadline index
or scheduler after profiling larger workloads. Matchmaking and ELO are Phase 8.

## Verification record

Baseline before review: 421 passed, 9 deeper perft tests skipped. This includes the added
timeout/move race, increment idempotence, persistence and disconnected expiry.
Actual HTTP and WebSocket smoke passed: two users, synchronized moves, SAN
checkmate and reconnect.
Frontend: 48 tests passed; strict TypeScript and Vite production build passed.
Ruff and strict mypy passed. Alembic upgrade and schema check passed on a fresh
PostgreSQL 17 database using America/New_York. No schema drift was detected.

Chromium was attempted but could not launch: socket creation was denied by the
execution environment. Downloading Playwright's bundled browser also failed.
The browser smoke, visual appearance, Docker/Nginx runtime, multiworker load,
long outages, deep perft and coverage were not verified in this phase.

The independent reviewer subsequently passed both browser smokes, the layout
assertions and a real two-browser timeout on the baseline. See REVIEW_FIXES.md
for the latest patch's separate verification results. Repeat browser acceptance
after upgrading to this patch.

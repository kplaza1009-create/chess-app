# Phase 6–7 independent-review patch

Implemented immediate local game wakeups and transactional PostgreSQL LISTEN/NOTIFY
across workers. A five-second safety poll remains for missed notifications and
session revocation; it no longer takes exclusive game locks. All snapshot sends
remain bounded by timeouts. The listener reconnects and wakes subscribed games on
recovery. PostgreSQL must support a dedicated session connection for LISTEN (do
not route that connection through transaction-mode pooling).

New rooms have 30 seconds for each side's opening move. Clocks start after both
opening moves and increments begin with subsequent moves. Missing a deadline
aborts, sets rated=false and leaves result='*'. Migration 0003 enforces that an
aborted game cannot be marked rated. Tests verify no rating-change rows are made.
Phase 8's rating service must additionally require status=finished AND rated=true
before writing ratings; that future service does not exist yet.

JWT signature, type, audience and expiry are checked at handshake. Sockets retain
verified claims, but query user activity, session revocation and session expiry
before moves and every five seconds while idle. A new socket still requires an
unexpired token. This removes periodic expiry interruptions without making logout
or refresh-family revocation ineffective. All terminal game timestamps use DB time.

The board displays the registered opponent's username and a separate first-move
countdown. Aborts have an explicit status, not a draw or a normal turn prompt.

The latency follow-up brings the engine-history cache forward from Phase 15.
Each Database instance owns a worker-local LRU cache limited to 128 games. Before
reuse, it checks game ID, database version, initial FEN and the complete stored
move prefix. It replays only the committed suffix on a match and reconstructs
on mismatch or eviction. Database moves remain authoritative across workers.
Only the history read from the database is cached; applying the proposed move
uses an independent copy. Failed writes cannot expose an uncommitted position.
Copies preserve repetition counters and draw claims without sharing mutable
lists or counters. Cache operations are protected across worker threads.

## Actual checks

- Full backend suite on fresh PostgreSQL 17 / America/New_York: 437 passed,
  9 opt-in deep perft tests skipped (46.68 seconds). Includes a forced database
  rollback followed by reconnect and a different legal move, cache eviction,
  prefix catch-up, version/history mismatches, concurrent copies, and repetition.
- Frontend: 49 passed; TypeScript/Vite build passed.
- Ruff and strict mypy: passed. Alembic upgrade 0001 through 0003 and check:
  passed, no drift.
- Same-worker real WebSockets, two separate 30-move games: mean 34.6 ms / maximum
  87.8 ms, and mean 32.4 ms / maximum 46.6 ms. Both passed the unchanged strict
  maximum <100 ms assertion, including engine processing and database time.
- Two real Uvicorn processes, 30 moves over real WebSockets: opponent delivery
  mean 33.4 ms / maximum 41.7 ms, also passed. Both sockets remained usable after
  30-second JWT expiry and accepted another move without reconnecting.
- HTTP/WebSocket wire smoke passed: authentication, two players, synchronized
  moves, checkmate SAN, and reconnect.
- Before caching, same-worker runs failed at maxima of 130.0 ms and 111.0 ms.
  Those historical failures prompted this fix. The acceptance check now passes
  locally; these measurements are not a latency guarantee under arbitrary load.
- Browser smoke and visual acceptance of this patch were not run here. The
  reviewer verified the preceding baseline, not these new UI changes.
- Docker/Nginx runtime and deep perft were not rerun in this follow-up.

Reproduce timing with two development API instances on ports 8000 and 8001,
both using the same database and ACCESS_TOKEN_SECONDS=30:

```bash
cd backend
SMOKE_PEER_URL=http://127.0.0.1:8001 SMOKE_WAIT_EXPIRY=1 python scripts/delivery_smoke.py
python scripts/delivery_smoke.py
```

This creates test users/games; only run against a development database.
The script retains a strict maximum of 100ms; it may fail on a busy machine.
Do not change the threshold to conceal a regression.

## Later-phase work accepted from review

Phase 15: the bounded engine cache is implemented in this patch because replay
was affecting latency acceptance. Reprofile long games and concurrent workloads;
move-row reads and history copies still grow with game length, and cold/evicted
games still require replay. No broad load-test or throughput claim is made.

Phase 9: parse_san currently renders every candidate (~29ms/move, ~4.6s for an
80-move import). Filter by destination/piece first; accept omitted +/# and omitted
'=' in promotions. Add ambiguous/illegal SAN tests before relaxing parsing.

Upgrade with the existing .env and database volume. From the new chess-app root:

```bash
docker compose up --build --force-recreate -d
docker compose --profile test run --build --rm test
docker compose --profile test run --build --rm frontend_test
cd frontend
npm ci
npx playwright install chromium
node scripts/board-smoke.mjs
node scripts/game-smoke.mjs
```

Do not advance to rated release until latency and browser acceptance are checked
on the target environment. Phase 8 has not been implemented.

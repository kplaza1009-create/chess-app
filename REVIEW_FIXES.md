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

## Actual checks

- Full backend suite on fresh PostgreSQL 17 / America/New_York: 425 passed,
  9 deep perft skips. An additional exact-deadline unit test was then added;
  the focused clock suite passed all 12 tests (426 total cases now expected).
- Frontend: 49 passed; TypeScript/Vite build passed.
- Ruff and strict mypy: passed. Alembic upgrade 0001 through 0003 and check:
  passed, no drift.
- Two real Uvicorn processes, 30 moves over real WebSockets: opponent delivery
  mean 44.5 ms, maximum 77.3 ms. Both sockets remained usable after 30-second
  JWT expiry and accepted another move without reconnecting.
- Same-process timing had outliers: mean 59.9 ms / max 130.0 ms while frontend
  tests also ran; isolated rerun mean 54.0 ms / max 111.0 ms. The strict max<100ms
  assertion therefore FAILED for those runs. Immediate notification removes the
  half-second polling delay, but a hard end-to-end latency bound is not established
  on this shared host. The script includes engine processing and database time.
- Browser smoke and visual acceptance of this patch were not run here. The
  reviewer verified the preceding baseline, not these new UI changes.

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

Phase 15: replay in play() measured 18ms at ply 20, 121ms at ply 160 and 212ms
at ply 300. Cache EngineGame by game ID with a committed version check; rebuild
on mismatch/restart and never expose uncommitted state. This patch does not
implement that cache. Long-game CPU time can still dominate move latency.

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

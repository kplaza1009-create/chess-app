# Codex handoff — Phase 7 implemented, browser acceptance pending

Read PHASE7.md first. Persistent clocks use database timestamps, row locks,
increments, a background expiration worker and two browser clock displays.
Read REVIEW_FIXES.md for migration 0003, push delivery, first-move aborts,
socket authentication, and the bounded engine cache brought forward to resolve
the strict <100 ms local delivery check. Browser acceptance of this patch is
still required on the target environment.
New games are timed; existing games with null turn_started_at stay untimed.
The timeout material policy is not a complete dead-position solver; see limits.
Phase 8 requires the user's next-phase instruction. The notes below are history.

Read PHASE6.md first. Phase 6 is now implemented: participant-only unrated rooms,
WebSockets, durable versioned moves, reconnect, SAN and automatic draw claims.
No clocks are running yet. Phase 7 is next. The notes below describe the prior
baseline. Do not interpret them as a request to reimplement Phase 6.
Current results: 406 backend passed/9 slow skips; 46 frontend passed; build,
Ruff, mypy, Alembic and actual Uvicorn network WebSocket smoke passed.
The user manually verified two-browser room creation. The browser offline-event
regression is covered by Vitest; the corrected game-smoke script still needs a
local rerun because Chromium cannot launch in the build environment.

Read AGENTS.md, PROJECT_PLAN.md, PHASE2.md, PHASE3.md, and PHASE4.md.
Read PHASE5.md as well. Phases 1–5 are implemented. Phase 6 is next and requires
the user to request the next phase. The practice board is at /practice and uses
the stateless /api/v1/board/position endpoint. Real-browser QA was blocked in
the build environment; run the included frontend/scripts/board-smoke.mjs locally.

The Phase 5 independent-review patch fixes live-region heading semantics,
adds viewport-height board sizing and mobile sticky controls, names terminal
results, and rate-limits practice requests using PostgreSQL (120/IP/minute).
PHASE5.md records the new 380/43 test counts and pending browser layout checks.

The custom standard-library engine is in backend/app/chess. Run it from
backend with `python3 -m app.chess --perft 3` or `--divide 3`.
backend/engine_tests contains 313 cases. The routine run executes 304;
`python -m pytest engine_tests --runslow -q` includes the nine deeper trees.
PHASE3.md explains the engine API and rules. PHASE4.md records the new tests,
diagnostics, verification evidence, and local upgrade instructions.

The existing Phase 1/2 application, migrations, authentication, frontend, and
visual system are included. PHASE2.md records their setup and prior evidence.
Preserve the local .env and database volume when upgrading. This archive
contains source files, without credentials, running services, or installed
dependencies. Open chess-app in Codex to continue.

For interface work, read PRODUCT.md and DESIGN.md. REVIEW.md records the
Phase 1/2 remake. Do not use python-chess in any later phase.

The pre-Phase-5 auth patch normalizes refresh-cookie expiry to UTC. Read
AUTH_TIMEZONE_FIX.md for current verification and the timestamp audit.
PROJECT_PLAN.md now records the accepted Phase 6 SAN, termination mapping,
and automatic draw requirements, plus Phase 7 timeout and Phase 10 AI notes.

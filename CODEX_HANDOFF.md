# Codex handoff — Phase 4 complete

Read AGENTS.md, PROJECT_PLAN.md, PHASE2.md, PHASE3.md, and PHASE4.md.
Phases 1–4 are implemented. Phase 5, the chessboard UI, is next and requires
the user to request the next phase.

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

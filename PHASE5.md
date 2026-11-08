# Phase 5 — interactive chessboard

This snapshot includes Phases 1–5 and the Phase 4 auth timezone fix.

## Start on your Mac

Keep Docker Desktop running. Extract this ZIP into a separate folder, open
Terminal inside its `chess-app` folder (the one containing `compose.yaml`), and run:

```bash
python3 scripts/configure_env.py
docker compose up --build -d
```

Open http://localhost:5173/practice in your browser. You can also click Practice
in the navigation. No account is required for this local practice board.
If a previous copy is already using ports 5173, 8000 or 5432, stop that copy's
services from its folder with `docker compose down` first. Do not delete its
database volume. Preserve your existing `.env` when updating a working copy.

## What you can do

- Move pieces by clicking/tapping source and destination, or dragging.
- Select a piece to see legal destination dots and capture rings.
- Navigate squares with arrow keys; Enter/Space selects or moves, Escape clears.
- Choose queen, rook, bishop or knight in the native promotion dialog. Escape
  or Cancel abandons the promotion without changing the position.
- See check, last-move squares, side to move, and terminal position reasons.
- Flip the board, undo local moves, reset, or load a validated FEN position.
- Use the responsive layout and automatic system light/dark theme.

Pieces are original SVG artwork in `frontend/src/components/Piece.tsx`; no
external piece font, emoji rendering or remote asset request is required.

## Scope and design decisions

`Chessboard` is a controlled React component: it receives a position, legal
UCI moves, orientation, pending state and last move, then emits a chosen UCI
move. It owns only interaction state. The Python engine remains the only
move generator; there is no JavaScript chess library or duplicate rules engine.

`POST /api/v1/board/position` accepts a bounded FEN and optionally one move.
It validates the position and move, then returns the board, legal moves, check
and terminal-position reason. The synchronous FastAPI route runs its CPU work
in the thread pool. This is one-position evaluation, not perft or AI search.
Requests do not write database rows, cookies, ratings or games. No auth or CSRF
token is required for this stateless calculation. Normal middleware body-size
and response-security controls still apply. Deployment rate limits and broader
abuse protection require the planned security review before public release.

`BoardPage` handles requests, retains confirmed positions for local undo, blocks
duplicate submissions while pending, and ignores responses after unmount. A
failed move leaves the current board intact. Reload position re-evaluates that
position and starts a fresh undo stack. Refreshing the page resets the board.

This is a practice position explorer, not a persisted game. Repetition and
50-move claims are not adjudicated here; the engine's automatic terminal checks
still apply to the supplied position. Online gameplay, reconnect, server-owned
history, SAN, outcome-name mapping and automatic claim policy remain Phase 6.
The Phase 4 review requirements in PROJECT_PLAN.md remain binding.

Pointer Events provide mouse, pen and touch handling without a drag library.
Pointer capture keeps a drag active outside its source square; hit testing at
release determines the destination. Illegal and outside drops do not emit a move.
The native dialog provides modal focus management and Escape dismissal.

## Tests

From `chess-app`:

```bash
docker compose --profile test run --build --rm test
docker compose --profile test run --build --rm frontend_test
```

Expected routine results: 379 backend/engine cases passed with nine deliberately
skipped deep perft cases; 38 frontend cases passed. `pytest tests -q` alone now
runs 75 backend cases, including the 11 new practice-API cases. All 40 database
cases require the dedicated test database supplied by Compose.

For development without Docker, follow PHASE2.md for the API/environment setup,
then run `npm ci` and `npm run dev` from `frontend`. Run `npm test` and
`npm run build` there. Python tests run from `backend` with Python 3.12 and
`requirements-dev.lock` installed.

An additional real-browser smoke script is included. With the application
running, from `frontend`:

```bash
npm ci
npx playwright install chromium
node scripts/board-smoke.mjs
```

It exercises responsive widths, click moves, pointer dragging, keyboard moves,
flip, undo, promotion, castling, en passant and Fool's Mate against the real API.
It writes desktop/mobile screenshots to `/tmp`. `BOARD_URL` can override the
default http://127.0.0.1:5173/practice; `CHROMIUM_PATH` can select an installed
Chromium binary. Touch-device testing should additionally check tap, drag,
pointer cancellation and scrolling outside the board on an actual phone.

## Verification actually performed

- Python 3.12 and PostgreSQL 17.11: 379 passed, 9 deep-perft skips.
- Alembic upgrade and schema check: passed, no schema drift.
- Ruff: passed. Mypy: passed for 22 application source files.
- Vite production build and strict TypeScript: passed.
- Vitest/Testing Library: 38 passed, including existing 23 auth/client cases.
- Figma editable layout and vector pieces: rendered and visually inspected.

Real-browser execution was attempted but **did not run successfully**: local
Chromium was blocked from creating its socket, and the connected browser could
not access the local preview under its security policy. Therefore desktop/mobile
browser appearance, actual pointer capture, touch behavior, native dialog focus
and the smoke script itself still need verification on your machine. Unit tests
use simulated pointer events and dialog methods; they are not substitutes for
that browser pass. No browser-success claim is made for this snapshot.
Docker images were not built in this environment. The nine slow engine tests
and coverage measurement were not rerun because engine source was unchanged.

## Design reference and tools

Editable Figma reference:
https://www.figma.com/design/38mBm2HVg8wzKEQlz2GdsH

The Figma file is a desktop interaction blueprint, not a pixel-perfect capture
or a working React prototype. It contains editable board-square instances,
vector pieces and annotations. The implemented React page is authoritative.
The frontend engineering guidance informed keyboard access, focus, error states
and responsive layout; Ponytail informed reuse of the existing API client,
native Pointer Events/dialog and the single Python rules source. No unrelated
plugins were invoked. No Figma AI image generation was needed.

## Next phase and effort estimate

Phase 6 is next after user authorization: WebSocket game server, authoritative
game state and reconnect, plus the accepted SAN and draw-persistence requirements.
A human engineer familiar with the codebase would typically spend about 2–4
working days implementing, testing and reviewing this scope; cross-browser and
device QA can add time. This estimate is not a claim about elapsed agent time.

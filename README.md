# Chess Room

A real-time multiplayer chess web app with its own chess engine, written from scratch.

**Status:** in active development. Phases 1–8 of a 16-phase plan are complete
(see [PROJECT_PLAN.md](PROJECT_PLAN.md)). It runs locally with Docker; public deployment comes later.

## What works today

- **Accounts:** register, log in, log out. JWT access tokens, rotating refresh tokens with
  reuse detection, CSRF protection, and rate limiting.
- **Chess engine in pure Python** (no chess libraries): castling, en passant, promotion, check,
  checkmate, stalemate, threefold repetition, the 50-move rule, and insufficient material.
  Move generation is verified against published
  [perft](https://www.chessprogramming.org/Perft_Results) counts for six reference positions.
- **Interactive board:** click, drag, touch, and keyboard input, legal-move highlights,
  promotion dialog, light and dark themes, and a practice mode.
- **Online games over WebSockets:** two-player rooms, reconnect handling, and moves pushed to the
  opponent immediately using PostgreSQL `LISTEN/NOTIFY`.
- **Server-side clocks:** 1+0, 3+2, 5+0, 10+0, and 15+10. The server is the only timekeeper,
  timeouts are decided on the server, and a first-move rule aborts games nobody shows up for.
- **Rated matchmaking and Elo:** a queue that pairs players on the same time control within a
  rating window that widens the longer they wait, with separate bullet, blitz, and rapid
  ratings settled in the same database transaction that records the result.

## Still to come

Game history and PGN import/export, a minimax AI opponent with
alpha-beta pruning, spectators and chat, leaderboards, a security review, and deployment.

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React, TypeScript (strict), Vite, Tailwind CSS |
| Backend | Python 3.12, FastAPI, WebSockets |
| Database | PostgreSQL, SQLAlchemy 2.0, Alembic |
| Testing | pytest, Vitest, React Testing Library, Playwright |
| Tooling | Docker Compose, Ruff, mypy (strict) |

## Run it locally

You need Docker Desktop running.

```bash
python3 scripts/configure_env.py
docker compose up --build -d
```

Open http://localhost:5173. To play a game against yourself, create two accounts in two
different browsers (for example Safari and Chrome), then use **Online rooms**.

## Run the tests

```bash
docker compose --profile test run --build --rm test
docker compose --profile test run --build --rm frontend_test
```

The backend suite has 476 tests (467 routine, plus 9 deeper perft trees enabled with
`--runslow`). The frontend suite has 55. Browser smoke tests live in `frontend/scripts`.

## How it was built

This project is built phase by phase with AI coding assistants, directed and reviewed by me.
Each phase is independently tested and reviewed before the next one starts; the `PHASE*.md`
files and [REVIEW_FIXES.md](REVIEW_FIXES.md) record what was built, what was verified, and what
each review found.

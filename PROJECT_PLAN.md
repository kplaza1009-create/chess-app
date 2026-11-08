# Online multiplayer chess: complete project plan

## Goal and stack

Build a complete, production-quality multiplayer chess application while
mentoring a CS junior. This is the target for the finished project, not a claim
that the current snapshot is ready for production deployment.

- Frontend: React, TypeScript in strict mode, Vite, Tailwind CSS.
- Backend: Python FastAPI with WebSockets.
- Database: PostgreSQL, SQLAlchemy 2.0, Alembic migrations.
- Authentication: JWT access and refresh tokens, bcrypt password hashing.
- Chess: our own Python board representation and move generator; no python-chess.
- Tests: pytest, Vitest, and React Testing Library.
- Deployment: Docker and Docker Compose, deployable to Render.

## Required features

1. User accounts: registration, login, logout, profile page, avatar.
2. Full chess rules: castling, en passant, promotion, check, checkmate,
   stalemate, threefold repetition, 50-move rule, insufficient material.
3. Real-time multiplayer over WebSockets with reconnect handling.
4. Matchmaking queue pairing players by ELO rating.
5. Bullet, blitz, and rapid time controls with server-authoritative clocks.
6. ELO rating updates after every rated game.
7. Game history and complete move replay with forward/back controls.
8. PGN export and import.
9. Spectator mode for live games.
10. In-game chat with basic profanity filtering.
11. Computer opponent: minimax with alpha-beta pruning and three difficulties.
12. Paginated leaderboard.
13. Draw offers, resignation, and rematch requests.

## Phase sequence

| Phase | Scope | Transfer status |
| --- | --- | --- |
| 1 | Project structure, Docker Compose, database models, Alembic setup | Complete; included |
| 2 | Authentication backend and frontend login/register pages | Complete; included |
| 3 | Chess engine: board representation, move generation, all rules | Complete; included |
| 4 | Full engine pytest suite, including perft tests | Complete; included |
| 5 | Chessboard UI, drag-and-drop, legal move highlights | Next |
| 6 | WebSocket game server, state synchronization, reconnect | Pending |
| 7 | Time controls and server-side clocks | Pending |
| 8 | Matchmaking queue and ELO system | Pending |
| 9 | Game history, replay viewer, PGN import/export | Pending |
| 10 | Minimax AI with alpha-beta pruning | Pending |
| 11 | Spectators, chat, draw/resign/rematch | Pending |
| 12 | Leaderboard and profile pages | Pending |
| 13 | Frontend tests and backend integration tests | Pending |
| 14 | Security review and fixes | Pending |
| 15 | Performance review and refactoring | Pending |
| 16 | README, Mermaid architecture diagram, setup and Render deployment guides | Pending |

Work on one phase per response and wait for "next phase". Earlier phases may
include necessary focused tests; Phase 4 adds the comprehensive engine/perft
suite, and Phase 13 adds broader frontend and integration coverage.

## Requirements for the next phase

When the user authorizes Phase 3, inspect the existing backend layout and
implement an independent Python chess engine that can later support the
WebSocket server, replay, PGN, and AI. Explain the selected board representation,
pseudo-legal versus legal moves, and king-safety filtering. Cover every required
rule, including edge cases involving castling and en passant. Keep the engine
independent of FastAPI and SQLAlchemy so it can be tested and searched directly.

Do not silently redefine draw rules. Document which outcomes are automatic and
which require a player claim, and how the API exposes that distinction.
Use appropriate correctness checks during implementation; the comprehensive
pytest/perft suite remains Phase 4. Do not implement later-phase UI or services
in the Phase 3 response.

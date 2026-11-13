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
| 5 | Chessboard UI, drag-and-drop, legal move highlights | Implemented; browser smoke independently verified |
| 6 | WebSocket game server, state synchronization, reconnect | Implemented; browser smoke independently verified |
| 7 | Time controls and server-side clocks | Implemented; review fixes in REVIEW_FIXES.md |
| 8 | Matchmaking queue and ELO system | Implemented; checks in PHASE8.md |
| 9 | Game history, replay viewer, PGN import/export | Implemented; checks and limits in PHASE9.md |
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

## Original Phase 3 implementation brief (completed)

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

## Accepted requirements from the independent Phase 4 review

These are requirements for the named phases. The auth timezone fix is delivered
before Phase 5. See AUTH_TIMEZONE_FIX.md for its regression tests and verification.

### Phase 6 prerequisites and draw policy

- Keep the Phase 5 practice endpoint's shared PostgreSQL rate limit. Add
  WebSocket connection/message limits before public deployment in Phase 6,
  along with explicit trusted-proxy configuration and ingress-wide limits.

- Add SAN generation and parsing in the custom engine, with engine_tests cases.
  Cover legal-move disambiguation (Nbd2, R1e2, and file plus rank when required),
  captures, pawn capture files, promotions, O-O/O-O-O, and check/mate suffixes.
  Reject illegal or ambiguous input. Generate SAN from the pre-move position.
  The moves.san column is required and nonempty, and Phase 9 PGN import needs parsing.
- Introduce an explicit server mapping from engine outcome reasons to database
  termination values. Map threefold_repetition and fivefold_repetition to
  repetition, fifty_moves to fifty_move, and seventy_five_moves to seventy_five_move.
  Preserve the existing matching reasons. Test that every engine outcome can
  actually be stored in PostgreSQL with the corresponding result and ended_at.
- The user selected automatic threefold and 50-move draws for online play.
  After accepting a move, the server checks claimable_draws() on the resulting
  position and calls claim_draw when nonempty. Persist the resulting outcome
  atomically with the move. Keep the engine's claim API. Do not claim based on
  hypothetical intended moves before they are played. Existing automatic
  terminal outcomes, including checkmate, retain precedence.

### Phase 7 timeout adjudication

Determine whether the player with time remaining can ever checkmate by any
legal sequence. The current insufficient_material() checks both players
together and cannot answer that one-sided question. Add tests for asymmetric
material before implementing timeout wins and draws.

### Phase 10 AI execution and profiling

Run AI search in a separate process, such as ProcessPoolExecutor, to keep
FastAPI and WebSocket handling responsive. Bound pending work and handle stale
results when the game changes. The independent reviewer measured roughly 85k
perft leaves/sec and about 40% of runtime in Position.__post_init__. Reprofile
on the target environment and consider a private trusted constructor for
internal _apply transitions while preserving external input validation.

## Follow-ups from the independent Phase 8 review

- **Phase 11** will add resignation and a disconnect-forfeit timer for rated
  games. A player who reconnects before the deadline can continue the game.
- **Phase 14** will limit repeat pairings between the same two accounts and add
  a cooldown for repeated first-move aborts.

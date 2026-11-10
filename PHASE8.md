# Phase 8 — rated matchmaking and Elo

Choose **Play** in Chess Room, select a clock, then choose **Find opponent**.
Matchmaking pairs two players on the same time control and opens the game for
both. Private rooms remain available through **Create a private room** on the
Play page. They are unrated.

## Upgrade and try it

Extract the Phase 8 ZIP into a separate folder. Keep your existing `.env` and
PostgreSQL volume. Use the same Compose project name as your previous install.
For a fresh install, first run `python3 scripts/configure_env.py` from the new
`chess-app` directory.

```bash
docker compose up --build -d
docker compose ps
```

The migration service applies revision `0004`. Open
http://localhost:5173/play in two browsers or profiles so each player has their
own session. Register or sign in with two different accounts. Select the same
time control and click **Find opponent** on each side.

The board shows your assigned color. Make both first moves before the opening
deadlines. For a quick checkmate test, the moves are `f2f3 e7e5 g2g4 d8h4`.
With two new accounts, Black gains 16 points and White loses 16. Both players
see their own change on the game page and can choose **Find another game**.
The lobby shows your rating for the selected time control. Both player strips
use the game's rating pool. After a rated result, they show the settled
ratings from that game. Opening the account page loads current ratings.

| Rated time control | Rating pool |
| --- | --- |
| 1+0 | Bullet |
| 3+2 or 5+0 | Blitz |
| 10+0 or 15+10 | Rapid |

## How the queue works

Each player has one search ticket. The server looks for the oldest eligible
opponent in the same time control. Both players start with a 100-point window
that widens by 50 points every five seconds to a maximum of 400. The rating
difference must fit both windows. Colors are assigned randomly.

The lobby renews its search about every 2.5 seconds. Navigating away or a
browser `pagehide` sends a keepalive DELETE for the ticket and stops renewals.
If a join returns a ticket after SPA navigation, the lobby cancels that ticket
as well. The 20-second lease covers a lost request or a browser shutdown before
the ticket arrives. An API restart within the lease can resume the search.
The Play page checks the server again on return and reopens any active rated
game. A revoked login makes its search ineligible. Canceling targets a specific
ticket ID, so a delayed cancel cannot remove a newer search. If pairing commits
first, the cancel response returns the matched game.

PostgreSQL serializes the short queue transactions across API processes.
Creating the game and consuming both tickets commit together. The existing
WebSocket handles the game after the HTTP queue hands off its ID. The queue
uses one database lock, which keeps coordination small for this phase and can
be a throughput limit under heavier traffic.

| Request | Effect |
| --- | --- |
| `GET /api/v1/matchmaking` | Read your search or active rated game |
| `POST /api/v1/matchmaking` | Join with `{"time_control":"3+2"}` or resume your search |
| `PUT /api/v1/matchmaking/{ticket_id}` | Renew and try pairing |
| `DELETE /api/v1/matchmaking/{ticket_id}` | Cancel that search or return the match already created |

## How Elo settles

Each speed starts at 1200. The expected score for White is
`1 / (1 + 10 ** ((black_rating - white_rating) / 400))`. The server subtracts
that expectation from the actual score (1, 0.5, or 0), multiplies by 32, and
rounds to the nearest integer. The resulting points transfer between the two
players, with a zero rating floor. The winner of an even match gains 16
points. A draw between evenly rated players moves zero points and records a
draw for each player.

Checkmates, engine draws, and timeouts settle ratings as part of the same
transaction that records the game result. The game row lock orders competing
finish requests. The two rating rows are locked in player ID order, and the
ledger uses a unique key per game and player. The move, result, rating changes,
and win/loss/draw counts roll back together if the transaction fails. Unrated
games and first-move aborts award zero points and leave counts alone.

## Verification

The Phase 7 audit matched 134 project files against the delivered archive.
On PostgreSQL 16.11 with `America/New_York`, the baseline passed 442 backend
tests and 49 frontend tests. Alembic, Ruff, mypy, and the production frontend
build passed.

Phase 8 passed **467 backend tests** and **55 frontend tests**, plus the four
environment configuration tests. Both backend runs used the standard suite
with nine opt-in deep perft cases skipped. Those deep cases were last run in
the five Phase 7 teardown acceptance runs documented in TEARDOWN_FIX.md.
Ruff, strict mypy, and the TypeScript/Vite production build passed.

The migration was tested on seeded Phase 7 data with an upgrade, downgrade,
and re-upgrade. Both existing users, their ratings, and their unrated game
were preserved. Alembic reported no schema drift.

Two real Uvicorn processes sharing one PostgreSQL database passed the rated
wire check, including cancellation, pairing, checkmate, rating settlement,
and a duplicate final move. The existing private-room wire check passed.
The 30-move delivery test passed its unchanged 100 ms limit in both
configurations. The single-process run averaged 21.0 ms and peaked at
26.4 ms. The two-process run averaged 19.7 ms and peaked at 22.5 ms.
The prior Phase 7 single-process outlier remains documented in TEARDOWN_FIX.md.

Docker Compose was unavailable in the authoring environment. The backend
checks used PostgreSQL and Uvicorn directly. Chromium launch was blocked by
the workspace socket policy. Frontend behavior was checked with Vitest, and
the two-browser procedure above is available for local verification.

## Independent review patch

The independent reviewer confirmed rated play in two browsers, six games from
12 simultaneous joins, and agreement with the Elo formula in 18,204 cases.
The review found that navigating away from the lobby left its ticket eligible
until the lease expired. The patch sends an authenticated keepalive DELETE on
exit and handles join responses that arrive after navigation.

The patch passed **467 backend tests** on PostgreSQL 16.11 with
`America/New_York` and **59 frontend tests**. The nine opt-in deep perft cases
were skipped. Frontend regressions cover navigation, late joins, `pagehide`,
cached returns, and the keepalive request. Rated game tests also verify that
reopening a finished game preserves its settled ratings after later changes.
The build, Ruff, mypy, and Alembic checks passed.

The private and rated wire smokes passed. The rated smoke verified cancellation
across two API processes and checked both players' ratings before and after
checkmate. The 30-move delivery checks peaked at 31.3 ms on one process and
76.5 ms across two, both within the existing 100 ms limit. Chromium could not
launch under the workspace socket policy, so the updated browser flow was
exercised with Vitest.

To check the exit behavior in your browser, start a search with one account
and choose **Create a private room**. Return to **Play** and confirm the lobby
offers **Find opponent**. Repeat with a reload during a search to exercise
`pagehide`.

The follow-ups for resignation, disconnect forfeits, repeat pairings, and
first-move abort cooldowns are recorded in PROJECT_PLAN.md.

Run the ordinary test suites from the project root:

```bash
docker compose --profile test run --build --rm test
docker compose --profile test run --build --rm frontend_test
docker compose exec api alembic check
```

Run the rated wire smoke from `backend` with the development Python environment
active and the local stack running. It creates two accounts and a game in the
development database:

```bash
python scripts/matchmaking_smoke.py
```

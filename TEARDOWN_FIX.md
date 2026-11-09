# Phase 7: WebSocket teardown cancellation

## Root cause

The failure is in asynchronous teardown, not the chess assertions or PostgreSQL
timezone handling. Starlette's WebSocketTestSession exits by sending a disconnect,
cancelling its AnyIO cancel scope, and waiting for the application task's future.

The game handler uses separate asyncio receiver and notification-wakeup tasks.
It previously cancelled those tasks and awaited asyncio.gather with
return_exceptions=True without shielding cleanup from an enclosing cancel scope.
When that gather contains both a pending receiver and an already-cancelled wakeup,
the scope's cancellation can race with gather's completion. Python's gather can
then propagate a child's bare CancelledError instead of the cancellation carrying
AnyIO's scope identity. AnyIO deliberately does not suppress unrelated asyncio
cancellations. The handler future is therefore cancelled, and TestClient's
future.result() raises concurrent.futures.CancelledError during __exit__.

This was reproduced with deterministic event-loop ordering and no database:
start two tasks, cancel and finish one, schedule cancellation of the caller's
scope, then cancel and gather both tasks. Removing the shield makes the new
regression fail with the same bare CancelledError. It is not necessary to add
wall-clock sleeps, retries, or more permissive test assertions.

## Change

backend/app/api/games.py now uses one small _cancel_tasks helper for both wakeup
cleanup and final socket cleanup. An AnyIO CancelScope(shield=True) covers only
cancelling and draining those child tasks. Normal work remains cancellable, and
the caller's original cancellation still propagates outside the shield. No
CancelledError is broadly caught or suppressed in the handler or tests.

Connection-slot accounting and subscription removal run before the asynchronous
drain, so a further server cancellation cannot skip those synchronous releases.
The zero-count pending-authentication entry is now removed when a connection
becomes authenticated, rather than leaving {"pending": 0} after all sockets close.
The protocol, move transactions, clocks, authentication, and latency threshold
are unchanged. No dependency downgrade or test-framework patch is shipped.

AnyIO documents shielding asynchronous finalization here:
https://anyio.readthedocs.io/en/stable/cancellation.html#finalization

## Regression coverage

- Mixed pending/already-cancelled tasks preserve the caller's cancel-scope identity.
- Cleanup finishes when the enclosing scope is already cancelled.
- Plain asyncio task cancellation still propagates to the caller.
- Real TestClient socket exits release slots/subscriptions while idle and directly
  after sending a move, without waiting for acknowledgement.
- Existing first-move-abort and concurrent-duplicate-move tests retain their
  assertions and additionally check that slots/subscriptions are released.

## Reproduce the five-run acceptance check

Use a dedicated PostgreSQL 16 test database whose name ends in _test. The
integration fixtures truncate that database; never use a database with real data.
Set both DATABASE_URL and TEST_DATABASE_URL to its SQLAlchemy psycopg URL.
Set the test database timezone to America/New_York before opening application
connections. Activate the project's Python 3.12 environment, then from backend:

```bash
alembic upgrade head
alembic check
set -e
for run in 1 2 3 4 5; do
  python -m pytest --runslow -xq
done
```

The sequence stops on any failure. --runslow includes the nine deeper perft tests;
there are no acceptance retries or newly skipped tests.

## Executed verification

The final acceptance sequence used Python 3.12.14, the project's unchanged locked
dependencies, and PostgreSQL 16.11 with database timezone America/New_York.
Each row below is a separate pytest process running the entire backend suite,
including all nine deep perft cases. The application and tests were unchanged
throughout these five consecutive runs. There were no retries, xfails or skips.

| Run | Passed | Failed | Skipped | Duration |
| --- | ---: | ---: | ---: | ---: |
| 1 | 451 | 0 | 0 | 727.50 seconds |
| 2 | 451 | 0 | 0 | 518.10 seconds |
| 3 | 451 | 0 | 0 | 502.53 seconds |
| 4 | 451 | 0 | 0 | 475.47 seconds |
| 5 | 451 | 0 | 0 | 468.38 seconds |

Ruff, strict mypy (28 application files), and formatting of the changed Python
files passed. Alembic upgraded the fresh PostgreSQL 16 database through 0003;
alembic check reported no schema drift. This fix adds no migration.

The deterministic negative control disabled only the new shielding, without
altering the assertions. It failed the mixed-task-cleanup regression with a bare
CancelledError (1 failed, 2 passed). Restoring shielding passed all three focused
regressions. The negative-control plugin is not included in the application.

A preliminary full run with the new stronger accounting assertions found five
failures caused solely by the leftover {"pending": 0} entry (446 passed). That
bookkeeping defect was corrected before the five-run sequence above; the failed
preliminary run is not counted as acceptance evidence.

The real HTTP/WebSocket wire smoke passed after both Uvicorn processes reported
readiness: authentication, synchronized moves, checkmate SAN, and reconnect.
An initial smoke invocation used a fixed two-second startup delay and reached
the server before it listened, producing connection refused. The validation
harness was corrected to check /health/ready before running the smoke; no
application code changed and no pytest acceptance run was retried.

The additional same-worker latency check did NOT pass on this host: 30 moves
averaged 47.2 ms with a maximum of 102.1 ms, exceeding the unchanged strict
100 ms assertion. This failed measurement is retained, not replaced by a rerun.
The independent review's earlier passing latency measurements remain separate
evidence; the five-suite teardown acceptance above is a different check.

The separate cross-worker latency check passed: 30 moves averaged 55.9 ms,
maximum 69.5 ms, with the same strict 100 ms threshold. It was run once after
server readiness and does not replace the failed same-worker result.

Frontend tests, browser smokes and Docker/Nginx runtime were not rerun for this
backend-only cleanup patch. The user's independent browser and real-server
cleanup results apply to the preceding version.

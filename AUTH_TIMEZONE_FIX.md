# Phase 4 follow-up: refresh-cookie timezone fix

The refresh endpoint now converts the database expiry to `datetime.UTC` before
passing it to Starlette's cookie formatter. No migration or dependency change
is required. Phase 5 has not started.

## Why the conversion belongs here

PostgreSQL `timestamptz` represents an instant, but psycopg returns it with the
database session's timezone. An aware New York datetime still denotes the
correct instant. HTTP cookie dates, however, require GMT, and Python's
`format_datetime(..., usegmt=True)` requires UTC tzinfo. Calling
`issued.expires_at.astimezone(UTC)` preserves the instant and satisfies that
formatting requirement. Replacing tzinfo without converting would change the
instant and would be incorrect.

The only production-code change is in `backend/app/api/auth.py`: import `UTC`
and normalize the `expires` argument. Session lifetime, refresh rotation, JWT
expiry, and cookie security flags retain their existing behavior.

## Regression coverage

- `backend/tests/integration/conftest.py` accepts New York and Kathmandu
  fixture parameters. It passes the timezone through psycopg connection options
  for every application database connection, including connections obtained
  after a transaction commits. Setting a timezone on an unrelated cleanup
  connection would not exercise the application.
- `backend/tests/integration/test_auth.py` adds two real PostgreSQL cases.
  Each confirms the application's session timezone and nonzero expiry offset,
  refreshes twice, and checks the GMT cookie date, remaining Max-Age, JWT expiry,
  unchanged session family and absolute expiry, rotated refresh token, and
  successful authenticated access.
- `backend/tests/test_auth_cookie.py` adds six deterministic cookie cases:
  UTC, America/New_York, and Asia/Kathmandu in January and July. These cover
  New York's seasonal offsets and Kathmandu's fractional-hour offset.

## Timestamp audit

| Location | Finding |
| --- | --- |
| `backend/app/api/auth.py` | Cookie Expires required UTC normalization; fixed. Max-Age uses subtraction of aware datetimes and remains correct. |
| `backend/app/services/auth.py` | Expiry comparison, access-expiry minimum, and remaining lifetime use aware datetimes; no timezone stripping or UTC wall-clock assumption. |
| `backend/app/services/security.py` | JWT expiry uses `timestamp()`, which preserves the instant across offsets. `utc_now()` returns an aware UTC datetime. |
| `backend/app/api/dependencies.py` | Session expiry comparison is performed against a timezone-aware timestamp in PostgreSQL. |
| `backend/app/services/rate_limit.py` | Expiry comparisons use timestamptz; Retry-After uses an aware timedelta and integer seconds. |
| `backend/app/db/base.py`, `models.py`, `auth_throttle.py` | Database datetime columns use `DateTime(timezone=True)`. |
| `backend/app/schemas/auth.py` and frontend date handling | Profile creation dates retain offsets; frontend validation accepts offsets and JavaScript Date parses the instant. |

No additional UTC formatting/comparison defect was found in the current code.
Future game-clock and persistence paths still require their own tests when built.

## Checks actually executed for this patch

Environment: Python 3.12.14, PostgreSQL 17.11, locked backend development
dependencies. The independent reviewer used PostgreSQL 16; this patch was
verified here on PostgreSQL 17, which is also the existing Compose major version.

| Check | Result |
| --- | --- |
| `alembic upgrade head` on a fresh dedicated database | Both existing migrations applied successfully. |
| `alembic check` | No new upgrade operations detected. |
| `pytest tests -q`, database default America/New_York | 64 passed, no skips. |
| `pytest tests -q`, database default UTC | 64 passed, no skips. |
| Negative control in a separate backend copy, with only the expiry conversion removed | Both new non-UTC integration cases failed with the reported `ValueError: usegmt option requires a UTC datetime`. |
| `ruff check app alembic tests engine_tests` | Passed. |
| `ruff format --check app/api/auth.py tests/integration/conftest.py tests/integration/test_auth.py tests/test_auth_cookie.py` | All four files formatted. |
| `mypy` | Passed: 21 source files. |

The 64 backend cases consist of the previous 56 plus two database regressions
and six cookie unit cases. Each full database run includes all 40 database
cases; none were skipped. The unchanged engine suite, engine coverage, frontend
suite, and Docker build were not rerun for this targeted patch. Their earlier
Phase 4 results are historical evidence, not new results from this patch.

## Apply and test on your machine

Extract the updated ZIP into a separate folder. If updating an existing working
copy, merge these files while preserving your local changes, `.env`, `.venv`,
and database volume:

- `backend/app/api/auth.py`
- `backend/tests/integration/conftest.py`
- `backend/tests/integration/test_auth.py`
- `backend/tests/test_auth_cookie.py`
- `AUTH_TIMEZONE_FIX.md`, `PROJECT_PLAN.md`, `CODEX_HANDOFF.md`, and `PHASE4.md`

From `chess-app`, with your existing Compose setup:

```bash
docker compose --profile test run --build --rm test sh -ec 'alembic upgrade head && alembic check && pytest tests -q'
```

This command is provided for your machine; Docker was not used for this patch's
verification. The new regression fixture forces non-UTC sessions even if the
test database defaults to UTC. Expect 64 passed.

For a local Python 3.12 environment, from `backend`:

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pytest tests/test_auth_cookie.py -q
```

Expect six passed. To run all backend tests locally, first configure
`TEST_DATABASE_URL` for a disposable PostgreSQL database named with the `_test`
suffix. The fixtures truncate that database's application data. Then run:

```bash
: "${TEST_DATABASE_URL:?Set this to your dedicated PostgreSQL test database URL}"
export DATABASE_URL="$TEST_DATABASE_URL"
export APP_ENV=test
export JWT_SECRET='test-only-signing-key-never-use-in-production-123456'
python -m alembic upgrade head
python -m alembic check
python -m pytest tests -q
```

Use a SQLAlchemy URL with the `postgresql+psycopg` scheme. Without
`TEST_DATABASE_URL`, the 40 database cases skip and the other 24 cases pass;
that does not verify the database regression.

To reproduce the reviewer's database-wide setup, run this SQL against your
disposable test server before starting the tests (not against production):

```sql
ALTER DATABASE chess_test SET timezone TO 'America/New_York';
```

New connections inherit that default. The application fixture's explicit
timezone cases continue to test both New York and Kathmandu.

## Accepted later-phase work

`PROJECT_PLAN.md` records the requested SAN generation/parsing, engine-to-database
termination mapping and persistence tests, and automatic threefold/50-move
server draw policy for Phase 6. It also records one-sided timeout adjudication
for Phase 7 and process-based AI search plus validation profiling for Phase 10.
Those features are scheduled, not implemented by this auth patch. The engine's
claim API and database termination constraint remain unchanged at this point.

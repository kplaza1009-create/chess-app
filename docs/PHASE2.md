# Phases 1 and 2: reviewed and remade

Version 0.2.1 contains the complete foundation and authentication system.
The custom chess engine starts in Phase 3. See PROJECT_PLAN.md for the full
16-phase plan and REVIEW.md for the review findings and changes.

## Start locally

Requirements: Docker with Compose v2 and Python 3.10+ for local configuration.
From the extracted `chess-app` folder:

```bash
python3 scripts/configure_env.py
docker compose up --build -d
```

Open http://localhost:5173. Create an account, sign out, and sign in again.
API documentation is available at http://localhost:8000/docs in development.

The configuration script generates a random JWT signing secret. It writes
atomically and preserves existing credentials. It rejects duplicate settings
instead of guessing which secret should win. The archive contains no `.env`.

When upgrading an existing Phase 1/2 checkout, merge the new project files,
keep your `.env` and PostgreSQL volume, and run the same commands. The database
schema is unchanged; migration head remains `0002`.

```bash
docker compose ps -a
docker compose logs -f api migrate frontend
docker compose exec api alembic current
docker compose exec api alembic check
```

The migration service exits with code 0 on success. Do not delete the database
volume to apply this update.

## Tests and checks

```bash
docker compose --profile test run --build --rm test
docker compose --profile test run --build --rm frontend_test
docker compose exec api ruff check --no-cache app alembic tests
docker compose exec api mypy --cache-dir=/tmp/chess-mypy
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

The backend test service uses the separate `chess_test` database. Integration
fixtures reset it; never point TEST_DATABASE_URL at a database with real data.
To stop local services while keeping the main database:

```bash
docker compose down
```

## Included functionality

- SQLAlchemy 2.0 models, integrity constraints, indexes, async sessions, and
  explicit Alembic migrations.
- Registration, login, refresh, logout, and current-user endpoints.
- Normalized email/usernames, duplicate handling, and validated passwords.
- Bcrypt hashing in bounded worker threads, keeping the event loop available.
- Five-minute access JWTs held only in browser memory.
- Refresh JWTs in a host-only HttpOnly cookie, with Secure and the `__Host-`
  prefix in production. PostgreSQL stores only a SHA-256 token hash.
- Refresh rotation, reuse detection, fixed 30-day session lifetime, and
  immediate session revocation checks on protected HTTP requests.
- Signed, cookie-bound CSRF tokens and exact Origin validation.
- Shared PostgreSQL rate limits, request body size/read-time limits,
  sanitized errors, and no-store authentication responses.
- Complete React account pages with strict TypeScript, runtime response
  validation, password visibility controls, field-level errors, and focus.
- Session restoration, single-flight refresh, cross-tab Web Locks, and
  BroadcastChannel synchronization without broadcasting credentials.
- Protection against delayed private responses after logout/account changes
  and redundant rotations caused by late expired-token responses.
- Responsive light/dark interfaces, self-hosted Manrope, Phosphor icons,
  and a bundled 75 kB decorative chess image.
- A separate frontend production build and unprivileged Nginx target.

The account screen shows actual stored ratings and labels initial values as
starting ratings. Online play is explicitly described as being built.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /api/v1/auth/csrf | Obtain a fresh signed CSRF token |
| POST | /api/v1/auth/register | Register and start a session |
| POST | /api/v1/auth/login | Sign in and replace the current cookie session |
| POST | /api/v1/auth/refresh | Rotate the refresh token |
| POST | /api/v1/auth/logout | Revoke the current session family |
| GET | /api/v1/auth/me | Read the authenticated user's private account data |

Cookie-changing calls need an allowed Origin and an X-CSRF-Token header.
The React client supplies both through same-origin browser requests. Protected
calls carry the in-memory access JWT in an Authorization Bearer header.

## Design decisions

The original refresh row has the family ID as its own ID. Every family mutation
locks it first. Reuse revocation commits before raising the rejected-request
error, so revocation cannot be rolled back accidentally.

Every private frontend request remembers the current session revision. The
client checks it before dispatch and after awaiting the response. If a login
or logout changed the identity meanwhile, the caller gets a session-changed
error instead of old account data. Cross-tab events tell peers to re-read the
shared cookie rather than trusting a stale family ID from another tab.

The form validates Unicode character count separately from encoded size:
Python's 12-character minimum counts Unicode code points, while bcrypt accepts
at most 72 UTF-8 bytes. Passwords are never silently truncated.

## Verification performed

- 56 backend pytest cases passed, including refresh replay/concurrency,
  revocation, JWT validation, CSRF, input validation, database constraints,
  rate limits, production cookies, oversized bodies, and read timeouts.
- 23 Vitest/React Testing Library cases passed, including account-switch
  races, late 401 responses, cross-tab changes, field errors, keyboard focus,
  busy states, and Unicode password validation.
- Four configuration-script checks passed, including failed replacement
  leaving existing credentials intact.
- Ruff, strict mypy, TypeScript checking, and the Vite production build passed.
- Both migrations applied and Alembic reported no schema drift.
- Real Chromium checks passed registration, valid/invalid login, reload,
  concurrent tabs, cross-tab logout, offline recovery, error focus, cookie
  attributes, absence of Web Storage tokens, and the not-found route.
- 29 automated axe WCAG scans passed across page states, both color schemes,
  and 320px, 768px, 1024px, and 1440px viewports without violations.
- A separate contrast check found and corrected the light input boundary:
  #7b8d7e now measures 3.46:1 against the input and 3.24:1 against the page.
- The production dependency npm audit reported no known vulnerabilities at
  the time of this review. This is not a complete security audit.

The authoring environment used PGlite's embedded PostgreSQL runtime with a
validation-only prepared-statement compatibility shim. The shim is not part
of the application. Docker, Compose startup, and the Nginx container could not
run here. Verify them using the commands above on your machine.

Lighthouse ran against the built frontend in a simulated browser environment.
Its overall performance score was unavailable, so no performance pass is
claimed. This check is not evidence of real-user performance.

## Remaining operational boundaries

Browsers with Web Locks serialize cookie changes across tabs. Older browsers
fall back to per-tab serialization; concurrent cross-tab refreshes can trigger
strict reuse detection and require signing in again. A lost refresh response
can also require login; consumed refresh tokens are not blindly retried.

The default Compose frontend is for development. Its Dockerfile also provides
a production target that serves the built assets and proxies /api to the API.
That target accepts PORT (default 8080) and API_UPSTREAM (default api:8000,
host:port without a URL scheme). Render networking, TLS, trusted proxy addresses,
production secrets/origins, and deployment are completed in Phase 16. Production
rate limits must use deliberately configured trusted proxy addresses.

Public profiles and leaderboards must not expose the email field from the
private current-user response. Profile/avatar work remains Phase 12.
The full security and performance reviews remain Phases 14 and 15.

## Human effort estimate

For this review and remake alone, approximately 12-24 focused hours for an
experienced full-stack developer, or 25-50 hours for a student with React,
FastAPI, and PostgreSQL experience. This includes redesign, fixes, tests,
debugging, and documentation. These are estimates, not measured work times;
they exclude the original implementation and the remaining chess phases.

# Phase 1 and 2 review

## Baseline inspected

The source is the delivered Phase 2 Codex handoff. The original files were
extracted into a separate working copy before any changes. The prior snapshot
remains available through its saved version history.

The database already has typed SQLAlchemy models, useful integrity constraints,
indexes, and explicit Alembic migrations. Keep that schema and migration
history. The review found no reason to regenerate or rewrite those migrations.

Authentication already had bcrypt off the event loop, strict JWT verification,
HttpOnly refresh cookies, signed CSRF tokens, token-family rotation and reuse
detection, server-side logout revocation, and shared rate limits. Preserve them.

## Findings addressed

| Area | Before | Revised behavior |
| --- | --- | --- |
| Pending private responses | A successful response could outlive logout or an account switch | Session revision checked before dispatch and after the response |
| Concurrent expired requests | A late 401 could rotate a token another request had already refreshed | Compare the token actually sent before refreshing again |
| Cross-tab events | Logout relied on a potentially stale local family ID | Other tabs re-read the shared cookie and resolve the current session |
| Validation | Server field errors became one generic message | Known field locations map to inline descriptions and focus |
| Unicode passwords | Browser length checks could disagree with Python code-point and byte limits | Validate code-point count and UTF-8 size before submission |
| Keyboard focus | No route focus management | New-page heading focus and error-field focus, without deferred typing interference |
| Theme | Light interface with mixed typography and Unicode artwork | Self-hosted type, one icon family, both system themes, compressed chess image |
| Account data | Equal rating cards with little context | Rating rows labeled as starting ratings and real account details |
| Local configuration | Existing .env truncated before rewriting | Write and sync a temporary file, then atomically replace it |
| Auth body reads | Size cap with no read deadline | Early size rejection and a bounded read timeout |
| Configuration | Empty origins/issuer/audience accepted | Reject unusable auth configuration at startup |
| Frontend container | Development server only | Separate build and unprivileged Nginx production target |
| Unused UI helper | Protected-route component had no callers | Removed; current account view and API authorization remain enforced |

## Tools and skills used

Ponytail guided reuse, deletion of unused code, and avoiding speculative
abstractions. Taste's frontend engineering guidance and Impeccable's Operate
and craft guidance shaped the interface, state coverage, responsive behavior,
and verification. The connected Taste account returned no learned profile or
matching references. ImageGen produced the decorative knight asset; no
customer statistics, live games, or testimonials were invented.

The Impeccable launcher was not installed in this environment. Its automated
context, detector, and concept commands did not run. Project context was read
directly, and the missing automation is not reported as a successful check.

## Finish review

An independent reviewer inspected all ten desktop/mobile captures, both color
schemes, the forms, focus behavior, and relevant source. The one material
finding was insufficient light-theme input-border contrast. That token was
changed to #7b8d7e, measuring 3.457:1 against the input and 3.244:1 against the
page. The same views were recaptured, the browser checks and 29 axe scans
passed again, and the reviewer scored that named finding resolved. This is
a scoped verdict on the fix, not a performance or automated-detector pass.

Lighthouse's overall performance score was unavailable because the Chromium
harness did not collect trace screenshots (NO_SCREENSHOTS). No performance
score is inferred from the remaining metrics. The build's accessibility audit
scored 100 in that run; real-user performance still needs later measurement.

## Boundaries

This is a remake of the foundation and authentication. Phases 3-16 remain in
PROJECT_PLAN.md. Production deployment and the project-wide security and
performance reviews still belong to their scheduled phases.

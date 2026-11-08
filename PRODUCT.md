# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People creating an account to play online chess. The initial audience's exact
skill distribution is undecided; a focused chess-club tone is an implementation
assumption, not a learned personal Taste preference.

## Product Purpose

Build a complete multiplayer chess application while teaching Kevin, a CS
junior, how move generation, perft, WebSockets, and alpha-beta search work.

## Capabilities and Constraints

The stack and all 16 phases are specified in PROJECT_PLAN.md. This remake
covers the project foundation and authentication only. Registration, login,
logout, session restoration, and current-user ratings are implemented.
Gameplay, AI, matchmaking, history, profiles, and deployment remain later work.
The engine must be written in Python without python-chess.

## Operating Context

React and FastAPI run locally through Docker Compose with PostgreSQL. The
production deployment target is Render; deployment itself is Phase 16.
Use the dedicated test database for integration tests.

## Brand Commitments

The existing product name is Chess Room. Existing routes are /, /login, and
/register. Preserve those routes and account behavior. The user authorized a
remake of Phases 1 and 2 using relevant installed skills and plugins.

## Evidence on Hand

Actual source, migrations, tests, and prior verification notes are included.
There are no supplied customer statistics, testimonials, or live game feeds.
Never fabricate them. Taste returned no learned profile or matching references.

## Product Principles

- Server state is authoritative for authentication and future gameplay.
- Preserve working security controls while simplifying their implementation.
- Every visible control performs a real action in the delivered scope.
- Provide clear validation, loading, empty, and failure states.
- Finish one authorized phase at a time and explain the important decisions.

## Accessibility & Inclusion

Use semantic controls, visible labels, keyboard access, useful focus movement,
reduced-motion support, and sufficient contrast in both color schemes.

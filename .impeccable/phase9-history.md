# History and replay surface brief

Mode: Operate. This extends Chess Room's established interface; it is not a redesign.

The user authorized Phase 9: a personal game history, forward/back replay, and
PGN import/export. Preserve the account, board, live game, clocks, matchmaking,
and rating behavior. Keep Manrope, the semantic green light/dark palette,
quiet controls, flat surfaces and existing focus treatment from DESIGN.md.

The first view presents actual saved games in a divided table, with an empty
state when there are none. Replay prioritizes the board and adjacent numbered
moves, with First/Back/Next/Last controls directly beneath the board. Import is
a separate labeled form, not a modal. Do not invent statistics or demo games.

Success: users can find a completed game, inspect every stored position and
download its PGN; paste/upload one PGN, see an actionable validation error or
open the saved replay. Imports must be visibly private and unrated. No replay
action sends a move to a live game. URLs retain history filtering/pagination.

Required states: session loading/anonymous; history loading/empty/error/retry;
invalid or forbidden replay; import pending/error; start/end replay controls;
black-to-move custom FEN starts; long names; narrow windows; light/dark themes.
Keyboard controls must have real text labels and visible focus, with selected
moves exposed through aria-current. The engine, not browser code, validates
imports; the frontend only decodes validated FEN for board rendering.

Verification boundary: component tests and production build are available.
Chromium launch fails with socket() Operation not permitted, so this environment
cannot supply valid current screenshots or claim a browser layout pass.

## Source documentation check

Compared PRODUCT.md and DESIGN.md with history.css, HistoryPage.tsx,
ReplayBoard.tsx, ReplayPage.tsx, and the incumbent styles.css, board.css and
main.tsx. History/replay reuse the self-hosted Manrope stack, semantic light/dark
colors, divided flat surfaces, shared primary/quiet buttons and global focus
outline. The history extension adds no palette literals or surface shadows.
Source confirms the bounded board sizing, preserved return query, heading focus
after replay data loads, and explicit “Back one move” accessible name. These
checks establish implementation intent, not rendered appearance or viewport fit.

Pre-existing drift is recorded without repair: DESIGN.md still contains
account-era statements that gameplay is unbuilt, while PRODUCT.md records the
later implemented phases. The incumbent board.css (also present at HEAD) uses
fixed board colors, inset selected/check highlights and a blue square focus
outline rather than the account palette/flat-surface description. Replay reuses
that board. DESIGN.md and .impeccable/design.json remain unchanged; browser
appearance, narrow-window fit and theme rendering remain unverified.

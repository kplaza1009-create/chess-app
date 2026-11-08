# Accounts surface direction

Mode: Operate. Public home introduces the account flow; /login and /register
complete it; authenticated / shows real account data and starting ratings.

The user asked to review and remake Phases 1 and 2 using the installed plugins
and skills. Gameplay and later phases are outside this task. Preserve the
Chess Room name, routes, auth contract, and server-owned session revocation.

Working direction: a focused chess club. This was offered as an optional
preference question, received no answer, and was stated as the implementation
assumption. No personal Taste preferences were inferred or saved.

DESIGN_VARIANCE: 5. Two columns on wider screens, one focused form on mobile.
MOTION_INTENSITY: 2. Only feedback transitions; respect reduced motion.
VISUAL_DENSITY: 5. Clear form groups and compact, readable rating rows.

Use Manrope, forest-green actions, green-tinted neutral surfaces, and system
light/dark color schemes. Every control has a real account action. The knight
image is decorative and generated, not evidence of a playable game. It is
compressed to WebP and bundled with a content hash.

First viewport: a legible account task paired with a single chess photograph
on desktop; the account task takes the full width on mobile. The notable
interaction is useful focus movement: navigation focuses the new page title;
failed submission focuses the offending field or the error summary. Focus
must not jump away while typing or while tokens refresh.

Quality bar: complete forms and errors, no horizontal overflow from 320px to
1440px, keyboard access, contrast in both themes, no fake stats or dead links,
and session changes that cannot expose delayed data from a previous account.

Impeccable's local launcher was unavailable. The implementation used its
documented craft guidance with direct project context and code-led execution;
no default workflow preference was saved. The independent finish review and
design documentation are still required before delivery.

---
name: Chess Room
description: 'The implemented account interface: green-tinted surfaces, clear forms, and quiet chess imagery.'
colors:
  page: '#f4f6f2'
  surface: '#fcfdfb'
  subtle: '#e9eee7'
  text: '#1b2921'
  muted: '#56635a'
  line: '#d3dcd2'
  field-line: '#7b8d7e'
  accent: '#275b40'
  accent-hover: '#1d4932'
  on-accent: '#f5faf6'
  focus: '#346c46'
  error: '#a3222a'
  error-surface: '#fff0ef'
  error-line: '#e7b9b7'
  dark-page: '#151b17'
  dark-surface: '#1b241e'
  dark-subtle: '#263229'
  dark-text: '#eef3ec'
  dark-muted: '#b0bcae'
  dark-line: '#364439'
  dark-field-line: '#718473'
  dark-accent: '#b5d7a9'
  dark-accent-hover: '#c9e7bf'
  dark-on-accent: '#18251b'
  dark-focus: '#b5d7a9'
  dark-error: '#ffb5b6'
  dark-error-surface: '#3d2426'
  dark-error-line: '#795057'
typography:
  display:
    fontFamily: '"Manrope Variable", "Manrope", sans-serif'
    fontSize: 3.8rem
    fontWeight: 650
    lineHeight: 1.1
    letterSpacing: -.04em
  headline:
    fontFamily: '"Manrope Variable", "Manrope", sans-serif'
    fontSize: 2.5rem
    fontWeight: 650
    lineHeight: 1.14
    letterSpacing: -.035em
  title:
    fontFamily: '"Manrope Variable", "Manrope", sans-serif'
    fontSize: 1.25rem
    fontWeight: 650
    letterSpacing: -.025em
  body:
    fontFamily: '"Manrope Variable", "Manrope", sans-serif'
  label:
    fontFamily: '"Manrope Variable", "Manrope", sans-serif'
    fontSize: .85rem
    fontWeight: 650
  button:
    fontFamily: '"Manrope Variable", "Manrope", sans-serif'
    fontSize: .875rem
    fontWeight: 650
  field:
    fontFamily: '"Manrope Variable", "Manrope", sans-serif'
    fontSize: 1rem
    lineHeight: 1.5
  helper:
    fontFamily: '"Manrope Variable", "Manrope", sans-serif'
    fontSize: .75rem
    lineHeight: 1.6
  rating-value:
    fontFamily: '"Manrope Variable", "Manrope", sans-serif'
    fontSize: 1.6rem
    fontWeight: 650
    letterSpacing: -.025em
rounded:
  control: 12px
  container: 16px
  brand-mark: 10px
  password-toggle: 9px
  avatar: 50%
spacing:
  space-8: 8px
  space-16: 16px
  space-24: 24px
  space-28: 28px
  space-32: 32px
  space-40: 40px
  space-56: 56px
  space-72: 72px
components:
  button-primary:
    backgroundColor: '{colors.accent}'
    textColor: '{colors.on-accent}'
    typography: '{typography.button}'
    rounded: '{rounded.control}'
    padding: 12px 22px
  button-primary-hover:
    backgroundColor: '{colors.accent-hover}'
  button-quiet:
    textColor: '{colors.text}'
    typography: '{typography.button}'
    rounded: '{rounded.control}'
    padding: 10px 17px
  button-quiet-hover:
    backgroundColor: '{colors.subtle}'
  text-field:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.text}'
    typography: '{typography.field}'
    rounded: '{rounded.control}'
    padding: 12px 15px
    width: 100%
  account-card:
    backgroundColor: '{colors.subtle}'
    textColor: '{colors.text}'
    rounded: '{rounded.container}'
    padding: 28px
  error-banner:
    backgroundColor: '{colors.error-surface}'
    textColor: '{colors.error}'
    rounded: '{rounded.control}'
    padding: 14px 16px
  avatar:
    backgroundColor: '{colors.accent}'
    textColor: '{colors.on-accent}'
    rounded: '{rounded.avatar}'
    width: 52px
    height: 52px
  account-status:
    textColor: '{colors.accent}'
  button-primary-dark:
    backgroundColor: '{colors.dark-accent}'
    textColor: '{colors.dark-on-accent}'
  button-primary-hover-dark:
    backgroundColor: '{colors.dark-accent-hover}'
  button-quiet-dark:
    textColor: '{colors.dark-text}'
  button-quiet-hover-dark:
    backgroundColor: '{colors.dark-subtle}'
  text-field-dark:
    backgroundColor: '{colors.dark-surface}'
    textColor: '{colors.dark-text}'
  account-card-dark:
    backgroundColor: '{colors.dark-subtle}'
    textColor: '{colors.dark-text}'
  error-banner-dark:
    backgroundColor: '{colors.dark-error-surface}'
    textColor: '{colors.dark-error}'
  avatar-dark:
    backgroundColor: '{colors.dark-accent}'
    textColor: '{colors.dark-on-accent}'
  account-status-dark:
    textColor: '{colors.dark-accent}'
---

# Design System: Chess Room

## Overview

**Creative North Star: "A focused chess club"**

The focused chess club is the working implementation assumption behind the current account interface. It was stated after an optional preference question received no answer; it is not a user-selected identity or a saved personal Taste preference. This document records the code now present, rather than prescribing the appearance of unbuilt gameplay.

Chess Room pairs a single green accent with green-tinted neutral surfaces, self-hosted Manrope, and a small set of flat controls. Spacing gives headings and forms room to breathe while rating rows remain compact. A generated knight photograph is decorative context; it does not imply that online play exists. No visual anti-reference was confirmed.

**Key Characteristics:**

- One type family, with weight and scale carrying hierarchy.
- System light and dark schemes using the same semantic color roles.
- Flat surfaces, visible field boundaries, and restrained control feedback.
- Rounded controls and containers, with a circular initial avatar.
- Semantic forms, useful focus movement, and truthful account states.

## Colors

The palette uses forest green in light mode and pale green in dark mode, surrounded by green-tinted neutrals. Exact colors are normative in the frontmatter; `dark-` entries are the automatic `prefers-color-scheme: dark` counterparts, not a separate selectable product theme.

### Primary

- **Forest action / pale-green action** (`accent`, `dark-accent`): primary buttons, the brand mark, avatar, status and rating icons, caret, and text selection.
- **Action hover** (`accent-hover`, `dark-accent-hover`): primary button hover.
- **On-action ink** (`on-accent`, `dark-on-accent`): text and icons placed on the accent fill.
- **Focus green** (`focus`, `dark-focus`): visible keyboard focus outlines. The dark focus role currently shares the dark accent value.

### Neutral

| Light token | Dark counterpart | Implemented use |
| --- | --- | --- |
| `page` | `dark-page` | Full-page background |
| `surface` | `dark-surface` | Input fill |
| `subtle` | `dark-subtle` | Account card, skeleton blocks, quiet hover fills |
| `text` | `dark-text` | Primary text |
| `muted` | `dark-muted` | Explanations, hints, metadata, footer |
| `line` | `dark-line` | Header and rating dividers, quiet-button borders, link underlines |
| `field-line` | `dark-field-line` | Resting input outline and the small introductory rule |
| `error` | `dark-error` | Error text, invalid-field outline |
| `error-surface` | `dark-error-surface` | Error summary fill |
| `error-line` | `dark-error-line` | Error summary outline |

The error trio is semantic feedback, not an additional decorative accent. The photograph retains its own fixed artwork colors and is not recolored by system theme. The sidecar contains synthesized tonal ramps for palette previews; those ramps are not additional runtime tokens.

**The Semantic Theme Rule.** Use the existing semantic color role in both system schemes; do not apply a light-theme literal to an interactive surface that must also work in dark mode.

**The Visible Boundary Rule.** Use field-line for resting input boundaries and line for quieter dividers; the two roles are intentionally different.

## Typography

**Display Font:** Manrope Variable (with Manrope and sans-serif fallbacks).

**Body Font:** The same stack. It is self-hosted through `@fontsource-variable/manrope`, imported once in the frontend entry point. There is no separate serif or monospaced interface font.

**Character:** The implemented hierarchy relies on moderately heavy headings, compact labels, and lighter supporting copy. Headings use balanced wrapping and slightly negative tracking. The code uses discrete responsive sizes, not a fluid type clamp or a single mathematical scale.

### Hierarchy

- **Display:** The public-home heading uses the display token; its size steps down at the wide, compact, and phone breakpoints (3.1rem, 3rem, and 2.55rem).
- **Headline:** Authentication and account headings use the headline token. The base heading reduces on compact screens (2.25rem); the account heading reduces further (2rem). Session failure and not-found headings also use that smaller size.
- **Title:** Section headings use the title token; the account-card title is smaller (1rem). Rating row labels use a compact size (.95rem) and semibold weight (600).
- **Body:** Paragraph sizes are contextual. Authentication introductions are compact (.925rem, line-height 1.65); the public introduction is larger (1.025rem, line-height 1.8), becoming smaller on compact screens (.95rem). Muted copy is paired with primary text, not substituted for it.
- **Label / button / field / helper:** These exact reusable roles are in the frontmatter. Inputs retain normal-size text; hints and errors share the helper role. Labels and buttons use weight to remain legible at smaller sizes.
- **Rating value:** The rating-value token is paired with tabular numerals and right-aligned metadata. The artwork caption uses its own larger, medium-weight treatment (2.8rem, weight 550, line-height 1.13), reducing at the wide breakpoint (2.3rem).

**The Single Family Rule.** Keep interface text in the self-hosted Manrope stack; distinguish headings, labels, and data through the implemented sizes and weights.

## Layout

The shell is a vertical flex layout with a minimum viewport height (`100dvh`), a growing main region, and a footer. The shared content width is capped (1200px) with horizontal gutters (40px per side); compact screens use smaller gutters (20px per side). The header has a minimum height (80px), reducing on compact screens (72px). The footer uses the same shared width.

Authentication uses equal columns with a generous gap (72px) and a centered form panel capped at a comfortable width (390px). At the wide breakpoint the gap and form cap tighten (40px and 350px). Below the compact breakpoint the layout becomes one column, the form cap expands (420px), and its decorative artwork is hidden. The public home uses a slightly wider text column (1.1fr / 1fr); its image remains as a shorter block below the copy on compact screens.

The authenticated account uses a flexible ratings column and a fixed details column (320px), separated by a large gap (80px). Those reduce at the wide breakpoint (290px and 40px), then stack at the compact breakpoint. Rating rows are a three-column grid (36px / flexible / auto), with a minimum row height (96px). Long usernames and account details wrap; the navigation username truncates when needed.

Responsive thresholds are inclusive `max-width` queries: wide (1100px), compact (767px), and phone (479px). At phone width, the secondary registration navigation action and navigation username are hidden; the account flow remains reachable from the main content. Primary-button horizontal padding and the rating-row gap reduce. The footer can wrap.

The spacing frontmatter records recurring observed distances, not an existing utility-only scale. Preserve component-specific spacing where it serves a purpose: form groups have a small internal gap (9px), form rows have a larger gap (24px), and the form starts below its introduction (32px). Keep these relationships when extending the account surfaces.

## Elevation & Depth

The current interface has no box shadows. Page, input, and subtle surfaces provide tonal separation; thin dividers organize the header and rating rows. The account card is distinguished by its fill, while the photograph gains depth from the image itself. Focus is an outline, not a shadow or glow.

**The Flat Surface Rule.** Use tonal contrast and dividers for structure; the current interface has no box shadows.

## Shapes

Controls, error banners, and skeleton blocks use the shared control radius. Larger containers and the artwork use the container radius. The brand mark and password-visibility control have their own smaller corner radii; the avatar is circular. These exact values are in the frontmatter. Borders are thin (1px), with a stronger semantic color for fields and errors rather than a thicker default stroke.

The photograph is clipped to its container and covers the available area. It is a decorative, locally bundled WebP with explicit intrinsic dimensions. It is hidden from assistive technology, including its caption. It is not a gameplay preview.

## Components

### Buttons

Primary actions are filled, comfortably sized controls. Their minimum height is generous (48px), with inline arrow icons separated from the label. Authentication submit buttons fill the form width, use a slightly taller minimum (50px), and distribute the label and arrow across the row. Quiet actions use a transparent fill, the quiet divider border, and a smaller minimum height (42px).

Hover changes the primary fill or adds the subtle fill to a quiet action. Pressing an enabled button translates it slightly downward (1px). Those changes use short CSS transitions (160ms, ease). Disabled buttons use a wait cursor and reduced opacity (.64); the label explains the busy state. No spinner is required by the implemented pattern. The narrowest breakpoint reduces primary-button horizontal padding (18px).

Global keyboard focus uses an offset outline (3px with 4px offset). Reduced-motion preferences remove transitions. The password toggle is an icon-only exception with a meaningful accessible name and a pressed state.

### Inputs / Fields

Inputs use the surface fill, field-line border, shared control radius, full width, and a minimum height (50px). Their padding is in the frontmatter. Hover changes the boundary to accent. Keyboard focus uses an accent border and a closer focus outline (2px with 2px offset). Invalid fields use the error boundary, with associated text feedback; disabled inputs reduce opacity (.72).

Labels remain visible above the fields. Hints and inline errors are connected through `aria-describedby`; invalid fields set `aria-invalid`. The password input reserves right-hand space (52px) for its visibility control, whose target is comfortably sized (42px square). Form submission disables the fields and controls and sets `aria-busy`.

After failed submission, focus moves to the first invalid field, or to the error summary for a general failure. Route navigation focuses the new page heading. This behavior is scoped so typing and background session refreshes do not pull focus away.

### Error summaries

The summary combines the error surface, border, text, and an inline Phosphor warning icon. It uses the shared control radius and compact readable copy (.825rem, line-height 1.65). Form summaries are alerts and can receive programmatic focus. Logout failure uses the same pattern above the page content. Text explains the problem; color is additional feedback.

### Navigation

The header combines the filled knight brand mark and Chess Room wordmark with a compact right-side navigation row. Anonymous navigation shows relevant sign-in and create-account routes; authenticated navigation shows a username and sign-out action. Text links underline on hover and use the global focus treatment. The small-screen visibility changes are described in Layout. There are no dead menu items or placeholders for later features.

A skip link becomes visible when focused. The main region is programmatically focusable, while heading and main focus do not add a decorative outline; ordinary interactive elements retain visible keyboard focus.

### Cards / Containers

The account-details card is a flat subtle surface with the container radius and roomy internal padding, reducing on compact screens (24px). It contains a circular initial avatar, a small heading, and a definition list of actual account data. It has neither a border nor a shadow. Account values wrap instead of expanding the page width.

### Rating rows and account status

Ratings use a divided list, not separate cards. Each row pairs a Phosphor pace icon, a readable pace label, and a right-aligned tabular rating with compact metadata. The metadata distinguishes starting ratings from completed rated games. The account-ready indicator is plain accent-colored text with a check icon; it is not a filled chip or a control.

The empty-state copy explains that online play is being built. No play action, match feed, testimonial, or fabricated statistic is included in the delivered account scope.

### Session feedback

Session restoration uses a short status message and three static skeleton bars; the final bar is shorter (65% width). The loading region is busy, and the skeleton is hidden from assistive technology. Session failure supplies an alert and a real retry action. The not-found surface uses the same limited-width message-and-action pattern. These states introduce no new visual vocabulary or animated shimmer.

## Do's and Don'ts

### Do:

- Do reuse the semantic light/dark color pairs and the self-hosted Manrope stack.
- Do preserve the distinction between field boundaries, quiet dividers, and focus outlines.
- Do keep form labels, inline error descriptions, busy feedback, and keyboard focus visible.
- Do use the Phosphor icon family and hide decorative icons from assistive technology.
- Do let long account values wrap and allow header actions to adapt at small widths.
- Do describe stored initial ratings as starting ratings and unfinished play as being built.

### Don't:

- Don't add shadows to reproduce depth that the current system expresses with tones and dividers.
- Don't turn every rating row into a separate elevated card; the implemented pattern is a divided list.
- Don't replace text labels or feedback with color or icons alone.
- Don't keep the desktop authentication photograph beside the form below the compact breakpoint.
- Don't add looping, entrance, or parallax animation to the current feedback-only motion vocabulary.
- Don't present this working direction as a learned personal preference or imply that gameplay is already available.

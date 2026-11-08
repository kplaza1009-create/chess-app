# Assets and notices

## Chess photograph

`frontend/src/assets/chess-knight.webp` is a decorative asset generated with the
built-in ImageGen tool for this remake. It is not a photograph of a real game,
evidence of gameplay, or a reference to a player. It is 1086 by 1448 pixels.
The selected generated PNG was encoded as WebP at quality 82 for delivery;
the shipped file is approximately 75 kB. No visual retouching was applied.

Final generation prompt:

```text
Use case: photorealistic-natural. Asset type: photographic background for Chess Room web application account pages, portrait 3:4 composition. Primary request: a beautifully simple editorial still-life of a real carved black wooden Staunton knight chess piece in close-up on a muted sage green chess table. A second pale ivory pawn sits out of focus farther behind it. Contemporary chess club atmosphere, honest tactile wood grain, soft natural window light from upper left, deep charcoal shadows, restrained forest green and off-white colors. The knight occupies the center-lower part of the frame, with generous clean negative space in the upper third for UI copy that will be implemented separately. Shot on a medium-format camera, shallow depth of field, subtle photographic texture. Cropped table surface, no need for full board or a chess position. No people, no hands, no text, no logos, no watermarks, no borders, no fake interface, no gradients or CGI gloss.
```

## Typeface and icons

Manrope is self-hosted through `@fontsource-variable/manrope`. Phosphor icons
come from `@phosphor-icons/react`. Their upstream notices are included in
`frontend/public/licenses/manrope.txt` and `frontend/public/licenses/phosphor.txt`
and copied into production frontend output by Vite.

Other dependencies remain declared and locked rather than vendored into the
source archive. Preserve upstream notices when distributing a compiled build.

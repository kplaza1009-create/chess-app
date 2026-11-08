// Original vector artwork: same geometry on every browser, with no emoji fallback.
export const piecePaths: Record<string, string> = {
  "p": "M18 17a6 6 0 1 0 12 0a6 6 0 1 0-12 0M20 23h8l3 12H17z",
  "r": "M14 10h5v5h3v-5h4v5h3v-5h5v12l-5 3 2 10H17l2-10-5-3z",
  "n": "M16 35l1-8 9-7-8 1-5-4 5-8 6-3 2 5c9 4 9 15 7 24zM22 14h2",
  "b": "M24 6c-3 4-9 8-9 13 0 5 4 7 9 7s9-2 9-7c0-5-6-9-9-13zM25 12l-5 8M21 26h6l4 9H17z",
  "q": "M12 15l5 20h14l5-20-8 8-4-12-4 12zM9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0M21 8a3 3 0 1 0 6 0a3 3 0 1 0-6 0M33 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
  "k": "M24 5v10M20 9h8M24 17c-14-9-16 8-7 12l1 6h12l1-6c9-4 7-21-7-12z"
};

export function Piece({ piece }: { piece: string }) {
  const white = piece === piece.toUpperCase();
  return <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false" width="100%" height="100%">
    <g fill={white ? "#fffdf0" : "#17291e"} stroke={white ? "#17291e" : "#e6e9d6"}
      strokeWidth="1.7" strokeLinejoin="round" strokeLinecap="round">
      <path d={piecePaths[piece.toLowerCase()]} />
      <path d="M16 35h16l3 6H13z" />
    </g>
  </svg>;
}

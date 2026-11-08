import knightImage from "../assets/chess-knight.webp";

export function ChessArtwork({ compact = false }: { compact?: boolean }) {
  return <figure className={`chess-artwork${compact ? " chess-artwork-compact" : ""}`} aria-hidden="true">
    <img src={knightImage} alt="" width={1086} height={1448}
      fetchPriority="high" decoding="async" />
    {!compact && <figcaption>
      <span className="artwork-title">A little space<br />to think.</span>
    </figcaption>}
  </figure>;
}

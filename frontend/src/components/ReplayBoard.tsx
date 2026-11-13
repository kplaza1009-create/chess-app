import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { replayPosition, resultLabel, type Replay } from "../api/history";
import { Chessboard } from "./Chessboard";
import "../board.css";
import "../history.css";

export function ReplayBoard({ game }: { game: Replay }) {
  const [ply, setPly] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const moveList = useRef<HTMLOListElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  const current = game.moves[ply - 1];
  const fen = current?.fen_after ?? game.initial_fen;
  const initial = game.initial_fen.split(" ");
  const blackFirst = initial[1] === "b";
  const startNumber = Number(initial[5]);
  const select = (value: number) => setPly(Math.max(0, Math.min(game.moves.length, value)));
  useEffect(() => {
    const selected = moveList.current?.querySelector<HTMLElement>('[aria-current="step"]');
    if (selected && moveList.current) {
      const list = moveList.current;
      if (selected.offsetTop < list.scrollTop) list.scrollTop = selected.offsetTop;
      else if (selected.offsetTop + selected.offsetHeight > list.scrollTop + list.clientHeight)
        list.scrollTop = selected.offsetTop + selected.offsetHeight - list.clientHeight;
    }
  }, [ply]);
  function keyboard(event: KeyboardEvent<HTMLElement>) {
    if ((event.target as HTMLElement).closest(".chessboard, textarea")) return;
    const target = event.key === "ArrowLeft" ? ply - 1 : event.key === "ArrowRight" ? ply + 1 :
      event.key === "Home" ? 0 : event.key === "End" ? game.moves.length : null;
    if (target !== null) { event.preventDefault(); select(target); }
  }
  function download() {
    setDownloadError(null);
    try {
      const url = URL.createObjectURL(new Blob([game.pgn], { type: "application/x-chess-pgn;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url; link.download = `chess-room-${game.id}.pgn`;
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setDownloadError("Could not download the PGN. Try again."); }
  }
  return <section className="replay" aria-label="Game replay" onKeyDown={keyboard}>
    <div className="replay-summary"><h1 ref={heading} tabIndex={-1}>{game.headers.White ?? "?"} <span>vs</span> {game.headers.Black ?? "?"}</h1>
      <p>{game.termination === "aborted" ? "Aborted" : resultLabel(game.result)} · {game.result}
        {game.termination && ` · ${game.termination.replaceAll("_", " ")}`}
        {game.source === "import" && " · Imported, unrated"}</p>
    </div>
    <div className="replay-layout"><div className="board-column">
      <div className="player-strip"><span>{game.headers[flipped ? "White" : "Black"] ?? "?"}</span>
        <span>{game.headers[flipped ? "WhiteElo" : "BlackElo"] ?? ""}</span></div>
      <Chessboard state={replayPosition(fen)} flipped={flipped} busy={false} readOnly lastMove={current?.uci ?? null} onMove={() => {}} />
      <div className="player-strip"><span>{game.headers[flipped ? "Black" : "White"] ?? "?"}</span>
        <span>{game.headers[flipped ? "BlackElo" : "WhiteElo"] ?? ""}</span></div>
      <div className="replay-controls" role="group" aria-label="Replay controls">
        <button className="button-quiet" disabled={ply === 0} onClick={() => select(0)} aria-label="First position">First</button>
        <button className="button-quiet" disabled={ply === 0} onClick={() => select(ply - 1)} aria-label="Back one move">Back</button>
        <button className="button-quiet" disabled={ply === game.moves.length} onClick={() => select(ply + 1)} aria-label="Next move">Next</button>
        <button className="button-quiet" disabled={ply === game.moves.length} onClick={() => select(game.moves.length)} aria-label="Last position">Last</button>
      </div>
      <p className="replay-position" role="status">{ply === 0 ? "Starting position" : `Ply ${ply} of ${game.moves.length} · ${current?.san}`}</p>
      <p id="replay-help" className="board-hint">Read-only replay. Use the controls or choose a move. Left/Right and Home/End work on the replay controls.</p>
    </div><aside className="replay-sidebar">
      <div className="board-actions"><button className="button-quiet" onClick={() => setFlipped(value => !value)}>Flip board</button>
        <button className="button-quiet" onClick={download}>Download PGN</button></div>
      {downloadError && <p role="alert" className="error-banner">{downloadError}</p>}
      <h2>Moves</h2>
      {game.moves.length === 0 && <p>No moves were recorded.</p>}
      <ol ref={moveList} className="replay-moves" aria-label="Recorded moves">{game.moves.map((move, index) => {
        const black = (index + Number(blackFirst)) % 2 === 1;
        const label = `${startNumber + Math.floor((index + Number(blackFirst)) / 2)}${black ? "..." : "."}`;
        return <li key={index}><button className="replay-move" aria-current={ply === index + 1 ? "step" : undefined}
          aria-label={`Go to move ${label} ${move.san}`} onClick={() => select(index + 1)}>
          <span>{label}</span> {move.san}</button></li>;
      })}</ol>
      <details className="replay-details"><summary>Game details</summary><dl>{Object.entries(game.headers).map(([name, value]) =>
        <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl>
        <label htmlFor="replay-fen">Current FEN</label><textarea id="replay-fen" readOnly value={fen} rows={3} /></details>
    </aside></div>
  </section>;
}

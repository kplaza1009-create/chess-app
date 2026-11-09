import { useEffect, useRef, useState } from "react";
import { loadPosition, START_FEN, type BoardState } from "../api/board";
import { Chessboard } from "../components/Chessboard";
import { errorMessage } from "../auth/session";
import "../board.css";

type Entry = { state: BoardState; move: string | null };
export function BoardPage() {
  const [history, setHistory] = useState<Entry[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flipped, setFlipped] = useState(false);
  const [fen, setFen] = useState(START_FEN);
  const sequence = useRef(0);
  const pending = useRef(false);
  const entry = history.at(-1);

  async function update(position: string, move?: string) {
    if (pending.current) return;
    pending.current = true;
    const id = ++sequence.current;
    setBusy(true); setError(null);
    try {
      const state = await loadPosition(position, move);
      if (id !== sequence.current) return;
      const next = { state, move: move ?? null };
      setHistory(previous => move ? [...previous, next] : [next]);
      setFen(state.fen);
    } catch (failure: unknown) {
      if (id === sequence.current) setError(errorMessage(failure));
    } finally {
      if (id === sequence.current) { setBusy(false); pending.current = false; }
    }
  }
  useEffect(() => {
    void update(START_FEN);
    return () => { sequence.current++; pending.current = false; };
  }, []);
  const state = entry?.state;
  const turn = state?.turn === "b" ? "Black" : "White";
  const status = state?.ending === "checkmate"
    ? `Checkmate — ${state.turn === "w" ? "Black" : "White"} wins`
    : state?.ending ? `Draw — ${state.ending.replaceAll("_", " ")}`
    : `${turn} to move${state?.check ? " — check" : ""}`;
  return <section className="practice page-width">
    <div className="practice-heading"><div><p className="eyebrow">THE PRACTICE ROOM</p><h1 tabIndex={-1}>Your next move.</h1></div><span className="practice-label">Local · Unrated</span></div>
    <div className="board-toolbar">
      <div role="status"><h2 className="turn-status">{busy ? "Checking position…" : state ? status : "Let’s set up"}</h2></div>
      <div className="board-actions"><button className="button-quiet" disabled={busy || history.length < 2} onClick={() => { const previous = history.at(-2); if (previous) { setHistory(history.slice(0, -1)); setFen(previous.state.fen); } }}>Undo move</button>
        <button className="button-quiet" disabled={busy} onClick={() => setFlipped(!flipped)}>Flip board</button>
        <button className="button-primary" disabled={busy} onClick={() => { void update(START_FEN); }}>Reset board</button></div>
    </div>
    <div className="practice-layout"><div className="board-column">
      <div className="player-strip"><span className={`player-disc ${flipped ? "white-disc" : "black-disc"}`} />{flipped ? "White" : "Black"}<span>Local player</span></div>
      {state ? <Chessboard state={state} flipped={flipped} busy={busy} lastMove={entry.move}
        onMove={move => { void update(state.fen, move); }} /> : <div className="board-loading" role="status">{busy ? "Preparing your board…" : "Board unavailable"}</div>}
      <div className="player-strip"><span className={`player-disc ${flipped ? "black-disc" : "white-disc"}`} />{flipped ? "Black" : "White"}<span>Local player</span></div>
    </div><aside className="board-sidebar">
      <p className="eyebrow">ON THE BOARD</p>
      <p id="board-help">Play both sides. Drag a piece, or select it and then its destination. On a keyboard, use arrow keys and Enter. Escape clears selection.</p>
      {error && <div className="error-banner" role="alert"><p>{error}</p><button className="button-quiet" disabled={busy} onClick={() => { void update(state?.fen ?? START_FEN); }}>Reload position</button></div>}
      <section className="practice-note"><h2>A place to explore</h2><p>This board checks every move with our chess engine. Positions are kept only in this tab; refresh starts a new board. Online games and clocks arrive in later phases.</p><p>Repetition claims and saved game history are not tracked in this practice view.</p></section>
      <details className="position-tools"><summary>Set up a position</summary><form onSubmit={event => { event.preventDefault(); void update(fen); }}>
        <label htmlFor="fen">FEN position</label><textarea id="fen" value={fen} onChange={event => setFen(event.target.value)} maxLength={120} required disabled={busy} spellCheck={false} />
        <button className="button-quiet" disabled={busy}>Load position</button></form></details>
    </aside></div>
  </section>;
}

import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { squareName, type BoardState } from "../api/board";
import { Piece } from "./Piece";

const names: Record<string, string> = { p: "pawn", r: "rook", n: "knight", b: "bishop", q: "queen", k: "king" };
type Props = {
  state: BoardState; flipped: boolean; busy: boolean; lastMove: string | null;
  onMove: (move: string) => void;
};

export function Chessboard({ state, flipped, busy, lastMove, onMove }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [promotion, setPromotion] = useState<string[]>([]);
  const [focus, setFocus] = useState("e2");
  const [drag, setDrag] = useState<{ source: string; x: number; y: number; piece: string } | null>(null);
  const origin = useRef<{ source: string; x: number; y: number; piece: string } | null>(null);
  const moved = useRef(false);
  const board = useRef<HTMLDivElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { setSelected(null); setPromotion([]); setDrag(null); origin.current = null; }, [state.fen]);
  const locked = busy || state.ending !== null;
  const squares = Array.from({ length: 64 }, (_, i) => flipped
    ? (Math.floor(i / 8) * 8 + 7 - i % 8) : ((7 - Math.floor(i / 8)) * 8 + i % 8));
  const legal = state.legal_moves.filter(move => move.slice(0, 2) === selected);

  function attempt(source: string, target: string): boolean {
    const choices = state.legal_moves.filter(move => move.startsWith(source + target));
    if (!choices.length || locked) return false;
    if (choices.length > 1) {
      setPromotion(choices);
      dialog.current?.showModal();
    } else if (choices[0]) {
      setSelected(null);
      onMove(choices[0]);
    }
    return true;
  }
  function select(name: string) {
    if (locked) return;
    if (selected && attempt(selected, name)) return;
    setSelected(selected === name ? null : state.legal_moves.some(m => m.startsWith(name)) ? name : null);
  }
  function keyboard(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    moved.current = false;
    if (event.key === "Escape") { setSelected(null); return; }
    const steps: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -8, ArrowDown: 8 };
    const step = steps[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const next = index + step;
    if (next < 0 || next >= 64 || (Math.abs(step) === 1 && Math.floor(next / 8) !== Math.floor(index / 8))) return;
    const square = squares[next];
    if (square === undefined) return;
    const name = squareName(square);
    setFocus(name);
    board.current?.querySelector<HTMLButtonElement>(`[data-square="${name}"]`)?.focus();
  }
  function start(event: PointerEvent<HTMLButtonElement>, name: string, piece: string) {
    if (locked || event.isPrimary === false || event.button !== 0 || !state.legal_moves.some(m => m.startsWith(name))) return;
    origin.current = { source: name, x: event.clientX, y: event.clientY, piece };
    moved.current = false;
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function moving(event: PointerEvent<HTMLButtonElement>) {
    const from = origin.current;
    if (!from) return;
    if (Math.hypot(event.clientX - from.x, event.clientY - from.y) > 5) moved.current = true;
    if (moved.current) { setSelected(from.source); setDrag({ ...from, x: event.clientX, y: event.clientY }); }
  }
  function finish(event: PointerEvent<HTMLButtonElement>) {
    const from = origin.current;
    origin.current = null;
    setDrag(null);
    if (!from || !moved.current) return;
    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>("[data-square]");
    if (target && board.current?.contains(target) && target.dataset.square) attempt(from.source, target.dataset.square);
  }
  function cancelPromotion() { dialog.current?.close(); setPromotion([]); }

  return <>
    <div className="chessboard" ref={board} role="group" aria-label="Chessboard" aria-busy={busy}
      aria-describedby="board-help">
      {squares.map((square, index) => {
        const name = squareName(square);
        const piece = state.board[square] ?? ".";
        const white = piece !== "." && piece === piece.toUpperCase();
        const destination = legal.some(move => move.slice(2, 4) === name);
        const check = state.check && piece === (state.turn === "w" ? "K" : "k");
        const last = lastMove?.slice(0, 2) === name || lastMove?.slice(2, 4) === name;
        return <button key={name} type="button" data-square={name} tabIndex={focus === name ? 0 : -1}
          aria-label={`${name}, ${piece === "." ? "empty" : `${white ? "White" : "Black"} ${names[piece.toLowerCase()]}`}${destination ? ", legal destination" : ""}${check ? ", in check" : ""}`}
          aria-pressed={selected === name} aria-disabled={locked}
          className={`square ${(Math.floor(square / 8) + square % 8) % 2 ? "light" : "dark"}${selected === name ? " selected" : ""}${last ? " last" : ""}${check ? " checked" : ""}`}
          onFocus={() => setFocus(name)} onKeyDown={event => keyboard(event, index)}
          onClick={() => { if (moved.current) { moved.current = false; return; } select(name); }}
          onPointerDown={event => start(event, name, piece)} onPointerMove={moving} onPointerUp={finish}
          onPointerCancel={() => { origin.current = null; moved.current = false; setDrag(null); }}
          onLostPointerCapture={() => { origin.current = null; setDrag(null); }}>
          {index % 8 === 0 && <span className="rank" aria-hidden="true">{name[1]}</span>}
          {index >= 56 && <span className="file" aria-hidden="true">{name[0]}</span>}
          {piece !== "." && <span aria-hidden="true" className={`piece${drag?.source === name ? " dragging" : ""}`}><Piece piece={piece} /></span>}
          {destination && <span aria-hidden="true" className={piece === "." ? "move-dot" : "capture-ring"} />}
        </button>;
      })}
    </div>
    {drag && <span aria-hidden="true" className="drag-piece piece"
      style={{ left: drag.x, top: drag.y }}><Piece piece={drag.piece} /></span>}
    {state.ending === null && <p className="board-selection" role="status">{selected ? `${selected} selected. ${new Set(legal.map(m => m.slice(2, 4))).size} legal destinations.` : "Select a piece to see its legal moves."}</p>}
    <dialog ref={dialog} className="promotion-dialog" aria-labelledby="promotion-title" onCancel={() => setPromotion([])}>
      <h2 id="promotion-title">Promote your pawn</h2>
      <p>Choose the piece to complete your move.</p>
      <div className="promotion-options">{promotion.map(move => <button key={move} className="button-quiet"
        onClick={() => { cancelPromotion(); setSelected(null); onMove(move); }}>{names[move[4] ?? "q"]}</button>)}</div>
      <button className="button-quiet" onClick={cancelPromotion}>Cancel</button>
    </dialog>
  </>;
}

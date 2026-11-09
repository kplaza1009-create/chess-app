import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";
import { boardSchema } from "../api/board";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { errorMessage } from "../auth/session";
import { Chessboard } from "../components/Chessboard";
import { GameClock } from "../components/GameClock";
import "../board.css";

export const gameStateSchema = z.object({
  type: z.literal("state"), id: z.uuid(), version: z.number().int().nonnegative(),
  color: z.enum(["w", "b"]), result: z.enum(["*", "1-0", "0-1", "1/2-1/2"]),
  position: boardSchema,
  clock: z.object({ white_ms: z.number().nonnegative(), black_ms: z.number().nonnegative(),
    running: z.boolean(), timed: z.boolean(), initial_ms: z.number().positive(),
    increment_ms: z.number().nonnegative() }).optional(),
  moves: z.array(z.object({ uci: z.string(), san: z.string(), request_id: z.uuid() })).max(20000),
});
type GameState = z.infer<typeof gameStateSchema> & { receivedAt: number };

export function GamePage() {
  const { id } = useParams();
  const { user, status, session } = useAuth();
  const navigate = useNavigate();
  const [opponent, setOpponent] = useState("");
  const [timeControl, setTimeControl] = useState("10+0");
  const [state, setState] = useState<GameState | null>(null);
  const [connection, setConnection] = useState("Connecting…");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const socket = useRef<WebSocket | null>(null);
  const pending = useRef<string | null>(null);
  const pendingVersion = useRef(-1);
  const moveTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    setState(null); setError(null); setBusy(false); setConnection("Connecting…"); pending.current = null;
    if (!id || !user) return;
    if (!z.uuid().safeParse(id).success) { setError("Invalid game link"); return; }
    let stopped = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let watchdog: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    const handleOffline = () => {
      if (stopped) return;
      setConnection("Reconnecting…"); setBusy(false); pending.current = null;
      socket.current?.close();
    };
    window.addEventListener("offline", handleOffline);
    const schedule = () => {
      if (stopped) return;
      setConnection("Reconnecting…"); setBusy(false); pending.current = null;
      retry = setTimeout(() => { void connect(); }, Math.min(1000 * 2 ** attempts++, 15000) + Math.random() * 500);
    };
    async function connect() {
      try {
        const ticket = await session.authorized(`/games/${id}/ticket`, z.object({ token: z.string() }));
        if (stopped) return;
        const ws = new WebSocket(`${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/v1/games/${id}/ws`);
        socket.current = ws;
        watchdog = setTimeout(() => ws.close(), 10000);
        ws.onopen = () => ws.send(JSON.stringify({ type: "auth", token: ticket.token }));
        ws.onmessage = event => {
          if (stopped || socket.current !== ws) return;
          try {
            const data: unknown = JSON.parse(String(event.data));
            clearTimeout(watchdog);
            watchdog = setTimeout(() => ws.close(), 45000);
            if (z.object({ type: z.literal("heartbeat") }).safeParse(data).success) return;
            const parsed = gameStateSchema.safeParse(data);
            if (parsed.success && parsed.data.id === id) {
              attempts = 0;
              setState(previous => !previous || parsed.data.version >= previous.version ? { ...parsed.data, receivedAt: performance.now() } : previous);
              setError(null);
              setConnection("Connected");
              if (!pending.current || parsed.data.version > pendingVersion.current) {
                setBusy(false); pending.current = null; clearTimeout(moveTimer.current);
              }
            } else {
              const failure = z.object({ type: z.literal("error"), message: z.string() }).parse(data);
              setError(failure.message); setBusy(false); pending.current = null;
            }
          } catch { setError("Invalid server message"); ws.close(); }
        };
        ws.onclose = event => {
          clearTimeout(watchdog);
          if (stopped) return;
          if (event.code === 1008) { setConnection("Disconnected"); setError("Connection rejected. Reload to retry."); setBusy(false); return; }
          schedule();
        };
        ws.onerror = () => ws.close();
      } catch (failure: unknown) {
        if (stopped) return;
        setError(errorMessage(failure));
        if (failure instanceof ApiError && [401, 403, 404].includes(failure.status)) {
          setConnection("Unavailable"); return;
        }
        schedule();
      }
    }
    void connect();
    return () => { stopped = true; window.removeEventListener("offline", handleOffline); pending.current = null; clearTimeout(moveTimer.current); clearTimeout(retry); clearTimeout(watchdog); socket.current?.close(); socket.current = null; };
  }, [id, user?.id, session]);

  async function create(event: React.FormEvent) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError(null);
    try {
      const game = await session.authorized("/games", z.object({ id: z.uuid() }), {
        method: "POST", body: JSON.stringify({ opponent: opponent.trim().toLowerCase(), time_control: timeControl }),
      });
      navigate(`/games/${game.id}`);
    } catch (failure: unknown) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }
  if (status === "loading") return <p className="page-width" role="status">Restoring session…</p>;
  if (!user) return <section className="practice page-width"><h1>Online rooms</h1><Link to="/login">Sign in to play</Link></section>;
  const turn = state?.position.turn === "w" ? "White" : "Black";
  const result = state?.result === "1-0" ? "White wins" : state?.result === "0-1" ? "Black wins" : "Draw";
  function clock(color: "w" | "b") {
    if (!state?.clock?.timed) return null;
    return <GameClock color={color === "w" ? "White" : "Black"}
      milliseconds={color === "w" ? state.clock.white_ms : state.clock.black_ms}
      running={state.clock.running && state.position.turn === color}
      receivedAt={state.receivedAt} />;
  }
  return <section className="practice page-width">
    <div className="practice-heading"><h1 tabIndex={-1}>{id ? "Your game" : "Create a room"}</h1><span>Unrated · {id ? state?.clock?.timed ? `${state.clock.initial_ms / 60000}+${state.clock.increment_ms / 1000}` : "No clock" : "Timed play"}</span></div>
    {error && <p className="error-banner" role="alert">{error}</p>}
    {!id ? <form className="room-form" onSubmit={event => { void create(event); }}>
      <label htmlFor="opponent">Opponent’s username</label>
      <input id="opponent" value={opponent} onChange={event => setOpponent(event.target.value)} pattern="[a-zA-Z0-9_]{3,24}" required maxLength={24} />
      <label htmlFor="time-control">Time control</label>
      <select id="time-control" value={timeControl} onChange={event => setTimeControl(event.target.value)}>
        <option value="1+0">Bullet · 1 minute</option>
        <option value="3+2">Blitz · 3 minutes + 2 seconds per move</option>
        <option value="5+0">Blitz · 5 minutes</option>
        <option value="10+0">Rapid · 10 minutes</option>
        <option value="15+10">Rapid · 15 minutes + 10 seconds per move</option>
      </select>
      <p>White’s clock starts when you create the game. Have your opponent ready.</p>
      <p>You play White. Share the resulting page link with this registered player.</p>
      <button className="button-primary" disabled={busy}>Create game</button>
    </form> : <>
      <div className="board-toolbar"><div role="status"><h2 className="turn-status">{state ? state.result === "*" ? `${turn} to move` : `${result} — ${state.position.ending?.replaceAll("_", " ")}` : "Loading game…"}</h2></div><span role="status">{connection}</span></div>
      <div className="practice-layout"><div className="board-column">
        <div className="player-strip"><span>Opponent</span>{clock(state?.color === "b" ? "w" : "b")}</div>
        {state && <Chessboard state={state.position} flipped={state.color === "b"}
          busy={busy || connection !== "Connected" || state.position.turn !== state.color || state.result !== "*"}
          lastMove={state.moves.at(-1)?.uci ?? null} onMove={uci => {
            if (pending.current || socket.current?.readyState !== WebSocket.OPEN) return;
            const requestId = crypto.randomUUID(); pending.current = requestId; pendingVersion.current = state.version;
            setBusy(true); setError(null);
            socket.current.send(JSON.stringify({ type: "move", version: state.version, request_id: requestId, uci }));
            // A missing acknowledgement triggers a fresh snapshot; never blindly replay a move.
            moveTimer.current = setTimeout(() => { if (pending.current === requestId) socket.current?.close(); }, 10000);
          }} />}
        <div className="player-strip"><span>You · {state?.color === "b" ? "Black" : "White"}</span>{clock(state?.color ?? "w")}</div>
        {state?.clock?.timed && <p className="board-hint">Clocks keep running while disconnected. Only the server confirms a timeout.</p>}
      </div><aside className="board-sidebar"><p>Share this page’s URL with your opponent. Only the two players can open this room. Reloading restores confirmed moves.</p>
        <h2>Moves</h2>{state?.moves.length === 0 && <p>No moves yet. White starts.</p>}<ol className="game-moves" aria-label="Move history">{state?.moves.map((move, index) => <li key={move.request_id}>{index % 2 === 0 ? "White" : "Black"}: {move.san}</li>)}</ol>
      </aside></div>
    </>}
  </section>;
}

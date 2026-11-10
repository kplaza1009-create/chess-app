import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { z } from "zod";
import { useAuth } from "../auth/AuthProvider";
import { errorMessage, type AuthSession } from "../auth/session";
import { SessionStatus } from "../components/SessionStatus";
import type { User } from "../types/api";
import "../board.css";

const timeControlSchema = z.enum(["1+0", "3+2", "5+0", "10+0", "15+10"]);
type TimeControl = z.infer<typeof timeControlSchema>;
const timeControls: Record<TimeControl, { label: string; speed: User["ratings"][number]["speed"] }> = {
  "1+0": { label: "Bullet · 1 minute", speed: "bullet" },
  "3+2": { label: "Blitz · 3 minutes + 2 seconds per move", speed: "blitz" },
  "5+0": { label: "Blitz · 5 minutes", speed: "blitz" },
  "10+0": { label: "Rapid · 10 minutes", speed: "rapid" },
  "15+10": { label: "Rapid · 15 minutes + 10 seconds per move", speed: "rapid" },
};
const queueSchema = z.discriminatedUnion("state", [
  z.object({ state: z.literal("idle") }),
  z.object({ state: z.literal("queued"), ticket_id: z.uuid(), time_control: timeControlSchema }),
  z.object({ state: z.literal("matched"), game_id: z.uuid() }),
]);
type Queue = z.infer<typeof queueSchema>;
const path = "/matchmaking";
const pollInterval = 2500;

function Lobby({ session, user }: { session: AuthSession; user: User }) {
  const [queue, setQueue] = useState<Queue | null>(null);
  const [control, setControl] = useState<TimeControl>("10+0");
  const [action, setAction] = useState<"join" | "cancel" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const generation = useRef(0);
  const visit = useRef({ closed: false });
  const liveTicket = useRef<string | null>(null);
  const ticketId = queue?.state === "queued" ? queue.ticket_id : null;
  const selected = timeControls[queue?.state === "queued" ? queue.time_control : control];
  const rating = user.ratings.find(row => row.speed === selected.speed);
  const ratingText = rating ? `Your ${rating.speed} rating: ${rating.rating}` : null;

  const saveQueue = useCallback((next: Queue) => {
    liveTicket.current = next.state === "queued" ? next.ticket_id : null;
    setQueue(next);
  }, []);

  const cancelOnExit = useCallback((id: string) => {
    session.deleteOnExit(`${path}/${id}`, user.id);
  }, [session, user.id]);

  useEffect(() => {
    visit.current.closed = false;
    function leave() {
      if (visit.current.closed) return;
      visit.current.closed = true;
      generation.current += 1;
      const id = liveTicket.current;
      liveTicket.current = null;
      if (id) cancelOnExit(id);
    }
    function restore(event: PageTransitionEvent) {
      if (!event.persisted || !visit.current.closed) return;
      // A page restored from the back/forward cache does not remount.
      visit.current = { closed: false };
      setQueue(null);
      setAction(null);
      setError(null);
      setNotice(null);
      setLoadAttempt(attempt => attempt + 1);
    }
    window.addEventListener("pagehide", leave);
    window.addEventListener("pageshow", restore);
    return () => {
      window.removeEventListener("pagehide", leave);
      window.removeEventListener("pageshow", restore);
      leave();
    };
  }, [cancelOnExit]);

  useEffect(() => {
    void session.reloadUser().catch(() => { /* Keep the last loaded ratings. */ });
  }, [session, user.id]);

  useEffect(() => {
    let active = true;
    const currentVisit = visit.current;
    void session.authorized(path, queueSchema).then(next => {
      if (currentVisit.closed) {
        if (next.state === "queued") cancelOnExit(next.ticket_id);
      } else if (active) saveQueue(next);
    }).catch((failure: unknown) => {
      if (active && !currentVisit.closed) setError(errorMessage(failure));
    });
    return () => { active = false; };
  }, [cancelOnExit, loadAttempt, saveQueue, session]);

  useEffect(() => {
    if (!ticketId || action) return;
    let active = true;
    const currentVisit = visit.current;
    const revision = generation.current;
    const canPoll = () => active && !currentVisit.closed && revision === generation.current;
    let timer = setTimeout(() => { void heartbeat(); }, pollInterval);
    async function heartbeat() {
      if (!canPoll()) return;
      try {
        const next = await session.authorized(`${path}/${ticketId}`, queueSchema, { method: "PUT" });
        if (!canPoll()) return;
        setError(null);
        saveQueue(next);
        if (next.state === "idle") setNotice("Your search ended. Find an opponent to search again.");
        if (next.state === "queued" && next.ticket_id === ticketId) {
          timer = setTimeout(() => { void heartbeat(); }, pollInterval);
        }
      } catch (failure: unknown) {
        if (!canPoll()) return;
        setError(errorMessage(failure));
        timer = setTimeout(() => { void heartbeat(); }, 2 * pollInterval);
      }
    }
    return () => { active = false; clearTimeout(timer); };
  }, [action, saveQueue, session, ticketId]);

  async function changeSearch(command: "join" | "cancel") {
    const currentVisit = visit.current;
    if (currentVisit.closed || action || (command === "cancel" && !ticketId)) return;
    const revision = ++generation.current;
    setAction(command);
    setError(null);
    setNotice(null);
    try {
      const next = command === "join"
        ? await session.authorized(path, queueSchema, {
            method: "POST", body: JSON.stringify({ time_control: control }),
          })
        : await session.authorized(`${path}/${ticketId}`, queueSchema, { method: "DELETE" });
      if (currentVisit.closed) {
        // A join may have committed while the browser was leaving this view.
        if (command === "join" && next.state === "queued") cancelOnExit(next.ticket_id);
        return;
      }
      if (revision !== generation.current) return;
      saveQueue(next);
      if (command === "cancel" && next.state === "idle") setNotice("Search canceled.");
    } catch (failure: unknown) {
      if (revision === generation.current) setError(errorMessage(failure));
    } finally {
      if (revision === generation.current) setAction(null);
    }
  }

  function join(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void changeSearch("join");
  }

  if (queue?.state === "matched") return <Navigate replace to={`/games/${queue.game_id}`} />;
  return <div className="matchmaking-panel" aria-busy={action !== null}>
    {error && <p className="error-banner" role="alert">{error}</p>}
    {!queue ? (
      error ? <button type="button" className="button-quiet" onClick={() => {
        setError(null);
        setLoadAttempt(attempt => attempt + 1);
      }}>Retry</button> : <p role="status">Checking your search…</p>
    ) : queue.state === "queued" ? <>
      <div role="status">
        <h2>Searching for an opponent</h2>
        <p>{selected.label}. Stay on this page to keep searching.</p>
        {ratingText && <p>{ratingText}</p>}
      </div>
      <button className="button-quiet" type="button" disabled={action !== null}
        onClick={() => { void changeSearch("cancel"); }}>
        {action === "cancel" ? "Canceling…" : "Cancel search"}
      </button>
    </> : <form className="room-form" onSubmit={join}>
      {notice && <p role="status">{notice}</p>}
      <label htmlFor="rated-time-control">Time control</label>
      <select id="rated-time-control" value={control} disabled={action !== null}
        aria-describedby={ratingText ? "lobby-rating" : undefined}
        onChange={event => setControl(timeControlSchema.parse(event.target.value))}>
        {Object.entries(timeControls).map(([value, { label }]) =>
          <option key={value} value={value}>{label}</option>
        )}
      </select>
      {ratingText && <p id="lobby-rating" className="board-hint">{ratingText}</p>}
      <button className="button-primary" disabled={action !== null}>
        {action === "join" ? "Joining…" : "Find opponent"}
      </button>
    </form>}
  </div>;
}

export function MatchmakingPage() {
  const { user, status, session } = useAuth();
  if (status === "loading" || status === "error") return <SessionStatus />;
  return <section className="practice page-width">
    <div className="practice-heading"><h1 tabIndex={-1}>Rated play</h1></div>
    <p className="matchmaking-intro">Choose a time control and we’ll pair you with a player near your rating.</p>
    {user ? <Lobby key={user.id} session={session} user={user} /> : <Link className="button-primary" to="/login">Sign in to play</Link>}
    <p className="matchmaking-alternative"><Link className="text-link" to="/games">Create a private room</Link></p>
  </section>;
}

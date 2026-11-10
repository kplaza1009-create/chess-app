import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { z } from "zod";
import { useAuth } from "../auth/AuthProvider";
import { errorMessage, type AuthSession } from "../auth/session";
import { SessionStatus } from "../components/SessionStatus";
import "../board.css";

const timeControlSchema = z.enum(["1+0", "3+2", "5+0", "10+0", "15+10"]);
type TimeControl = z.infer<typeof timeControlSchema>;
const timeControls: Record<TimeControl, string> = {
  "1+0": "Bullet · 1 minute",
  "3+2": "Blitz · 3 minutes + 2 seconds per move",
  "5+0": "Blitz · 5 minutes",
  "10+0": "Rapid · 10 minutes",
  "15+10": "Rapid · 15 minutes + 10 seconds per move",
};
const queueSchema = z.discriminatedUnion("state", [
  z.object({ state: z.literal("idle") }),
  z.object({ state: z.literal("queued"), ticket_id: z.uuid(), time_control: timeControlSchema }),
  z.object({ state: z.literal("matched"), game_id: z.uuid() }),
]);
type Queue = z.infer<typeof queueSchema>;
const path = "/matchmaking";
const pollInterval = 2500;

function Lobby({ session }: { session: AuthSession }) {
  const [queue, setQueue] = useState<Queue | null>(null);
  const [control, setControl] = useState<TimeControl>("10+0");
  const [action, setAction] = useState<"join" | "cancel" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const generation = useRef(0);
  const ticketId = queue?.state === "queued" ? queue.ticket_id : null;

  useEffect(() => () => { generation.current += 1; }, []);

  useEffect(() => {
    let active = true;
    void session.authorized(path, queueSchema).then(next => {
      if (active) setQueue(next);
    }).catch((failure: unknown) => {
      if (active) setError(errorMessage(failure));
    });
    return () => { active = false; };
  }, [session, loadAttempt]);

  useEffect(() => {
    if (!ticketId || action) return;
    let active = true;
    const revision = generation.current;
    let timer = setTimeout(() => { void heartbeat(); }, pollInterval);
    async function heartbeat() {
      if (!active || revision !== generation.current) return;
      try {
        const next = await session.authorized(`${path}/${ticketId}`, queueSchema, { method: "PUT" });
        if (!active || revision !== generation.current) return;
        setError(null);
        setQueue(next);
        if (next.state === "idle") setNotice("Your search ended. Find an opponent to search again.");
        if (next.state === "queued" && next.ticket_id === ticketId) {
          timer = setTimeout(() => { void heartbeat(); }, pollInterval);
        }
      } catch (failure: unknown) {
        if (!active || revision !== generation.current) return;
        setError(errorMessage(failure));
        timer = setTimeout(() => { void heartbeat(); }, 2 * pollInterval);
      }
    }
    return () => { active = false; clearTimeout(timer); };
  }, [action, session, ticketId]);

  async function changeSearch(command: "join" | "cancel") {
    if (action || (command === "cancel" && !ticketId)) return;
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
      if (revision !== generation.current) return;
      setQueue(next);
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
        <p>{timeControls[queue.time_control]}. Stay on this page to keep searching.</p>
      </div>
      <button className="button-quiet" type="button" disabled={action !== null}
        onClick={() => { void changeSearch("cancel"); }}>
        {action === "cancel" ? "Canceling…" : "Cancel search"}
      </button>
    </> : <form className="room-form" onSubmit={join}>
      {notice && <p role="status">{notice}</p>}
      <label htmlFor="rated-time-control">Time control</label>
      <select id="rated-time-control" value={control} disabled={action !== null}
        onChange={event => setControl(timeControlSchema.parse(event.target.value))}>
        {Object.entries(timeControls).map(([value, label]) =>
          <option key={value} value={value}>{label}</option>
        )}
      </select>
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
    {user ? <Lobby key={user.id} session={session} /> : <Link className="button-primary" to="/login">Sign in to play</Link>}
    <p className="matchmaking-alternative"><Link className="text-link" to="/games">Create a private room</Link></p>
  </section>;
}

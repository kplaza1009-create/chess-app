import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { replaySchema } from "../api/history";
import { useAuth } from "../auth/AuthProvider";
import { errorMessage } from "../auth/session";
import "../history.css";

const LIMIT = 65_536;

export function ImportPage() {
  const { user, status, session } = useAuth();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const alert = useRef<HTMLParagraphElement>(null);
  const active = useRef(true);
  const fileVersion = useRef(0);
  const identity = useRef(user?.id);
  identity.current = user?.id;
  useEffect(() => { active.current = true; return () => { active.current = false; fileVersion.current++; }; }, []);
  useEffect(() => { setText(""); setError(null); setBusy(false); fileVersion.current++; }, [user?.id]);
  useEffect(() => { if (error) alert.current?.focus(); }, [error]);

  async function choose(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    const version = ++fileVersion.current;
    if (!file) return;
    setError(null);
    if (file.size > LIMIT) { setError("Choose a PGN file no larger than 64 KiB."); return; }
    try {
      const value = await file.text();
      if (active.current && fileVersion.current === version) setText(value);
    } catch { if (active.current && fileVersion.current === version) setError("Could not read that file. Try again or paste its PGN."); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !user) return;
    if (!text.trim()) { setError("Paste a PGN or choose a PGN file."); return; }
    if (new TextEncoder().encode(text).length > LIMIT) { setError("PGN must be at most 64 KiB."); return; }
    const owner = user.id;
    setBusy(true); setError(null); fileVersion.current++;
    try {
      const replay = await session.authorized("/history/import", replaySchema, { method: "POST", body: JSON.stringify({ pgn: text }) });
      if (active.current && identity.current === owner) navigate(`/history/import/${replay.id}`);
    } catch (failure: unknown) {
      if (active.current && identity.current === owner) setError(errorMessage(failure));
    } finally { if (active.current && identity.current === owner) setBusy(false); }
  }
  if (status === "loading") return <p className="page-width" role="status">Restoring session…</p>;
  if (!user) return <section className="history-page page-width"><h1>Import PGN</h1><Link to="/login">Sign in to import a game</Link></section>;
  return <section className="history-page page-width">
    <Link className="history-back" to="/history">Back to your games</Link>
    <h1 tabIndex={-1}>Import a game</h1>
    <p className="history-intro">Bring a game into your personal collection. Imports are private and never affect ratings.</p>
    <form className="pgn-form" aria-busy={busy} onSubmit={event => { void submit(event); }}>
      <label htmlFor="pgn-file">Choose a PGN file</label>
      <input id="pgn-file" type="file" accept=".pgn,.txt,application/x-chess-pgn,text/plain" disabled={busy} onChange={event => { void choose(event); }} />
      <label htmlFor="pgn-text">Or paste PGN</label>
      <textarea id="pgn-text" value={text} rows={12} disabled={busy} maxLength={LIMIT}
        aria-describedby="pgn-help" spellCheck={false} onChange={event => { fileVersion.current++; setText(event.target.value); }} />
      <p id="pgn-help">One standard-chess game, up to 64 KiB and 1,000 plies. Custom FEN starts are supported. Only the main line is saved; comments and variations are discarded.</p>
      {error && <p ref={alert} className="error-banner" role="alert" tabIndex={-1}>{error}</p>}
      <button className="button-primary" disabled={busy}>{busy ? "Validating game…" : "Import and replay"}</button>
    </form>
  </section>;
}

import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { z } from "zod";
import { replaySchema, sourceSchema, type Replay } from "../api/history";
import { useAuth } from "../auth/AuthProvider";
import { errorMessage } from "../auth/session";
import { ReplayBoard } from "../components/ReplayBoard";

export function ReplayPage() {
  const { source, id } = useParams();
  const { search } = useLocation();
  const { user, status, session } = useAuth();
  const path = `/history/${source}/${id}`;
  const [loaded, setLoaded] = useState<{ owner: string; path: string; game: Replay } | null>(null);
  const [failure, setFailure] = useState<{ owner: string; path: string; message: string } | null>(null);
  const [retry, setRetry] = useState(0);
  const valid = sourceSchema.safeParse(source).success && z.uuid().safeParse(id).success;
  useEffect(() => {
    if (!user || !valid) return;
    let active = true;
    setLoaded(null); setFailure(null);
    void session.authorized(path, replaySchema).then(game => {
      if (game.id !== id || game.source !== source) throw new Error("The server returned a different game.");
      if (active) setLoaded({ owner: user.id, path, game });
    }).catch((error: unknown) => {
      if (active) setFailure({ owner: user.id, path, message: errorMessage(error) });
    });
    return () => { active = false; };
  }, [user?.id, session, path, valid, retry]);
  const game = loaded?.owner === user?.id && loaded?.path === path ? loaded.game : null;
  const error = failure?.owner === user?.id && failure?.path === path ? failure.message : null;
  if (status === "loading") return <p className="page-width" role="status">Restoring session…</p>;
  if (!user) return <section className="history-page page-width"><h1>Game replay</h1><Link to="/login">Sign in to view this game</Link></section>;
  return <div className="history-page replay-page page-width">
    <Link className="history-back" to={`/history${search}`}>Back to your games</Link>
    {!valid ? <><h1 tabIndex={-1}>Game replay</h1><p role="alert" className="error-banner">Invalid replay link.</p></> : error ?
      <><h1 tabIndex={-1}>Game replay</h1><p role="alert" className="error-banner">{error}</p><button className="button-quiet" onClick={() => setRetry(value => value + 1)}>Retry</button></> :
      game ? <ReplayBoard key={`${user.id}-${source}-${id}`} game={game} /> : <><h1 tabIndex={-1}>Game replay</h1><p role="status">Loading game…</p></>}
  </div>;
}

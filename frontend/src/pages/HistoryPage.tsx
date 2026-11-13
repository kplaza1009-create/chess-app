import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { historySchema, resultLabel } from "../api/history";
import { useAuth } from "../auth/AuthProvider";
import { errorMessage } from "../auth/session";
import "../history.css";

type Loaded = { owner: string; query: string; data: z.infer<typeof historySchema> };

export function HistoryPage() {
  const { user, status, session } = useAuth();
  const [params, setParams] = useSearchParams();
  const rawPage = Number(params.get("page") ?? 1);
  const page = Number.isInteger(rawPage) && rawPage >= 1 && rawPage <= 500 ? rawPage : 1;
  const rawSource = params.get("source");
  const source = rawSource === "online" || rawSource === "import" ? rawSource : "all";
  const query = `?page=${page}&source=${source}`;
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [failure, setFailure] = useState<{ owner: string; query: string; message: string } | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!user) return;
    let active = true;
    setLoaded(null); setFailure(null);
    void session.authorized(`/history${query}`, historySchema).then(data => {
      if (active) setLoaded({ owner: user.id, query, data });
    }).catch((error: unknown) => {
      if (active) setFailure({ owner: user.id, query, message: errorMessage(error) });
    });
    return () => { active = false; };
  }, [user?.id, session, query, retry]);
  const data = loaded?.owner === user?.id && loaded?.query === query ? loaded.data : null;
  const error = failure?.owner === user?.id && failure?.query === query ? failure.message : null;
  if (status === "loading") return <p className="page-width" role="status">Restoring session…</p>;
  if (!user) return <section className="history-page page-width"><h1>Game history</h1><Link to="/login">Sign in to view your games</Link></section>;

  return <section className="history-page page-width">
    <div className="history-heading"><div><h1 tabIndex={-1}>Your games</h1>
      <p>Revisit a game, one move at a time.</p></div>
      <Link className="button-primary" to="/history/import">Import PGN</Link>
    </div>
    <div className="history-filter"><label htmlFor="history-source">Show</label>
      <select id="history-source" value={source} onChange={event => setParams({ source: event.target.value, page: "1" })}>
        <option value="all">All games</option><option value="online">Played online</option><option value="import">PGN imports</option>
      </select><p>Only you can see your imports. Online history includes your completed and aborted games.</p>
    </div>
    {error ? <div className="history-feedback"><p className="error-banner" role="alert">{error}</p>
      <button className="button-quiet" onClick={() => setRetry(value => value + 1)}>Retry</button></div> : !data ?
      <p role="status">Loading your games…</p> : data.items.length === 0 ? <div className="history-empty">
        <h2>{page > 1 ? "No games on this page" : "No games here yet"}</h2>
        <p>{page > 1 ? "Return to an earlier page to see your games." : "Finish an online game or import a PGN to start your collection."}</p>
        <Link className="button-quiet" to="/play">Find a game</Link>
      </div> : <div className="history-table-wrap"><table className="history-table">
        <caption className="sr-only">Your game history, page {page}</caption>
        <thead><tr><th scope="col">Players</th><th scope="col">Result</th><th scope="col">Details</th><th scope="col">Date</th><th scope="col">Replay</th></tr></thead>
        <tbody>{data.items.map(game => <tr key={`${game.source}-${game.id}`}>
          <td><span className="history-player">{game.white}</span><span className="history-opponent">vs {game.black}</span></td>
          <td>{game.status === "aborted" ? "Aborted" : resultLabel(game.result)}<span className="history-secondary">{game.result}</span></td>
          <td>{game.source === "import" ? "PGN import · Unrated" : `${game.rated ? "Rated" : "Unrated"} · ${game.time_control ?? "No clock"}`}
            <span className="history-secondary">{game.ply_count} {game.ply_count === 1 ? "ply" : "plies"}
              {game.rating_before != null && game.rating_after != null && ` · Your rating ${game.rating_before} → ${game.rating_after}`}</span></td>
          <td><time dateTime={game.created_at}>{new Date(game.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</time></td>
          <td><Link className="history-replay-link" aria-label={`Replay ${game.white} versus ${game.black}`} to={`/history/${game.source}/${game.id}${query}`}>Replay</Link></td>
        </tr>)}</tbody>
      </table></div>}
    {data && <nav className="history-pagination" aria-label="History pages">
      <button className="button-quiet" disabled={page === 1} onClick={() => setParams({ source, page: String(page - 1) })}>Previous page</button>
      <span aria-live="polite">Page {page}</span>
      <button className="button-quiet" disabled={!data.has_more || page === 500} onClick={() => setParams({ source, page: String(page + 1) })}>Next page</button>
    </nav>}
  </section>;
}

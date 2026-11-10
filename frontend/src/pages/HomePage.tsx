import { ArrowRight, CheckCircle, Clock, Lightning, Timer } from "@phosphor-icons/react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { ChessArtwork } from "../components/ChessArtwork";
import { SessionStatus } from "../components/SessionStatus";

const speeds = [
  { name: "bullet", label: "Bullet", icon: Lightning },
  { name: "blitz", label: "Blitz", icon: Timer },
  { name: "rapid", label: "Rapid", icon: Clock },
] as const;

export function HomePage() {
  const { status, user, session } = useAuth();
  useEffect(() => {
    if (user) void session.reloadUser().catch(() => { /* Keep the last loaded account details. */ });
  }, [session, user?.id]);
  if (status === "loading" || status === "error") return <SessionStatus />;
  if (!user) return <section className="home-hero page-width">
    <div className="home-intro">
      <h1 tabIndex={-1}>Your next move<br />starts here.</h1>
      <p>Create your Chess Room account.<br />Make a little room for the game.</p>
      <div className="hero-actions">
        <Link className="button-primary" to="/register">Create account<ArrowRight size={18} aria-hidden="true" /></Link>
        <Link className="text-link" to="/login">Sign in</Link>
      </div>
      <div className="home-note"><span className="note-rule" /><p>A fresh start.<br />A place of your own at the board.</p></div>
    </div>
    <ChessArtwork compact />
  </section>;

  const created = new Intl.DateTimeFormat("en", { month: "long", year: "numeric" }).format(new Date(user.created_at));
  return <section className="account-page page-width">
    <header className="account-heading">
      <div>
        <h1 tabIndex={-1}>Welcome, {user.username}.</h1>
        <p>Your place in Chess Room.</p>
      </div>
      <span className="account-status"><CheckCircle size={18} aria-hidden="true" />Account ready</span>
    </header>
    <div className="account-content">
      <section className="ratings-section" aria-labelledby="ratings-heading">
        <h2 id="ratings-heading">Your ratings</h2>
        <p className="section-description">A separate rating for each pace of play.</p>
        <div className="rating-list">
          {speeds.map(({ name, label, icon: Icon }) => {
            const rating = user.ratings.find((entry) => entry.speed === name);
            const games = rating ? rating.wins + rating.losses + rating.draws : 0;
            return <article className="rating-row" key={name} aria-label={`${label} rating`}>
              <Icon className="rating-icon" size={25} aria-hidden="true" />
              <h3>{label}</h3>
              <div className="rating-value"><strong>{rating?.rating ?? "Unrated"}</strong>
                <span>{games === 0 ? "Starting rating" : `${games} rated game${games === 1 ? "" : "s"}`}</span>
              </div>
            </article>;
          })}
        </div>
        <div className="account-empty"><h3>Ready to play?</h3>
          <p><Link className="text-link" to="/play">Find a rated opponent</Link></p>
        </div>
      </section>
      <aside className="account-details" aria-labelledby="account-details-heading">
        <span className="avatar" aria-hidden="true">{user.username.slice(0, 1).toUpperCase()}</span>
        <h2 id="account-details-heading">Your account</h2>
        <dl>
          <div><dt>Username</dt><dd>@{user.username}</dd></div>
          <div><dt>Email address</dt><dd>{user.email}</dd></div>
          <div><dt>Member since</dt><dd>{created}</dd></div>
        </dl>
      </aside>
    </div>
  </section>;
}

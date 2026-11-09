import { Horse } from "@phosphor-icons/react";
import { useLayoutEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { errorMessage } from "../auth/session";

export function Layout() {
  const { user, status, session } = useAuth();
  const { pathname } = useLocation();
  const main = useRef<HTMLElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useLayoutEffect(() => {
    const page = pathname === "/login" ? "Sign in" : pathname === "/register" ? "Create account"
      : pathname === "/practice" ? "Practice board" : pathname.startsWith("/games") ? "Online rooms" : pathname === "/" ? user ? "Your account" : "Welcome" : "Page not found";
    document.title = `${page} | Chess Room`;
    main.current?.querySelector<HTMLElement>("h1")?.focus();
  }, [pathname, status]);

  async function logout(): Promise<void> {
    if (busy) return;
    setBusy(true);
    setError(null);
    try { await session.logout(); }
    catch (failure: unknown) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }

  return <div className={`app-shell${pathname === "/practice" || pathname.startsWith("/games") ? " board-shell" : ""}`}>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="site-header">
      <div className="page-width header-inner">
        <Link to="/" className="brand" aria-label="Chess Room home">
          <span className="brand-mark"><Horse size={27} weight="fill" aria-hidden="true" /></span>
          <span>Chess Room<span className="brand-period">.</span></span>
        </Link>
        <nav aria-label="Main navigation" className="main-nav">
          <Link className="nav-link" to="/practice">Practice</Link>
          <Link className="nav-link" to="/games">Online rooms</Link>
          {status === "authenticated" && user ? <>
            <span className="nav-username">@{user.username}</span>
            <button className="button-quiet" onClick={() => { void logout(); }} disabled={busy}>
              {busy ? "Signing out..." : "Sign out"}
            </button>
          </> : status === "anonymous" ? <>
            {pathname !== "/login" && <Link className="nav-link" to="/login">Sign in</Link>}
            {pathname !== "/register" && <Link className="button-quiet nav-register" to="/register">Create account</Link>}
          </> : null}
        </nav>
      </div>
    </header>
    {error && <p className="error-banner page-width logout-error" role="alert">{error}</p>}
    <main ref={main} id="main-content" tabIndex={-1}><Outlet /></main>
    <footer className="site-footer page-width"><span>Chess Room</span><span>A place to think and play.</span></footer>
  </div>;
}

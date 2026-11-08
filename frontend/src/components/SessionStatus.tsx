import { ArrowClockwise } from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthProvider";

export function SessionStatus() {
  const { status, error, session } = useAuth();
  return <section className="session-status page-width" aria-busy={status === "loading"}>
    {status === "error" ? <>
      <h1 tabIndex={-1}>We couldn't check your session.</h1>
      <p role="alert">{error}</p>
      <button className="button-primary" onClick={() => { void session.restore(); }}>
        Try again<ArrowClockwise size={18} aria-hidden="true" />
      </button>
    </> : <>
      <h1 className="visually-hidden">Checking your session</h1>
      <p role="status">Checking your session...</p>
      <div className="session-skeleton" aria-hidden="true"><span /><span /><span /></div>
    </>}
  </section>;
}

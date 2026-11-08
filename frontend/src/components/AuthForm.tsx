import { ArrowRight, Eye, EyeSlash, WarningCircle } from "@phosphor-icons/react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ApiError, type AuthField, type FieldErrors } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { errorMessage } from "../auth/session";
import { ChessArtwork } from "./ChessArtwork";
import { SessionStatus } from "./SessionStatus";

type FormError = { message: string; fields: FieldErrors };

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const registering = mode === "register";
  const { status, session } = useAuth();
  const navigate = useNavigate();
  const form = useRef<HTMLFormElement>(null);
  const errorBox = useRef<HTMLDivElement>(null);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<FormError | null>(null);

  useEffect(() => {
    if (!error || busy) return;
    const field = (["username", "email", "password"] as const).find((name) => error.fields[name]);
    if (field) form.current?.querySelector<HTMLInputElement>(`#${field}`)?.focus();
    else errorBox.current?.focus();
  }, [error, busy]);

  function validate(): FieldErrors {
    const fields: FieldErrors = {};
    const emailInput = form.current?.querySelector<HTMLInputElement>("#email");
    if (registering && !/^[a-z0-9_]{3,24}$/.test(username.trim().toLowerCase())) {
      fields.username = "Use 3-24 letters, numbers, or underscores.";
    }
    if (!email.trim() || email.trim().length > 254 || emailInput?.validity.typeMismatch) {
      fields.email = "Enter a valid email address.";
    }
    if (!password) fields.password = "Enter your password.";
    else if (registering && Array.from(password).length < 12) {
      fields.password = "Use at least 12 characters. A passphrase works well.";
    } else if (new TextEncoder().encode(password).length > 72 || password.includes("\0")) {
      fields.password = "This password is too long or contains an unsupported character. Try a shorter passphrase.";
    }
    return fields;
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (busy) return;
    setError(null);
    const fields = validate();
    if (Object.keys(fields).length) {
      setError({ message: "Check the highlighted fields and try again.", fields });
      return;
    }
    setBusy(true);
    try {
      if (registering) await session.register({ username: username.trim(), email: email.trim(), password });
      else await session.login({ email: email.trim(), password });
      setPassword("");
      navigate("/", { replace: true });
    } catch (failure: unknown) {
      setError({ message: errorMessage(failure), fields: failure instanceof ApiError ? failure.fields : {} });
    } finally {
      setBusy(false);
    }
  }

  function describedBy(field: AuthField, hint?: string): string | undefined {
    return [hint, error?.fields[field] ? `${field}-error` : undefined].filter(Boolean).join(" ") || undefined;
  }

  if (status === "authenticated") return <Navigate to="/" replace />;
  if (status === "loading" || status === "error") return <SessionStatus />;

  return <div className="auth-layout page-width">
    <section className="auth-panel" aria-labelledby="auth-heading">
      <div className="auth-intro">
        <h1 id="auth-heading" tabIndex={-1}>{registering ? "Take your seat." : "Welcome back."}</h1>
        <p>{registering ? "Create your Chess Room account." : "Sign in to your Chess Room account."}</p>
      </div>
      <form ref={form} className="auth-form" noValidate aria-busy={busy}
        onSubmit={(event) => { void submit(event); }}>
        {error && <div ref={errorBox} className="error-banner" role="alert" tabIndex={-1}>
          <WarningCircle size={20} aria-hidden="true" /><p>{error.message}</p>
        </div>}
        {registering && <div className="field-group">
          <label htmlFor="username">Username</label>
          <input id="username" name="username" autoComplete="username" required
            minLength={3} maxLength={24} pattern="[A-Za-z0-9_]{3,24}" className="field"
            value={username} onChange={(event) => setUsername(event.target.value)}
            aria-describedby={describedBy("username", "username-hint")}
            aria-invalid={Boolean(error?.fields.username)} disabled={busy} spellCheck={false}
            autoCapitalize="none" />
          <p id="username-hint" className="field-hint">3-24 letters, numbers, or underscores.</p>
          {error?.fields.username && <p id="username-error" className="field-error">{error.fields.username}</p>}
        </div>}
        <div className="field-group">
          <label htmlFor="email">Email address</label>
          <input id="email" name="email" type="email" autoComplete={registering ? "email" : "username"}
            required maxLength={254} className="field" value={email}
            onChange={(event) => setEmail(event.target.value)} disabled={busy}
            aria-invalid={Boolean(error?.fields.email)} aria-describedby={describedBy("email")}
            autoCapitalize="none" spellCheck={false} />
          {error?.fields.email && <p id="email-error" className="field-error">{error.fields.email}</p>}
        </div>
        <div className="field-group">
          <label htmlFor="password">Password</label>
          <div className="password-field">
            <input id="password" name="password" type={visible ? "text" : "password"}
              autoComplete={registering ? "new-password" : "current-password"} required
              minLength={registering ? 12 : 1} maxLength={72} className="field"
              value={password} onChange={(event) => setPassword(event.target.value)}
              aria-describedby={describedBy("password", registering ? "password-hint" : undefined)}
              aria-invalid={Boolean(error?.fields.password)} disabled={busy} />
            <button type="button" className="password-toggle" aria-controls="password"
              aria-label={visible ? "Hide password" : "Show password"} aria-pressed={visible}
              disabled={busy} onClick={() => setVisible(!visible)}>
              {visible ? <EyeSlash size={20} aria-hidden="true" /> : <Eye size={20} aria-hidden="true" />}
            </button>
          </div>
          {registering && <p id="password-hint" className="field-hint">At least 12 characters. A passphrase works well.</p>}
          {error?.fields.password && <p id="password-error" className="field-error">{error.fields.password}</p>}
        </div>
        <button className="button-primary submit-button" type="submit" disabled={busy}>
          {busy ? registering ? "Creating account..." : "Signing in..." : registering ? "Create account" : "Sign in"}
          {!busy && <ArrowRight size={18} aria-hidden="true" />}
        </button>
      </form>
      <p className="auth-switch">
        {registering ? "Already have an account? " : "New to Chess Room? "}
        <Link className="text-link" to={registering ? "/login" : "/register"}>
          {registering ? "Sign in" : "Create account"}
        </Link>
      </p>
    </section>
    <ChessArtwork />
  </div>;
}

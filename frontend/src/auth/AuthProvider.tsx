import { createContext, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";
import { AuthSession, defaultSession } from "./session";

const AuthContext = createContext<AuthSession | null>(null);

export function AuthProvider({
  children,
  session = defaultSession,
}: { children: ReactNode; session?: AuthSession }): ReactNode {
  useEffect(() => session.start(), [session]);
  return <AuthContext.Provider value={session}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const session = useContext(AuthContext);
  if (!session) throw new Error("useAuth must be used inside AuthProvider");
  const state = useSyncExternalStore(session.subscribe, session.getSnapshot);
  return { ...state, session };
}

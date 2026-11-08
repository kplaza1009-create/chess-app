import { vi } from "vitest";
import type { AuthResponse } from "../types/api";

export const authResult: AuthResponse = {
  access_token: "access-token-from-test-server",
  token_type: "bearer",
  expires_in: 300,
  session_id: "22222222-2222-4222-8222-222222222222",
  user: {
    id: "11111111-1111-4111-8111-111111111111",
    username: "kevin",
    email: "kevin@example.com",
    avatar_key: null,
    created_at: "2026-10-28T12:00:00Z",
    ratings: ["bullet", "blitz", "rapid"].map((speed) => ({
      speed: speed as "bullet" | "blitz" | "rapid", rating: 1200, wins: 0, losses: 0, draws: 0,
    })),
  },
};

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function mockServer({ rejectLogin = false }: { rejectLogin?: boolean } = {}) {
  let signedIn = false;
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    const path = String(input);
    if (path.endsWith("/csrf")) return json({ csrf_token: "test-csrf" });
    if (path.endsWith("/refresh")) {
      return signedIn ? json(authResult) : json({ detail: "Please sign in again." }, 401);
    }
    if (path.endsWith("/login") || path.endsWith("/register")) {
      if (rejectLogin) return json({ detail: "Incorrect email or password." }, 401);
      signedIn = true;
      return json(authResult, path.endsWith("/register") ? 201 : 200);
    }
    if (path.endsWith("/logout")) {
      signedIn = false;
      return json({ message: "Signed out" });
    }
    return json(authResult.user);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

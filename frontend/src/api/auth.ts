import { request } from "./client";
import {
  authSchema, csrfSchema, messageSchema,
  type AuthResponse, type LoginInput, type RegisterInput,
} from "../types/api";

let localQueue: Promise<unknown> = Promise.resolve();

async function mutation<T>(execute: (csrf: string) => Promise<T>): Promise<T> {
  // Read the CSRF token inside the same lock as the cookie-changing request.
  const run = async (): Promise<T> => {
    const csrf = await request("/auth/csrf", csrfSchema);
    return execute(csrf.csrf_token);
  };
  if (typeof navigator !== "undefined" && navigator.locks) {
    return navigator.locks.request("chess-auth-cookie", run);
  }
  const pending = localQueue.then(run, run);
  localQueue = pending.catch(() => undefined);
  return pending;
}

export function authenticate(
  action: "login" | "register" | "refresh",
  input?: LoginInput | RegisterInput,
): Promise<AuthResponse> {
  return mutation((csrf) => request(`/auth/${action}`, authSchema, {
    method: "POST",
    headers: { "X-CSRF-Token": csrf },
    ...(input === undefined ? {} : { body: JSON.stringify(input) }),
  }));
}

export async function signOut(): Promise<void> {
  await mutation((csrf) => request("/auth/logout", messageSchema, {
    method: "POST", headers: { "X-CSRF-Token": csrf },
  }));
}

import type { z } from "zod";
import { authenticate, signOut } from "../api/auth";
import { ApiError, request } from "../api/client";
import { userSchema } from "../types/api";
import type { AuthResponse, LoginInput, RegisterInput, User } from "../types/api";

export type AuthState =
  | { status: "authenticated"; user: User; error: null }
  | { status: "loading" | "anonymous"; user: null; error: null }
  | { status: "error"; user: null; error: string };

export class AuthSession {
  private state: AuthState = { status: "loading", user: null, error: null };
  private accessToken: string | null = null;
  private expiresAt = 0;
  private revision = 0;
  private pendingRefresh: { revision: number; promise: Promise<AuthResponse> } | null = null;
  private listeners = new Set<() => void>();
  private channel: BroadcastChannel | null = null;
  private consumers = 0;

  getSnapshot = (): AuthState => this.state;
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  private update(state: AuthState): void {
    this.state = state;
    this.listeners.forEach((listener) => listener());
  }

  private ensureCurrent(revision: number): void {
    if (revision !== this.revision) throw new ApiError(409, "Your session changed. Try again.");
  }

  private accept(response: AuthResponse): void {
    this.accessToken = response.access_token;
    this.expiresAt = Date.now() + response.expires_in * 1000;
    this.update({ status: "authenticated", user: response.user, error: null });
  }

  private clear(status: "anonymous" | "loading" = "anonymous"): void {
    this.accessToken = null;
    this.expiresAt = 0;
    this.update({ status, user: null, error: null });
  }

  private refresh(): Promise<AuthResponse> {
    const revision = this.revision;
    if (this.pendingRefresh?.revision === revision) return this.pendingRefresh.promise;
    const promise = authenticate("refresh").then((response) => {
      this.ensureCurrent(revision);
      this.accept(response);
      return response;
    }).finally(() => {
      if (this.pendingRefresh?.promise === promise) this.pendingRefresh = null;
    });
    this.pendingRefresh = { revision, promise };
    return promise;
  }

  restore = async (): Promise<void> => {
    const revision = this.revision;
    if (this.state.status === "error") this.clear("loading");
    try {
      await this.refresh();
    } catch (error: unknown) {
      if (revision !== this.revision) return;
      this.clear();
      if (!(error instanceof ApiError && error.status === 401)) {
        this.update({ status: "error", user: null, error: errorMessage(error) });
      }
    }
  };

  private async signIn(action: "login" | "register", input: LoginInput | RegisterInput): Promise<void> {
    const revision = ++this.revision;
    const response = await authenticate(action, input);
    this.ensureCurrent(revision);
    this.accept(response);
    this.channel?.postMessage({ type: "changed" });
  }

  login = (input: LoginInput): Promise<void> => this.signIn("login", input);
  register = (input: RegisterInput): Promise<void> => this.signIn("register", input);

  logout = async (): Promise<void> => {
    const revision = ++this.revision;
    await signOut();
    this.ensureCurrent(revision);
    this.clear();
    // Other tabs re-read the shared cookie, including a newer login if one won the race.
    this.channel?.postMessage({ type: "changed" });
  };

  async reloadUser(): Promise<void> {
    const revision = this.revision;
    const user = await this.authorized("/auth/me", userSchema);
    this.ensureCurrent(revision);
    if (this.state.user?.id === user.id) this.update({ status: "authenticated", user, error: null });
  }

  async authorized<T>(path: string, schema: z.ZodType<T>, options: RequestInit = {}): Promise<T> {
    const revision = this.revision;
    const send = (token: string): Promise<T> => {
      this.ensureCurrent(revision);
      const headers = new Headers(options.headers);
      headers.set("Authorization", `Bearer ${token}`);
      return request(path, schema, { ...options, headers });
    };
    try {
      if (!this.accessToken || this.expiresAt - Date.now() < 15_000) await this.refresh();
      this.ensureCurrent(revision);
      const sentToken = this.accessToken ?? "";
      let result: T;
      try {
        result = await send(sentToken);
      } catch (error: unknown) {
        this.ensureCurrent(revision);
        if (!(error instanceof ApiError) || error.status !== 401) throw error;
        // A late 401 may refer to a token another request has already replaced.
        if (this.accessToken === sentToken) await this.refresh();
        result = await send(this.accessToken ?? "");
      }
      this.ensureCurrent(revision);
      return result;
    } catch (error: unknown) {
      if (revision === this.revision && error instanceof ApiError && error.status === 401) {
        this.clear();
      }
      throw error;
    }
  }

  start(): () => void {
    this.consumers += 1;
    if (this.consumers === 1 && typeof BroadcastChannel !== "undefined") {
      this.channel = new BroadcastChannel("chess-auth-events");
      this.channel.onmessage = (event: MessageEvent<unknown>): void => {
        const data = event.data;
        if (typeof data !== "object" || data === null || !("type" in data) || data.type !== "changed") return;
        this.revision += 1;
        this.clear("loading");
        void this.restore();
      };
    }
    void this.restore();
    return () => {
      this.consumers -= 1;
      if (this.consumers === 0) {
        this.channel?.close();
        this.channel = null;
      }
    };
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

export const defaultSession = new AuthSession();

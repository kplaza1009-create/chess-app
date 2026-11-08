import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthSession } from "../auth/session";
import { userSchema } from "../types/api";
import { authResult, json, mockServer } from "./fixtures";

beforeEach(() => { vi.stubGlobal("BroadcastChannel", undefined); });
afterEach(() => { vi.unstubAllGlobals(); });

describe("authentication session", () => {
  it("shares one refresh request among simultaneous callers", async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => String(input).endsWith("/csrf")
      ? json({ csrf_token: "test-csrf" }) : json(authResult));
    vi.stubGlobal("fetch", fetchMock);
    const session = new AuthSession();
    await Promise.all([session.restore(), session.restore(), session.restore()]);
    expect(fetchMock.mock.calls.filter(([path]) => String(path).endsWith("/refresh"))).toHaveLength(1);
    expect(session.getSnapshot().status).toBe("authenticated");
  });

  it("keeps tokens out of browser storage", async () => {
    mockServer();
    const storage = vi.spyOn(Storage.prototype, "setItem");
    const session = new AuthSession();
    await session.login({ email: "kevin@example.com", password: "a safe passphrase" });
    expect(storage).not.toHaveBeenCalled();
    expect(session.getSnapshot()).not.toHaveProperty("access_token");
  });

  it("refreshes once and retries an API request after an expired access token", async () => {
    let attempts = 0;
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const path = String(input);
      if (path.endsWith("/csrf")) return json({ csrf_token: "test-csrf" });
      if (path.endsWith("/me")) {
        attempts += 1;
        return attempts === 1 ? json({ detail: "Expired" }, 401) : json(authResult.user);
      }
      return json({ ...authResult, access_token: path.endsWith("/refresh") ? "new-token" : "old-token" });
    });
    vi.stubGlobal("fetch", fetchMock);
    const session = new AuthSession();
    await session.login({ email: "kevin@example.com", password: "a safe passphrase" });
    expect((await session.authorized("/auth/me", userSchema)).username).toBe("kevin");
    expect(attempts).toBe(2);
    const requests = fetchMock.mock.calls.filter(([path]) => String(path).endsWith("/me"));
    expect(new Headers(requests[1]?.[1]?.headers).get("Authorization")).toBe("Bearer new-token");
  });

  it("distinguishes a network failure from an anonymous session", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new TypeError("offline")));
    const session = new AuthSession();
    await session.restore();
    expect(session.getSnapshot().status).toBe("error");
    expect(session.getSnapshot().error).toContain("Could not reach the server");
  });

  it("does not report successful logout when the server cannot be reached", async () => {
    const fetchMock = mockServer();
    const session = new AuthSession();
    await session.login({ email: "kevin@example.com", password: "a safe passphrase" });
    fetchMock.mockRejectedValue(new TypeError("offline"));
    await expect(session.logout()).rejects.toThrow("Could not reach the server");
    expect(session.getSnapshot().status).toBe("authenticated");
  });

  it("rejects malformed successful responses", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>(async () => json({ unexpected: true })));
    const session = new AuthSession();
    await session.restore();
    expect(session.getSnapshot().status).toBe("error");
  });

  it("rejects a successful private response that arrives after logout", async () => {
    const fetchMock = mockServer();
    const session = new AuthSession();
    await session.login({ email: "kevin@example.com", password: "a safe passphrase" });
    let complete = (_response: Response): void => { throw new Error("Not initialized"); };
    const delayed = new Promise<Response>((resolve) => { complete = resolve; });
    fetchMock.mockImplementation(async (input) => {
      if (String(input).endsWith("/me")) return delayed;
      if (String(input).endsWith("/csrf")) return json({ csrf_token: "test-csrf" });
      return json({ message: "Signed out" });
    });
    const privateRequest = session.authorized("/auth/me", userSchema);
    await session.logout();
    complete(json(authResult.user));
    await expect(privateRequest).rejects.toThrow("Your session changed");
    expect(session.getSnapshot().status).toBe("anonymous");
  });

  it("does not refresh an old account's failed request after a new login", async () => {
    const fetchMock = mockServer();
    const session = new AuthSession();
    await session.login({ email: "kevin@example.com", password: "a safe passphrase" });
    let complete = (_response: Response): void => { throw new Error("Not initialized"); };
    const delayed = new Promise<Response>((resolve) => { complete = resolve; });
    fetchMock.mockImplementation(async (input) => {
      const path = String(input);
      if (path.endsWith("/csrf")) return json({ csrf_token: "test-csrf" });
      if (path.endsWith("/me")) return delayed;
      return json({ ...authResult, user: { ...authResult.user, username: "second_player" } });
    });
    const oldRequest = session.authorized("/auth/me", userSchema);
    await session.login({ email: "second@example.com", password: "another passphrase" });
    complete(json({ detail: "Expired" }, 401));
    await expect(oldRequest).rejects.toThrow("Your session changed");
    expect(session.getSnapshot().user?.username).toBe("second_player");
    expect(fetchMock.mock.calls.filter(([path]) => String(path).endsWith("/refresh"))).toHaveLength(0);
  });

  it("reuses an already refreshed token when a second 401 arrives late", async () => {
    let finishSecond = (_response: Response): void => { throw new Error("Not initialized"); };
    const delayed = new Promise<Response>((resolve) => { finishSecond = resolve; });
    const fetchMock = vi.fn<typeof fetch>(async (input, options) => {
      const path = String(input);
      if (path.endsWith("/csrf")) return json({ csrf_token: "test-csrf" });
      if (path.endsWith("/login")) return json({ ...authResult, access_token: "old-token" });
      if (path.endsWith("/refresh")) return json({ ...authResult, access_token: "new-token" });
      if (new Headers(options?.headers).get("Authorization") === "Bearer new-token") {
        return json(authResult.user);
      }
      return path.endsWith("/second") ? delayed : json({ detail: "Expired" }, 401);
    });
    vi.stubGlobal("fetch", fetchMock);
    const session = new AuthSession();
    await session.login({ email: "kevin@example.com", password: "a safe passphrase" });
    const first = session.authorized("/first", userSchema);
    const second = session.authorized("/second", userSchema);
    await first;
    finishSecond(json({ detail: "Expired" }, 401));
    await second;
    expect(fetchMock.mock.calls.filter(([path]) => String(path).endsWith("/refresh"))).toHaveLength(1);
  });

  it("synchronizes login and logout between tabs without broadcasting tokens", async () => {
    const messages: unknown[] = [];
    class Channel {
      static instances = new Set<Channel>();
      onmessage: ((event: MessageEvent<unknown>) => void) | null = null;
      constructor() { Channel.instances.add(this); }
      postMessage(data: unknown): void {
        messages.push(data);
        for (const channel of Channel.instances) {
          if (channel !== this) queueMicrotask(() => channel.onmessage?.(new MessageEvent("message", { data })));
        }
      }
      close(): void { Channel.instances.delete(this); }
    }
    vi.stubGlobal("BroadcastChannel", Channel);
    mockServer();
    const first = new AuthSession();
    const second = new AuthSession();
    const stopFirst = first.start();
    const stopSecond = second.start();
    try {
      await vi.waitFor(() => expect(second.getSnapshot().status).toBe("anonymous"));
      await first.login({ email: "kevin@example.com", password: "a safe passphrase" });
      await vi.waitFor(() => expect(second.getSnapshot().status).toBe("authenticated"));
      await first.logout();
      await vi.waitFor(() => expect(second.getSnapshot().status).toBe("anonymous"));
      expect(messages).toEqual([{ type: "changed" }, { type: "changed" }]);
    } finally {
      stopFirst();
      stopSecond();
    }
  });
});

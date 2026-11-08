import { afterEach, expect, it, vi } from "vitest";
import { ApiError, request } from "../api/client";
import { messageSchema } from "../types/api";
import { json } from "./fixtures";

afterEach(() => { vi.unstubAllGlobals(); });

it("only maps recognized body validation fields", async () => {
  vi.stubGlobal("fetch", vi.fn<typeof fetch>(async () => json({ detail: [
    { loc: ["body", "email"], msg: "private input should not be displayed" },
    { loc: ["body", "__proto__"], msg: "untrusted" },
    { loc: ["query", "password"], msg: "untrusted" },
  ] }, 422)));
  try {
    await request("/auth/login", messageSchema);
    throw new Error("Expected a validation error");
  } catch (error: unknown) {
    expect(error).toBeInstanceOf(ApiError);
    if (!(error instanceof ApiError)) throw error;
    expect(error.fields).toEqual({ email: "Enter a valid email address." });
    expect(error.message).not.toContain("private input");
  }
});

it("includes the server's bounded retry delay for rate limits", async () => {
  vi.stubGlobal("fetch", vi.fn<typeof fetch>(async () => new Response(
    JSON.stringify({ detail: "Too many attempts." }),
    { status: 429, headers: { "Content-Type": "application/json", "Retry-After": "45" } },
  )));
  await expect(request("/auth/login", messageSchema)).rejects.toThrow("Try again in 45 seconds.");
});

it("rejects a non-JSON response without leaking its body", async () => {
  vi.stubGlobal("fetch", vi.fn<typeof fetch>(async () => new Response("private gateway diagnostics", { status: 502 })));
  await expect(request("/auth/refresh", messageSchema)).rejects.toThrow("unexpected response");
});

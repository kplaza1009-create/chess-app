import type { z } from "zod";

export type AuthField = "username" | "email" | "password";
export type FieldErrors = Partial<Record<AuthField, string>>;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly fields: FieldErrors = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...options,
      headers,
      credentials: "same-origin",
      signal: options.signal ?? AbortSignal.timeout(10_000),
    });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(response.status, "The server returned an unexpected response.");
  }
  if (!response.ok) {
    const detail = typeof body === "object" && body !== null && "detail" in body
      ? body.detail : undefined;
    const fields: FieldErrors = {};
    if (response.status === 422 && Array.isArray(detail)) {
      for (const entry of detail as unknown[]) {
        if (typeof entry !== "object" || entry === null || !("loc" in entry)) continue;
        const location: unknown = entry.loc;
        if (!Array.isArray(location) || location[0] !== "body") continue;
        const field: unknown = location[1];
        if (field === "email") fields.email = "Enter a valid email address.";
        if (field === "username") fields.username = "Use 3-24 letters, numbers, or underscores.";
        if (field === "password") fields.password = "Check your password's length. Long passwords with symbols may need shortening.";
      }
    }
    const delay = Number(response.headers.get("Retry-After"));
    const retryHint = response.status === 429 && Number.isInteger(delay) && delay > 0 && delay <= 86_400
      ? ` Try again in ${delay} seconds.` : "";
    throw new ApiError(
      response.status,
      (typeof detail === "string" ? detail : "Check the highlighted fields and try again.") + retryHint,
      fields,
    );
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) throw new ApiError(502, "The server returned an invalid response.");
  return parsed.data;
}

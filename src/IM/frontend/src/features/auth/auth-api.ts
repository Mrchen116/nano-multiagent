import type { BrowserSession } from "./auth-store";

export const AUTH_REQUEST_TIMEOUT_MS = 10_000;

function apiBase() {
  return (import.meta.env.VITE_IM_API_BASE_URL ?? "").replace(/\/$/, "");
}

export function withBase(path: string) {
  return `${apiBase()}${path}`;
}

export class AuthApiError extends Error {
  status: number;
  detail: string;
  retryAfter: number;
  constructor(status: number, detail: string, retryAfter = 0) {
    super(`auth request failed: ${status} (${detail})`);
    this.name = "AuthApiError";
    this.status = status;
    this.detail = detail;
    this.retryAfter = retryAfter;
  }
}

/** Bound an authentication network operation so half-open connections cannot stall hydration or session locks.
 *
 * Args:
 *   operation: Async request callback receiving an `AbortSignal` that aborts when the deadline expires.
 *   timeoutMs: Deadline in milliseconds before aborting (defaults to `AUTH_REQUEST_TIMEOUT_MS`).
 *
 * Returns:
 *   Resolved value of `operation`.
 *
 * Raises:
 *   DOMException: `TimeoutError` when `operation` does not settle within `timeoutMs`.
 */
export async function withAuthRequestTimeout<T>(
  operation: (signal: AbortSignal) => Promise<T>,
  timeoutMs = AUTH_REQUEST_TIMEOUT_MS
): Promise<T> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeoutPromise = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      const reason = new DOMException("Authentication request timed out", "TimeoutError");
      controller.abort(reason);
      reject(reason);
    }, timeoutMs);
  });
  try {
    const pending = operation(controller.signal);
    pending.catch(() => undefined);
    return await Promise.race([pending, timeoutPromise]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  return withAuthRequestTimeout(async (signal) => {
    const res = await fetch(withBase(path), {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-IM-Session": "browser" },
      credentials: "include",
      body: JSON.stringify(body),
      signal
    });
    if (!res.ok) {
      const text = await res.text();
      let detail = text || res.statusText;
      try {
        const parsed = JSON.parse(text) as { detail?: string };
        if (typeof parsed.detail === "string" && parsed.detail.length > 0) detail = parsed.detail;
      } catch {
        // ignore json parse failure; raw text is the detail
      }
      throw new AuthApiError(res.status, detail, Number(res.headers.get("Retry-After")) || 0);
    }
    return (await res.json()) as T;
  });
}

export function login(input: { username: string; password: string }) {
  return postJson<BrowserSession>("/im/v1/auth/login", input);
}

export function register(input: { username: string; password: string; display_name: string; locale?: string }) {
  return postJson<BrowserSession>("/im/v1/auth/register", {
    username: input.username,
    password: input.password,
    display_name: input.display_name,
    locale: input.locale ?? "en"
  });
}

export function refreshTokens() {
  return postJson<BrowserSession>("/im/v1/auth/refresh", {});
}

export function logoutApi() {
  return postJson<{ ok: boolean }>("/im/v1/auth/logout", {});
}

import { useAuthStore } from "./auth-store";
import { withBase } from "./auth-api";
import { forceRefreshSession } from "./auth-session";

function buildHeaders(init: RequestInit | undefined, token: string | null): Headers {
  const headers = new Headers(init?.headers ?? {});
  if (!headers.has("Content-Type") && init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

/**
 * authFetch — global wrapper that adds Bearer access token and transparently
 * recovers from expired access tokens via the refresh endpoint exactly once.
 *
 * On a 401 it attempts one refresh; if refresh succeeds the original request is
 * replayed with the new access token. If refresh fails, the auth store is cleared
 * (RequireAuth will then redirect to /login) and the original 401 response is
 * surfaced to the caller — we deliberately do not throw so callers can decide
 * whether to render an inline error or fall through to the route guard.
 */
export async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith("http") ? path : withBase(path);
  const initialSession = useAuthStore.getState();
  const initialToken = initialSession.accessToken;
  const initialUserId = initialSession.user?.id;
  const firstHeaders = buildHeaders(init, initialToken);
  const first = await fetch(url, { ...init, headers: firstHeaders });
  if (first.status !== 401) return first;
  const readiness = await forceRefreshSession();
  if (readiness.status !== "ready" || readiness.userId !== initialUserId) return first;
  const retryHeaders = buildHeaders(init, readiness.accessToken);
  return fetch(url, { ...init, headers: retryHeaders });
}

export async function authFetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status} (${text || res.statusText})`);
  }
  return (await res.json()) as T;
}

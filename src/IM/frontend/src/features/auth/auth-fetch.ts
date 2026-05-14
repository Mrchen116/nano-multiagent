import { refreshTokens } from "./auth-api";
import { useAuthStore } from "./auth-store";
import { withBase } from "./auth-api";

let refreshPromise: Promise<boolean> | null = null;

async function attemptRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  const current = useAuthStore.getState();
  if (!current.refreshToken) return false;
  refreshPromise = (async () => {
    try {
      const pair = await refreshTokens(current.refreshToken!);
      useAuthStore.getState().setSession(pair);
      return true;
    } catch {
      useAuthStore.getState().clear();
      return false;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

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
  const initialToken = useAuthStore.getState().accessToken;
  const firstHeaders = buildHeaders(init, initialToken);
  const first = await fetch(url, { ...init, headers: firstHeaders });
  if (first.status !== 401) return first;
  const refreshed = await attemptRefresh();
  if (!refreshed) return first;
  const newToken = useAuthStore.getState().accessToken;
  const retryHeaders = buildHeaders(init, newToken);
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

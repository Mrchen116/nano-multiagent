import { AuthApiError, refreshTokens } from "./auth-api";
import { useAuthStore } from "./auth-store";

const FRESHNESS_WINDOW_SECONDS = 30;

export type SessionReadiness =
  | { status: "ready"; userId: string; accessToken: string }
  | { status: "retry" }
  | { status: "signed_out" };

interface RefreshSnapshot {
  userId: string;
  refreshToken: string;
}

let refreshPromise: Promise<SessionReadiness> | null = null;

function decodeJwtExpiry(token: string): number | null {
  const payload = token.split(".")[1];
  if (!payload) return null;
  try {
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const decoded = JSON.parse(atob(padded)) as { exp?: unknown };
    return typeof decoded.exp === "number" && Number.isFinite(decoded.exp) ? decoded.exp : null;
  } catch {
    return null;
  }
}

function isFresh(token: string): boolean {
  const expiry = decodeJwtExpiry(token);
  return expiry !== null && expiry - Date.now() / 1000 > FRESHNESS_WINDOW_SECONDS;
}

function stillMatches(snapshot: RefreshSnapshot): boolean {
  const current = useAuthStore.getState();
  return current.user?.id === snapshot.userId && current.refreshToken === snapshot.refreshToken;
}

function clearMatchingSession(snapshot: RefreshSnapshot): void {
  if (stillMatches(snapshot)) useAuthStore.getState().clear();
}

function startRefresh(snapshot: RefreshSnapshot): Promise<SessionReadiness> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const pair = await refreshTokens(snapshot.refreshToken);
      if (pair.user.id !== snapshot.userId) {
        throw new Error("refresh response user does not match the active session");
      }
      if (!stillMatches(snapshot)) return { status: "retry" } as const;
      useAuthStore.getState().setSession(pair);
      return { status: "ready", userId: snapshot.userId, accessToken: pair.access_token } as const;
    } catch (error) {
      if (error instanceof AuthApiError && error.status === 401) {
        clearMatchingSession(snapshot);
        return { status: "signed_out" } as const;
      }
      if (error instanceof AuthApiError && error.status >= 500) return { status: "retry" } as const;
      if (error instanceof TypeError) return { status: "retry" } as const;
      throw error;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

/**
 * Returns a session whose access token is safe to use for a new transport.
 * HTTP and WebSocket callers share the same refresh flight within this tab.
 */
export async function ensureFreshSession(): Promise<SessionReadiness> {
  const current = useAuthStore.getState();
  const userId = current.user?.id;
  const accessToken = current.accessToken;
  if (!userId || !accessToken) return { status: "signed_out" };
  if (isFresh(accessToken)) return { status: "ready", userId, accessToken };

  const refreshToken = current.refreshToken;
  if (!refreshToken) {
    useAuthStore.getState().clear();
    return { status: "signed_out" };
  }
  const snapshot = { userId, refreshToken };
  return startRefresh(snapshot);
}

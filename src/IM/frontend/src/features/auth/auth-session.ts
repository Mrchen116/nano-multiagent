import { desktopScopedKey } from "../../desktop/desktop-context";
import { AuthApiError, refreshTokens, login as loginApi, register as registerApi, logoutApi } from "./auth-api";
import { useAuthStore, type BrowserSession } from "./auth-store";

const FRESHNESS_WINDOW_SECONDS = 30;
export const SESSION_LOCK_TIMEOUT_MS = 8_000;
export type SessionReadiness =
  | { status: "ready"; userId: string; accessToken: string }
  | { status: "retry" }
  | { status: "signed_out" };
const refreshFlights = new Map<number, Promise<SessionReadiness>>();
let inTabLockTail: Promise<unknown> = Promise.resolve();
let channel: BroadcastChannel | undefined;
let channelName: string | undefined;
const SESSION_CHANGE_KEY = 'im_session_changed_at_v1';

function sessionChangeStorageKey() {
  return desktopScopedKey(SESSION_CHANGE_KEY);
}

function readSessionChangeTimestamp(): number {
  try {
    return Number(localStorage.getItem(sessionChangeStorageKey())) || 0;
  } catch {
    return 0;
  }
}

function recordSessionChangeTimestamp(): void {
  try {
    localStorage.setItem(sessionChangeStorageKey(), String(Date.now()));
  } catch {
    // Storage restrictions do not prevent current-tab cookie authentication.
  }
}

function sessionChannel(): BroadcastChannel | null {
  if (typeof BroadcastChannel !== "function") return null;
  const expectedName = desktopScopedKey("im-session");
  if (!channel || channelName !== expectedName) {
    try {
      channel?.close();
    } catch {
      // Ignore close errors from disposed browser contexts.
    }
    channel = undefined;
    channelName = undefined;
    try {
      const next = new BroadcastChannel(expectedName);
      next.onmessage = ({ data }) => {
        if (data !== "login" && data !== "logout") return;
        useAuthStore.getState().clear();
        if (data === "login") {
          useAuthStore.setState({ hydrated: false });
          void useAuthStore.getState().hydrate();
        }
      };
      channel = next;
      channelName = expectedName;
    } catch {
      return null;
    }
  }
  return channel;
}

function broadcastSessionChange(event: "login" | "logout"): void {
  recordSessionChangeTimestamp();
  try {
    sessionChannel()?.postMessage(event);
  } catch {
    channel = undefined;
    channelName = undefined;
  }
}

/** Adopt a server-verified document while retaining cross-tab account invalidation. */
export function adoptPageSession(session: BrowserSession): boolean {
  sessionChannel();
  // Another tab can change the Cookie while this document downloads its JS,
  // before our BroadcastChannel listener exists. Persist only this fence.
  if (readSessionChangeTimestamp() > performance.timeOrigin) return false;
  useAuthStore.getState().setSession(session, true);
  return true;
}

function enqueueInTab<T>(operation: () => Promise<T>): Promise<T> {
  const run = inTabLockTail.then(operation, operation);
  inTabLockTail = run.then(
    () => undefined,
    () => undefined
  );
  return run;
}

/** Coordinate cookie-bearing auth operations across tabs with bounded fallback.
 *
 * Non-SecureContext origins (such as private-LAN cleartext HTTP) omit `navigator.locks`,
 * and frozen or hibernated sibling tabs can hold a Web Lock indefinitely. When lock
 * acquisition is unavailable, rejected, or exceeds `SESSION_LOCK_TIMEOUT_MS`, execution
 * degrades to the in-tab queue while `revision` guards prevent stale state writes.
 * Once the lock is granted, errors thrown by `operation` propagate directly without replay.
 */
async function withSessionLock<T>(operation: () => Promise<T>): Promise<T> {
  sessionChannel();
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  if (typeof locks?.request !== "function") {
    return enqueueInTab(operation);
  }

  type LockAcquireState = "waiting" | "granted" | "fallback";
  const acquisition: { state: LockAcquireState } = { state: "waiting" };
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const lockTimeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      if (acquisition.state !== "waiting") return;
      acquisition.state = "fallback";
      const reason = new DOMException("Session lock timed out", "TimeoutError");
      controller.abort(reason);
      reject(reason);
    }, SESSION_LOCK_TIMEOUT_MS);
  });

  try {
    const lockRequest = locks.request(
      desktopScopedKey("im-session"),
      { signal: controller.signal },
      async () => {
        if (acquisition.state !== "waiting") return undefined as T;
        acquisition.state = "granted";
        if (timer !== undefined) clearTimeout(timer);
        return enqueueInTab(operation);
      }
    );
    Promise.resolve(lockRequest).catch(() => undefined);
    const result = await Promise.race([lockRequest, lockTimeout]);
    if (timer !== undefined) clearTimeout(timer);
    if (acquisition.state === "granted") {
      return result;
    }
    acquisition.state = "fallback";
  } catch (error) {
    if (timer !== undefined) clearTimeout(timer);
    if (acquisition.state === "granted") {
      throw error;
    }
    acquisition.state = "fallback";
  }

  return enqueueInTab(operation);
}

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

function startRefresh(revision: number): Promise<SessionReadiness> {
  const existing = refreshFlights.get(revision);
  if (existing) return existing;
  const flight = withSessionLock(async (): Promise<SessionReadiness> => {
    if (useAuthStore.getState().revision !== revision) return { status: "retry" };
    try {
      const session = await refreshTokens();
      if (useAuthStore.getState().revision !== revision) return { status: "retry" };
      useAuthStore.getState().setSession(session, true);
      return { status: "ready", userId: session.user.id, accessToken: session.access_token };
    } catch (error) {
      if (useAuthStore.getState().revision !== revision) return { status: "retry" };
      if (error instanceof AuthApiError && error.status === 401) {
        useAuthStore.getState().clear();
        return { status: "signed_out" };
      }
      return { status: "retry" };
    }
  }).finally(() => refreshFlights.delete(revision));
  refreshFlights.set(revision, flight);
  return flight;
}

/** Restore the browser session from the HttpOnly refresh cookie with bounded recovery.
 *
 * Side Effects:
 *   Transitions `useAuthStore` to authenticated (`200`), signed-out (`401`), or
 *   retryable `hydrationError` on transient/unexpected failures unless superseded by a newer `revision`.
 */
export async function restoreSession(): Promise<void> {
  const revision = useAuthStore.getState().revision;
  try {
    const result = await startRefresh(revision);
    if (useAuthStore.getState().revision !== revision) return;
    if (result.status === "retry" || !useAuthStore.getState().hydrated) {
      useAuthStore.setState({ hydrationError: true });
    }
  } catch {
    if (useAuthStore.getState().revision === revision && !useAuthStore.getState().hydrated) {
      useAuthStore.setState({ hydrationError: true });
    }
  }
}

/** HTTP and WebSocket transports share a single refresh within this tab. */
export async function ensureFreshSession(): Promise<SessionReadiness> {
  const current = useAuthStore.getState();
  if (!current.user || !current.accessToken) return { status: "signed_out" };
  if (isFresh(current.accessToken)) return { status: "ready", userId: current.user.id, accessToken: current.accessToken };
  return forceRefreshSession();
}

export function forceRefreshSession(): Promise<SessionReadiness> {
  const current = useAuthStore.getState();
  if (!current.user || !current.accessToken) return Promise.resolve({ status: "signed_out" });
  return startRefresh(current.revision);
}

async function establishSession(operation: () => Promise<BrowserSession>): Promise<BrowserSession> {
  useAuthStore.getState().clear();
  const revision = useAuthStore.getState().revision;
  return withSessionLock(async () => {
    if (useAuthStore.getState().revision !== revision) throw new Error("Session changed");
    const session = await operation();
    if (useAuthStore.getState().revision !== revision) throw new Error("Session changed");
    useAuthStore.getState().setSession(session, true);
    broadcastSessionChange("login");
    return session;
  });
}

export function login(input: Parameters<typeof loginApi>[0]) {
  return establishSession(() => loginApi(input));
}
export function register(input: Parameters<typeof registerApi>[0]) {
  return establishSession(() => registerApi(input));
}

/** Clear in-memory auth state immediately and revoke the server cookie session if still current. */
export function logout(): Promise<void> {
  useAuthStore.getState().clear();
  const revision = useAuthStore.getState().revision;
  return withSessionLock(async () => {
    if (useAuthStore.getState().revision !== revision) return;
    await logoutApi();
    if (useAuthStore.getState().revision !== revision) return;
    broadcastSessionChange("logout");
  });
}

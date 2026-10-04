import { AuthApiError, refreshTokens, login as loginApi, register as registerApi, logoutApi } from "./auth-api";
import { useAuthStore, type BrowserSession } from "./auth-store";

const FRESHNESS_WINDOW_SECONDS = 30;
export type SessionReadiness =
  | { status: "ready"; userId: string; accessToken: string }
  | { status: "retry" }
  | { status: "signed_out" };
const refreshFlights = new Map<number, Promise<SessionReadiness>>();
let channel: BroadcastChannel | undefined;

function sessionChannel() {
  if (!channel) {
    channel = new BroadcastChannel("im-session");
    channel.onmessage = ({ data }) => {
      if (data !== "login" && data !== "logout") return;
      useAuthStore.getState().clear();
      if (data === "login") {
        useAuthStore.setState({ hydrated: false });
        void useAuthStore.getState().hydrate();
      }
    };
  }
  return channel;
}

async function withSessionLock<T>(operation: () => Promise<T>): Promise<T> {
  sessionChannel();
  return navigator.locks.request("im-session", operation);
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
      useAuthStore.getState().setSession(session);
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

export async function restoreSession(): Promise<void> {
  const revision = useAuthStore.getState().revision;
  const result = await startRefresh(revision);
  if (result.status === "retry" && useAuthStore.getState().revision === revision) {
    useAuthStore.setState({ hydrationError: true });
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
    useAuthStore.getState().setSession(session);
    sessionChannel().postMessage("login");
    return session;
  });
}

export function login(input: Parameters<typeof loginApi>[0]) {
  return establishSession(() => loginApi(input));
}
export function register(input: Parameters<typeof registerApi>[0]) {
  return establishSession(() => registerApi(input));
}
export function logout(): Promise<void> {
  useAuthStore.getState().clear();
  return withSessionLock(async () => {
    await logoutApi();
    sessionChannel().postMessage("logout");
  });
}

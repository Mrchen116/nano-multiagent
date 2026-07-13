import { authFetchJson } from "../../features/auth/auth-fetch";
import { ensureFreshSession } from "../../features/auth/auth-session";
import { useAuthStore } from "../../features/auth/auth-store";
import {
  createUserStreamRuntime,
  type UserStreamEvent,
  type UserStreamSocket,
  type UserStreamSubscriber
} from "./user-stream-runtime";

export type { UserStreamEvent, UserStreamSubscriber };

const CURSOR_PREFIX = "im:user_stream_cursor:";

function resolveUserStreamUrl(accessToken: string): string {
  const configuredBase = (import.meta.env.VITE_IM_API_BASE_URL ?? "").replace(/\/$/, "");
  const httpOrigin = configuredBase ? new URL(configuredBase, window.location.origin).origin : window.location.origin;
  const url = new URL("/im/ws/user", httpOrigin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("token", accessToken);
  return url.toString();
}

const runtime = createUserStreamRuntime({
  getSession: () => {
    const state = useAuthStore.getState();
    return { userId: state.user?.id ?? null, accessToken: state.accessToken };
  },
  subscribeSession: (listener) => useAuthStore.subscribe(listener),
  ensureSession: ensureFreshSession,
  createSocket: (url) => new WebSocket(url) as UserStreamSocket,
  readCursor: (userId) => {
    const raw = window.sessionStorage.getItem(`${CURSOR_PREFIX}${userId}`);
    if (raw === null) return 0;
    const parsed = Number.parseInt(raw, 10);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  },
  writeCursor: (userId, cursor) => window.sessionStorage.setItem(`${CURSOR_PREFIX}${userId}`, String(cursor)),
  sync: async () => {
    const result = await authFetchJson<{ max_event_id: number }>("/im/v1/sync");
    if (!Number.isFinite(result.max_event_id) || result.max_event_id < 0) {
      throw new Error("GET /im/v1/sync returned an invalid max_event_id");
    }
    return { maxEventId: result.max_event_id };
  },
  reportError: (error) => console.error("user stream runtime error", error),
  resolveUrl: resolveUserStreamUrl
});

export function subscribeUserStream(subscriber: UserStreamSubscriber): () => void {
  return runtime.subscribe(subscriber);
}

// WS subscription for IM → Browser events.
//
// The IM service exposes `/im/ws/user`; auth is handled by query-string
// `access_token=` (the WS handshake cannot carry an Authorization header
// portably in browsers). The connection lives for the chat workspace's
// lifetime; `openChatStream` returns a handle that closes the socket and
// stops dispatching when the caller unmounts.

import { useAuthStore } from "../../auth/auth-store";
import type { WsEvent } from "./chat-types";

const KNOWN_TYPES = new Set([
  "message.created",
  "message.delta",
  "message.completed",
  "tool_call.upserted",
  "tool_call.completed"
]);

function resolveWsUrl(token: string): string {
  if (typeof window === "undefined") return `/im/ws/user?access_token=${encodeURIComponent(token)}`;
  const httpOrigin = window.location.origin;
  const url = new URL("/im/ws/user", httpOrigin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("access_token", token);
  return url.toString();
}

export interface ChatStreamHandle {
  close(): void;
}

export interface ChatStreamOptions {
  onEvent(event: WsEvent): void;
  onError?(error: Error): void;
}

export function openChatStream(opts: ChatStreamOptions): ChatStreamHandle {
  const token = useAuthStore.getState().accessToken;
  if (!token) {
    // No session → no stream. Caller can re-open after login.
    return { close: () => {} };
  }
  const ws = new WebSocket(resolveWsUrl(token));
  let closed = false;

  ws.onmessage = (frame) => {
    if (closed) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(String(frame.data));
    } catch {
      return;
    }
    if (!parsed || typeof parsed !== "object") return;
    const type = (parsed as { type?: unknown }).type;
    if (typeof type !== "string" || !KNOWN_TYPES.has(type)) return;
    opts.onEvent(parsed as WsEvent);
  };
  ws.onerror = () => opts.onError?.(new Error("chat stream socket error"));

  return {
    close() {
      closed = true;
      try { ws.close(); } catch { /* socket already closed */ }
    }
  };
}

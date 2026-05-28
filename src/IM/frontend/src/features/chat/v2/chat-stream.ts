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
  "tool_call.completed",
  // feat-333-M3/R1: permission ask flow — agent awaits user decision and resolution.
  // Backend emits these from IM event_bridge.on_permission_request/on_permission_resolved.
  "permission.request",
  "permission.resolved"
]);

function resolveWsUrl(token: string): string {
  if (typeof window === "undefined") return `/im/ws/user?token=${encodeURIComponent(token)}`;
  const httpOrigin = window.location.origin;
  const url = new URL("/im/ws/user", httpOrigin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("token", token);
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
    const envelope = parsed as Record<string, unknown>;

    // IM user-stream frames use {op:"event", event_type:..., data:{...}} envelope.
    // Reconstruct a flat WsEvent by merging data fields with the event_type as `type`.
    const eventType = envelope.event_type;
    if (typeof eventType === "string" && KNOWN_TYPES.has(eventType)) {
      const data = (typeof envelope.data === "object" && envelope.data !== null)
        ? (envelope.data as Record<string, unknown>)
        : {};
      opts.onEvent({ ...data, type: eventType } as WsEvent);
      return;
    }
    // Fallback: some frames may already carry a flat `type` field (e.g. direct pushes).
    const type = envelope.type;
    if (typeof type === "string" && KNOWN_TYPES.has(type)) {
      opts.onEvent(envelope as unknown as WsEvent);
    }
  };
  ws.onerror = () => opts.onError?.(new Error("chat stream socket error"));

  return {
    close() {
      closed = true;
      try { ws.close(); } catch { /* socket already closed */ }
    }
  };
}

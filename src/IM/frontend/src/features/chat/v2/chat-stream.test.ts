import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "../../auth/auth-store";
import { openChatStream } from "./chat-stream";
import type { WsEvent } from "./chat-types";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  readyState = 0;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  sent: string[] = [];
  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
  send(data: string) { this.sent.push(data); }
  close() { this.readyState = 3; this.onclose?.(new CloseEvent("close")); }
  emit(payload: unknown) { this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) })); }
  static last(): FakeWebSocket { return FakeWebSocket.instances[FakeWebSocket.instances.length - 1]!; }
}

function seedAuth() {
  useAuthStore.getState().setSession({
    access_token: "access-test",
    refresh_token: "refresh-test",
    user: {
      id: "user-1", username: "alex", display_name: "Alex", owner_id: "user-1",
      locale: "en", default_entry_node_id: null, owned_node_ids: [], created_at: "2026-01-01T00:00:00Z"
    }
  });
}

describe("chat-stream", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    seedAuth();
    vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
  });
  afterEach(() => {
    useAuthStore.getState().clear();
    vi.unstubAllGlobals();
  });

  it("opens a WebSocket against /im/ws/user with the access token as ?token= query param", () => {
    const handle = openChatStream({ onEvent: () => {} });
    const ws = FakeWebSocket.last();
    expect(ws.url).toContain("/im/ws/user");
    expect(ws.url).toContain("token=access-test");
    expect(ws.url).not.toContain("access_token=");
    handle.close();
  });

  it("dispatches parsed JSON events to the onEvent callback", () => {
    const events: WsEvent[] = [];
    const handle = openChatStream({ onEvent: (e) => events.push(e) });
    const ws = FakeWebSocket.last();
    ws.emit({
      type: "message.delta", conversation_id: "c1", message_id: "m2", delta_text: "hi"
    });
    expect(events).toHaveLength(1);
    expect(events[0]!.type).toBe("message.delta");
    handle.close();
  });

  it("ignores non-JSON or unrelated payloads without throwing", () => {
    const events: WsEvent[] = [];
    const handle = openChatStream({ onEvent: (e) => events.push(e) });
    const ws = FakeWebSocket.last();
    ws.onmessage?.(new MessageEvent("message", { data: "not-json" }));
    ws.onmessage?.(new MessageEvent("message", { data: JSON.stringify({ type: "unknown.thing" }) }));
    expect(events).toEqual([]);
    handle.close();
  });
});

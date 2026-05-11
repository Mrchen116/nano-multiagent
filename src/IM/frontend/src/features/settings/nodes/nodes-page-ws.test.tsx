import { screen, act, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { useAuthStore } from "../../auth/auth-store";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as typeof fetch;

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static readonly OPEN = 1;
  static readonly CONNECTING = 0;
  static readonly CLOSED = 3;
  readyState = FakeWebSocket.OPEN;
  url: string;
  onopen?: (ev: Event) => void;
  onmessage?: (ev: MessageEvent) => void;
  onclose?: (ev: CloseEvent) => void;
  onerror?: (ev: Event) => void;
  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.onopen?.(new Event("open"));
    });
  }
  send(_data: string) {
    /* noop */
  }
  close() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close"));
  }
  emit(eventType: string, data: Record<string, unknown>) {
    this.onmessage?.(
      new MessageEvent("message", {
        data: JSON.stringify({ op: "event", event_type: eventType, data })
      })
    );
  }
}

afterEach(() => {
  fetchMock.mockReset();
  FakeWebSocket.instances = [];
  // Reset store user so subsequent tests don't share session state.
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null });
});

describe("nodes page — node.status_changed WS subscription", () => {
  it("flips a node's status pill from online to offline when the owner WS emits node.status_changed", async () => {
    vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);

    // Seed an authenticated user so the user-stream WS auto-attaches with our selfUserId.
    useAuthStore.setState({
      accessToken: "tok",
      refreshToken: "rtok",
      user: {
        id: "user-1",
        username: "alice",
        display_name: "Alice",
        owner_id: "owner-1",
        owned_node_ids: ["node-a"],
        default_entry_node_id: "node-a",
        locale: "en",
        created_at: "2026-05-11T00:00:00Z"
      },
      hydrated: true
    });

    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes") {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                node_id: "node-a",
                owner_id: "owner-1",
                node_name: "node-a",
                status: "online",
                last_heartbeat_at: "2026-05-11T10:00:00Z",
                agent_count: 1,
                version: "1.8.2",
                relay_enabled: true,
                reporting_enabled: true,
                alias: null,
                last_error: null
              }
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      if (url === "/im/v1/agents") {
        return Promise.resolve(
          new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } })
        );
      }
      return Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    const pill = await screen.findByTestId("node-status-pill-node-a");
    expect(pill).toHaveTextContent(/online/i);

    // Wait for the shared user-stream WS to open.
    await waitFor(() => {
      expect(FakeWebSocket.instances.length).toBeGreaterThan(0);
    });
    const ws = FakeWebSocket.instances[FakeWebSocket.instances.length - 1]!;

    await act(async () => {
      ws.emit("node.status_changed", {
        seq: 7,
        node_id: "node-a",
        status: "offline",
        last_heartbeat_at: "2026-05-11T10:01:00Z",
        last_error: "heartbeat timeout"
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId("node-status-pill-node-a")).toHaveTextContent(/offline/i);
    });
    expect(screen.getByTestId("node-last-error-node-a")).toHaveTextContent("heartbeat timeout");
  });
});

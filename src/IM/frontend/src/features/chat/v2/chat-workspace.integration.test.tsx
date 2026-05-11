import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import { ChatWorkspacePageV2 } from "./chat-workspace-page";

// ─── Fake WebSocket ─────────────────────────────────────────────────────────
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 1;
  url: string;
  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
  close() {
    this.readyState = 3;
  }
  send(_data: string) {}
  emit(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

const FIXTURES = {
  conversations: [
    {
      id: "c1",
      title: "Planner",
      participants: [
        { type: "user", id: "u-self", display_name: "You" },
        { type: "agent", id: "a-planner", display_name: "Planner" }
      ],
      participant_ids: ["u-self", "a-planner"],
      type: "direct",
      direct_kind: "agent",
      owner_id: "u-self",
      creator_id: "u-self",
      is_pinned: false,
      is_muted: false,
      unread_count: 0,
      last_message_preview: null,
      last_message_at: null,
      created_at: "2026-05-01T00:00:00Z"
    }
  ],
  messagesC1: [
    {
      id: "m1",
      conversation_id: "c1",
      sender: { type: "user", id: "u-self", display_name: "You" },
      sender_user_id: "u-self",
      sender_type: "user",
      content: "Hi Planner",
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-05-01T00:00:01Z"
    }
  ]
};

function jsonResponse(data: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" }, ...init });
}

function mockFetch(): ReturnType<typeof vi.fn> {
  const sent: { url: string; init?: RequestInit }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    sent.push({ url, init });
    if (url.endsWith("/im/v1/conversations") && (!init || init.method === undefined || init.method === "GET")) {
      return jsonResponse({ items: FIXTURES.conversations });
    }
    if (/\/im\/v1\/conversations\/c1\/messages/.test(url) && (!init || init.method === undefined || init.method === "GET")) {
      return jsonResponse({ items: FIXTURES.messagesC1, next_before_message_id: null });
    }
    if (url.endsWith("/im/v1/agents")) {
      return jsonResponse([{ agent_id: "a-planner", display_name: "Planner" }]);
    }
    if (/\/im\/v1\/conversations\/c1\/messages$/.test(url) && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      return jsonResponse({
        id: "m2",
        conversation_id: "c1",
        sender: body.sender,
        sender_user_id: "u-self",
        sender_type: "user",
        content: body.content,
        attachments: [],
        delivery_status: "sent",
        created_at: "2026-05-01T00:00:02Z"
      });
    }
    return new Response("not found", { status: 404 });
  });
  (fn as unknown as { sent: typeof sent }).sent = sent;
  return fn;
}

function renderAtRoute(initial: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/chat" element={<ChatWorkspacePageV2 />} />
          <Route path="/chat/:conversationId" element={<ChatWorkspacePageV2 />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ChatWorkspacePage v2 — integration", () => {
  let originalWS: typeof WebSocket;
  let fetchSpy: ReturnType<typeof mockFetch>;

  beforeEach(() => {
    FakeWebSocket.instances = [];
    originalWS = globalThis.WebSocket;
    (globalThis as unknown as { WebSocket: unknown }).WebSocket = FakeWebSocket;
    fetchSpy = mockFetch();
    vi.stubGlobal("fetch", fetchSpy);
    useAuthStore.getState().setSession({
      access_token: "tk",
      refresh_token: "rk",
      user: {
        id: "u-self",
        username: "self",
        display_name: "Self",
        owner_id: "u-self",
        locale: "en",
        default_entry_node_id: null,
        owned_node_ids: [],
        created_at: "2026-05-01T00:00:00Z"
      }
    });
  });

  afterEach(() => {
    (globalThis as unknown as { WebSocket: typeof WebSocket }).WebSocket = originalWS;
    vi.unstubAllGlobals();
    useAuthStore.getState().clear();
  });

  it("renders the conversation list and the active conversation messages", async () => {
    renderAtRoute("/chat/c1");
    expect(await screen.findByRole("button", { name: /Planner/ })).toBeInTheDocument();
    expect(await screen.findByText("Hi Planner")).toBeInTheDocument();
    // Header title rendered too:
    expect(screen.getByRole("heading", { name: "Planner" })).toBeInTheDocument();
  });

  it("renders an incoming agent message + delta + completion via the WS stream", async () => {
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");

    // The reducer + page wait for `messages` to be hydrated before applying WS
    // events; once the historical fetch resolves, FakeWebSocket has been created
    // by the workspace effect. Emit the three-event sequence.
    await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0));
    const ws = FakeWebSocket.instances[0]!;

    ws.emit({
      type: "message.created",
      conversation_id: "c1",
      message_id: "m99",
      sender_user_id: "agent:a-planner",
      sender_type: "agent",
      content: "",
      tool_calls: [],
      token_usage: null,
      delivery_status: "running",
      created_at: "2026-05-01T00:00:10Z"
    });
    ws.emit({
      type: "message.delta",
      conversation_id: "c1",
      message_id: "m99",
      delta_text: "Hello "
    });
    ws.emit({
      type: "message.delta",
      conversation_id: "c1",
      message_id: "m99",
      delta_text: "there"
    });
    ws.emit({
      type: "message.completed",
      conversation_id: "c1",
      message_id: "m99",
      content: "Hello there",
      token_usage: { output: 12, context_used: 200, context_window: 200_000 }
    });

    await waitFor(() => expect(screen.getByText(/Hello there/)).toBeInTheDocument());
  });

  it("posts a new message and clears the composer", async () => {
    const user = userEvent.setup();
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");
    const composer = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.type(composer, "hello");
    await user.click(screen.getByRole("button", { name: /Send/i }));
    await waitFor(() => {
      const sent = (fetchSpy as unknown as { sent: { url: string; init?: RequestInit }[] }).sent;
      const posted = sent.find((r) => /messages$/.test(r.url) && r.init?.method === "POST");
      expect(posted).toBeDefined();
    });
    expect(composer.value).toBe("");
  });
});

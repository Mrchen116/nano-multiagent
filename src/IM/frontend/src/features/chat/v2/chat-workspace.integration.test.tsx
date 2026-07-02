import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import { ChatWorkspacePageV2 } from "./chat-workspace-page";
import type { ParsedImStreamEvent } from "../../chat/im-chat-api";

// ─── Mock attachUserConversationStream ──────────────────────────────────────
// chat-workspace-page 订阅 user-scoped SSE/WS 流（node.status_changed /
// agent.status_changed / message.*）时会调用此函数。测试通过 capturedStatusHandler
// 直接注入事件，通过 capturedResyncHandler 断言 onResyncRequired 已注册。
let capturedStatusHandler: ((ev: ParsedImStreamEvent) => void) | null = null;
let capturedResyncHandler: (() => Promise<void>) | null = null;

vi.mock("../../chat/im-chat-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../chat/im-chat-api")>();
  return {
    ...actual,
    attachUserConversationStream: (input: {
      selfUserId: string;
      token: string;
      onEvent: (ev: ParsedImStreamEvent) => void;
      onResyncRequired?: () => Promise<void>;
    }) => {
      capturedStatusHandler = input.onEvent;
      capturedResyncHandler = input.onResyncRequired ?? null;
      return () => {
        capturedStatusHandler = null;
        capturedResyncHandler = null;
      };
    }
  };
});

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
      created_at: "2026-05-01T00:00:00Z",
      run_state: "idle",
      source_agent_id: "a-planner",
      source_jsonl_path: "/tmp/planner-session.jsonl"
    },
    {
      id: "c2",
      title: "Research Squad",
      participants: [
        { type: "user", id: "u-self", display_name: "You", user_id: "u-self" },
        { type: "agent", id: "a-planner", display_name: "Planner", user_id: "user-uuid-planner" },
        { type: "agent", id: "a-writer", display_name: "Writer", user_id: "user-uuid-writer" }
      ],
      participant_ids: ["u-self", "a-planner", "a-writer"],
      type: "group",
      direct_kind: null,
      owner_id: "u-self",
      creator_id: "u-self",
      is_pinned: false,
      is_muted: false,
      unread_count: 0,
      last_message_preview: null,
      last_message_at: null,
      created_at: "2026-05-01T00:00:00Z",
      run_state: "idle",
      source_agent_id: "a-writer",
      source_jsonl_path: "/tmp/writer-session.jsonl"
    },
    {
      id: "c3",
      title: "Empty Group",
      participants: [
        { type: "user", id: "u-self", display_name: "You", user_id: "u-self" }
      ],
      participant_ids: ["u-self"],
      type: "group",
      direct_kind: null,
      owner_id: "u-self",
      creator_id: "u-self",
      is_pinned: false,
      is_muted: false,
      unread_count: 0,
      last_message_preview: null,
      last_message_at: null,
      created_at: "2026-05-01T00:00:00Z",
      run_state: "idle",
      source_agent_id: null,
      source_jsonl_path: null
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

function mockFetch(opts: { distillerVisible?: boolean } = {}): ReturnType<typeof vi.fn> {
  const distillerVisible = opts.distillerVisible ?? true;
  const sent: { url: string; init?: RequestInit }[] = [];
  const conversations = [...FIXTURES.conversations];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    sent.push({ url, init });
    if (url.endsWith("/im/v1/conversations") && (!init || init.method === undefined || init.method === "GET")) {
      return jsonResponse({ items: conversations });
    }
    if (url.endsWith("/im/v1/conversations") && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      const agent = (body.participants ?? []).find((p: { type?: string }) => p.type === "agent");
      const agentId = agent?.id ?? "a-planner";
      const created = {
        id: `c-distill-${conversations.length}`,
        title: body.title,
        participants: [
          { type: "user", id: "u-self", display_name: "You", user_id: "u-self" },
          { type: "agent", id: agentId, display_name: agentId === "a-writer" ? "Writer" : "Planner", user_id: `user-uuid-${agentId}` }
        ],
        participant_ids: ["u-self", agentId],
        type: "direct",
        direct_kind: "agent",
        owner_id: "u-self",
        creator_id: "u-self",
        is_pinned: false,
        is_muted: false,
        unread_count: 0,
        last_message_preview: null,
        last_message_at: null,
        created_at: "2026-05-01T00:02:00Z",
        run_state: "idle",
        source_agent_id: agentId,
        source_jsonl_path: null
      };
      conversations.unshift(created);
      return jsonResponse(created, { status: 201 });
    }
    if (/\/im\/v1\/conversations\/c1\/messages/.test(url) && (!init || init.method === undefined || init.method === "GET")) {
      return jsonResponse({ items: FIXTURES.messagesC1, next_before_message_id: null });
    }
    if (/\/im\/v1\/conversations\/[^/]+\/messages/.test(url) && (!init || init.method === undefined || init.method === "GET")) {
      return jsonResponse({ items: [], next_before_message_id: null });
    }
    if (url.endsWith("/im/v1/agents")) {
      return jsonResponse([
        { agent_id: "a-planner", display_name: "Planner", node_id: "node-prod", user_id: "user-uuid-planner" },
        { agent_id: "a-writer", display_name: "Writer", node_id: "node-prod", user_id: "user-uuid-writer" },
        { agent_id: "a-reviewer", display_name: "Reviewer", node_id: "node-prod", user_id: "user-uuid-reviewer" }
      ]);
    }
    if (url.endsWith("/im/v1/nodes")) {
      return jsonResponse([
        {
          node_id: "node-prod",
          owner_id: "u-self",
          node_name: "laptop-prod",
          status: "online",
          last_heartbeat_at: "2026-05-01T00:00:00Z",
          agent_count: 1,
          version: "1.0",
          relay_enabled: true,
          reporting_enabled: true,
          alias: null,
          last_error: null
        }
      ]);
    }
    if (/\/im\/v1\/agents\/[^/]+\/config\?source=live$/.test(url)) {
      const agentId = decodeURIComponent(url.match(/\/im\/v1\/agents\/([^/]+)\//)![1]!);
      return jsonResponse({
        agent_id: agentId,
        owner_id: "u-self",
        display_name: agentId === "a-writer" ? "Writer" : "Planner",
        description: "",
        system_prompt: "",
        skills: [],
        tool_allowlist: [],
        group_reply_policy: "manual",
        default_model: null,
        workspace_root: `/tmp/${agentId}`,
        workspace_is_default: false,
        profile_version: 1,
        node_id: "node-prod"
      });
    }
    if (/\/im\/v1\/agents\/[^/]+\/capabilities$/.test(url)) {
      return jsonResponse({
        node_id: "node-prod",
        node_name: "laptop-prod",
        node_status: "online",
        skills: distillerVisible
          ? [{ name: "conversation-skill-distiller", description: "Distill conversations", location: "/tmp/distiller/SKILL.md" }]
          : [],
        tools: [],
        model_options: [],
        platform_default_model: null,
        default_system_prompt: ""
      });
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
        attachments: body.attachments ?? [],
        delivery_status: "sent",
        created_at: "2026-05-01T00:00:02Z"
      });
    }
    if (/\/im\/v1\/uploads/.test(url) && init?.method === "POST") {
      return jsonResponse(
        {
          url: "http://im.local/im/uploads/dropped.png",
          content_type: "image/png",
          file_name: "dropped.png"
        },
        { status: 201 }
      );
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
    capturedStatusHandler = null;
    capturedResyncHandler = null;
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

  it("prefills the distiller skill prompt for a single-source conversation", async () => {
    const user = userEvent.setup();
    renderAtRoute("/chat");
    const plannerRow = await screen.findByRole("button", { name: /Planner/ });
    fireEvent.contextMenu(plannerRow);

    await user.click(screen.getByRole("checkbox", { name: /Planner/ }));
    await user.click(screen.getByRole("button", { name: "Distill to skill" }));
    await user.click(screen.getByRole("button", { name: "Start distillation" }));

    const composer = await screen.findByRole("textbox") as HTMLTextAreaElement;
    await waitFor(() => expect(composer.value).toContain("/skill:conversation-skill-distiller"));
    expect(composer.value).toContain("source_jsonl_paths:");
    expect(composer.value).toContain("  /tmp/planner-session.jsonl");
    expect(composer.value).toContain("execution_agent_id: a-planner");
    expect(composer.value).toContain("target_scope: agent");
  });

  it("requires an execution agent for cross-agent distillation sources", async () => {
    const user = userEvent.setup();
    renderAtRoute("/chat");
    await screen.findByRole("button", { name: /Planner/ });
    await user.click(screen.getByRole("button", { name: "Generate skill" }));

    await user.click(screen.getByRole("checkbox", { name: /Planner/ }));
    await user.click(screen.getByRole("checkbox", { name: /Research Squad/ }));
    await user.click(screen.getByRole("button", { name: "Distill to skill" }));

    expect(screen.getByText("Execution agent")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /Writer/ }));
    await user.click(screen.getByRole("radio", { name: "PA product" }));
    await user.click(screen.getByRole("button", { name: "Start distillation" }));

    const composer = await screen.findByRole("textbox") as HTMLTextAreaElement;
    await waitFor(() => expect(composer.value).toContain("execution_agent_id: a-writer"));
    expect(composer.value).toContain("target_scope: pa");
    expect(composer.value).toContain("  /tmp/planner-session.jsonl");
    expect(composer.value).toContain("  /tmp/writer-session.jsonl");
  });

  it("does not prefill the distiller command when the execution agent cannot see the skill", async () => {
    const user = userEvent.setup();
    fetchSpy = mockFetch({ distillerVisible: false });
    vi.stubGlobal("fetch", fetchSpy);

    renderAtRoute("/chat");
    await screen.findByRole("button", { name: /Planner/ });
    await user.click(screen.getByRole("button", { name: "Generate skill" }));
    await user.click(screen.getByRole("checkbox", { name: /Planner/ }));
    await user.click(screen.getByRole("button", { name: "Distill to skill" }));
    await user.click(screen.getByRole("button", { name: "Start distillation" }));

    expect(await screen.findByText(/Enable conversation-skill-distiller/)).toBeInTheDocument();
    const postedConversation = (fetchSpy as unknown as { sent: { url: string; init?: RequestInit }[] }).sent.find(
      (r) => r.url.endsWith("/im/v1/conversations") && r.init?.method === "POST"
    );
    expect(postedConversation).toBeUndefined();
  });

  // bugfix-442: 侧边栏会话列表必须随实时消息流 + 读消息刷新，否则未读角标 /
  // preview / 时间 / 排序停在加载时的快照。两条 regression 分别锁住两个触发点。
  function conversationGetCount(spy: ReturnType<typeof mockFetch>): number {
    const sent = (spy as unknown as { sent: { url: string; init?: RequestInit }[] }).sent;
    return sent.filter(
      (s) =>
        s.url.endsWith("/im/v1/conversations") &&
        (!s.init || s.init.method === undefined || s.init.method === "GET")
    ).length;
  }

  it("re-fetches conversations when a message event arrives (unread/preview/order update)", async () => {
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");
    // 用户维流由 page 订阅，mock 把它的 onEvent 捕到 capturedStatusHandler。
    await waitFor(() => expect(capturedStatusHandler).toBeTruthy());
    const before = conversationGetCount(fetchSpy);
    act(() => {
      capturedStatusHandler!({
        eventType: "message.sent",
        payload: {
          conversation_id: "c2",
          message_id: "m-incoming",
          sender_user_id: "agent:a-planner",
          sender_type: "agent",
          content: "新消息到达",
          created_at: "2026-05-01T00:01:00Z"
        },
        eventId: 42
      });
    });
    await waitFor(() => expect(conversationGetCount(fetchSpy)).toBeGreaterThan(before));
  });

  // Fix A: canonical dotted name message.created（agent 回复触发的事件）必须和
  // message.sent 一样驱动侧边栏刷新。修前只匹配下划线 message_created (legacy alias)，
  // 点号版本被遗漏 → agent 回复不触发 unread/preview 更新。
  it("re-fetches conversations when a message.created (canonical dotted) event arrives", async () => {
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");
    await waitFor(() => expect(capturedStatusHandler).toBeTruthy());
    const before = conversationGetCount(fetchSpy);
    act(() => {
      capturedStatusHandler!({
        eventType: "message.created",
        payload: {
          conversation_id: "c2",
          message_id: "m-agent-reply",
          sender_user_id: "user-uuid-planner",
          sender_type: "agent",
          content: "agent 回复",
          created_at: "2026-05-01T00:01:00Z"
        },
        eventId: 43
      });
    });
    await waitFor(() => expect(conversationGetCount(fetchSpy)).toBeGreaterThan(before));
  });

  // Fix B: v2 订阅必须注册 onResyncRequired，否则断线重连后 IM 发 resync 命令时
  // v2 侧边栏不强制刷新，可能停在断线期间错过消息的旧状态。
  it("v2 subscription registers onResyncRequired for post-reconnect refresh", async () => {
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");
    await waitFor(() => expect(capturedStatusHandler).toBeTruthy());
    // onResyncRequired must be registered so the shared resync path invokes it.
    expect(capturedResyncHandler).not.toBeNull();
  });

  it("re-fetches conversations after reading so the unread badge can clear", async () => {
    // 读消息走 mark_as_read=true 清零后端 unread；前端须重新拉会话列表角标才落地。
    // 没有这次刷新，/conversations 只会被 GET 一次（初次列表）。
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");
    await waitFor(() => expect(conversationGetCount(fetchSpy)).toBeGreaterThanOrEqual(2));
  });

  it("renders an incoming agent message + delta + completion via the WS stream", async () => {
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");

    // The reducer + page wait for `messages` to be hydrated before applying WS
    // events; once the historical fetch resolves, FakeWebSocket has been created
    // by the workspace effect. Emit the three-event sequence.
    await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0));
    const ws = FakeWebSocket.instances[0]!;

    act(() => {
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
    });

    await waitFor(() => expect(screen.getByText(/Hello there/)).toBeInTheDocument());
  });

  // feat-414-M1: message.completed 带 elapsed_ms → 气泡 status 行显示耗时
  it("shows elapsed_ms in the bubble status row after message.completed", async () => {
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");
    const ws = FakeWebSocket.instances[0]!;

    act(() => {
    ws.emit({
      type: "message.created",
      conversation_id: "c1",
      message_id: "m-elapsed",
      sender_user_id: "agent:a-planner",
      sender_type: "agent",
      content: "",
      tool_calls: [],
      token_usage: null,
      delivery_status: "running",
      created_at: new Date(Date.now() - 5000).toISOString(),
    });
    ws.emit({
      type: "message.completed",
      conversation_id: "c1",
      message_id: "m-elapsed",
      content: "Done answer",
      token_usage: null,
      elapsed_ms: 3721,
    });
    });

    await waitFor(() => {
      const chip = screen.getByTestId("message-elapsed-m-elapsed");
      // formatDuration(3721) = "3.7s"
      expect(chip.textContent).toContain("3.7s");
    });
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

  it("drops an image into the composer, uploads it, and sends with attachments in the payload", async () => {
    const user = userEvent.setup();
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");

    const composer = screen.getByRole("textbox") as HTMLTextAreaElement;
    const dropZone = composer.closest("[data-dragging]") as HTMLElement;
    expect(dropZone).toBeTruthy();

    const file = new File([new Uint8Array(8)], "dropped.png", { type: "image/png" });
    const { fireEvent } = await import("@testing-library/react");
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file], items: [], types: ["Files"] }
    });

    const chipImg = await screen.findByRole("img", { name: "dropped.png" });
    expect(chipImg).toHaveAttribute("src", "http://im.local/im/uploads/dropped.png");

    await user.type(composer, "see image");
    await user.click(screen.getByRole("button", { name: /Send/i }));

    await waitFor(() => {
      const sent = (fetchSpy as unknown as { sent: { url: string; init?: RequestInit }[] }).sent;
      const posted = sent.find(
        (r) => /\/conversations\/c1\/messages$/.test(r.url) && r.init?.method === "POST"
      );
      expect(posted).toBeDefined();
      const body = JSON.parse(String(posted!.init!.body));
      expect(body.attachments).toEqual([
        {
          url: "http://im.local/im/uploads/dropped.png",
          content_type: "image/png",
          file_name: "dropped.png"
        }
      ]);
      expect(body.content).toBe("see image");
    });

    // composer + chip strip both reset after send. (M18 R9-3: the user's bubble
    // is now rendered optimistically with its attachments, so we scope this
    // assertion to the composer chip strip rather than the whole document.)
    expect(composer.value).toBe("");
    const composerChipStrip = composer.closest("form")?.querySelector(".chat-composer-chip-strip");
    expect(composerChipStrip?.querySelector("img[alt='dropped.png']")).toBeFalsy();
  });

  it("R9-3: optimistically renders the user's bubble in the pane the instant the POST resolves", async () => {
    const user = userEvent.setup();
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");
    const composer = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.type(composer, "Say hello briefly");
    await user.click(screen.getByRole("button", { name: /Send/i }));

    // The user-authored bubble should land in the main pane without waiting for
    // a WS replay (which historically only echoed via message.delta for the
    // agent reply, leaving the user-self bubble missing until refetch).
    await waitFor(() => {
      expect(screen.getByText("Say hello briefly")).toBeInTheDocument();
    });

    // A late echo for the same message id must not produce a duplicate bubble.
    await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0));
    const ws = FakeWebSocket.instances[0]!;
    act(() => {
      ws.emit({
        type: "message.created",
        conversation_id: "c1",
        message_id: "m2",
        sender_user_id: "u-self",
        sender_type: "user",
        content: "Say hello briefly",
        tool_calls: [],
        token_usage: null,
        delivery_status: "completed",
        created_at: "2026-05-01T00:00:02Z"
      });
    });

    await waitFor(() => {
      const bubbles = screen.getAllByText("Say hello briefly");
      expect(bubbles).toHaveLength(1);
    });
  });

  it("R7-5: header shows the agent's Node chip and a ⚙ Config button that navigates to /settings/agents/<id>", async () => {
    const user = userEvent.setup();
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");

    // Node chip with the agent's node name; status pill marks it online.
    const chip = await screen.findByText(/laptop-prod/);
    expect(chip.closest(".chat-node-chip")).toHaveClass("chat-node-chip--online");

    // ⚙ Config button navigates to the agent settings page.
    const configButton = screen.getByRole("button", { name: /Config/i });
    await user.click(configButton);
    await waitFor(() => {
      // The MemoryRouter test rig doesn't mount /settings; we just assert the
      // workspace stops rendering the chat title because navigate("/settings/...")
      // unmounted the route.
      expect(screen.queryByRole("heading", { name: "Planner" })).not.toBeInTheDocument();
    });
  });

  it("R8-2: WS message.created with sender_user_id UUID renders the agent display_name (Planner), not the UUID", async () => {
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");
    await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0));
    const ws = FakeWebSocket.instances[0]!;

    act(() => {
      ws.emit({
        type: "message.created",
        conversation_id: "c1",
        message_id: "m-live-1",
        sender_user_id: "user-uuid-planner",
        sender_type: "agent",
        content: "live reply",
        tool_calls: [],
        token_usage: null,
        delivery_status: "running",
        created_at: "2026-05-01T00:00:09Z"
      });
    });

    await waitFor(() => expect(screen.getByText(/live reply/)).toBeInTheDocument());
    // Bubble meta line shows "Planner", not the raw UUID.
    const bubble = screen.getByText(/live reply/).closest(".chat-bubble");
    expect(bubble).not.toBeNull();
    expect(bubble!.textContent).toMatch(/Planner/);
    expect(bubble!.textContent).not.toMatch(/user-uuid-planner/);
  });

  it("bugfix-405 R1: node.status_changed offline event updates Node chip from online to offline without page refresh", async () => {
    // Page opens and initially shows the node as online (from initial fetch).
    renderAtRoute("/chat/c1");
    const chip = await screen.findByText(/laptop-prod/);
    expect(chip.closest(".chat-node-chip")).toHaveClass("chat-node-chip--online");

    // SSE event: node goes offline. Page must update without a manual refresh.
    await waitFor(() => expect(capturedStatusHandler).not.toBeNull());
    act(() => {
      capturedStatusHandler!({
        eventType: "node.status_changed",
        payload: { node_id: "node-prod", status: "offline" }
      });
    });

    await waitFor(() => {
      const updatedChip = screen.getByText(/laptop-prod/);
      expect(updatedChip.closest(".chat-node-chip")).not.toHaveClass("chat-node-chip--online");
    });
  });

  it("bugfix-405 R1: node.status_changed online event updates Node chip from offline to online without page refresh", async () => {
    // Override the nodes fixture to start with offline status.
    const offlineFetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/im/v1/nodes")) {
        return new Response(
          JSON.stringify([{ node_id: "node-prod", owner_id: "u-self", node_name: "laptop-prod", status: "offline", last_heartbeat_at: null, agent_count: 1, version: "1.0", relay_enabled: true, reporting_enabled: true, alias: null, last_error: null }]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return fetchSpy(input, init);
    });
    vi.stubGlobal("fetch", offlineFetch);

    renderAtRoute("/chat/c1");
    // Wait for initial render with offline status.
    await screen.findByText("Hi Planner");
    // Node chip initially offline.
    await waitFor(() => {
      const chip = screen.getByText(/laptop-prod/);
      expect(chip.closest(".chat-node-chip")).not.toHaveClass("chat-node-chip--online");
    });

    // SSE event: node comes back online.
    await waitFor(() => expect(capturedStatusHandler).not.toBeNull());
    act(() => {
      capturedStatusHandler!({
        eventType: "node.status_changed",
        payload: { node_id: "node-prod", status: "online" }
      });
    });

    await waitFor(() => {
      const chip = screen.getByText(/laptop-prod/);
      expect(chip.closest(".chat-node-chip")).toHaveClass("chat-node-chip--online");
    });
  });

  it("bugfix-405: agent.status_changed offline event resolves agent→node and patches nodes cache", async () => {
    // Page opens; node-prod starts online (default fixture).
    renderAtRoute("/chat/c1");
    const chip = await screen.findByText(/laptop-prod/);
    expect(chip.closest(".chat-node-chip")).toHaveClass("chat-node-chip--online");

    // SSE event arrives for the agent rather than the node directly.
    // The fix must look up a-planner's node_id (node-prod) from the agents cache
    // and patch the nodes cache accordingly.
    await waitFor(() => expect(capturedStatusHandler).not.toBeNull());
    act(() => {
      capturedStatusHandler!({
        eventType: "agent.status_changed",
        payload: { agent_id: "a-planner", status: "offline" }
      });
    });

    await waitFor(() => {
      const updatedChip = screen.getByText(/laptop-prod/);
      expect(updatedChip.closest(".chat-node-chip")).not.toHaveClass("chat-node-chip--online");
    });
  });

  it("bugfix-405: agent.status_changed for unknown agent_id is silently dropped without error", async () => {
    renderAtRoute("/chat/c1");
    await screen.findByText(/laptop-prod/);

    await waitFor(() => expect(capturedStatusHandler).not.toBeNull());
    // Injecting an agent that is not in the agents cache must not throw.
    expect(() => {
      act(() => {
        capturedStatusHandler!({
          eventType: "agent.status_changed",
          payload: { agent_id: "a-nonexistent", status: "offline" }
        });
      });
    }).not.toThrow();

    // Node chip remains unchanged (node-prod should still be online).
    const chip = screen.getByText(/laptop-prod/);
    expect(chip.closest(".chat-node-chip")).toHaveClass("chat-node-chip--online");
  });

  // bugfix-419: 乐观插入用户消息后，agent WS 回复有更早 created_at 时，渲染按 created_at 有序
  it("bugfix-419: after optimistic user bubble, agent WS reply with earlier created_at sorts before the user message", async () => {
    // mockFetch sends the POST response with created_at="2026-05-01T00:00:02Z".
    // Agent WS reply arrives with created_at="2026-05-01T00:00:01Z" (earlier).
    // After the fix, agent bubble must appear before the user bubble.
    const user = userEvent.setup();
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");
    await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0));
    const ws = FakeWebSocket.instances[0]!;

    // Send message → optimistic bubble lands (created_at from POST response = 2026-05-01T00:00:02Z)
    await user.type(screen.getByRole("textbox"), "user question");
    await user.click(screen.getByRole("button", { name: /Send/i }));
    await waitFor(() => expect(screen.getByText("user question")).toBeInTheDocument());

    // Agent reply via WS with created_at BEFORE the user message (01Z < 02Z)
    act(() => {
      ws.emit({
        type: "message.created",
        conversation_id: "c1",
        message_id: "m-agent-reply",
        sender_user_id: "user-uuid-planner",
        sender_type: "agent",
        content: "agent answer",
        tool_calls: [],
        token_usage: null,
        delivery_status: "completed",
        created_at: "2026-05-01T00:00:01Z"   // earlier than user's 00:00:02Z
      });
    });

    await waitFor(() => expect(screen.getByText("agent answer")).toBeInTheDocument());

    // Agent message has earlier created_at → must appear before user message in DOM
    const bubbles = document.querySelectorAll(".chat-bubble");
    const texts = Array.from(bubbles).map((b) => b.textContent ?? "");
    const agentIdx = texts.findIndex((t) => t.includes("agent answer"));
    const userIdx = texts.findIndex((t) => t.includes("user question"));
    expect(agentIdx).toBeGreaterThanOrEqual(0);
    expect(userIdx).toBeGreaterThanOrEqual(0);
    expect(agentIdx).toBeLessThan(userIdx);
  });

  // ─── feat-438-M1 R4: ⚙ entry dispatch by conversation kind ────────────────

  it("feat-438: group ⚙ opens Group settings (does not navigate to an agent config)", async () => {
    const user = userEvent.setup();
    renderAtRoute("/chat/c2");
    expect(await screen.findByRole("heading", { name: "Research Squad" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Config/i }));

    // The group settings drawer opens in place; the chat is NOT replaced by a
    // navigation to /settings/agents/<first-agent> (the old bug).
    const drawer = await screen.findByRole("dialog", { name: /Group settings/i });
    expect(within(drawer).getByText("Planner")).toBeInTheDocument();
    expect(within(drawer).getByText("Writer")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Research Squad" })).toBeInTheDocument();
  });

  it("feat-438: add-members candidates exclude agents already in the group", async () => {
    const user = userEvent.setup();
    renderAtRoute("/chat/c2");
    await screen.findByRole("heading", { name: "Research Squad" });
    await user.click(screen.getByRole("button", { name: /Config/i }));
    const drawer = await screen.findByRole("dialog", { name: /Group settings/i });

    await user.click(within(drawer).getByRole("button", { name: /Add members/i }));
    // Only Reviewer (not yet a member) is offered; Planner/Writer are excluded.
    expect(within(drawer).getByLabelText("Reviewer")).toBeInTheDocument();
    expect(within(drawer).queryByLabelText("Planner")).not.toBeInTheDocument();
    expect(within(drawer).queryByLabelText("Writer")).not.toBeInTheDocument();
  });

  it("feat-438: zero-agent group still exposes ⚙ and opens Group settings", async () => {
    const user = userEvent.setup();
    renderAtRoute("/chat/c3");
    expect(await screen.findByRole("heading", { name: "Empty Group" })).toBeInTheDocument();

    // ⚙ must stay available even with no agents, otherwise the group is locked.
    const config = screen.getByRole("button", { name: /Config/i });
    await user.click(config);
    expect(await screen.findByRole("dialog", { name: /Group settings/i })).toBeInTheDocument();
  });

  it("feat-438: direct-agent ⚙ navigates to the agent config (no group settings drawer)", async () => {
    const user = userEvent.setup();
    renderAtRoute("/chat/c1");
    await screen.findByText("Hi Planner");

    await user.click(screen.getByRole("button", { name: /Config/i }));
    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: "Planner" })).not.toBeInTheDocument();
    });
    expect(screen.queryByRole("dialog", { name: /Group settings/i })).not.toBeInTheDocument();
  });
});

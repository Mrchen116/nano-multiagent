import { describe, expect, it } from "vitest";

import { applyWsEvent, type ConversationState, emptyConversationState } from "./chat-stream-reducer";
import type { Message, WsEvent } from "./chat-types";

function userMessage(id: string, content: string): Message {
  return {
    id,
    conversation_id: "c1",
    sender: { type: "user", id: "user-1" },
    sender_user_id: "user:user-1",
    sender_type: "user",
    content,
    attachments: [],
    delivery_status: "completed",
    created_at: "2026-01-01T00:00:00Z",
    permission_requests: []
  };
}

describe("chat-stream-reducer", () => {
  it("appends a new agent message on message.created", () => {
    const state: ConversationState = { ...emptyConversationState, messages: [userMessage("m1", "hello")] };
    const ev: WsEvent = {
      type: "message.created",
      conversation_id: "c1",
      message_id: "m2",
      sender_user_id: "agent:agent-a",
      sender_type: "agent",
      content: "",
      tool_calls: [],
      token_usage: null,
      delivery_status: "running",
      created_at: "2026-01-01T00:00:01Z"
    };
    const next = applyWsEvent(state, ev);
    expect(next.messages).toHaveLength(2);
    expect(next.messages[1]!.id).toBe("m2");
    expect(next.messages[1]!.delivery_status).toBe("running");
    expect(next.messages[1]!.content).toBe("");
  });

  it("appends delta_text to a streaming message", () => {
    const seed: Message = { ...userMessage("m2", ""), sender: { type: "agent", id: "agent-a" }, sender_type: "agent", delivery_status: "running" };
    const state: ConversationState = { ...emptyConversationState, messages: [seed] };
    let next = applyWsEvent(state, { type: "message.delta", conversation_id: "c1", message_id: "m2", delta_text: "Hel" });
    next = applyWsEvent(next, { type: "message.delta", conversation_id: "c1", message_id: "m2", delta_text: "lo." });
    expect(next.messages[0]!.content).toBe("Hello.");
  });

  it("finalises message on message.completed and attaches token_usage", () => {
    const seed: Message = { ...userMessage("m2", "partial"), sender: { type: "agent", id: "agent-a" }, sender_type: "agent", delivery_status: "running" };
    const state: ConversationState = { ...emptyConversationState, messages: [seed] };
    const next = applyWsEvent(state, {
      type: "message.completed",
      conversation_id: "c1",
      message_id: "m2",
      content: "Hello world.",
      token_usage: { output: 312, context_used: 14800, context_window: 200000 }
    });
    expect(next.messages[0]!.content).toBe("Hello world.");
    expect(next.messages[0]!.delivery_status).toBe("completed");
    expect(next.messages[0]!.token_usage).toEqual({ output: 312, context_used: 14800, context_window: 200000 });
  });

  // feat-414-M1: message.completed 带出 elapsed_ms，reducer 写入 Message
  it("writes elapsed_ms from message.completed event onto the message", () => {
    const seed: Message = { ...userMessage("m3", ""), sender: { type: "agent", id: "agent-a" }, sender_type: "agent", delivery_status: "running" };
    const state: ConversationState = { ...emptyConversationState, messages: [seed] };
    const next = applyWsEvent(state, {
      type: "message.completed",
      conversation_id: "c1",
      message_id: "m3",
      content: "done",
      token_usage: null,
      elapsed_ms: 4200,
    });
    expect(next.messages[0]!.delivery_status).toBe("completed");
    expect(next.messages[0]!.elapsed_ms).toBe(4200);
  });

  // feat-445-M1: message.completed carries kernel_message_id so a live-completed agent
  // bubble becomes forkable without a refetch (regression for the WS serialization gap).
  it("writes kernel_message_id from message.completed onto the message", () => {
    const seed: Message = { ...userMessage("m4", ""), sender: { type: "agent", id: "agent-a" }, sender_type: "agent", delivery_status: "running" };
    const state: ConversationState = { ...emptyConversationState, messages: [seed] };
    const next = applyWsEvent(state, {
      type: "message.completed",
      conversation_id: "c1",
      message_id: "m4",
      content: "done",
      token_usage: null,
      kernel_message_id: "msg_live_abc",
    });
    expect(next.messages[0]!.kernel_message_id).toBe("msg_live_abc");
  });

  it("upserts a running tool_call onto the in-flight message and updates it on completion", () => {
    const seed: Message = { ...userMessage("m2", ""), sender: { type: "agent", id: "agent-a" }, sender_type: "agent", delivery_status: "running" };
    const state: ConversationState = { ...emptyConversationState, messages: [seed] };
    let next = applyWsEvent(state, {
      type: "tool_call.upserted",
      conversation_id: "c1",
      message_id: "m2",
      tool_call: { id: "t1", name: "list_files", status: "running", input: {} }
    });
    expect(next.messages[0]!.tool_calls).toHaveLength(1);
    expect(next.messages[0]!.tool_calls![0]!.status).toBe("running");

    next = applyWsEvent(next, {
      type: "tool_call.completed",
      conversation_id: "c1",
      message_id: "m2",
      tool_call: { id: "t1", name: "list_files", status: "completed", input: {}, duration_ms: 48, output: "ok" }
    });
    expect(next.messages[0]!.tool_calls![0]!.status).toBe("completed");
    expect(next.messages[0]!.tool_calls![0]!.duration_ms).toBe(48);
    expect(next.messages[0]!.tool_calls![0]!.output).toBe("ok");
  });

  it("bugfix-416 #111: a reconcile event with empty input must not wipe the existing command", () => {
    // belt-and-braces: a timed-out tool's reconcile event may carry fewer fields
    // than the upsert. Merging must never let an empty input/output overwrite an
    // already-present non-empty value, otherwise the bash command/description shown
    // at tool_start vanishes and only "bash Timed out" remains.
    const seed: Message = { ...userMessage("m2", ""), sender: { type: "agent", id: "agent-a" }, sender_type: "agent", delivery_status: "running" };
    const state: ConversationState = { ...emptyConversationState, messages: [seed] };
    let next = applyWsEvent(state, {
      type: "tool_call.upserted",
      conversation_id: "c1",
      message_id: "m2",
      tool_call: {
        id: "t1",
        name: "bash",
        status: "running",
        input: { command: "npm run test:all", description: "Run full frontend test suite" },
        output: "scanning…"
      }
    });
    next = applyWsEvent(next, {
      type: "tool_call.completed",
      conversation_id: "c1",
      message_id: "m2",
      tool_call: { id: "t1", name: "bash", status: "failed", reason: "timed_out", input: {} }
    });
    const tc = next.messages[0]!.tool_calls![0]!;
    expect(tc.status).toBe("failed");
    expect(tc.reason).toBe("timed_out");
    // command/description preserved despite the empty input on the reconcile event.
    expect(tc.input).toEqual({ command: "npm run test:all", description: "Run full frontend test suite" });
    // existing non-empty output is not clobbered by an absent/empty field either.
    expect(tc.output).toBe("scanning…");
  });

  it("feat-439-M2: appends thinking segments on thinking.segment in arrival order", () => {
    const seed: Message = { ...userMessage("m2", ""), sender: { type: "agent", id: "agent-a" }, sender_type: "agent", delivery_status: "running" };
    const state: ConversationState = { ...emptyConversationState, messages: [seed] };
    let next = applyWsEvent(state, {
      type: "thinking.segment",
      conversation_id: "c1",
      message_id: "m2",
      thinking_segment: { seq: 0, text: "先看 types.py" }
    });
    next = applyWsEvent(next, {
      type: "thinking.segment",
      conversation_id: "c1",
      message_id: "m2",
      thinking_segment: { seq: 1, text: "两家口径要归一" }
    });
    expect(next.messages[0]!.thinking).toEqual([
      { seq: 0, text: "先看 types.py" },
      { seq: 1, text: "两家口径要归一" }
    ]);
  });

  it("feat-439-M2: re-applying the same thinking.segment is idempotent (dedup by seq)", () => {
    // reducer 契约本就会重放事件(sync/重连/双投递)；thinking 按 seq 去重，正如
    // tool_calls 按 id 幂等。seq 是 per-message 全局单调唯一键。
    const seed: Message = { ...userMessage("m2", ""), sender: { type: "agent", id: "agent-a" }, sender_type: "agent", delivery_status: "running" };
    const state: ConversationState = { ...emptyConversationState, messages: [seed] };
    const ev: WsEvent = {
      type: "thinking.segment",
      conversation_id: "c1",
      message_id: "m2",
      thinking_segment: { seq: 0, text: "想一下" }
    };
    let next = applyWsEvent(state, ev);
    next = applyWsEvent(next, ev); // duplicate delivery
    next = applyWsEvent(next, {
      type: "thinking.segment",
      conversation_id: "c1",
      message_id: "m2",
      thinking_segment: { seq: 2, text: "再想一下" }
    });
    expect(next.messages[0]!.thinking).toEqual([
      { seq: 0, text: "想一下" },
      { seq: 2, text: "再想一下" }
    ]);
  });

  it("feat-439-M2: message.created restores persisted thinking segments", () => {
    const state: ConversationState = { ...emptyConversationState, messages: [] };
    const next = applyWsEvent(state, {
      type: "message.created",
      conversation_id: "c1",
      message_id: "m3",
      sender_user_id: "agent:agent-a",
      sender_type: "agent",
      content: "答案",
      tool_calls: [],
      thinking: [{ seq: 0, text: "想一下" }],
      token_usage: null,
      delivery_status: "completed",
      created_at: "2026-01-01T00:00:02Z"
    });
    expect(next.messages[0]!.thinking).toEqual([{ seq: 0, text: "想一下" }]);
  });

  it("tool completion replaces the running summary and parameter detail with result detail", () => {
    const seed: Message = { ...userMessage("m2", ""), sender: { type: "agent", id: "agent-a" }, sender_type: "agent", delivery_status: "running" };
    const state: ConversationState = { ...emptyConversationState, messages: [seed] };
    let next = applyWsEvent(state, {
      type: "tool_call.upserted",
      conversation_id: "c1",
      message_id: "m2",
      tool_call: {
        id: "t1",
        name: "bash",
        status: "running",
        input: { command: "sleep 5 && echo done" },
        output: "run slow command",
        detail: { command: "sleep 5 && echo done" }
      }
    });
    next = applyWsEvent(next, {
      type: "tool_call.completed",
      conversation_id: "c1",
      message_id: "m2",
      tool_call: {
        id: "t1",
        name: "bash",
        status: "completed",
        input: { command: "sleep 5 && echo done" },
        output: "run completed",
        detail: { command: "sleep 5 && echo done", stdout: "done", exit_code: 0 }
      }
    });
    const tc = next.messages[0]!.tool_calls![0]!;
    expect(tc.status).toBe("completed");
    expect(tc.output).toBe("run completed");
    expect(tc.detail).toEqual({ command: "sleep 5 && echo done", stdout: "done", exit_code: 0 });
  });

  it("ignores events for other conversations", () => {
    const seed: Message = { ...userMessage("m2", ""), sender: { type: "agent", id: "agent-a" }, sender_type: "agent", delivery_status: "running" };
    const state: ConversationState = { ...emptyConversationState, conversation_id: "c1", messages: [seed] };
    const next = applyWsEvent(state, { type: "message.delta", conversation_id: "OTHER", message_id: "m2", delta_text: "X" });
    expect(next).toBe(state);
  });

  it("is a no-op when message.delta references an unknown message_id", () => {
    const state: ConversationState = { ...emptyConversationState, conversation_id: "c1", messages: [] };
    const next = applyWsEvent(state, { type: "message.delta", conversation_id: "c1", message_id: "missing", delta_text: "x" });
    expect(next).toBe(state);
  });

  it("R8-2: populates sender.display_name on message.created via senders lookup", () => {
    const state: ConversationState = { ...emptyConversationState, conversation_id: "c1", messages: [] };
    const ev: WsEvent = {
      type: "message.created",
      conversation_id: "c1",
      message_id: "m-agent-1",
      sender_user_id: "11112222-3333-4444-5555-666677778888",
      sender_type: "agent",
      content: "",
      tool_calls: [],
      token_usage: null,
      delivery_status: "running",
      created_at: "2026-01-01T00:00:01Z"
    };
    const next = applyWsEvent(state, ev, {
      sendersById: { "11112222-3333-4444-5555-666677778888": "Alpha" }
    });
    expect(next.messages[0]!.sender.display_name).toBe("Alpha");
  });

  it("uses sender display name and attachments from external message.created payload", () => {
    const state: ConversationState = { ...emptyConversationState, conversation_id: "c1", messages: [] };
    const ev: WsEvent & {
      sender: { type: "user"; id: string; display_name: string };
      sender_display_name: string;
      attachments: [{ url: string; content_type: string; file_name: string }];
    } = {
      type: "message.created",
      conversation_id: "c1",
      message_id: "m-external-1",
      sender_user_id: "owner-user-id",
      sender_type: "user",
      sender: { type: "user", id: "owner-user-id", display_name: "Alice" },
      sender_display_name: "Alice",
      content: "from feishu",
      attachments: [
        {
          url: "https://example.test/a.png",
          content_type: "image/png",
          file_name: "a.png"
        }
      ],
      tool_calls: [],
      token_usage: null,
      delivery_status: "completed",
      created_at: "2026-01-01T00:00:01Z"
    };

    let next = applyWsEvent(state, ev);
    next = applyWsEvent(next, ev);

    expect(next.messages).toHaveLength(1);
    expect(next.messages[0]!.sender.display_name).toBe("Alice");
    expect(next.messages[0]!.attachments).toEqual([
      {
        url: "https://example.test/a.png",
        content_type: "image/png",
        file_name: "a.png"
      }
    ]);
  });

  it("R8-1: ignores message.created whose id contains :relay: (defensive against synthetic mirror)", () => {
    const state: ConversationState = { ...emptyConversationState, conversation_id: "c1", messages: [] };
    const ev: WsEvent = {
      type: "message.created",
      conversation_id: "c1",
      message_id: "user-msg-1:relay:task-9",
      sender_user_id: "agent:alpha",
      sender_type: "agent",
      content: "Hi",
      tool_calls: [],
      token_usage: null,
      delivery_status: "completed",
      created_at: "2026-01-01T00:00:01Z"
    };
    const next = applyWsEvent(state, ev);
    expect(next.messages).toHaveLength(0);
  });

  // bugfix-367: permission_requests 改为 list, 多次 ask 累积保留
  it("bugfix-367: permission.request appends a new entry with pending status", () => {
    const seed: Message = {
      ...userMessage("m2", ""),
      sender: { type: "agent", id: "agent-a" },
      sender_type: "agent",
      delivery_status: "running",
      permission_requests: []
    };
    const state: ConversationState = { ...emptyConversationState, conversation_id: "c1", messages: [seed] };
    const ev: WsEvent = {
      type: "permission.request",
      conversation_id: "c1",
      message_id: "m2",
      permission_request: {
        request_id: "req-1",
        tool_name: "bash",
        tool_input: { command: "rm -rf /tmp/foo" },
        question: "Allow bash command?",
        options: [
          { id: "allow_once", label: "Allow once", description: "Run this time only" },
          { id: "deny", label: "Deny", description: "Block this action" }
        ],
        status: "pending"
      }
    };
    const next = applyWsEvent(state, ev);
    const reqs = next.messages[0]!.permission_requests;
    expect(reqs).toHaveLength(1);
    expect(reqs[0]!.request_id).toBe("req-1");
    expect(reqs[0]!.status).toBe("pending");
    expect(reqs[0]!.tool_name).toBe("bash");
  });

  it("bugfix-367: second permission.request keeps the first as resolved history", () => {
    // 第一次 ask 已经 resolved, 第二次 ask 不能把第一次抹掉。
    const seed: Message = {
      ...userMessage("m2", ""),
      sender: { type: "agent", id: "agent-a" },
      sender_type: "agent",
      delivery_status: "running",
      permission_requests: [
        {
          request_id: "req-1",
          tool_name: "bash",
          tool_input: { command: "rm a" },
          question: "Allow bash?",
          options: [],
          status: "resolved",
          decision: "allow_once"
        }
      ]
    };
    const state: ConversationState = { ...emptyConversationState, conversation_id: "c1", messages: [seed] };
    const ev: WsEvent = {
      type: "permission.request",
      conversation_id: "c1",
      message_id: "m2",
      permission_request: {
        request_id: "req-2",
        tool_name: "write",
        tool_input: {},
        question: "Allow write?",
        options: [],
        status: "pending"
      }
    };
    const next = applyWsEvent(state, ev);
    const reqs = next.messages[0]!.permission_requests;
    expect(reqs).toHaveLength(2);
    expect(reqs[0]!.request_id).toBe("req-1");
    expect(reqs[0]!.status).toBe("resolved");
    expect(reqs[1]!.request_id).toBe("req-2");
    expect(reqs[1]!.status).toBe("pending");
  });

  it("bugfix-367: same request_id idempotent — replace in place, no duplicate", () => {
    const seed: Message = {
      ...userMessage("m2", ""),
      sender: { type: "agent", id: "agent-a" },
      sender_type: "agent",
      delivery_status: "running",
      permission_requests: [
        {
          request_id: "req-1",
          tool_name: "bash",
          tool_input: {},
          question: "v1",
          options: [],
          status: "pending"
        }
      ]
    };
    const state: ConversationState = { ...emptyConversationState, conversation_id: "c1", messages: [seed] };
    const ev: WsEvent = {
      type: "permission.request",
      conversation_id: "c1",
      message_id: "m2",
      permission_request: {
        request_id: "req-1",
        tool_name: "bash",
        tool_input: {},
        question: "v2",
        options: [],
        status: "pending"
      }
    };
    const next = applyWsEvent(state, ev);
    const reqs = next.messages[0]!.permission_requests;
    expect(reqs).toHaveLength(1);
    expect(reqs[0]!.question).toBe("v2");
  });

  it("bugfix-367: permission.resolved updates only the entry matching request_id", () => {
    const seed: Message = {
      ...userMessage("m2", ""),
      sender: { type: "agent", id: "agent-a" },
      sender_type: "agent",
      delivery_status: "running",
      permission_requests: [
        {
          request_id: "req-a",
          tool_name: "bash",
          tool_input: {},
          question: "Allow?",
          options: [],
          status: "pending"
        },
        {
          request_id: "req-b",
          tool_name: "write",
          tool_input: {},
          question: "Allow?",
          options: [],
          status: "pending"
        }
      ]
    };
    const state: ConversationState = { ...emptyConversationState, conversation_id: "c1", messages: [seed] };
    const ev: WsEvent = {
      type: "permission.resolved",
      conversation_id: "c1",
      message_id: "m2",
      request_id: "req-b",
      decision: "deny"
    };
    const next = applyWsEvent(state, ev);
    const reqs = next.messages[0]!.permission_requests;
    expect(reqs).toHaveLength(2);
    expect(reqs[0]!.request_id).toBe("req-a");
    expect(reqs[0]!.status).toBe("pending");
    expect(reqs[1]!.request_id).toBe("req-b");
    expect(reqs[1]!.status).toBe("resolved");
    expect(reqs[1]!.decision).toBe("deny");
  });

  it("bugfix-367: permission.request for unknown message is a no-op", () => {
    const state: ConversationState = { ...emptyConversationState, conversation_id: "c1", messages: [] };
    const ev: WsEvent = {
      type: "permission.request",
      conversation_id: "c1",
      message_id: "missing-msg",
      permission_request: {
        request_id: "req-2",
        tool_name: "bash",
        tool_input: {},
        question: "Allow?",
        options: [],
        status: "pending"
      }
    };
    const next = applyWsEvent(state, ev);
    expect(next).toBe(state);
  });

  // bugfix-419: WS message.created 到达顺序与 created_at 相反时，渲染顺序仍按 created_at 升序
  it("bugfix-419: message.created events arriving out-of-order are sorted by created_at, not arrival order", () => {
    // Simulate: user message already in state with a later created_at.
    // Agent reply arrives via WS with an earlier created_at (e.g. clock skew / race).
    // The list must be re-sorted so agent message appears before the user message.
    const userMsg: Message = {
      ...userMessage("m-user", "hello"),
      created_at: "2026-01-01T00:00:02Z"
    };
    const state: ConversationState = { conversation_id: "c1", messages: [userMsg] };

    const agentEarlierEv: WsEvent = {
      type: "message.created",
      conversation_id: "c1",
      message_id: "m-agent",
      sender_user_id: "agent:a",
      sender_type: "agent",
      content: "hi",
      tool_calls: [],
      token_usage: null,
      delivery_status: "running",
      created_at: "2026-01-01T00:00:01Z"   // earlier than user msg
    };
    const next = applyWsEvent(state, agentEarlierEv);

    expect(next.messages).toHaveLength(2);
    // Agent message has earlier created_at → must be first after sort
    expect(next.messages[0]!.id).toBe("m-agent");
    expect(next.messages[1]!.id).toBe("m-user");
  });

  // bugfix-419: 同 created_at 以 message id 作 tie-break，保证稳定排序
  it("bugfix-419: messages with equal created_at are tie-broken by id for stable ordering", () => {
    const state: ConversationState = {
      conversation_id: "c1",
      messages: [userMessage("id-b", "b")]   // created_at = "2026-01-01T00:00:00Z"
    };
    const ev: WsEvent = {
      type: "message.created",
      conversation_id: "c1",
      message_id: "id-a",
      sender_user_id: "agent:a",
      sender_type: "agent",
      content: "a",
      tool_calls: [],
      token_usage: null,
      delivery_status: "completed",
      created_at: "2026-01-01T00:00:00Z"   // same timestamp as id-b
    };
    const next = applyWsEvent(state, ev);
    expect(next.messages).toHaveLength(2);
    // "id-a" < "id-b" lexicographically → id-a first
    expect(next.messages[0]!.id).toBe("id-a");
    expect(next.messages[1]!.id).toBe("id-b");
  });
});

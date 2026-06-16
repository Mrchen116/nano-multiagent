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
});

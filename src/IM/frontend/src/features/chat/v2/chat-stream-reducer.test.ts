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
    created_at: "2026-01-01T00:00:00Z"
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
});

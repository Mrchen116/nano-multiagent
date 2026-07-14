import { describe, expect, it } from "vitest";

import type { UserStreamEvent } from "../../realtime/user-stream";
import {
  emptyAgentCompletionState,
  hydrateAgentCompletionState,
  persistAgentCompletionState,
  reduceAgentCompletionEvent
} from "./agent-completion-accumulator";

const created: UserStreamEvent = {
  eventType: "message.created",
  eventId: 10,
  payload: {
    conversation_id: "conv-1",
    message_id: "msg-1",
    sender_user_id: "agent:planner",
    sender_type: "agent",
    sender_display_name: "Planner",
    content: "",
    created_at: "2026-07-13T08:00:00Z"
  }
};

const completed: UserStreamEvent = {
  eventType: "message.completed",
  eventId: 11,
  payload: {
    conversation_id: "conv-1",
    message_id: "msg-1",
    content: "Finished"
  }
};

describe("agent completion accumulator", () => {
  it("emits one canonical completion candidate and treats relay.completed as a receipt", () => {
    const afterCreated = reduceAgentCompletionEvent(emptyAgentCompletionState, created);
    expect(afterCreated.candidate).toBeNull();

    const afterCompleted = reduceAgentCompletionEvent(afterCreated.state, completed);
    expect(afterCompleted.candidate).toEqual({
      messageKey: "message:msg-1",
      messageId: "msg-1",
      conversationId: "conv-1",
      senderName: "Planner",
      senderUserId: "agent:planner",
      preview: "Finished",
      createdAt: "2026-07-13T08:00:00Z"
    });

    const relayReceipt = reduceAgentCompletionEvent(afterCompleted.state, {
      eventType: "relay.completed",
      eventId: 12,
      payload: {
        conversation_id: "conv-1",
        message_id: "msg-1",
        relay_task_id: "relay-1",
        detail: "Finished"
      }
    });
    expect(relayReceipt.candidate).toBeNull();
  });

  it("persists the minimum pending identity across a reload gap", () => {
    const storage = new Map<string, string>();
    const adapter = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key)
    };
    const afterCreated = reduceAgentCompletionEvent(emptyAgentCompletionState, created);
    persistAgentCompletionState("user-a", afterCreated.state, adapter);

    const reloaded = hydrateAgentCompletionState("user-a", adapter);
    const afterCompleted = reduceAgentCompletionEvent(reloaded, completed);
    expect(afterCompleted.candidate?.senderName).toBe("Planner");
    expect(afterCompleted.candidate?.conversationId).toBe("conv-1");
  });

  it("clears a persisted pending identity when the canonical message is discarded", () => {
    const afterCreated = reduceAgentCompletionEvent(emptyAgentCompletionState, created);
    const discarded = reduceAgentCompletionEvent(afterCreated.state, {
      eventType: "message.discarded",
      eventId: 11,
      payload: { conversation_id: "conv-1", message_id: "msg-1", reason: "empty_visible_reply" }
    });
    expect(discarded.state.pendingByMessageId).toEqual({});
    expect(discarded.candidate).toBeNull();
  });

  it("does not revive the retired message_created notification alias", () => {
    const legacy = reduceAgentCompletionEvent(emptyAgentCompletionState, {
      ...created,
      eventType: "message_created"
    });
    expect(legacy.state).toBe(emptyAgentCompletionState);
    expect(legacy.candidate).toBeNull();
  });
});

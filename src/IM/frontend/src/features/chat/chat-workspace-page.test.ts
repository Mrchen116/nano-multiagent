import { describe, expect, it } from "vitest";

import { toRelayAgentMessage } from "./chat-workspace-page";

describe("chat workspace relay event mapping", () => {
  it("converts relay.processing into a synthetic running agent message", () => {
    expect(
      toRelayAgentMessage({
        eventType: "relay.processing",
        payload: {
          message_id: "msg-1",
          node_id: "node-demo",
          summary: "working on it",
          created_at: "2026-03-12T00:00:00Z"
        }
      })
    ).toEqual({
      message_id: "msg-1:agent",
      sender_type: "agent",
      sender_name: "node-demo",
      is_mine: false,
      content: "working on it",
      created_at: "2026-03-12T00:00:00Z",
      delivery_status: "running"
    });
  });

  it("converts relay completion receipts into a synthetic completed agent message", () => {
    expect(
      toRelayAgentMessage({
        eventType: "relay.completed",
        payload: {
          message_id: "msg-1",
          detail: "done"
        }
      })
    ).toMatchObject({
      message_id: "msg-1:agent",
      sender_type: "agent",
      content: "done",
      delivery_status: "completed"
    });
  });
});

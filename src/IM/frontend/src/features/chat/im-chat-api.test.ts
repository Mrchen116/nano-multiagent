import { describe, expect, it } from "vitest";

import {
  buildCreateMessageRequest,
  normalizeItemsEnvelope,
  parseImStreamEvent,
  pickPrimaryOwnedNodeId
} from "./im-chat-api";

describe("im chat api helpers", () => {
  it("normalizes pagination envelopes from real IM APIs", () => {
    expect(normalizeItemsEnvelope({ items: [{ id: "conv-1" }, { id: "conv-2" }] })).toEqual([
      { id: "conv-1" },
      { id: "conv-2" }
    ]);
    expect(normalizeItemsEnvelope([{ id: "conv-legacy" }])).toEqual([{ id: "conv-legacy" }]);
  });

  it("picks the first owned node for relay-backed sends", () => {
    expect(pickPrimaryOwnedNodeId({ owned_node_ids: ["node-a", "node-b"] })).toBe("node-a");
    expect(pickPrimaryOwnedNodeId({ owned_node_ids: [] })).toBeNull();
  });

  it("builds relay-aware create-message payloads only when a node is bound", () => {
    expect(buildCreateMessageRequest({ selfUserId: "u-self", content: "hello", targetNodeId: "node-a" })).toEqual({
      sender_user_id: "u-self",
      content: "hello",
      target_node_id: "node-a"
    });
    expect(buildCreateMessageRequest({ selfUserId: "u-self", content: "hello", targetNodeId: null })).toEqual({
      sender_user_id: "u-self",
      content: "hello"
    });
  });
});

describe("im chat stream parser", () => {
  it("parses text_delta payload for incremental rendering", () => {
    const parsed = parseImStreamEvent({
      eventType: "text_delta",
      data: JSON.stringify({
        conversation_id: "conv-1",
        message_id: "m-2",
        sender_user_id: "u-peer",
        delta: "hello"
      })
    });

    expect(parsed).toEqual({
      eventType: "text_delta",
      payload: {
        conversation_id: "conv-1",
        message_id: "m-2",
        sender_user_id: "u-peer",
        delta: "hello"
      }
    });
  });

  it("parses relay completion payload for real gateway round-trips", () => {
    const parsed = parseImStreamEvent({
      eventType: "relay.completed",
      data: JSON.stringify({
        conversation_id: "conv-1",
        message_id: "m-1",
        detail: "agent reply"
      })
    });

    expect(parsed).toEqual({
      eventType: "relay.completed",
      payload: {
        conversation_id: "conv-1",
        message_id: "m-1",
        detail: "agent reply"
      }
    });
  });

  it("returns null when payload is not valid json", () => {
    const parsed = parseImStreamEvent({
      eventType: "turn_end",
      data: "{broken"
    });

    expect(parsed).toBeNull();
  });
});

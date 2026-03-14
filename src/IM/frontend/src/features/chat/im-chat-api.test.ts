import { describe, expect, it } from "vitest";

import {
  buildCreateMessageRequest,
  buildGroupConversationTitle,
  buildStarterConversationTitle,
  buildStarterPeerUsername,
  normalizeItemsEnvelope,
  parseImStreamEvent,
  pickCanonicalDirectConversation,
  pickDefaultNodeForSend,
  pickPrimaryOwnedNodeId,
  resolveSendAvailability
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

  it("prefers an online relay-enabled node for default sends", () => {
    expect(
      pickDefaultNodeForSend([
        { node_id: "node-offline", node_name: "Offline", status: "offline", relay_enabled: true },
        { node_id: "node-online", node_name: "Online", status: "online", relay_enabled: true }
      ])
    ).toMatchObject({ node_id: "node-online", status: "online" });
  });

  it("falls back to the first relay-enabled node when nothing is online", () => {
    expect(
      pickDefaultNodeForSend([
        { node_id: "node-offline", node_name: "Offline", status: "offline", relay_enabled: true },
        { node_id: "node-disabled", node_name: "Disabled", status: "online", relay_enabled: false }
      ])
    ).toMatchObject({ node_id: "node-offline", status: "offline" });
    expect(buildStarterConversationTitle("OpsBot")).toBe("主 Agent · OpsBot");
    expect(buildStarterConversationTitle("主 Agent OpsBot")).toBe("主 Agent · OpsBot");
  });

  it("classifies send readiness for bound, offline, and unbound states", () => {
    expect(resolveSendAvailability({ targetNodeId: null, nodeStatus: null })).toEqual({
      canSend: false,
      state: "unbound",
      helperText: "Bind this Gateway to continue. Web IM disables the composer until one of your Gateway nodes is connected.",
      placeholder: "Bind this Gateway to continue"
    });
    expect(resolveSendAvailability({ targetNodeId: "node-offline", nodeStatus: "offline" })).toEqual({
      canSend: false,
      state: "offline",
      helperText: "Your bound Gateway is offline. Bring that node online or bind another online node to re-enable chat.",
      placeholder: "Gateway offline — chat disabled"
    });
    expect(resolveSendAvailability({ targetNodeId: "node-online", nodeStatus: "online" })).toEqual({
      canSend: true,
      state: "available",
      helperText: null,
      placeholder: "Type message"
    });
  });

  it("reuses the legacy peer username when no agent profile exists", () => {
    expect(buildStarterPeerUsername("agent-1")).toBe("agent:agent-1");
    expect(buildStarterPeerUsername("peer")).toBe("peer");
  });

  it("builds stable group chat titles from selected participant labels", () => {
    expect(buildGroupConversationTitle([])).toBe("New group chat");
    expect(buildGroupConversationTitle(["OpsBot"])).toBe("OpsBot group");
    expect(buildGroupConversationTitle(["OpsBot", "Alex"])).toBe("OpsBot + Alex");
    expect(buildGroupConversationTitle(["OpsBot", "Alex", "Agent New"])).toBe("OpsBot + Alex +1");
  });

  it("reuses the oldest matching direct thread as the canonical agent chat", () => {
    expect(
      pickCanonicalDirectConversation({
        selfUserId: "user-self",
        peerUserId: "agent-user",
        conversations: [
          {
            id: "conv-newer",
            title: "Agent New",
            participant_ids: ["user-self", "agent-user"],
            type: "direct",
            owner_id: "owner-1",
            created_at: "2026-03-13T10:00:00Z"
          },
          {
            id: "conv-group",
            title: "Ignore group",
            participant_ids: ["user-self", "agent-user", "teammate-1"],
            type: "group",
            owner_id: "owner-1",
            created_at: "2026-03-11T10:00:00Z"
          },
          {
            id: "conv-older",
            title: "Agent New",
            participant_ids: ["user-self", "agent-user"],
            type: "direct",
            owner_id: "owner-1",
            created_at: "2026-03-12T10:00:00Z"
          }
        ]
      })
    ).toMatchObject({ id: "conv-older" });
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

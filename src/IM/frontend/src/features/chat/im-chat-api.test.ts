import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildCreateMessageRequest,
  buildGroupConversationTitle,
  buildStarterConversationTitle,
  buildStarterPeerUsername,
  confirmBindToken,
  getConversation,
  getConversationLatestEventId,
  listDiscoverableGroupParticipants,
  normalizeItemsEnvelope,
  parseImStreamEvent,
  pickCanonicalDirectConversation,
  pickDefaultNodeForSend,
  pickPrimaryOwnedNodeId,
  resetChatBootstrapState,
  resolveConversationSendNodeState,
  resolveGroupConversationTitle,
  resolveSendAvailability,
  streamConversationEvents
} from "./im-chat-api";

afterEach(() => {
  resetChatBootstrapState();
  vi.restoreAllMocks();
});

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
      sender: {
        type: "user",
        id: "u-self"
      },
      sender_user_id: "u-self",
      content: "hello",
      target_node_id: "node-a"
    });
    expect(buildCreateMessageRequest({ selfUserId: "u-self", content: "hello", targetNodeId: null })).toEqual({
      sender: {
        type: "user",
        id: "u-self"
      },
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

  it("prefers explicit conversation summary node state before refetching direct send availability", async () => {
    await expect(
      resolveConversationSendNodeState({
        conversationId: "conv-1",
        conversations: [
          {
            conversation_id: "conv-1",
            title: "Ops Bot",
            last_message_preview: "",
            last_message_at: undefined,
            unread_count: 0,
            participants: ["You", "Ops Bot"],
            kind: "direct-agent",
            kind_label: "Direct agent chat",
            target_label: "Ops Bot",
            discoverability_hint: "",
            node_id: "node-online",
            node_label: "node-online",
            node_status: "online"
          }
        ],
        selfUserId: "user-self",
        fallback: {
          targetNodeId: "bootstrap-node",
          targetNodeStatus: "offline"
        }
      })
    ).resolves.toEqual({
      targetNodeId: "node-online",
      targetNodeStatus: "online"
    });
  });

  it("builds stable group chat titles from selected participant labels", () => {
    expect(buildGroupConversationTitle([])).toBe("New group chat");
    expect(buildGroupConversationTitle(["OpsBot"])).toBe("OpsBot group");
    expect(buildGroupConversationTitle(["OpsBot", "Alex"])).toBe("OpsBot + Alex");
    expect(buildGroupConversationTitle(["OpsBot", "Alex", "Agent New"])).toBe("OpsBot + Alex +1");
  });

  it("resolves group conversation title: custom name overrides auto-generated title (M235)", () => {
    // Custom name provided → use it regardless of participant labels.
    expect(resolveGroupConversationTitle({ groupName: "Dev Team", participantLabels: ["OpsBot", "Alex"] })).toBe("Dev Team");
    // Whitespace-only name → fall back to auto-generated title.
    expect(resolveGroupConversationTitle({ groupName: "   ", participantLabels: ["OpsBot", "Alex"] })).toBe("OpsBot + Alex");
    // Empty string → fall back.
    expect(resolveGroupConversationTitle({ groupName: "", participantLabels: ["OpsBot"] })).toBe("OpsBot group");
    // Undefined → fall back.
    expect(resolveGroupConversationTitle({ groupName: undefined, participantLabels: [] })).toBe("New group chat");
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

  it("falls back to the peer agent display name when a direct chat still stores the placeholder title", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/users") {
        return new Response(
          JSON.stringify([
            {
              id: "user-self",
              username: "you",
              display_name: "You",
              owner_id: "owner-1",
              owned_node_ids: ["node-1"],
              created_at: "2026-03-14T00:00:00Z"
            },
            {
              id: "agent-user",
              username: "agent:ops-bot",
              display_name: "Ops Bot",
              owner_id: "owner-1",
              owned_node_ids: [],
              created_at: "2026-03-14T00:00:00Z"
            }
          ]),
          { status: 200 }
        );
      }
      if (url === "/im/v1/agents") {
        return new Response(JSON.stringify([{ agent_id: "ops-bot", display_name: "Ops Bot", description: "starter agent" }]), {
          status: 200
        });
      }
      if (url === "/im/v1/nodes") {
        return new Response(JSON.stringify([{ node_id: "node-1", node_name: "Node 1", status: "online", relay_enabled: true }]), {
          status: 200
        });
      }
      if (url === "/im/v1/conversations") {
        return new Response(
          JSON.stringify([
            {
              id: "conv-1",
              title: "Direct conversation",
              participant_ids: ["user-self", "agent-user"],
              type: "direct",
              owner_id: "owner-1",
              created_at: "2026-03-14T00:00:00Z"
            }
          ]),
          { status: 200 }
        );
      }
      if (url === "/im/v1/conversations/conv-1/messages?mark_as_read=true") {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      return new Response(null, { status: 404 });
    });

    vi.stubGlobal("fetch", fetchMock);

    await expect(getConversation("conv-1")).resolves.toMatchObject({
      conversation_id: "conv-1",
      title: "Ops Bot",
      direct_agent_id: "ops-bot"
    });
  });

  it("falls back to the peer teammate display name when a direct user chat keeps the default placeholder", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/users" && (!init?.method || init.method === "GET")) {
        return new Response(
          JSON.stringify([
            {
              id: "user-self",
              username: "you",
              display_name: "You",
              owner_id: "owner-1",
              owned_node_ids: ["node-1"],
              created_at: "2026-03-14T00:00:00Z"
            },
            {
              id: "agent-user",
              username: "agent:ops-bot",
              display_name: "Ops Bot",
              owner_id: "owner-1",
              owned_node_ids: [],
              created_at: "2026-03-14T00:00:00Z"
            },
            {
              id: "user-peer",
              username: "alex",
              display_name: "Alex",
              owner_id: "owner-1",
              owned_node_ids: [],
              created_at: "2026-03-14T00:00:00Z"
            }
          ]),
          { status: 200 }
        );
      }
      if (url === "/im/v1/agents") {
        return new Response(JSON.stringify([{ agent_id: "ops-bot", display_name: "Ops Bot", description: "starter agent" }]), {
          status: 200
        });
      }
      if (url === "/im/v1/nodes") {
        return new Response(JSON.stringify([{ node_id: "node-1", node_name: "Node 1", status: "online", relay_enabled: true }]), {
          status: 200
        });
      }
      if (url === "/im/v1/conversations") {
        return new Response(
          JSON.stringify([
            {
              id: "starter-conv",
              title: "主 Agent · OpsBot",
              participant_ids: ["user-self", "agent-user"],
              type: "direct",
              owner_id: "owner-1",
              created_at: "2026-03-13T00:00:00Z"
            },
            {
              id: "conv-user",
              title: "You & Teammate",
              participant_ids: ["user-self", "user-peer"],
              type: "direct",
              owner_id: "owner-1",
              created_at: "2026-03-14T00:00:00Z"
            }
          ]),
          { status: 200 }
        );
      }
      if (url === "/im/v1/conversations/conv-user/messages?mark_as_read=true") {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      return new Response(null, { status: 404 });
    });

    vi.stubGlobal("fetch", fetchMock);

    await expect(getConversation("conv-user")).resolves.toMatchObject({
      conversation_id: "conv-user",
      title: "Alex"
    });
  });

  it("returns the confirmed self user id so the browser can invalidate stale chat bootstrap state", async () => {
    let usersResponse = [
      {
        id: "user-self",
        username: "you",
        display_name: "You",
        owner_id: "owner-1",
        owned_node_ids: ["node-1"],
        created_at: "2026-03-14T00:00:00Z"
      }
    ];

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/users" && (!init?.method || init.method === "GET")) {
        return new Response(JSON.stringify(usersResponse), { status: 200 });
      }
      if (url === "/im/v1/bind" && init?.method === "POST") {
        return new Response(JSON.stringify({ node_id: "node-1" }), { status: 201 });
      }
      return new Response(null, { status: 404 });
    });

    vi.stubGlobal("fetch", fetchMock);

    await expect(confirmBindToken("bind-token-1")).resolves.toEqual({
      node_id: "node-1",
      self_user_id: "user-self"
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/im/v1/bind",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          action: "confirm",
          bind_token: "bind-token-1",
          user_id: "user-self"
        })
      })
    );
  });

  it("derives selectable group participants from runtime agents after bootstrap creates aliases", async () => {
    let usersResponse = [
      {
        id: "user-self",
        username: "you",
        display_name: "You",
        owner_id: "owner-1",
        owned_node_ids: ["node-1"],
        created_at: "2026-03-14T00:00:00Z"
      }
    ];

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/users" && (!init?.method || init.method === "GET")) {
        return new Response(JSON.stringify(usersResponse), { status: 200 });
      }
      if (url === "/im/v1/users" && init?.method === "POST") {
        const payload = JSON.parse(String(init.body));
        const created = {
          id: `${payload.username}-id`,
          username: payload.username,
          display_name: payload.display_name,
          owner_id: payload.username === "you" ? "owner-1" : `${payload.username}-id`,
          owned_node_ids: [],
          created_at: "2026-03-14T00:00:01Z"
        };
        usersResponse = [...usersResponse, created];
        return new Response(JSON.stringify(created), { status: 201 });
      }
      if (url === "/im/v1/agents") {
        return new Response(
          JSON.stringify([
            {
              agent_id: "agent-a",
              display_name: "Agent A",
              description: "runtime selectable"
            },
            {
              agent_id: "agent-b",
              display_name: "Agent B",
              description: "runtime selectable"
            }
          ]),
          { status: 200 }
        );
      }
      if (url === "/im/v1/nodes") {
        return new Response(
          JSON.stringify([
            { node_id: "node-1", node_name: "MacBook", status: "online", relay_enabled: true, owner_id: "owner-1" }
          ]),
          { status: 200 }
        );
      }
      if (url === "/im/v1/conversations") {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.startsWith("/im/v1/conversations/") && url.endsWith("/messages")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      return new Response(null, { status: 404 });
    });

    vi.stubGlobal("fetch", fetchMock);

    const participants = await listDiscoverableGroupParticipants();

    expect(participants).toEqual([
      {
        user_id: "agent:agent-a-id",
        label: "Agent A",
        kind: "agent",
        description: "runtime selectable"
      },
      {
        user_id: "agent:agent-b-id",
        label: "Agent B",
        kind: "agent",
        description: "runtime selectable"
      }
    ]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/im/v1/users",
      expect.objectContaining({ method: "POST" })
    );
  });
});

describe("im chat stream parser", () => {
  it("requests latest event id for one conversation", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ latest_event_id: 42 }), { status: 200 })
    );

    await expect(getConversationLatestEventId("conv-1")).resolves.toBe(42);
    expect(fetchMock).toHaveBeenCalledWith(
      "/im/v1/conversations/conv-1/events/latest",
      expect.objectContaining({
        headers: expect.objectContaining({ "Content-Type": "application/json" })
      })
    );
  });

  it("passes after_event_id when opening an SSE stream", () => {
    class FakeEventSource {
      static instances: FakeEventSource[] = [];
      url: string;
      onerror: (() => void) | null = null;
      constructor(url: string) {
        this.url = url;
        FakeEventSource.instances.push(this);
      }
      addEventListener() {}
      removeEventListener() {}
      close() {}
    }

    vi.stubGlobal("EventSource", FakeEventSource);

    const teardown = streamConversationEvents({
      conversationId: "conv-9",
      afterEventId: 17,
      onEvent: () => undefined
    });

    expect(FakeEventSource.instances[0]?.url).toBe("/im/v1/conversations/conv-9/events?after_event_id=17");
    teardown();
  });

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

// M234: group chat delete API
describe("deleteConversation / leaveConversation", () => {
  it("deleteConversation sends DELETE to /im/v1/conversations/{id} with requester_id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(null, { status: 204 })
    );

    const { deleteConversation } = await import("./im-chat-api");
    await deleteConversation({ conversationId: "conv-abc", requesterId: "user-123" });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/im\/v1\/conversations\/conv-abc$/);
    expect(init.method).toBe("DELETE");
    const body = JSON.parse(init.body as string) as { requester_id: string };
    expect(body.requester_id).toBe("user-123");
  });

  it("leaveConversation sends DELETE to /im/v1/conversations/{id}/participants/{userId}", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(null, { status: 204 })
    );

    const { leaveConversation } = await import("./im-chat-api");
    await leaveConversation({ conversationId: "conv-abc", userId: "user-456" });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/im\/v1\/conversations\/conv-abc\/participants\/user-456$/);
    expect(init.method).toBe("DELETE");
  });
});

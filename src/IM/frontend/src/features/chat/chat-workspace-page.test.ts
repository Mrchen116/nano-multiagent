import { createElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderRouter } from "../../test/render-router";
import { resolveSendAvailability } from "./im-chat-api";
import {
  buildUsageView,
  ChatWorkspacePage,
  mergeConversationDetail,
  shouldRefreshUsageForEvent,
  toRelayAgentMessage
} from "./chat-workspace-page";
import { UsageMetricRow } from "./types";

const getChatBootstrapState = vi.fn();
const getChatStarter = vi.fn();
const listConversations = vi.fn();
const listDiscoverableGroupParticipants = vi.fn();
const createGroupConversation = vi.fn();
const createFreshDirectConversation = vi.fn();
const getConversation = vi.fn();
const sendMessage = vi.fn();
const uploadAttachment = vi.fn();
const getUsageMetrics = vi.fn();
const streamConversationEvents = vi.fn((_: unknown) => () => undefined);

vi.mock("../../hooks/use-is-mobile", () => ({
  useIsMobile: () => false
}));

vi.mock("./chat-api", () => ({
  getChatBootstrapState: () => getChatBootstrapState(),
  getChatStarter: () => getChatStarter(),
  listConversations: () => listConversations(),
  listDiscoverableGroupParticipants: () => listDiscoverableGroupParticipants(),
  createGroupConversation: (input: { participantIds: string[] }) => createGroupConversation(input),
  createFreshDirectConversation: (input: { agentId: string }) => createFreshDirectConversation(input),
  getConversation: (conversationId: string) => getConversation(conversationId),
  getUsageMetrics: (input: { ownerId?: string; conversationId?: string }) => getUsageMetrics(input),
  uploadAttachment: (file: File) => uploadAttachment(file),
  resolveSendAvailability,
  sendMessage: (input: { conversationId: string; content: string; attachments?: unknown[] }) => sendMessage(input),
  streamConversationEvents: (input: {
    conversationId: string;
    onEvent: (event: unknown) => void;
    onError?: (error: Error) => void;
  }) => streamConversationEvents(input)
}));

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function renderWorkspaceRouter(initialEntries: string[] = ["/chat/conv-1"]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  });
  const router = createMemoryRouter(
    [
      { path: "/chat", element: createElement(ChatWorkspacePage) },
      { path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }
    ],
    { initialEntries }
  );

  return {
    queryClient,
    router,
    ...render(
      createElement(
        QueryClientProvider,
        { client: queryClient },
        createElement(RouterProvider, { router })
      )
    )
  };
}

function getRenderedMessageContents(container: HTMLElement) {
  return Array.from(container.querySelectorAll(".whitespace-pre-wrap")).map((node) => node.textContent);
}

function createConversationUsageRow(input: {
  conversationId: string;
  ownerId?: string;
  turns: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens?: number;
}): UsageMetricRow {
  return {
    scope: "conversation",
    scope_id: input.conversationId,
    owner_id: input.ownerId ?? "owner-1",
    conversation_id: input.conversationId,
    agent_id: null,
    turns: input.turns,
    prompt_tokens: input.promptTokens,
    completion_tokens: input.completionTokens,
    total_tokens: input.totalTokens ?? input.promptTokens + input.completionTokens,
    last_used_at: "2026-03-14T00:00:00Z"
  };
}

function createWorkspaceUsageRow(input: {
  ownerId?: string;
  turns: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens?: number;
}): UsageMetricRow {
  return {
    scope: "owner",
    scope_id: input.ownerId ?? "owner-1",
    owner_id: input.ownerId ?? "owner-1",
    conversation_id: null,
    agent_id: null,
    turns: input.turns,
    prompt_tokens: input.promptTokens,
    completion_tokens: input.completionTokens,
    total_tokens: input.totalTokens ?? input.promptTokens + input.completionTokens,
    last_used_at: "2026-03-14T00:00:01Z"
  };
}

function renderWorkspaceWithPersistentClient(options: {
  initialEntries: string[];
  routes?: Array<{ path: string; element: ReturnType<typeof createElement> }>;
}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 5_000
      }
    }
  });
  const router = createMemoryRouter(
    options.routes ?? [
      { path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) },
      { path: "/settings", element: createElement("div", null, "Settings") }
    ],
    {
      initialEntries: options.initialEntries
    }
  );
  const rendered = render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(RouterProvider, { router })
    )
  );
  return {
    ...rendered,
    queryClient,
    router
  };
}

describe("chat workspace usage helpers", () => {
  it("builds conversation, workspace, and per-agent usage without double counting", () => {
    expect(
      buildUsageView({
        conversationRows: [
          {
            scope: "conversation",
            scope_id: "conv-1",
            owner_id: "owner-1",
            conversation_id: "conv-1",
            agent_id: null,
            turns: 1,
            prompt_tokens: 11,
            completion_tokens: 7,
            total_tokens: 18,
            last_used_at: "2026-03-13T00:00:00Z"
          },
          {
            scope: "agent",
            scope_id: "agent-alpha",
            owner_id: "owner-1",
            conversation_id: "conv-1",
            agent_id: "agent-alpha",
            turns: 1,
            prompt_tokens: 11,
            completion_tokens: 7,
            total_tokens: 18,
            last_used_at: "2026-03-13T00:00:01Z"
          }
        ],
        workspaceRows: [
          {
            scope: "owner",
            scope_id: "owner-1",
            owner_id: "owner-1",
            conversation_id: null,
            agent_id: null,
            turns: 3,
            prompt_tokens: 21,
            completion_tokens: 13,
            total_tokens: 34,
            last_used_at: "2026-03-13T00:00:02Z"
          },
          {
            scope: "conversation",
            scope_id: "conv-1",
            owner_id: "owner-1",
            conversation_id: "conv-1",
            agent_id: null,
            turns: 1,
            prompt_tokens: 11,
            completion_tokens: 7,
            total_tokens: 18,
            last_used_at: "2026-03-13T00:00:03Z"
          }
        ]
      })
    ).toEqual({
      conversation: {
        turns: 1,
        promptTokens: 11,
        completionTokens: 7,
        totalTokens: 18
      },
      workspace: {
        turns: 3,
        promptTokens: 21,
        completionTokens: 13,
        totalTokens: 34
      },
      agents: [
        {
          agentId: "agent-alpha",
          label: "agent-alpha",
          totals: {
            turns: 1,
            promptTokens: 11,
            completionTokens: 7,
            totalTokens: 18
          }
        }
      ]
    });
  });

  it("refreshes usage only for events that can change visible totals", () => {
    expect(shouldRefreshUsageForEvent("message.sent")).toBe(true);
    expect(shouldRefreshUsageForEvent("relay.report")).toBe(true);
    expect(shouldRefreshUsageForEvent("relay.completed")).toBe(true);
    expect(shouldRefreshUsageForEvent("message.delivered")).toBe(true);
    expect(shouldRefreshUsageForEvent("turn_end")).toBe(true);
    expect(shouldRefreshUsageForEvent("message_status")).toBe(true);
    expect(shouldRefreshUsageForEvent("relay.processing")).toBe(false);
    expect(shouldRefreshUsageForEvent("conversation.notice")).toBe(false);
  });
});

describe("chat workspace relay event mapping", () => {
  it("adds recovery guidance when relay failure becomes an agent failure bubble", () => {
    expect(
      toRelayAgentMessage({
        eventType: "relay.failed",
        payload: {
          message_id: "msg-2",
          detail: "agent execution aborted"
        }
      })
    ).toMatchObject({
      message_id: "msg-2:agent",
      sender_type: "agent",
      content: "agent execution aborted",
      delivery_status: "failed",
      recovery_action_label: "Retry request",
      recovery_hint: "The agent stopped before finishing this turn. Retry the request to ask the agent again."
    });
  });

  it("prefers relay agent display name over node identity for synthetic agent messages", () => {
    expect(
      toRelayAgentMessage({
        eventType: "relay.processing",
        payload: {
          message_id: "msg-1",
          agent_id: "A",
          sender_display_name: "Alpha",
          node_id: "my-macbook",
          summary: "working on it",
          created_at: "2026-03-12T00:00:00Z"
        }
      })
    ).toEqual({
      message_id: "msg-1:agent",
      sender_type: "agent",
      sender_name: "A",
      sender_display_name: "Alpha",
      is_mine: false,
      content: "working on it",
      created_at: "2026-03-12T00:00:00Z",
      delivery_status: "running",
      recovery_action_label: undefined,
      recovery_hint: undefined
    });
  });

  it("falls back to relay agent id before node identity when display name is absent", () => {
    expect(
      toRelayAgentMessage({
        eventType: "relay.processing",
        payload: {
          message_id: "msg-1",
          agent_id: "Q",
          node_id: "my-macbook",
          summary: "working on it",
          created_at: "2026-03-12T00:00:00Z"
        }
      })
    ).toMatchObject({
      message_id: "msg-1:agent",
      sender_type: "agent",
      sender_name: "Q",
      content: "working on it",
      delivery_status: "running"
    });
  });

  it("keeps relay.processing NO_REPLY tokens out of visible agent messages", () => {
    expect(
      toRelayAgentMessage({
        eventType: "relay.processing",
        payload: {
          message_id: "msg-1",
          node_id: "node-demo",
          summary: "NO_REPLY",
          created_at: "2026-03-12T00:00:00Z"
        }
      })
    ).toBeNull();
  });

  it("keeps relay.report NO_REPLY tokens out of visible agent messages", () => {
    expect(
      toRelayAgentMessage({
        eventType: "relay.report",
        payload: {
          message_id: "msg-1",
          node_id: "node-demo",
          summary: "NO_REPLY",
          created_at: "2026-03-12T00:00:00Z"
        }
      })
    ).toBeNull();
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
      delivery_status: "completed",
      recovery_action_label: undefined,
      recovery_hint: undefined
    });
  });

  it("keeps suppressed NO_REPLY completion receipts out of visible agent messages", () => {
    expect(
      toRelayAgentMessage({
        eventType: "relay.completed",
        payload: {
          message_id: "msg-1",
          detail: "suppressed_by=no_reply_token"
        }
      })
    ).toBeNull();
  });

  it("keeps suppressed NO_REPLY delivery receipts out of visible agent messages", () => {
    expect(
      toRelayAgentMessage({
        eventType: "message.delivered",
        payload: {
          message_id: "msg-1",
          detail: "NO_REPLY | suppressed_by=no_reply_token"
        }
      })
    ).toBeNull();
  });
});

describe("chat workspace message ordering", () => {
  it("keeps cached relay messages interleaved when reloading persisted history", () => {
    const merged = mergeConversationDetail(
      {
        conversation_id: "conv-1",
        title: "You & Teammate",
        kind_label: "Direct agent chat",
        target_label: "Teammate",
        discoverability_hint: "This is a one-to-one conversation with an available target.",
        mention_candidates: [],
        messages: [
          {
            message_id: "msg-user-1",
            sender_type: "user",
            sender_name: "You",
            is_mine: true,
            content: "First user turn",
            created_at: "2026-03-14T10:00:00Z",
            delivery_status: "completed",
            attachments: []
          },
          {
            message_id: "msg-user-2",
            sender_type: "user",
            sender_name: "You",
            is_mine: true,
            content: "Second user turn",
            created_at: "2026-03-14T10:00:02Z",
            delivery_status: "completed",
            attachments: []
          }
        ]
      },
      {
        conversation_id: "conv-1",
        title: "You & Teammate",
        mention_candidates: [],
        messages: [
          {
            message_id: "msg-user-1",
            sender_type: "user",
            sender_name: "You",
            is_mine: true,
            content: "First user turn",
            created_at: "2026-03-14T10:00:00Z",
            delivery_status: "completed",
            attachments: []
          },
          {
            message_id: "msg-user-1:agent",
            sender_type: "agent",
            sender_name: "node-demo",
            is_mine: false,
            content: "Agent reply between the two user turns",
            created_at: "2026-03-14T10:00:01Z",
            delivery_status: "completed",
            attachments: []
          },
          {
            message_id: "msg-user-2",
            sender_type: "user",
            sender_name: "You",
            is_mine: true,
            content: "Second user turn",
            created_at: "2026-03-14T10:00:02Z",
            delivery_status: "completed",
            attachments: []
          }
        ]
      }
    );

    expect(merged?.messages.map((message) => message.content)).toEqual([
      "First user turn",
      "Agent reply between the two user turns",
      "Second user turn"
    ]);
  });

  it("renders re-entered conversations in chronological order after history and SSE state merge", async () => {
    const persistedHistory = {
      conversation_id: "conv-1",
      title: "You & Teammate",
      kind_label: "Direct agent chat",
      target_label: "Teammate",
      discoverability_hint: "This is a one-to-one conversation with an available target.",
      mention_candidates: [],
      messages: [
        {
          message_id: "msg-user-1",
          sender_type: "user",
          sender_name: "You",
          is_mine: true,
          content: "First user turn",
          created_at: "2026-03-14T10:00:00Z",
          delivery_status: "completed",
          attachments: []
        },
        {
          message_id: "msg-user-2",
          sender_type: "user",
          sender_name: "You",
          is_mine: true,
          content: "Second user turn",
          created_at: "2026-03-14T10:00:02Z",
          delivery_status: "completed",
          attachments: []
        }
      ]
    };
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      ownerId: "owner-1",
      targetNodeId: "node-online",
      targetNodeStatus: "online",
      initialConversationId: "conv-1",
      ownership: {
        nodeId: "node-online",
        nodeLabel: "Online Node",
        nodeStatus: "online",
        agentLabel: "OpsBot",
        ownershipLabel: "Using OpsBot on Online Node (online)"
      }
    });
    getChatStarter.mockResolvedValue({
      title: "主 Agent · OpsBot",
      actionLabel: "Open 主 Agent · OpsBot",
      actionHref: "/chat/conv-1",
      agentName: "OpsBot",
      description:
        "OpsBot is your main agent and default starter chat, but you can also open direct agent chats, group chats, and agent-to-agent threads from the conversation list.",
      nodeLabel: "node-online",
      statusLabel: "Using your main agent OpsBot on node-online (online)"
    });
    listConversations.mockResolvedValue([
      {
        conversation_id: "conv-1",
        title: "You & Teammate",
        last_message_preview: "Second user turn",
        last_message_at: "2026-03-14T10:00:02Z",
        unread_count: 0,
        participants: ["You", "Teammate"],
        kind_label: "Direct agent chat",
        target_label: "Teammate",
        discoverability_hint: "This is a one-to-one conversation with an available target."
      }
    ]);
    getUsageMetrics.mockResolvedValue([]);
    getConversation.mockResolvedValue(persistedHistory);

    const { container, router } = renderWorkspaceRouter();

    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    expect(getConversation).toHaveBeenCalledTimes(1);

    const initialStreamInput = streamConversationEvents.mock.calls.at(-1)?.[0] as
      | { onEvent: (event: { eventType: string; payload: Record<string, unknown> }) => void }
      | undefined;
    expect(initialStreamInput).toBeDefined();

    initialStreamInput?.onEvent({
      eventType: "relay.report",
      payload: {
        message_id: "msg-user-1",
        node_id: "node-demo",
        summary: "Agent reply between the two user turns",
        created_at: "2026-03-14T10:00:01Z"
      }
    });

    expect(await screen.findByText("Agent reply between the two user turns", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    expect(getRenderedMessageContents(container)).toEqual([
      "First user turn",
      "Agent reply between the two user turns",
      "Second user turn"
    ]);

    await act(async () => {
      await router.navigate("/chat");
    });
    expect(await screen.findByText("主 Agent · OpsBot")).toBeInTheDocument();

    await act(async () => {
      await router.navigate("/chat/conv-1");
    });
    await waitFor(() => {
      expect(getConversation).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    await screen.findByText("Agent reply between the two user turns", { selector: ".whitespace-pre-wrap" });

    expect(getRenderedMessageContents(container)).toEqual([
      "First user turn",
      "Agent reply between the two user turns",
      "Second user turn"
    ]);
  });
});

describe("chat workspace page", () => {
  it("shows the main-agent semantics on the default starter entry", async () => {
    renderRouter({
      routes: [{ path: "/chat", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat"]
    });

    expect(await screen.findByText("主 Agent · OpsBot")).toBeInTheDocument();
    expect(screen.getByText("OpsBot is your main agent and default starter chat. Reuse each agent's dedicated direct chat from Settings, or open group chats and agent-to-agent threads from the conversation list.")).toBeInTheDocument();
    expect(screen.getByText("Using your main agent OpsBot on node-1 (online)")).toBeInTheDocument();
  });

  beforeEach(() => {
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      ownerId: "owner-1",
      targetNodeId: null,
      targetNodeStatus: null,
      initialConversationId: "conv-1",
      ownership: {
        nodeId: null,
        nodeLabel: null,
        nodeStatus: null,
        agentLabel: "OpsBot",
        ownershipLabel: "No bound node is selected for OpsBot"
      }
    });
    getChatStarter.mockResolvedValue({
      title: "主 Agent · OpsBot",
      actionLabel: "Open 主 Agent · OpsBot",
      actionHref: "/chat/conv-1",
      agentName: "OpsBot",
      description: "OpsBot is your main agent and default starter chat. Reuse each agent's dedicated direct chat from Settings, or open group chats and agent-to-agent threads from the conversation list.",
      nodeLabel: "node-1",
      statusLabel: "Using your main agent OpsBot on node-1 (online)"
    });
    listConversations.mockResolvedValue([
      {
        conversation_id: "conv-1",
        title: "You & Teammate",
        last_message_preview: "",
        last_message_at: null,
        unread_count: 0,
        participants: ["You", "Teammate"],
        kind_label: "Direct agent chat",
        target_label: "Teammate",
        discoverability_hint: "This is a one-to-one conversation with an available target."
      }
    ]);
    listDiscoverableGroupParticipants.mockResolvedValue([
      {
        user_id: "agent-ops-user",
        label: "OpsBot",
        kind: "agent",
        description: "Primary runtime agent"
      },
      {
        user_id: "agent-new-user",
        label: "Agent New",
        kind: "agent",
        description: "runtime-created helper"
      },
      {
        user_id: "teammate-alex",
        label: "Alex",
        kind: "teammate",
        description: "Human teammate"
      }
    ]);
    createGroupConversation.mockResolvedValue({ conversation_id: "conv-group-new" });
    createFreshDirectConversation.mockResolvedValue({ conversation_id: "conv-fresh-1" });
    getConversation.mockImplementation(async (conversationId: string) => {
      if (conversationId === "conv-group-new") {
        return {
          conversation_id: "conv-group-new",
          title: "OpsBot + Alex",
          kind_label: "Group chat",
          target_label: "Multiple participants",
          discoverability_hint: "Use this thread when you want multiple participants working together.",
          mention_candidates: [
            { agentId: "ops-bot", label: "OpsBot" },
            { agentId: "agent-new", label: "Agent New" }
          ],
          messages: []
        };
      }
      if (conversationId === "conv-fresh-1") {
        return {
          conversation_id: "conv-fresh-1",
          title: "Teammate · Fresh session",
          kind_label: "Direct agent chat",
          target_label: "Teammate",
          discoverability_hint: "Reuse this stable direct chat for the same agent, or start a fresh session here when you need a new prompt snapshot.",
          direct_agent_id: "agent-ops",
          mention_candidates: [],
          messages: []
        };
      }
      return {
        conversation_id: "conv-1",
        title: "You & Teammate",
        kind_label: "Direct agent chat",
        target_label: "Teammate",
        discoverability_hint: "Reuse this stable direct chat for the same agent, or start a fresh session here when you need a new prompt snapshot.",
        direct_agent_id: "agent-ops",
        mention_candidates: [],
        messages: []
      };
    });
    getUsageMetrics.mockImplementation(async (input: { ownerId?: string; conversationId?: string }) => {
      if (input.conversationId === "conv-1") {
        return [
          {
            scope: "conversation",
            scope_id: "conv-1",
            owner_id: "owner-1",
            conversation_id: "conv-1",
            agent_id: null,
            turns: 3,
            prompt_tokens: 11,
            completion_tokens: 7,
            total_tokens: 18,
            last_used_at: "2026-03-12T00:00:00Z"
          },
          {
            scope: "agent",
            scope_id: "agent-alpha",
            owner_id: "owner-1",
            conversation_id: "conv-1",
            agent_id: "agent-alpha",
            turns: 3,
            prompt_tokens: 11,
            completion_tokens: 7,
            total_tokens: 18,
            last_used_at: "2026-03-12T00:00:00Z"
          },
          {
            scope: "agent",
            scope_id: "agent-beta",
            owner_id: "owner-1",
            conversation_id: "conv-1",
            agent_id: "agent-beta",
            turns: 1,
            prompt_tokens: 5,
            completion_tokens: 9,
            total_tokens: 14,
            last_used_at: "2026-03-12T00:05:00Z"
          }
        ];
      }
      if (input.ownerId === "owner-1") {
        return [
          {
            scope: "owner",
            scope_id: "owner-1",
            owner_id: "owner-1",
            conversation_id: null,
            agent_id: null,
            turns: 8,
            prompt_tokens: 26,
            completion_tokens: 18,
            total_tokens: 44,
            last_used_at: "2026-03-12T01:00:00Z"
          },
          {
            scope: "conversation",
            scope_id: "conv-1",
            owner_id: "owner-1",
            conversation_id: "conv-1",
            agent_id: null,
            turns: 3,
            prompt_tokens: 11,
            completion_tokens: 7,
            total_tokens: 18,
            last_used_at: "2026-03-12T00:00:00Z"
          }
        ];
      }
      return [];
    });
    sendMessage.mockResolvedValue({});
    uploadAttachment.mockResolvedValue({
      url: "http://im.test/im/uploads/demo.txt",
      file_name: "demo.txt",
      content_type: "text/plain"
    });
    streamConversationEvents.mockReturnValue(() => undefined);
  });

  it("blocks sending when no node is bound yet", async () => {
    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    expect(await screen.findByText("Chat unavailable")).toBeInTheDocument();
    expect(screen.getByText("Bind this Gateway to continue. Web IM disables the composer until one of your Gateway nodes is connected.")).toBeInTheDocument();
    expect(screen.getByText("Next: Open bind flow")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByPlaceholderText("Bind this Gateway to continue")).toBeDisabled();
  });

  it("shows a product-grade send blocker when the bound node is offline", async () => {
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      ownerId: "owner-1",
      targetNodeId: "node-offline",
      targetNodeStatus: "offline",
      initialConversationId: "conv-1",
      ownership: {
        nodeId: "node-offline",
        nodeLabel: "Offline Node",
        nodeStatus: "offline",
        agentLabel: "OpsBot",
        ownershipLabel: "Using OpsBot on Offline Node (offline)"
      }
    });
    getChatStarter.mockResolvedValue({
      title: "主 Agent · OpsBot",
      actionLabel: "Open 主 Agent · OpsBot",
      actionHref: "/chat/conv-1",
      agentName: "OpsBot",
      description: "OpsBot is your main agent and default IM entry for this workspace.",
      nodeLabel: "Offline Node",
      statusLabel: "offline"
    });

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    expect(await screen.findByText("Chat unavailable")).toBeInTheDocument();
    expect(
      screen.getByText("Your bound Gateway is offline. Bring that node online or bind another online node to re-enable chat.")
    ).toBeInTheDocument();
    expect(screen.getByText("Next: Bring Gateway online")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByPlaceholderText("Gateway offline — chat disabled")).toBeDisabled();
  });

  it("shows selectable participants, selected state, and a disabled create affordance for group chat creation", async () => {
    const user = userEvent.setup();

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create group chat" }));

    expect(await screen.findByText("Select participants")).toBeInTheDocument();
    expect(screen.getByText("OpsBot")).toBeInTheDocument();
    expect(screen.getByText("Agent New")).toBeInTheDocument();
    expect(screen.getByText("Alex")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create selected group chat" })).toBeDisabled();
    expect(screen.getByText("No participants selected yet. Pick at least two people or agents to create a real group chat.")).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: /OpsBot/i }));
    expect(screen.getByRole("checkbox", { name: /OpsBot/i })).toBeChecked();
    expect(screen.getAllByText("Selected").length).toBeGreaterThan(0);
    expect(screen.getByText("1 participant selected.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create selected group chat" })).toBeDisabled();

    await user.click(screen.getByRole("checkbox", { name: /Alex/i }));
    expect(screen.getByRole("button", { name: "Create selected group chat" })).toBeEnabled();
    expect(screen.getByText("Ready to create a group chat with 2 selected participants plus you.")).toBeInTheDocument();
  });

  it("shows loading and no-available-participants states in the group creation panel", async () => {
    const user = userEvent.setup();
    const deferredParticipants = createDeferred<
      Array<{ user_id: string; label: string; kind: "agent" | "teammate"; description?: string }>
    >();
    listDiscoverableGroupParticipants.mockReturnValueOnce(deferredParticipants.promise);

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create group chat" }));

    expect(screen.getByText("Loading available participants...")).toBeInTheDocument();

    deferredParticipants.resolve([]);

    expect(await screen.findByText("No available participants yet. Add a teammate or configure another agent to start a shared thread.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create selected group chat" })).toBeDisabled();
  });

  it("creates a group chat from selected participants and navigates into the new thread", async () => {
    const user = userEvent.setup();

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create group chat" }));
    await user.click(screen.getByRole("checkbox", { name: /OpsBot/i }));
    await user.click(screen.getByRole("checkbox", { name: /Alex/i }));
    await user.click(screen.getByRole("button", { name: "Create selected group chat" }));

    // M235: groupName is now passed alongside participantIds (empty string = auto-generate title).
    expect(createGroupConversation).toHaveBeenCalledWith({ participantIds: ["agent-ops-user", "teammate-alex"], groupName: "" });
    expect(await screen.findByRole("heading", { name: "OpsBot + Alex" })).toBeInTheDocument();
    expect(getConversation).toHaveBeenCalledWith("conv-group-new");
    expect(screen.queryByText("Select participants")).not.toBeInTheDocument();
  });

  it("removes the new direct chat CTA while keeping group chat creation available", async () => {
    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New direct chat" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create group chat" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start fresh session" })).toBeInTheDocument();
    expect(screen.queryByText("Keep each agent's reusable direct chat, shared threads, and agent coordination in one production inbox.")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /You & Teammate/i })).toBeInTheDocument();
  });

  it("starts a fresh session from a direct chat without restoring the global new-direct entry", async () => {
    const user = userEvent.setup();

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Start fresh session" }));

    expect(createFreshDirectConversation).toHaveBeenCalledWith({ agentId: "agent-ops" });
    expect(await screen.findByRole("heading", { name: "Teammate · Fresh session" })).toBeInTheDocument();
    expect(getConversation).toHaveBeenCalledWith("conv-fresh-1");
  });

  it("exposes group-chat mention candidates from agent participants only", async () => {
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      ownerId: "owner-1",
      targetNodeId: "node-online",
      targetNodeStatus: "online",
      initialConversationId: "conv-group",
      ownership: {
        nodeId: "node-online",
        nodeLabel: "Online Node",
        nodeStatus: "online",
        agentLabel: "OpsBot",
        ownershipLabel: "Using OpsBot on Online Node (online)"
      }
    });
    getConversation.mockResolvedValueOnce({
      conversation_id: "conv-group",
      title: "Kernel Ops Crew",
      kind_label: "Group chat",
      target_label: "Multiple participants",
      discoverability_hint: "Shared thread",
      mention_candidates: [
        { agentId: "ops-bot", label: "OpsBot" },
        { agentId: "review-bot", label: "ReviewBot" }
      ],
      messages: []
    });

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-group"]
    });

    expect(await screen.findByRole("heading", { name: "Kernel Ops Crew" })).toBeInTheDocument();
    await userEvent.type(screen.getByPlaceholderText("Type message"), "@");
    expect(screen.getByRole("option", { name: /OpsBot/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /ReviewBot/i })).toBeInTheDocument();
  });

  it("reconciles replayed agent events that arrive before history loading completes", async () => {
    const deferredConversation = createDeferred<{
      conversation_id: string;
      title: string;
      kind_label: string;
      target_label: string;
      discoverability_hint: string;
      mention_candidates: [];
      messages: Array<{
        message_id: string;
        sender_type: "user";
        sender_name: string;
        is_mine: true;
        content: string;
        created_at: string;
        delivery_status: "sent";
        attachments: [];
      }>;
    }>();

    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      ownerId: "owner-1",
      targetNodeId: "node-online",
      targetNodeStatus: "online",
      initialConversationId: "conv-1",
      ownership: {
        nodeId: "node-online",
        nodeLabel: "Online Node",
        nodeStatus: "online",
        agentLabel: "OpsBot",
        ownershipLabel: "Using OpsBot on Online Node (online)"
      }
    });
    getConversation.mockImplementationOnce(async () => deferredConversation.promise);

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    await waitFor(() => {
      expect(streamConversationEvents).toHaveBeenCalled();
    });

    const streamInput = streamConversationEvents.mock.calls.at(-1)?.[0] as
      | { onEvent: (event: { eventType: string; payload: Record<string, unknown> }) => void }
      | undefined;
    expect(streamInput).toBeDefined();

    streamInput?.onEvent({
      eventType: "relay.processing",
      payload: {
        message_id: "msg-history",
        node_id: "node-demo",
        summary: "Agent is preparing the response",
        created_at: "2026-03-13T10:00:01Z"
      }
    });

    deferredConversation.resolve({
      conversation_id: "conv-1",
      title: "You & Teammate",
      kind_label: "Direct agent chat",
      target_label: "Teammate",
      discoverability_hint: "This is a one-to-one conversation with an available target.",
      mention_candidates: [],
      messages: [
        {
          message_id: "msg-history",
          sender_type: "user",
          sender_name: "You",
          is_mine: true,
          content: "Need a full update",
          created_at: "2026-03-13T10:00:00Z",
          delivery_status: "sent",
          attachments: []
        }
      ]
    });

    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    expect(screen.getByText("Need a full update", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    expect(screen.getByText("Agent is preparing the response", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    expect(screen.queryByText("You")).not.toBeInTheDocument();
    expect(screen.queryByText("node-demo")).not.toBeInTheDocument();
  });

  it("keeps optimistic self messages on the local side after SSE reconciliation", async () => {
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      ownerId: "owner-1",
      targetNodeId: "node-online",
      targetNodeStatus: "online",
      initialConversationId: "conv-1",
      ownership: {
        nodeId: "node-online",
        nodeLabel: "Online Node",
        nodeStatus: "online",
        agentLabel: "OpsBot",
        ownershipLabel: "Using OpsBot on Online Node (online)"
      }
    });
    sendMessage.mockResolvedValue({
      message_id: "msg-self",
      sender_type: "user",
      sender_name: "You",
      is_mine: true,
      content: "I will handle this update.",
      created_at: "2026-03-13T10:00:00Z",
      delivery_status: "sent",
      attachments: []
    });

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();

    await userEvent.type(screen.getByPlaceholderText("Type message"), "I will handle this update.");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    const streamInput = streamConversationEvents.mock.calls.at(-1)?.[0] as
      | { onEvent: (event: { eventType: string; payload: Record<string, unknown> }) => void }
      | undefined;
    expect(streamInput).toBeDefined();
    streamInput?.onEvent({
      eventType: "message.sent",
      payload: {
        message_id: "msg-self",
        sender_user_id: "user-1",
        sender_type: "user",
        content: "I will handle this update.",
        created_at: "2026-03-13T10:00:00Z",
        delivery_status: "sent"
      }
    });

    expect(screen.getByText("I will handle this update.", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    expect(screen.queryByText("You")).not.toBeInTheDocument();
    expect(screen.queryByText("user-1")).not.toBeInTheDocument();
  });

  it("keeps relay-completed agent replies visible after late history hydration for direct chats", async () => {
    const deferredConversation = createDeferred<{
      conversation_id: string;
      title: string;
      kind_label: string;
      target_label: string;
      discoverability_hint: string;
      mention_candidates: [];
      messages: Array<{
        message_id: string;
        sender_type: "user";
        sender_name: string;
        is_mine: true;
        content: string;
        created_at: string;
        delivery_status: "sent";
        attachments: [];
      }>;
    }>();

    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      ownerId: "owner-1",
      targetNodeId: "node-online",
      targetNodeStatus: "online",
      initialConversationId: "conv-1",
      ownership: {
        nodeId: "node-online",
        nodeLabel: "Online Node",
        nodeStatus: "online",
        agentLabel: "OpsBot",
        ownershipLabel: "Using OpsBot on Online Node (online)"
      }
    });
    getConversation.mockImplementationOnce(async () => deferredConversation.promise);

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    await waitFor(() => {
      expect(streamConversationEvents).toHaveBeenCalled();
    });

    const streamInput = streamConversationEvents.mock.calls.at(-1)?.[0] as
      | { onEvent: (event: { eventType: string; payload: Record<string, unknown> }) => void }
      | undefined;
    expect(streamInput).toBeDefined();

    streamInput?.onEvent({
      eventType: "relay.completed",
      payload: {
        message_id: "msg-history",
        node_id: "node-demo",
        detail: "assistant:resolved after completion receipt",
        created_at: "2026-03-13T10:00:02Z"
      }
    });

    deferredConversation.resolve({
      conversation_id: "conv-1",
      title: "You & Teammate",
      kind_label: "Direct agent chat",
      target_label: "Teammate",
      discoverability_hint: "This is a one-to-one conversation with an available target.",
      mention_candidates: [],
      messages: [
        {
          message_id: "msg-history",
          sender_type: "user",
          sender_name: "You",
          is_mine: true,
          content: "Need a full update",
          created_at: "2026-03-13T10:00:00Z",
          delivery_status: "sent",
          attachments: []
        }
      ]
    });

    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    expect(screen.getByText("Need a full update", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    expect(screen.getByText("assistant:resolved after completion receipt", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    expect(screen.queryByText("node-demo")).not.toBeInTheDocument();
  });

  it("keeps NO_REPLY processing and report events out of the live group thread and conversation preview", async () => {
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      ownerId: "owner-1",
      targetNodeId: "m170-node",
      targetNodeStatus: "online",
      initialConversationId: "conv-group",
      ownership: {
        nodeId: "m170-node",
        nodeLabel: "m170-node",
        nodeStatus: "online",
        agentLabel: "assistant",
        ownershipLabel: "Using your main agent assistant on m170-node (online and ready to chat)"
      }
    });
    listConversations.mockResolvedValueOnce([
      {
        conversation_id: "conv-group",
        title: "Agent M170 Alpha + Agent M170 Beta",
        last_message_preview: "Previous visible reply",
        last_message_at: "2026-03-16T03:12:40Z",
        unread_count: 0,
        participants: ["You", "Agent M170 Alpha", "Agent M170 Beta"],
        kind_label: "Group chat",
        target_label: "Multiple participants",
        discoverability_hint: "Use this shared thread for multi-party coordination across people and agents.",
        ownership_label: "Using your main agent assistant on m170-node (online and ready to chat)"
      }
    ]);
    getConversation.mockResolvedValueOnce({
      conversation_id: "conv-group",
      title: "Agent M170 Alpha + Agent M170 Beta",
      kind_label: "Group chat",
      target_label: "Multiple participants",
      discoverability_hint: "Use this shared thread for multi-party coordination across people and agents.",
      mention_candidates: [
        { agentId: "agent-m170-alpha", label: "Agent M170 Alpha" },
        { agentId: "agent-m170-beta", label: "Agent M170 Beta" }
      ],
      messages: [
        {
          message_id: "msg-user-1",
          sender_type: "user",
          sender_name: "You",
          is_mine: true,
          content: "@agent-m170-alpha no-reply check: stay silent now.",
          created_at: "2026-03-16T03:12:56Z",
          delivery_status: "sent",
          attachments: []
        }
      ]
    });

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-group"]
    });

    expect(await screen.findByRole("heading", { name: "Agent M170 Alpha + Agent M170 Beta" })).toBeInTheDocument();
    expect(screen.getByText("Previous visible reply")).toBeInTheDocument();

    const streamInput = streamConversationEvents.mock.calls.at(-1)?.[0] as
      | { onEvent: (event: { eventType: string; payload: Record<string, unknown> }) => void }
      | undefined;
    expect(streamInput).toBeDefined();

    streamInput?.onEvent({
      eventType: "relay.processing",
      payload: {
        message_id: "msg-user-1",
        node_id: "m170-node",
        summary: "NO_REPLY",
        created_at: "2026-03-16T03:13:03Z"
      }
    });
    streamInput?.onEvent({
      eventType: "relay.report",
      payload: {
        message_id: "msg-user-1",
        node_id: "m170-node",
        summary: "NO_REPLY",
        created_at: "2026-03-16T03:13:03Z"
      }
    });

    expect(screen.queryByText("NO_REPLY", { selector: ".whitespace-pre-wrap" })).not.toBeInTheDocument();
    expect(screen.queryByText("Agent is working")).not.toBeInTheDocument();
    expect(screen.queryByText("Agent replied")).not.toBeInTheDocument();
    expect(screen.queryByText("Using your main agent assistant on m170-node (online and ready to chat)")).not.toBeInTheDocument();
    expect(screen.queryByText("Target: Multiple participants")).not.toBeInTheDocument();
    expect(screen.getByText("Previous visible reply")).toBeInTheDocument();
    expect(screen.getAllByText("Group chat").length).toBeGreaterThan(0);
  });

  it("shows real conversation and workspace token-turn usage for the active chat", async () => {
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      ownerId: "owner-1",
      targetNodeId: "node-online",
      targetNodeStatus: "online",
      initialConversationId: "conv-1",
      ownership: {
        nodeId: "node-online",
        nodeLabel: "Online Node",
        nodeStatus: "online",
        agentLabel: "OpsBot",
        ownershipLabel: "Using OpsBot on Online Node (online)"
      }
    });

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    // Usage strip is collapsed by default; expand it first.
    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /usage/i }));
    expect(await screen.findByText("This chat")).toBeInTheDocument();
    expect(screen.getByText("Workspace total")).toBeInTheDocument();
    expect(screen.getAllByText("3 turns")).toHaveLength(2);
    expect(screen.getAllByText("18 tokens")).toHaveLength(2);
    expect(await screen.findByText("8 turns")).toBeInTheDocument();
    expect(screen.getByText("44 tokens")).toBeInTheDocument();
    const agentAlphaTab = screen.getByRole("tab", { name: "agent-alpha" });
    const agentBetaTab = screen.getByRole("tab", { name: "agent-beta" });
    expect(agentAlphaTab).toBeInTheDocument();
    expect(agentBetaTab).toBeInTheDocument();
    expect(agentAlphaTab).toHaveAttribute("aria-selected", "true");
    await userEvent.click(agentBetaTab);
    expect(agentBetaTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Agent · agent-beta")).toBeInTheDocument();
    expect(screen.getByText("Completion 9")).toBeInTheDocument();
    expect(getUsageMetrics).toHaveBeenCalledWith({ conversationId: "conv-1" });
    expect(getUsageMetrics).toHaveBeenCalledWith({ ownerId: "owner-1" });
  });

  it("refreshes visible usage after relay completion delivers real metrics", async () => {
    let usageStage: "initial" | "updated" = "initial";
    getUsageMetrics.mockImplementation(async (input: { ownerId?: string; conversationId?: string }) => {
      if (input.conversationId === "conv-1") {
        return usageStage === "updated"
          ? [createConversationUsageRow({ conversationId: "conv-1", turns: 4, promptTokens: 16, completionTokens: 8 })]
          : [];
      }
      if (input.ownerId === "owner-1") {
        return usageStage === "updated"
          ? [createWorkspaceUsageRow({ ownerId: "owner-1", turns: 10, promptTokens: 36, completionTokens: 24 })]
          : [];
      }
      return [];
    });

    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    // Usage strip is collapsed by default; expand it first.
    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /usage/i }));
    expect(await screen.findByText("This chat")).toBeInTheDocument();
    expect(screen.getAllByText("0 turns")).toHaveLength(2);
    expect(screen.getAllByText("0 tokens")).toHaveLength(2);

    usageStage = "updated";
    const streamInput = streamConversationEvents.mock.calls.at(-1)?.[0] as
      | { onEvent: (event: { eventType: string; payload: Record<string, unknown> }) => void }
      | undefined;
    expect(streamInput).toBeDefined();
    streamInput?.onEvent({
      eventType: "relay.completed",
      payload: {
        message_id: "msg-usage-refresh",
        node_id: "node-online",
        summary: "Usage updated",
        status: "completed"
      }
    });

    await waitFor(() => {
      expect(screen.getByText("4 turns")).toBeInTheDocument();
      expect(screen.getByText("24 tokens")).toBeInTheDocument();
      expect(screen.getByText("10 turns")).toBeInTheDocument();
      expect(screen.getByText("60 tokens")).toBeInTheDocument();
    });
  });

  it("refetches workspace totals when switching chats under the same owner", async () => {
    let usageScenario: "conv-1" | "conv-2" = "conv-1";
    getConversation.mockImplementation(async (conversationId: string) => {
      if (conversationId === "conv-2") {
        return {
          conversation_id: "conv-2",
          title: "Project Escalation",
          kind_label: "Direct agent chat",
          target_label: "Teammate",
          discoverability_hint: "This is a one-to-one conversation with an available target.",
          mention_candidates: [],
          messages: []
        };
      }
      return {
        conversation_id: "conv-1",
        title: "You & Teammate",
        kind_label: "Direct agent chat",
        target_label: "Teammate",
        discoverability_hint: "This is a one-to-one conversation with an available target.",
        mention_candidates: [],
        messages: []
      };
    });
    getUsageMetrics.mockImplementation(async (input: { ownerId?: string; conversationId?: string }) => {
      if (usageScenario === "conv-1") {
        return [];
      }
      if (input.conversationId === "conv-2") {
        return [createConversationUsageRow({ conversationId: "conv-2", turns: 5, promptTokens: 18, completionTokens: 12 })];
      }
      if (input.ownerId === "owner-1") {
        return [createWorkspaceUsageRow({ ownerId: "owner-1", turns: 9, promptTokens: 31, completionTokens: 23 })];
      }
      return [];
    });

    const { router } = renderWorkspaceWithPersistentClient({ initialEntries: ["/chat/conv-1"] });

    // Usage strip is collapsed by default; expand it first.
    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /usage/i }));
    expect(await screen.findByText("This chat")).toBeInTheDocument();
    expect(screen.getAllByText("0 turns")).toHaveLength(2);

    usageScenario = "conv-2";
    await act(async () => {
      await router.navigate("/chat/conv-2");
    });

    expect(await screen.findByRole("heading", { name: "Project Escalation" })).toBeInTheDocument();
    // Strip resets to collapsed on navigation; expand again to verify updated totals.
    await userEvent.click(screen.getByRole("button", { name: /usage/i }));
    await waitFor(() => {
      expect(screen.getByText("5 turns")).toBeInTheDocument();
      expect(screen.getByText("30 tokens")).toBeInTheDocument();
      expect(screen.getByText("9 turns")).toBeInTheDocument();
      expect(screen.getByText("54 tokens")).toBeInTheDocument();
    });
  });

  it("refetches usage when re-entering the chat so cached zeros do not stick", async () => {
    let usageStage: "initial" | "updated" = "initial";
    getUsageMetrics.mockImplementation(async (input: { ownerId?: string; conversationId?: string }) => {
      if (input.conversationId === "conv-1") {
        return usageStage === "updated"
          ? [createConversationUsageRow({ conversationId: "conv-1", turns: 6, promptTokens: 21, completionTokens: 15 })]
          : [];
      }
      if (input.ownerId === "owner-1") {
        return usageStage === "updated"
          ? [createWorkspaceUsageRow({ ownerId: "owner-1", turns: 12, promptTokens: 44, completionTokens: 28 })]
          : [];
      }
      return [];
    });

    const { router } = renderWorkspaceWithPersistentClient({ initialEntries: ["/chat/conv-1"] });

    // Usage strip is collapsed by default; expand it first.
    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /usage/i }));
    expect(await screen.findByText("This chat")).toBeInTheDocument();
    expect(screen.getAllByText("0 turns")).toHaveLength(2);

    usageStage = "updated";
    await act(async () => {
      await router.navigate("/settings");
    });
    expect(await screen.findByText("Settings")).toBeInTheDocument();

    await act(async () => {
      await router.navigate("/chat/conv-1");
    });

    // Strip resets to collapsed on navigation; expand again to verify updated totals.
    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /usage/i }));
    await waitFor(() => {
      expect(screen.getByText("6 turns")).toBeInTheDocument();
      expect(screen.getByText("36 tokens")).toBeInTheDocument();
      expect(screen.getByText("12 turns")).toBeInTheDocument();
      expect(screen.getByText("72 tokens")).toBeInTheDocument();
    });
  });

  it("invalidates stale bootstrap identity after bind confirmation state is carried into chat", async () => {
    getChatBootstrapState
      .mockResolvedValueOnce({
        selfUserId: "user-stale",
        ownerId: "owner-stale",
        targetNodeId: "node-1",
        targetNodeStatus: "online",
        initialConversationId: "conv-1",
        ownership: {
          ownershipLabel: "Owned by you",
          nodeLabel: "MacBook"
        }
      })
      .mockResolvedValueOnce({
        selfUserId: "user-fresh",
        ownerId: "owner-fresh",
        targetNodeId: "node-1",
        targetNodeStatus: "online",
        initialConversationId: "conv-1",
        ownership: {
          ownershipLabel: "Owned by you",
          nodeLabel: "MacBook"
        }
      });

    const { queryClient } = renderWorkspaceWithPersistentClient({
      initialEntries: [{ pathname: "/chat/conv-1", state: { boundSelfUserId: "user-fresh" } } as unknown as string],
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }]
    });

    await waitFor(() => {
      expect(getChatBootstrapState.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
    await waitFor(() => {
      expect(queryClient.getQueryData(["chat", "bootstrap"])).toMatchObject({ selfUserId: "user-fresh" });
    });
  });

  // M237: 候选列表容器必须有限高和滚动，防止撑高左栏后 ConversationList 滑出视口。
  it("group chat panel - candidate list has max-height and overflow scroll", async () => {
    const user = userEvent.setup();

    const { container } = renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create group chat" }));

    // 等待候选列表渲染完毕（至少一个 agent 出现）。
    expect(await screen.findByText("OpsBot")).toBeInTheDocument();

    // 候选列表包裹层必须带限高（max-h-*）与溢出滚动（overflow-y-auto）。
    const scrollableWrapper = container.querySelector(".overflow-y-auto");
    expect(scrollableWrapper).not.toBeNull();
    const wrapperClasses = scrollableWrapper?.className ?? "";
    expect(/\bmax-h-\S+/.test(wrapperClasses)).toBe(true);
  });
});

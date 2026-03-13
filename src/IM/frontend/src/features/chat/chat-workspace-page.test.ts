import { createElement } from "react";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderRouter } from "../../test/render-router";
import { resolveSendAvailability } from "./im-chat-api";
import { buildUsageView, ChatWorkspacePage, shouldRefreshUsageForEvent, toRelayAgentMessage } from "./chat-workspace-page";

const getChatBootstrapState = vi.fn();
const getChatStarter = vi.fn();
const listConversations = vi.fn();
const listDiscoverableAgents = vi.fn();
const listDiscoverableGroupParticipants = vi.fn();
const createDirectConversation = vi.fn();
const createGroupConversation = vi.fn();
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
  listDiscoverableAgents: () => listDiscoverableAgents(),
  listDiscoverableGroupParticipants: () => listDiscoverableGroupParticipants(),
  createDirectConversation: (input: { agentId: string }) => createDirectConversation(input),
  createGroupConversation: (input: { participantIds: string[] }) => createGroupConversation(input),
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
    expect(shouldRefreshUsageForEvent("message.delivered")).toBe(true);
    expect(shouldRefreshUsageForEvent("turn_end")).toBe(true);
    expect(shouldRefreshUsageForEvent("message_status")).toBe(true);
    expect(shouldRefreshUsageForEvent("relay.processing")).toBe(false);
    expect(shouldRefreshUsageForEvent("conversation.notice")).toBe(false);
  });
});

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

describe("chat workspace page", () => {
  it("shows the main-agent semantics on the default starter entry", async () => {
    renderRouter({
      routes: [{ path: "/chat", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat"]
    });

    expect(await screen.findByText("主 Agent · OpsBot")).toBeInTheDocument();
    expect(screen.getByText("OpsBot is your main agent and default starter chat, but you can also open direct agent chats, group chats, and agent-to-agent threads from the conversation list.")).toBeInTheDocument();
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
      description: "OpsBot is your main agent and default starter chat, but you can also open direct agent chats, group chats, and agent-to-agent threads from the conversation list.",
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
    listDiscoverableAgents.mockResolvedValue([
      {
        agent_id: "agent-new",
        display_name: "Agent New",
        description: "runtime-created helper",
        existing_conversation_id: null
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
    createDirectConversation.mockResolvedValue({ conversation_id: "conv-agent-new" });
    createGroupConversation.mockResolvedValue({ conversation_id: "conv-group-new" });
    getConversation.mockImplementation(async (conversationId: string) => {
      if (conversationId === "conv-agent-new") {
        return {
          conversation_id: "conv-agent-new",
          title: "Agent New",
          kind_label: "Direct agent chat",
          target_label: "Agent New",
          discoverability_hint: "This is a one-to-one conversation with an available target.",
          mention_candidates: [],
          messages: []
        };
      }
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

    expect(createGroupConversation).toHaveBeenCalledWith({ participantIds: ["agent-ops-user", "teammate-alex"] });
    expect(await screen.findByRole("heading", { name: "OpsBot + Alex" })).toBeInTheDocument();
    expect(getConversation).toHaveBeenCalledWith("conv-group-new");
    expect(screen.queryByText("Select participants")).not.toBeInTheDocument();
    expect(screen.getByText("Target: Multiple participants")).toBeInTheDocument();
  });

  it("lets users discover an agent and open a fresh direct chat from the workspace", async () => {
    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    expect(await screen.findByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New direct chat" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "New direct chat" }));
    expect(await screen.findByText("Available agents")).toBeInTheDocument();
    expect(screen.getByText("Agent New")).toBeInTheDocument();
    expect(screen.getByText("runtime-created helper")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Chat with Agent New" }));

    expect(createDirectConversation).toHaveBeenCalledWith({ agentId: "agent-new" });
    expect(await screen.findByText("Agent New")).toBeInTheDocument();
    expect(getConversation).toHaveBeenCalledWith("conv-agent-new");
    expect(screen.queryByText("Available agents")).not.toBeInTheDocument();
    expect(screen.getByText("Target: Agent New")).toBeInTheDocument();
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
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("node-demo")).toBeInTheDocument();
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

    expect(await screen.findByText("You")).toBeInTheDocument();
    expect(screen.getByText("I will handle this update.", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    expect(screen.queryByText("user-1")).not.toBeInTheDocument();
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
});

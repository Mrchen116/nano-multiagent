import { createElement } from "react";
import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderRouter } from "../../test/render-router";
import { resolveSendAvailability } from "./im-chat-api";
import { ChatWorkspacePage, toRelayAgentMessage } from "./chat-workspace-page";

const getChatBootstrapState = vi.fn();
const getChatStarter = vi.fn();
const listConversations = vi.fn();
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
  beforeEach(() => {
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
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
      title: "Agent · OpsBot",
      actionLabel: "Open Agent · OpsBot",
      actionHref: "/chat/conv-1",
      agentName: "OpsBot",
      description: "OpsBot is your default starter chat, but you can also open direct agent chats, group chats, and agent-to-agent threads from the conversation list.",
      nodeLabel: "node-1",
      statusLabel: "Using OpsBot on node-1 (online)"
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
    getConversation.mockResolvedValue({
      conversation_id: "conv-1",
      title: "You & Teammate",
      kind_label: "Direct agent chat",
      target_label: "Teammate",
      discoverability_hint: "This is a one-to-one conversation with an available target.",
      messages: []
    });
    getUsageMetrics.mockImplementation(async (input: { ownerId?: string; conversationId?: string }) => {
      if (input.conversationId === "conv-1") {
        return [
          {
            scope: "conversation",
            scope_id: "conv-1",
            owner_id: "user-1",
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
      if (input.ownerId === "user-1") {
        return [
          {
            scope: "owner",
            scope_id: "user-1",
            owner_id: "user-1",
            conversation_id: null,
            agent_id: null,
            turns: 8,
            prompt_tokens: 26,
            completion_tokens: 18,
            total_tokens: 44,
            last_used_at: "2026-03-12T01:00:00Z"
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
      title: "Agent · OpsBot",
      actionLabel: "Open Agent · OpsBot",
      actionHref: "/chat/conv-1",
      agentName: "OpsBot",
      description: "OpsBot handles the default IM replies for this workspace.",
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

  it("shows real conversation and workspace token-turn usage for the active chat", async () => {
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
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
    expect(screen.getByText("3 turns")).toBeInTheDocument();
    expect(screen.getByText("18 tokens")).toBeInTheDocument();
    expect(await screen.findByText("8 turns")).toBeInTheDocument();
    expect(screen.getByText("44 tokens")).toBeInTheDocument();
    expect(getUsageMetrics).toHaveBeenCalledWith({ conversationId: "conv-1" });
    expect(getUsageMetrics).toHaveBeenCalledWith({ ownerId: "user-1" });
  });
});

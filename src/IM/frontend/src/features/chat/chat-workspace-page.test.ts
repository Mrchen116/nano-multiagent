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
const streamConversationEvents = vi.fn((_: unknown) => () => undefined);

vi.mock("../../hooks/use-is-mobile", () => ({
  useIsMobile: () => false
}));

vi.mock("./chat-api", () => ({
  getChatBootstrapState: () => getChatBootstrapState(),
  getChatStarter: () => getChatStarter(),
  listConversations: () => listConversations(),
  getConversation: (conversationId: string) => getConversation(conversationId),
  resolveSendAvailability,
  sendMessage: (input: { conversationId: string; content: string }) => sendMessage(input),
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
      initialConversationId: "conv-1"
    });
    getChatStarter.mockResolvedValue({
      title: "Agent · OpsBot",
      actionLabel: "Open Agent · OpsBot",
      actionHref: "/chat/conv-1",
      agentName: "OpsBot",
      description: "OpsBot handles the default IM replies for this workspace.",
      nodeLabel: "node-1",
      statusLabel: "online"
    });
    listConversations.mockResolvedValue([
      {
        conversation_id: "conv-1",
        title: "You & Teammate",
        last_message_preview: "",
        last_message_at: null,
        unread_count: 0,
        participants: ["You", "Teammate"]
      }
    ]);
    getConversation.mockResolvedValue({
      conversation_id: "conv-1",
      title: "You & Teammate",
      messages: []
    });
    sendMessage.mockResolvedValue({});
    streamConversationEvents.mockReturnValue(() => undefined);
  });

  it("blocks sending when no node is bound yet", async () => {
    renderRouter({
      routes: [{ path: "/chat/:conversationId", element: createElement(ChatWorkspacePage) }],
      initialEntries: ["/chat/conv-1"]
    });

    expect(await screen.findByText("Bind this Gateway before sending messages from Web IM.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByPlaceholderText("Bind this Gateway to enable chat")).toBeDisabled();
  });

  it("shows a product-grade send blocker when the bound node is offline", async () => {
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      targetNodeId: "node-offline",
      initialConversationId: "conv-1"
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

    expect(
      await screen.findByText("The current bound node is offline. Bring the Gateway online or bind an online node, then retry.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByPlaceholderText("Bring the Gateway online to enable chat")).toBeDisabled();
  });
});

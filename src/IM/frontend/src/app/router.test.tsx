import { screen } from "@testing-library/react";
import { isValidElement } from "react";
import { beforeEach, vi } from "vitest";
import { Navigate } from "react-router-dom";

const getChatBootstrapState = vi.fn();
const getChatStarter = vi.fn();
const listConversations = vi.fn();
const getConversation = vi.fn();
const sendMessage = vi.fn();
const streamConversationEvents = vi.fn((_: unknown) => () => undefined);

vi.mock("../features/chat/chat-api", () => ({
  getChatBootstrapState: () => getChatBootstrapState(),
  getChatStarter: () => getChatStarter(),
  listConversations: () => listConversations(),
  getConversation: (conversationId: string) => getConversation(conversationId),
  sendMessage: (input: { conversationId: string; content: string }) => sendMessage(input),
  streamConversationEvents: (input: unknown) => streamConversationEvents(input)
}));

import { appRoutes } from "./router";
import { renderRouter } from "../test/render-router";

describe("app routes", () => {
  beforeEach(() => {
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      targetNodeId: "node-1",
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

  it("renders the chat conversation route", async () => {
    renderRouter({ routes: appRoutes, initialEntries: ["/chat/conv-1"] });

    expect(await screen.findByText("Conversations")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "You & Teammate" })).toBeInTheDocument();
  });

  it("declares the root entry redirect to /chat", () => {
    const rootIndexRoute = appRoutes[0]?.children?.find((route) => route.index);

    expect(rootIndexRoute).toBeDefined();
    expect(isValidElement(rootIndexRoute?.element)).toBe(true);
    expect(rootIndexRoute?.element.type).toBe(Navigate);
    expect(rootIndexRoute?.element.props.to).toBe("/chat");
    expect(rootIndexRoute?.element.props.replace).toBe(true);
  });

  it("renders the bind confirmation route", async () => {
    renderRouter({ routes: appRoutes, initialEntries: ["/bind/confirm?token=test-token"] });

    expect(await screen.findByText("Bind this Gateway")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue to chat" })).toBeEnabled();
  });

  it("renders the settings agents entry", async () => {
    renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });

    expect(await screen.findByRole("heading", { name: "Agents" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Settings Sections" })).toBeInTheDocument();
  });
});

import { screen } from "@testing-library/react";
import { beforeEach, vi } from "vitest";

const getChatBootstrapState = vi.fn();
const getChatStarter = vi.fn();
const listConversations = vi.fn();
const getConversation = vi.fn();
const sendMessage = vi.fn();
const streamConversationEvents = vi.fn((_: unknown) => () => undefined);

vi.mock("./chat-api", () => ({
  getChatBootstrapState: () => getChatBootstrapState(),
  getChatStarter: () => getChatStarter(),
  listConversations: () => listConversations(),
  getConversation: (conversationId: string) => getConversation(conversationId),
  sendMessage: (input: { conversationId: string; content: string }) => sendMessage(input),
  streamConversationEvents: (input: unknown) => streamConversationEvents(input)
}));

import { appRoutes } from "../../app/router";
import { renderRouter } from "../../test/render-router";

describe("chat layout", () => {
  beforeEach(() => {
    getChatBootstrapState.mockResolvedValue({
      selfUserId: "user-1",
      targetNodeId: "node-1",
      initialConversationId: "conv-kernel-ops"
    });
    getChatStarter.mockResolvedValue({
      title: "Agent · OpsBot",
      actionLabel: "Open Agent · OpsBot",
      actionHref: "/chat/conv-kernel-ops",
      agentName: "OpsBot",
      description: "OpsBot handles the default IM replies for this workspace.",
      nodeLabel: "node-app-01",
      statusLabel: "online"
    });
    listConversations.mockResolvedValue([
      {
        conversation_id: "conv-kernel-ops",
        title: "Kernel Ops Crew",
        last_message_preview: "Retry policy was bumped to 30s cooldown.",
        last_message_at: "2026-03-03T22:35:00+08:00",
        unread_count: 3,
        participants: ["You", "OpsBot"]
      }
    ]);
    getConversation.mockResolvedValue({
      conversation_id: "conv-kernel-ops",
      title: "Kernel Ops Crew",
      messages: [
        {
          message_id: "m-1",
          sender_type: "agent",
          sender_name: "OpsBot",
          content: "CI is green after the retry-loop fix.",
          created_at: "2026-03-03T22:31:00+08:00",
          delivery_status: "completed"
        }
      ]
    });
    sendMessage.mockResolvedValue({});
    streamConversationEvents.mockReturnValue(() => undefined);
  });

  it("shows desktop two-panel frame on a conversation route", async () => {
    window.innerWidth = 1280;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat/conv-kernel-ops"] });

    expect(await screen.findByRole("heading", { name: "Conversations" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Kernel Ops Crew" })).toBeInTheDocument();
  });

  it("shows a default agent starter on desktop /chat", async () => {
    window.innerWidth = 1280;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat"] });

    expect(await screen.findByRole("heading", { name: "Conversations" })).toBeInTheDocument();
    expect(screen.getByText("OpsBot handles the default IM replies for this workspace.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Agent · OpsBot" })).toBeInTheDocument();
    expect(screen.queryByText("Select a conversation")).not.toBeInTheDocument();
  });

  it("shows single panel conversation view on mobile", async () => {
    window.innerWidth = 375;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat/conv-kernel-ops"] });

    expect(await screen.findByRole("heading", { name: "Kernel Ops Crew" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Conversations" })).not.toBeInTheDocument();
  });

  it("shows the default agent starter on mobile /chat", async () => {
    window.innerWidth = 375;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat"] });

    expect(await screen.findByRole("heading", { name: "Conversations" })).toBeInTheDocument();
    expect(screen.getByText("OpsBot handles the default IM replies for this workspace.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Agent · OpsBot" })).toBeInTheDocument();
  });

  it("anchors desktop conversation messages to the bottom", async () => {
    window.innerWidth = 1280;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat/conv-kernel-ops"] });

    const stack = await screen.findByTestId("message-list-stack");
    expect(stack).toHaveClass("justify-end");
  });
});

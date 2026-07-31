import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import "../../../i18n";
import type { Conversation, Message } from "../chat-types";
import { MessagePane } from "./message-pane";

const { markdownRenderSpy } = vi.hoisted(() => ({
  markdownRenderSpy: vi.fn(),
}));

vi.mock("react-markdown", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-markdown")>();
  const react = await import("react");

  function InstrumentedReactMarkdown(
    props: Parameters<typeof actual.default>[0]
  ) {
    markdownRenderSpy();
    return react.createElement(actual.default, props);
  }

  return {
    ...actual,
    default: InstrumentedReactMarkdown,
  };
});

const CONVERSATION: Conversation = {
  id: "memo-conversation",
  title: "Planner",
  participants: [{ type: "agent", id: "planner", display_name: "Planner" }],
  participant_ids: ["planner"],
  type: "direct",
  direct_kind: "agent",
  owner_id: "user-1",
  creator_id: "user-1",
  is_pinned: false,
  is_muted: false,
  unread_count: 0,
  last_message_preview: null,
  last_message_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const MARKDOWN_MESSAGE: Message = {
  id: "markdown-message",
  conversation_id: CONVERSATION.id,
  sender: { type: "agent", id: "planner", display_name: "Planner" },
  sender_user_id: "planner",
  sender_type: "agent",
  content: "Historical **Markdown** with `code`.",
  attachments: [],
  delivery_status: "completed",
  created_at: "2026-01-01T00:00:01Z",
  permission_requests: [],
};

beforeEach(() => {
  markdownRenderSpy.mockClear();
});

it("does not rebuild historical Markdown while the user types a draft", async () => {
  const user = userEvent.setup();
  render(
    <MessagePane
      conversation={CONVERSATION}
      messages={[MARKDOWN_MESSAGE]}
      mentionCandidates={[]}
      onSend={() => {}}
    />
  );

  expect(markdownRenderSpy).toHaveBeenCalledTimes(1);
  await user.type(screen.getByRole("textbox"), "new draft");
  expect(markdownRenderSpy).toHaveBeenCalledTimes(1);
});

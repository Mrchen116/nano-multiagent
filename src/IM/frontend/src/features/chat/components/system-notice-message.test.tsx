import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { i18n } from "../../../i18n";
import type { Conversation, Message } from "../chat-types";
import { MessagePane } from "./message-pane";

const conversation: Conversation = {
  id: "group-1",
  title: "SpecLab",
  participants: [
    { type: "user", id: "user-1" },
    { type: "agent", id: "product", display_name: "SpecLab Product" },
  ],
  participant_ids: ["user-1", "product"],
  type: "group",
  direct_kind: null,
  owner_id: "user-1",
  creator_id: "user-1",
  is_pinned: false,
  is_muted: false,
  unread_count: 0,
  last_message_preview: null,
  last_message_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function notice(overrides: Partial<Message> = {}): Message {
  return {
    id: "notice-1",
    conversation_id: conversation.id,
    sender: { type: "system", id: "system" },
    sender_user_id: "system",
    sender_type: "system",
    content: "legacy fallback",
    attachments: [],
    delivery_status: "completed",
    created_at: "2026-01-01T00:00:01Z",
    permission_requests: [],
    system_notice: {
      kind: "self_evolution_review",
      source_agent_id: "product",
      source_agent_display_name: "SpecLab Product",
      updated_targets: ["memory"],
    },
    ...overrides,
  };
}

function renderNotice(message: Message, isDirectChat = false) {
  return render(
    <MessagePane
      conversation={conversation}
      messages={[message]}
      mentionCandidates={[]}
      onSend={() => {}}
      isDirectChat={isDirectChat}
    />,
  );
}

async function changeLanguage(language: "en" | "zh") {
  await act(async () => {
    await i18n.changeLanguage(language);
  });
}

afterEach(async () => {
  await changeLanguage("en");
});

describe("structured system notice", () => {
  it("shows agent attribution only in a group and reacts to language changes", async () => {
    await changeLanguage("zh");
    const view = renderNotice(notice());
    expect(
      screen.getByText("· SpecLab Product · 后台自进化：记忆已更新"),
    ).toBeTruthy();

    await changeLanguage("en");
    expect(
      screen.getByText(
        "· SpecLab Product · Background self-evolution: memory updated",
      ),
    ).toBeTruthy();
    view.unmount();

    await changeLanguage("zh");
    renderNotice(notice(), true);
    expect(screen.getByText("· 后台自进化：记忆已更新")).toBeTruthy();
  });

  it("falls back to stored content for unknown sidecars", async () => {
    await changeLanguage("zh");
    renderNotice(
      notice({
        system_notice: {
          kind: "future_notice",
          source_agent_id: "product",
          source_agent_display_name: "SpecLab Product",
          updated_targets: ["memory"],
        },
      }),
    );
    expect(screen.getByText("legacy fallback")).toBeTruthy();
  });
});

import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { i18n } from "../../../i18n";
import type { Conversation, Message, TimelineItem } from "../chat-types";
import { MessagePane } from "./message-pane";

const conversation: Conversation = {
  id: "dates", title: "Dates", participants: [], participant_ids: [], type: "direct",
  direct_kind: "agent", owner_id: "u1", creator_id: "u1", is_pinned: false,
  is_muted: false, unread_count: 0, last_message_preview: null, last_message_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function message(id: string, date: Date, overrides: Partial<Message> = {}): Message {
  return {
    id, conversation_id: conversation.id,
    sender: { type: "user", id: "u1", display_name: "You" },
    sender_user_id: "u1", sender_type: "user", content: id, attachments: [],
    delivery_status: "completed", permission_requests: [], created_at: date.toISOString(), ...overrides,
  };
}

function pane(messages: Message[], timeline?: TimelineItem[]) {
  return <MessagePane conversation={conversation} messages={messages} timeline={timeline}
    mentionCandidates={[]} onSend={() => {}} />;
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 3, 12));
});
afterEach(() => vi.useRealTimers());

it("groups adjacent messages like iOS, including a local midnight less than five minutes apart", () => {
  render(pane([
    message("yesterday", new Date(2026, 10, 2, 23, 58)),
    message("today", new Date(2026, 10, 3, 0, 0)),
    message("nearby", new Date(2026, 10, 3, 0, 4)),
    message("five-minutes", new Date(2026, 10, 3, 0, 9)),
  ]));
  const markers = screen.getAllByTestId("chat-time-divider");
  expect(markers).toHaveLength(3);
  const oldFormat = new Intl.DateTimeFormat(i18n.language, {
    year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
  });
  expect(markers[0]).toHaveTextContent(oldFormat.format(new Date(2026, 10, 2, 23, 58)));
  expect(markers[1]).toHaveTextContent(/^00:00$/);
  expect(markers[2]).toHaveTextContent(/^00:09$/);
});

it("ignores system notices and configuration boundaries when grouping normal messages", () => {
  const messages = [
    message("first", new Date(2026, 10, 2, 10)),
    message("notice", new Date(2026, 10, 2, 10, 4), {
      sender: { type: "system", id: "system" }, sender_type: "system",
      system_notice: { kind: "self_evolution_review", source_agent_id: "agent", updated_targets: ["memory"] },
    }),
    message("later", new Date(2026, 10, 2, 10, 5)),
  ];
  const timeline: TimelineItem[] = [
    { type: "message", message: messages[0] }, { type: "message", message: messages[1] },
    { type: "agent_config_changed", id: "boundary", conversation_id: "dates", agent_id: "agent", before_message_id: "later", applied_at: messages[2].created_at },
    { type: "message", message: messages[2] },
  ];
  render(pane(messages, timeline));
  const markers = screen.getAllByTestId("chat-time-divider");
  expect(markers).toHaveLength(2);
  expect(markers[1]).toHaveTextContent("10:05");
  expect(screen.getByTestId("message-timestamp-later")).toHaveTextContent("10:05");
});

it("recomputes the first marker after older history is prepended and new messages arrive", () => {
  const current = message("current", new Date(2026, 10, 3, 10, 1));
  const { rerender } = render(pane([current]));
  expect(screen.getAllByTestId("chat-time-divider")).toHaveLength(1);
  const older = message("older", new Date(2026, 10, 3, 10));
  rerender(pane([older, current]));
  expect(screen.getAllByTestId("chat-time-divider")).toHaveLength(1);
  expect(screen.getByTestId("chat-time-divider")).toHaveAttribute("dateTime", older.created_at);
  rerender(pane([older, current, message("live", new Date(2026, 10, 3, 10, 6))]));
  expect(screen.getAllByTestId("chat-time-divider")).toHaveLength(2);
});

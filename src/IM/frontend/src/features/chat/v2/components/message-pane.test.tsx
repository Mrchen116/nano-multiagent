import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import type { Conversation, MentionCandidate, Message } from "../chat-types";
import { MessagePane } from "./message-pane";

const DIRECT_CONV: Conversation = {
  id: "c1",
  title: "Planner",
  participants: [{ type: "agent", id: "a-planner", display_name: "Planner" }],
  participant_ids: ["a-planner"],
  type: "direct",
  direct_kind: "agent",
  owner_id: "u1",
  creator_id: "u1",
  is_pinned: false,
  is_muted: false,
  unread_count: 0,
  last_message_preview: null,
  last_message_at: null,
  created_at: "2026-01-01T00:00:00Z"
};

const GROUP_CONV: Conversation = {
  ...DIRECT_CONV,
  id: "c2",
  title: "Sprint Crew",
  type: "group",
  direct_kind: null,
  participants: [
    { type: "user", id: "u1", display_name: "You" },
    { type: "agent", id: "a-planner", display_name: "Planner" },
    { type: "agent", id: "a-coder", display_name: "Coder" }
  ],
  participant_ids: ["u1", "a-planner", "a-coder"]
};

const SAMPLE_MESSAGES: Message[] = [
  {
    id: "m1",
    conversation_id: "c1",
    sender: { type: "user", id: "u1", display_name: "You" },
    sender_user_id: "u1",
    sender_type: "user",
    content: "Hello",
    attachments: [],
    delivery_status: "completed",
    created_at: "2026-01-01T00:00:00Z"
  },
  {
    id: "m2",
    conversation_id: "c1",
    sender: { type: "agent", id: "a-planner", display_name: "Planner" },
    sender_user_id: "u1",
    sender_type: "agent",
    content: "Hi back",
    attachments: [],
    delivery_status: "completed",
    created_at: "2026-01-01T00:00:01Z"
  }
];

const MENTION_CANDIDATES: MentionCandidate[] = [
  { agent_id: "a-planner", display_name: "Planner", initials: "PL", status: "online" },
  { agent_id: "a-coder", display_name: "Coder", initials: "CO", status: "online" }
];

describe("MessagePane", () => {
  it("renders the conversation title and each message content", () => {
    render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={SAMPLE_MESSAGES}
        mentionCandidates={[]}
        onSend={() => {}}
      />
    );
    expect(screen.getByRole("heading", { name: "Planner" })).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Hi back")).toBeInTheDocument();
  });

  it("renders an empty-state hint when there are no messages", () => {
    render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={[]}
        mentionCandidates={[]}
        onSend={() => {}}
      />
    );
    expect(screen.getByText(/No messages yet/i)).toBeInTheDocument();
  });

  it("submits typed draft and calls onSend with trimmed text", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={SAMPLE_MESSAGES}
        mentionCandidates={[]}
        onSend={onSend}
      />
    );
    const composer = screen.getByRole("textbox");
    await user.type(composer, "  hello world  ");
    await user.click(screen.getByRole("button", { name: /Send/i }));
    expect(onSend).toHaveBeenCalledWith("hello world");
  });

  it("shows mention picker after typing '@' inside a group conversation", async () => {
    const user = userEvent.setup();
    render(
      <MessagePane
        conversation={GROUP_CONV}
        messages={[]}
        mentionCandidates={MENTION_CANDIDATES}
        onSend={() => {}}
      />
    );
    await user.type(screen.getByRole("textbox"), "hey @P");
    expect(await screen.findByRole("button", { name: /Planner/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Coder/ })).not.toBeInTheDocument();
  });

  it("does not show mention picker in direct-agent conversations", async () => {
    const user = userEvent.setup();
    render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={[]}
        mentionCandidates={MENTION_CANDIDATES}
        onSend={() => {}}
      />
    );
    await user.type(screen.getByRole("textbox"), "@");
    // mention picker container is the listbox/role-button list; ensure no candidate
    // buttons render
    expect(screen.queryByRole("button", { name: /Planner/i })).not.toBeInTheDocument();
  });

  it("inserts @AgentName when a mention candidate is clicked", async () => {
    const user = userEvent.setup();
    render(
      <MessagePane
        conversation={GROUP_CONV}
        messages={[]}
        mentionCandidates={MENTION_CANDIDATES}
        onSend={() => {}}
      />
    );
    const composer = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.type(composer, "ping @P");
    await user.click(await screen.findByRole("button", { name: /Planner/ }));
    expect(composer.value).toBe("ping @Planner ");
  });
});

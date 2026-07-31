/**
 * feat-445-M1 R5 + feat-484-M1: Branch (fork) button visibility gates on the canonical MessageBubble.
 *
 * The Branch button is rendered into the DOM only when the message is a *completed
 * agent reply in a direct chat that carries a kernel_message_id*; CSS :hover (not
 * exercised in jsdom) only controls the desktop toolbar visual reveal. So
 * presence-in-DOM == the React gate, which is exactly what we assert here.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../../../i18n";
import type { Conversation, Message } from "../chat-types";
import { MessagePane } from "./message-pane";

function conv(): Conversation {
  return {
    id: "c1",
    title: "Assistant",
    participants: [
      { type: "user", id: "user-1" },
      { type: "agent", id: "agent-a", display_name: "Assistant", user_id: "agent-uid" },
    ],
    participant_ids: ["user-1", "agent-uid"],
    type: "direct",
    direct_kind: "user-agent",
    owner_id: "user-1",
    creator_id: "user-1",
    is_pinned: false,
    is_muted: false,
    unread_count: 0,
    last_message_preview: null,
    last_message_at: null,
    created_at: "2026-01-01T00:00:00Z",
  };
}

function msg(over: Partial<Message>): Message {
  return {
    id: "m",
    conversation_id: "c1",
    sender: { type: "agent", id: "agent-a", display_name: "Assistant" },
    sender_user_id: "agent-uid",
    sender_type: "agent",
    content: "hello",
    attachments: [],
    delivery_status: "completed",
    created_at: "2026-01-01T00:00:00Z",
    permission_requests: [],
    ...over,
  };
}

function renderPane(messages: Message[], opts: { isDirectChat?: boolean; agentOnline?: boolean; onFork?: (id: string) => void; forkPending?: boolean } = {}) {
  return render(
    <MessagePane
      conversation={conv()}
      messages={messages}
      mentionCandidates={[]}
      onSend={() => {}}
      isDirectChat={opts.isDirectChat ?? true}
      agentOnline={opts.agentOnline ?? true}
      onFork={opts.onFork}
      forkPending={opts.forkPending ?? false}
    />
  );
}

afterEach(() => vi.restoreAllMocks());

describe("MessageBubble fork button gating", () => {
  it("shows Branch on a completed agent reply with kernel_message_id (online direct chat)", () => {
    const onFork = vi.fn();
    renderPane(
      [msg({ id: "a1", kernel_message_id: "kmsg-a1" })],
      { onFork },
    );
    const btn = screen.getByTestId("message-branch-a1");
    expect(btn).toBeTruthy();
    expect(btn.getAttribute("aria-disabled")).not.toBe("true");
    fireEvent.click(btn);
    expect(onFork).toHaveBeenCalledWith("a1");
  });

  it("no Branch button on the user's own message", () => {
    renderPane([
      msg({
        id: "u1",
        sender: { type: "user", id: "user-1" },
        sender_type: "user",
        kernel_message_id: null,
      }),
    ]);
    expect(screen.queryByTestId("message-branch-u1")).toBeNull();
  });

  it("no Branch button on a still-running agent reply", () => {
    renderPane([msg({ id: "r1", delivery_status: "running", kernel_message_id: null })]);
    expect(screen.queryByTestId("message-branch-r1")).toBeNull();
  });

  it("no Branch button on a completed agent reply lacking kernel_message_id (legacy bubble)", () => {
    renderPane([msg({ id: "old1", kernel_message_id: null })]);
    expect(screen.queryByTestId("message-branch-old1")).toBeNull();
  });

  it("no Branch button in a group chat (not a direct agent chat)", () => {
    renderPane([msg({ id: "g1", kernel_message_id: "kmsg-g1" })], { isDirectChat: false });
    expect(screen.queryByTestId("message-branch-g1")).toBeNull();
  });

  it("offline agent renders an aria-disabled Branch button (does not fire onFork)", () => {
    const onFork = vi.fn();
    renderPane([msg({ id: "off1", kernel_message_id: "kmsg-off1" })], { agentOnline: false, onFork });
    const btn = screen.getByTestId("message-branch-off1");
    expect(btn.getAttribute("aria-disabled")).toBe("true");
    fireEvent.click(btn);
    expect(onFork).not.toHaveBeenCalled();
  });

  // feat-445-M2 #7: while a fork is in flight the button is disabled, so a double-click
  // cannot fire a second POST (which produced two orphan branch chats).
  it("disables Branch while a fork is in flight (no double submit)", () => {
    const onFork = vi.fn();
    renderPane([msg({ id: "p1", kernel_message_id: "kmsg-p1" })], { forkPending: true, onFork });
    const btn = screen.getByTestId("message-branch-p1");
    expect(btn.getAttribute("aria-disabled")).toBe("true");
    fireEvent.click(btn);
    expect(onFork).not.toHaveBeenCalled();
  });
});

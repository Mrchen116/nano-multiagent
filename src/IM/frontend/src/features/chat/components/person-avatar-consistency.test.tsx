import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../../i18n";
import type { Actor, Conversation, Message } from "../chat-types";
import { ConversationSidebar } from "./conversation-sidebar";
import { MentionPicker } from "./mention-picker";
import { MessagePane } from "./message-pane";

const PEOPLE: Actor[] = [
  { type: "user", id: "chen", display_name: "小陈" },
  { type: "user", id: "li", display_name: "小李" },
];

function background(element: Element): string {
  return getComputedStyle(element).backgroundColor;
}

describe("person avatar consistency", () => {
  it.each([PEOPLE, [...PEOPLE].reverse()])(
    "keeps the peer's avatar consistent across a renamed DM, group messages and mentions for viewer %j",
    (self, peer) => {
      const conversation: Conversation = {
        id: "dm", title: peer.display_name!, type: "direct", direct_kind: "user-user",
        participants: PEOPLE, participant_ids: PEOPLE.map(person => person.id),
        owner_id: "chen", creator_id: "chen", is_pinned: false, is_muted: false,
        unread_count: 0, last_message_preview: null, last_message_at: null,
        created_at: "2026-09-14T00:00:00Z",
      };
      const message: Message = {
        id: "reply", conversation_id: "dm", sender: peer,
        sender_user_id: peer.id, sender_type: "user", content: "准备好了",
        attachments: [], permission_requests: [], delivery_status: "completed", created_at: conversation.created_at,
      };
      const view = (group = false) => <>
        <ConversationSidebar conversations={[conversation]} selfUserId={self.id}
          activeConversationId="dm" onSelect={() => {}} onNewGroup={() => {}} />
        <MessagePane conversation={group ? { ...conversation, type: "group", direct_kind: null } : conversation}
          messages={[message]} selfUserId={self.id} mentionCandidates={[]} onSend={() => {}} />
        <MentionPicker candidates={[{ user_id: peer.id, display_name: peer.display_name!,
          initials: peer.display_name!, status: "offline" }]} query="" onSelect={() => {}} onClose={() => {}} />
      </>;
      const { container, rerender } = render(view());
      const mentionFace = container.querySelector(".chat-mention-picker .chat-avatar-face")!;
      const sidebarFace = screen.getByTestId("conv-avatar-dm").querySelector(".chat-avatar-face")!;
      const headerFace = container.querySelector(".chat-pane-header .chat-avatar-face")!;
      const messageFace = screen.getByTestId("message-avatar-reply");

      for (const face of [sidebarFace, headerFace, messageFace]) {
        expect(face).toHaveTextContent(peer.display_name!);
        expect(background(face)).toBe(background(mentionFace));
        expect(getComputedStyle(face).color).toBe(getComputedStyle(mentionFace).color);
      }
      expect(getComputedStyle(container.querySelector(".chat-bubble-sender")!).color)
        .toBe(getComputedStyle(mentionFace).color);

      const directColor = background(messageFace);
      conversation.title = "周五的安排";
      rerender(view());
      for (const face of [sidebarFace, headerFace]) {
        expect(face).toHaveTextContent(peer.display_name!);
        expect(background(face)).toBe(directColor);
      }
      rerender(view(true));
      expect(background(screen.getByTestId("message-avatar-reply"))).toBe(directColor);
      expect(container.querySelector(".chat-pane-header .chat-avatar-face")).toBeNull();
    },
  );
});

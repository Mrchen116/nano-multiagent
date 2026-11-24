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
      const messageFace = screen.getByTestId("message-avatar-reply").querySelector(".chat-avatar-face")!;

      for (const face of [sidebarFace, headerFace, messageFace]) {
        expect(face).toHaveTextContent(peer.display_name!);
        expect(background(face)).toBe(background(mentionFace));
        expect(getComputedStyle(face).color).toBe(getComputedStyle(mentionFace).color);
      }
      expect(container.querySelector(".chat-bubble-sender")).toBeNull();

      const directColor = background(messageFace);
      conversation.title = "周五的安排";
      rerender(view());
      for (const face of [sidebarFace, headerFace]) {
        expect(face).toHaveTextContent(peer.display_name!);
        expect(background(face)).toBe(directColor);
      }
      rerender(view(true));
      expect(container.querySelector(".chat-bubble-sender")).toHaveTextContent(peer.display_name!);
      expect(background(screen.getByTestId("message-avatar-reply").querySelector(".chat-avatar-face")!)).toBe(directColor);
      expect(container.querySelector(".chat-pane-header .chat-avatar-face")).toBeNull();
    },
  );
});

it('distinguishes two same-name personal assistants in a group and keeps the chosen face in private chat', () => {
  const assistants: Actor[] = [
    {type:'agent',id:'pa-one',display_name:'Milo',role:'personal',avatar_variant:0},
    {type:'agent',id:'pa-two',display_name:'Milo',role:'personal',avatar_variant:7},
  ];
  const conversation: Conversation = {
    id:'avatars',title:'Team',type:'group',direct_kind:null,participants:assistants,participant_ids:assistants.map(a=>a.id),
    owner_id:'u1',creator_id:'u1',is_pinned:false,is_muted:false,unread_count:0,last_message_preview:null,last_message_at:null,created_at:'2026-11-17T00:00:00Z',
  };
  const messages: Message[] = assistants.map((sender,i)=>({
    id:`avatar-${i}`,conversation_id:conversation.id,sender,sender_user_id:sender.id,sender_type:'agent',
    content:'Hello',attachments:[],permission_requests:[],delivery_status:'completed',created_at:conversation.created_at,
  }));
  const {container,rerender} = render(<MessagePane conversation={conversation} messages={messages} mentionCandidates={[]} onSend={()=>{}} />);
  expect(screen.getByTestId('message-avatar-avatar-0').querySelector('svg')).toHaveAttribute('data-avatar','personal-0');
  expect(screen.getByTestId('message-avatar-avatar-1').querySelector('svg')).toHaveAttribute('data-avatar','personal-7');
  rerender(<MessagePane conversation={{...conversation,type:'direct',direct_kind:'agent',title:'A new name',participants:[assistants[1]]}}
    personalAgent messages={[messages[1]]} mentionCandidates={[]} onSend={()=>{}} />);
  expect(container.querySelector('.chat-pane-header [data-avatar]')).toHaveAttribute('data-avatar','personal-7');
  expect(screen.getByTestId('message-avatar-avatar-1').querySelector('svg')).toHaveAttribute('data-avatar','personal-7');
});

import avatarCases from "../../../../../shared/avatar-test-cases.json";
import { avatarVariantFor } from "./avatar-picker";
import { clearAvatarBlobStore } from "./avatar-blob-store";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, expectTypeOf, it, vi } from "vitest";

import "../../../i18n";
import type { Actor, Conversation, Message } from "../chat-types";
import { Avatar, AvatarIdentities, colorForAgentSeed } from "./avatar";
import { ConversationSidebar } from "./conversation-sidebar";
import { MentionPicker } from "./mention-picker";
import { MessagePane } from "./message-pane";

it("matches the native avatar contract for stable IDs and palette seeds", () => {
  for (const [id, variant] of Object.entries(avatarCases.agentSeeds)) expect(avatarVariantFor(id)).toBe(variant);
  for (const [seed, color] of Object.entries(avatarCases.colors)) expect(colorForAgentSeed(seed)).toBe(color);
});

it("uses the same eight portrait silhouettes as the native image catalogue", () => {
  const nativeArt = import.meta.glob("../../../../../ios/NanoIM/Assets.xcassets/portrait-*.imageset/*.svg", {
    eager: true, query: "?raw", import: "default",
  }) as Record<string, string>;
  for (const personal of [true, false]) {
    for (const style of [0, 1, 2, 3]) {
      const actor: Actor = {id:"agent", type:"agent", role:personal ? "personal" : undefined, avatar_variant:style * 6};
      const {container, unmount} = render(<AvatarIdentities actors={[actor]}><Avatar id="agent:agent" /></AvatarIdentities>);
      const name = `portrait-${personal ? "personal" : "agent"}-${style}`;
      const svg = nativeArt[`../../../../../ios/NanoIM/Assets.xcassets/${name}.imageset/${name}.svg`];
      const shape = new DOMParser().parseFromString(svg, "image/svg+xml").querySelector("path");
      expect(container.querySelector("svg > path")).toHaveAttribute("d", shape!.getAttribute("d"));
      unmount();
    }
  }
});

it("requires portrait identity when adding an avatar surface", () => {
  type Props = Parameters<typeof Avatar>[0];
  expectTypeOf<keyof Props>().toEqualTypeOf<"id" | "size" | "status">();
  expectTypeOf<Props>().toMatchTypeOf<{id:string}>();
});

it("keeps the portrait renderer private to identity avatars and the creation picker", () => {
  const files = import.meta.glob("/src/**/*.{ts,tsx}", {eager: true, query: "?raw", import: "default"}) as Record<string, string>;
  const imports = Object.entries(files).filter(([path, source]) =>
    !path.includes(".test.") && /["'][^"']*\/assistant-portrait(?:\.tsx)?["']/.test(source));
  expect(imports.map(([path]) => path).sort()).toEqual([
    "/src/features/chat/components/avatar-picker.tsx",
    "/src/features/chat/components/avatar.tsx",
  ]);
});

it("updates all sizes and both ID forms together when the contact profile arrives", () => {
  const actor: Actor = {type:"agent", id:"milo", user_id:"uuid-milo", role:"personal", avatar_variant:3};
  const view = (contacts: Actor[]) => <AvatarIdentities source="contacts" actors={contacts}>
    <Avatar id="uuid-milo" size={24} />
    <AvatarIdentities actors={[actor]}><Avatar id="agent:milo" size={48} /></AvatarIdentities>
  </AvatarIdentities>;
  const {container, rerender} = render(view([]));
  const faces = () => Array.from(container.querySelectorAll("svg"), face =>
    [face.getAttribute("width"), face.getAttribute("data-avatar")]);
  expect(faces()).toEqual([["24","personal-3"], ["48","personal-3"]]);
  rerender(view([{...actor, avatar_variant:7}]));
  expect(faces()).toEqual([["24","personal-7"], ["48","personal-7"]]);
});

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
      const view = (group = false) => <AvatarIdentities actors={PEOPLE}>
        <ConversationSidebar conversations={[conversation]} selfUserId={self.id}
          activeConversationId="dm" onSelect={() => {}} onNewGroup={() => {}} />
        <MessagePane conversation={group ? { ...conversation, type: "group", direct_kind: null } : conversation}
          messages={[message]} selfUserId={self.id} mentionCandidates={[]} onSend={() => {}} />
        <MentionPicker candidates={[{ user_id: peer.id, display_name: peer.display_name!,
          initials: peer.display_name!, status: "offline" }]} query="" onSelect={() => {}} onClose={() => {}} />
      </AvatarIdentities>;
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

it("keeps two mirrored senders distinct from the IM owner who received both messages", () => {
  const owner = PEOPLE[0];
  const conversation: Conversation = {
    id:"mirror", title:"Feishu", type:"group", direct_kind:null, participants:[owner], participant_ids:[owner.id],
    owner_id:owner.id, creator_id:owner.id, is_pinned:false, is_muted:false, unread_count:0,
    last_message_preview:null, last_message_at:null, created_at:"2026-11-17T00:00:00Z",
  };
  const messages: Message[] = ["Lin", "Alex"].map(name => ({
    id:name, conversation_id:conversation.id, sender_user_id:owner.id, sender_type:"user",
    sender:{...owner, display_name:name, avatar_id:`external:${name}`}, content:"hello", attachments:[],
    permission_requests:[], delivery_status:"completed", created_at:conversation.created_at,
  }));
  render(<AvatarIdentities actors={[owner]} source="contacts"><MessagePane conversation={conversation}
    messages={messages} mentionCandidates={[]} onSend={()=>{}} /></AvatarIdentities>);
  expect(screen.getByTestId("message-avatar-Lin")).toHaveTextContent("LI");
  expect(screen.getByTestId("message-avatar-Alex")).toHaveTextContent("AL");
});

it('distinguishes two same-name personal assistants in a group and keeps the chosen face in private chat', () => {
  const assistants: Actor[] = [
    {type:'agent',id:'pa-one',user_id:'uuid-one',display_name:'Milo',role:'personal',avatar_variant:0},
    {type:'agent',id:'pa-two',user_id:'uuid-two',display_name:'Milo',role:'personal',avatar_variant:7},
  ];
  const conversation: Conversation = {
    id:'avatars',title:'Team',type:'group',direct_kind:null,participants:assistants,participant_ids:assistants.map(a=>a.id),
    owner_id:'u1',creator_id:'u1',is_pinned:false,is_muted:false,unread_count:0,last_message_preview:null,last_message_at:null,created_at:'2026-11-17T00:00:00Z',
  };
  const messages: Message[] = assistants.map((sender,i)=>({
    id:`avatar-${i}`,conversation_id:conversation.id,sender,sender_user_id:sender.user_id!,sender_type:'agent',
    content:'Hello',attachments:[],permission_requests:[],delivery_status:'completed',created_at:conversation.created_at,
  }));
  messages.push({
    ...messages[0], id:'outgoing', sender:PEOPLE[0], sender_user_id:PEOPLE[0].id, sender_type:'user',
    receipts:assistants.map(actor => ({recipient_id:actor.user_id!, recipient:actor, display_name:'Milo', status:'read'})),
  });
  const {container,rerender} = render(<MessagePane conversation={conversation} selfUserId={PEOPLE[0].id} messages={messages} mentionCandidates={[]} onSend={()=>{}} />);
  expect(screen.getByTestId('message-avatar-avatar-0').querySelector('svg')).toHaveAttribute('data-avatar','personal-0');
  expect(screen.getByTestId('message-avatar-avatar-1').querySelector('svg')).toHaveAttribute('data-avatar','personal-7');
  fireEvent.click(screen.getByRole('button', {name:/Milo.*Milo/}));
  const receiptFaces = Array.from(screen.getByRole('dialog').querySelectorAll('[data-avatar]'),
    face => face.getAttribute('data-avatar'));
  expect(receiptFaces).toEqual(['personal-0', 'personal-7']);
  // Reopen history after both recipients leave, with only the outgoing message loaded.
  rerender(<MessagePane conversation={{...conversation, participants:[PEOPLE[0]]}} messages={[messages[2]]}
    selfUserId={PEOPLE[0].id} mentionCandidates={[]} onSend={()=>{}} />);
  expect(Array.from(screen.getByRole('dialog').querySelectorAll('[data-avatar]'), face => face.getAttribute('data-avatar')))
    .toEqual(['personal-0', 'personal-7']);
  rerender(<MessagePane conversation={{...conversation,type:'direct',direct_kind:'agent',title:'A new name',participants:[assistants[1]]}}
    messages={[messages[1]]} mentionCandidates={[]} onSend={()=>{}} />);
  expect(container.querySelector('.chat-pane-header [data-avatar]')).toHaveAttribute('data-avatar','personal-7');
  expect(screen.getByTestId('message-avatar-avatar-1').querySelector('svg')).toHaveAttribute('data-avatar','personal-7');
});

it("renders custom human photos single-flight, merges IdentityDirectory priority cleanly, excludes external shadows and quote blocks, and revokes on clear", async () => {
  const origFetch = globalThis.fetch;
  const origCreate = URL.createObjectURL;
  const origRevoke = URL.revokeObjectURL;
  const revoked: string[] = [];
  let avatarFetches = 0;

  globalThis.fetch = vi.fn(async (input) => {
    const url = String(input);
    if (url.includes("/im/v1/users/u-photo/avatar")) {
      avatarFetches += 1;
      return new Response(new Uint8Array([82, 73, 70, 70]), {
        status: 200,
        headers: { "Content-Type": "image/webp" },
      });
    }
    return new Response(null, { status: 404 });
  }) as typeof fetch;
  URL.createObjectURL = vi.fn(() => "blob:human-photo-v1");
  URL.revokeObjectURL = vi.fn((u: string) => {
    revoked.push(u);
  });

  try {
    clearAvatarBlobStore();
    const historyStub: Actor = { type: "user", id: "u-photo", display_name: "林夏" }; // avatar_version === undefined
    const nameWithPhoto: Actor = { type: "user", id: "u-photo", display_name: "林夏", avatar_version: "ver111222333" };

    const conversation: Conversation = {
      id: "grp-1",
      title: "研发群",
      type: "group",
      direct_kind: null,
      participants: [historyStub],
      participant_ids: ["u-photo"],
      owner_id: "u-photo",
      creator_id: "u-photo",
      is_pinned: false,
      is_muted: false,
      unread_count: 0,
      last_message_preview: null,
      last_message_at: null,
      created_at: "2026-11-27T00:00:00Z",
    };
    const quotedReply: Message = {
      id: "m-quote",
      conversation_id: "grp-1",
      sender: nameWithPhoto,
      sender_user_id: "u-photo",
      sender_type: "user",
      content: "收到",
      reply_to: {
        message_id: "m-root",
        sender: { type: "user", id: "u-photo", display_name: "林夏" },
        content: "上一条消息",
        attachments: [],
      },
      attachments: [],
      permission_requests: [],
      delivery_status: "completed",
      created_at: conversation.created_at,
    };
    const externalShadowMsg: Message = {
      id: "m-ext",
      conversation_id: "grp-1",
      sender: { type: "user", id: "u-photo", display_name: "外部访客", avatar_id: "external:feishu:visitor", avatar_version: "ver111222333" },
      sender_user_id: "u-photo",
      sender_type: "user",
      content: "外部消息",
      attachments: [],
      permission_requests: [],
      delivery_status: "completed",
      created_at: conversation.created_at,
    };

    const { container, rerender } = render(
      <MemoryRouter>
        <AvatarIdentities source="members" actors={[historyStub]}>
          <AvatarIdentities source="names" actors={[nameWithPhoto]}>
            <Avatar id="u-photo" size={36} />
            <MessagePane
              conversation={conversation}
              messages={[quotedReply, externalShadowMsg]}
              selfUserId="u-other"
              mentionCandidates={[]}
              onSend={() => {}}
            />
          </AvatarIdentities>
        </AvatarIdentities>
      </MemoryRouter>,
    );

    await waitFor(() => {
      const imgs = container.querySelectorAll(".chat-avatar-face img");
      expect(imgs.length).toBeGreaterThanOrEqual(2);
    });
    // Single-flight: multiple <Avatar id="u-photo" /> instances only fetch once!
    expect(avatarFetches).toBe(1);
    // Quote block (.chat-message-quote) must NEVER contain an avatar or img!
    const quoteEl = container.querySelector(".chat-message-quote")!;
    expect(quoteEl.querySelector("img")).toBeNull();
    expect(quoteEl.querySelector(".chat-avatar")).toBeNull();
    // External shadow sender must stay on initials fallback, never owner's photo.
    expect(screen.getByTestId("message-avatar-m-ext").querySelector("img")).toBeNull();

    // Explicit avatar_version: null on higher-priority contacts overrides lower-priority string -> reverts to initials.
    rerender(
      <AvatarIdentities source="contacts" actors={[{ type: "user", id: "u-photo", display_name: "林夏", avatar_version: null }]}>
        <AvatarIdentities source="names" actors={[nameWithPhoto]}>
          <Avatar id="u-photo" size={36} />
        </AvatarIdentities>
      </AvatarIdentities>,
    );
    expect(container.querySelector(".chat-avatar-face img")).toBeNull();
    expect(container.querySelector(".chat-avatar-face")).toHaveTextContent("林夏");

    clearAvatarBlobStore();
    expect(revoked).toContain("blob:human-photo-v1");
  } finally {
    globalThis.fetch = origFetch;
    URL.createObjectURL = origCreate;
    URL.revokeObjectURL = origRevoke;
  }
});

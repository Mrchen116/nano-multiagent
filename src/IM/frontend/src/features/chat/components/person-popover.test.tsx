import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { setLanguage } from "../../../i18n";
import type { Conversation, Message } from "../chat-types";
import type { Contact } from "../contacts-api";
import { MessagePane } from "./message-pane";

const GROUP_CONV: Conversation = {
  id: "grp-1",
  title: "Product Daily",
  type: "group",
  direct_kind: null,
  owner_id: "u-self",
  creator_id: "u-self",
  is_pinned: false,
  is_muted: false,
  unread_count: 0,
  last_message_preview: null,
  last_message_at: null,
  created_at: "2026-01-01T00:00:00Z",
  run_state: "idle",
  source_agent_id: null,
  source_node_id: null,
  can_write: true,
  participants: [
    { type: "user", id: "u-self", user_id: "u-self", display_name: "Alex" },
    { type: "user", id: "u-lin", user_id: "u-lin", display_name: "Lin Xia" },
    { type: "agent", id: "planner", user_id: "ag-planner", display_name: "Planner" }
  ],
  participant_ids: ["u-self", "u-lin", "ag-planner"]
};

const CONTACTS: Contact[] = [
  { user_id: "u-self", kind: "human", display_name: "Alex", username: "alex" },
  { user_id: "u-lin", kind: "human", display_name: "Lin Xia", username: "linxia" },
  {
    user_id: "pa-lin",
    kind: "agent",
    role: "personal",
    agent_id: "lin-pa",
    owner_id: "o-lin",
    owner_user_id: "u-lin",
    display_name: "Lin PA",
    status: "online"
  },
  {
    user_id: "ag-qa",
    kind: "agent",
    agent_id: "qa-bot",
    owner_id: "o-lin",
    owner_user_id: "u-lin",
    display_name: "QA Bot",
    status: "online"
  }
];

function msg(over: Partial<Message>): Message {
  return {
    id: "m-1",
    conversation_id: "grp-1",
    sender_type: "user",
    sender_user_id: "u-lin",
    sender: { type: "user", id: "u-lin", user_id: "u-lin", display_name: "Lin Xia" },
    content: "Hello team!",
    attachments: [],
    permission_requests: [],
    delivery_status: "completed",
    created_at: "2026-01-01T10:00:00Z",
    ...over
  };
}

describe("PersonPopover in MessagePane", () => {
  beforeEach(async () => {
    await act(async () => setLanguage("en"));
  });

  it("opens colleague card from group avatar and @mention chips (excluding quote previews), messages or appends @mention", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    const onStartDirectChat = vi.fn().mockResolvedValue(undefined);
    const messages: Message[] = [
      msg({ id: "m-human", content: 'Hi <mention type="user" target_id="u-lin"/>!' }),
      msg({
        id: "m-agent",
        sender_type: "agent",
        sender_user_id: "ag-planner",
        sender: { type: "agent", id: "planner", user_id: "ag-planner", display_name: "Planner" },
        content: 'Synced with <mention type="user" target_id="u-lin"/> on **scope**.',
        reply_to: {
          message_id: "m-human",
          sender: { type: "user", id: "u-lin", display_name: "Lin Xia" },
          content: 'Quote <mention type="user" target_id="u-lin"/> inside link',
          attachments: []
        }
      })
    ];

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <MessagePane
            conversation={GROUP_CONV}
            messages={messages}
            selfUserId="u-self"
            contacts={CONTACTS}
            onStartDirectChat={onStartDirectChat}
            mentionCandidates={[
              { user_id: "u-lin", display_name: "Lin Xia", initials: "LX", status: "online" }
            ]}
            onSend={onSend}
          />
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Quote preview inside <Link className="chat-message-quote"> must NOT nest a <button>.
    const quoteLink = container.querySelector(".chat-message-quote")!;
    expect(quoteLink.querySelector("button")).toBeNull();

    // Clicking the colleague's message avatar opens PersonPopover.
    await user.click(screen.getByRole("button", { name: "View Lin Xia’s card" }));
    const dialog = await screen.findByRole("dialog", { name: "Lin Xia" });
    expect(within(dialog).getByText("@linxia")).toBeVisible();
    expect(within(dialog).getByRole("button", { name: /Lin PA/ })).toBeVisible();
    expect(within(dialog).getByRole("link", { name: /QA Bot/ })).toHaveAttribute("href", "/settings/agents/qa-bot");

    // Pre-type a draft, reopen via Markdown @mention chip, and click "@ Mention" to verify non-destructive append + wire tag!
    await user.keyboard("{Escape}");
    const composer = screen.getByPlaceholderText(/Message Product Daily/);
    await user.type(composer, "Quick check:");

    const agentBubble = screen.getByTestId("message-bubble-m-agent");
    await user.click(within(agentBubble).getByRole("button", { name: "@Lin Xia" }));
    const dialogFromMention = await screen.findByRole("dialog", { name: "Lin Xia" });
    await user.click(within(dialogFromMention).getByRole("button", { name: "@ Mention" }));

    expect(composer).toHaveValue("Quick check: @Lin Xia ");
    await user.type(composer, "ready?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(onSend).toHaveBeenCalledWith(
        'Quick check: <mention type="user" target_id="u-lin"/> ready?',
        [],
        undefined,
        expect.any(String)
      )
    );
  });

  it("never renders a colleague card trigger for external unmapped surrogate senders", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <MessagePane
            conversation={GROUP_CONV}
            messages={[
              msg({
                id: "m-ext-surrogate",
                // Surrogate sender_user_id matches real colleague u-lin, distinguished by external: avatar_id!
                sender_user_id: "u-lin",
                sender: {
                  type: "user",
                  id: "u-lin",
                  user_id: "u-lin",
                  display_name: "External Visitor",
                  avatar_id: "external:feishu:ou_abc"
                },
                content: "From Feishu"
              })
            ]}
            selfUserId="u-self"
            contacts={CONTACTS}
            onStartDirectChat={vi.fn()}
            mentionCandidates={[]}
            onSend={vi.fn()}
          />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.queryByRole("button", { name: /View .* card/i })).toBeNull();
  });
});

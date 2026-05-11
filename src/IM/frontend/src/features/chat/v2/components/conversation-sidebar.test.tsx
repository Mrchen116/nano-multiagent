import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import type { Conversation } from "../chat-types";
import { ConversationSidebar } from "./conversation-sidebar";

function conv(over: Partial<Conversation>): Conversation {
  return {
    id: "c?",
    title: "?",
    participants: [],
    participant_ids: [],
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
    ...over
  };
}

const CONVS: Conversation[] = [
  conv({ id: "c1", title: "Assistant", type: "direct", direct_kind: "agent", unread_count: 2, last_message_preview: "Hi" }),
  conv({ id: "c2", title: "Sprint Planning", type: "group", direct_kind: null,
    participants: [{ type: "user", id: "u1" }, { type: "agent", id: "a1" }] }),
  conv({ id: "c3", title: "Deploy: agent network", type: "group", direct_kind: null,
    participants: [{ type: "agent", id: "a1" }, { type: "agent", id: "a2" }] }),
  conv({ id: "c4", title: "Planner", type: "direct", direct_kind: "agent" })
];

describe("ConversationSidebar", () => {
  it("renders all conversations under the default 'all' filter", () => {
    render(
      <ConversationSidebar
        conversations={CONVS}
        activeConversationId={null}
        onSelect={() => {}}
        onNewGroup={() => {}}
      />
    );
    expect(screen.getByRole("button", { name: /Assistant/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sprint Planning/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Deploy: agent network/ })).toBeInTheDocument();
  });

  it("filters by kind when a tab is selected", async () => {
    const user = userEvent.setup();
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} />);
    await user.click(screen.getByRole("tab", { name: "Group" }));
    expect(screen.queryByRole("button", { name: /Assistant/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sprint Planning/ })).toBeInTheDocument();
    // agent-network excluded under Group
    expect(screen.queryByRole("button", { name: /Deploy: agent network/ })).not.toBeInTheDocument();
  });

  it("filters by search query against title + preview", async () => {
    const user = userEvent.setup();
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} />);
    await user.type(screen.getByRole("searchbox"), "plan");
    expect(screen.getByRole("button", { name: /Sprint Planning/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Planner/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Assistant/ })).not.toBeInTheDocument();
  });

  it("invokes onSelect with the clicked conversation id", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={onSelect} onNewGroup={() => {}} />);
    await user.click(screen.getByRole("button", { name: /Assistant/ }));
    expect(onSelect).toHaveBeenCalledWith("c1");
  });

  it("invokes onNewGroup when the + Group button is clicked", async () => {
    const user = userEvent.setup();
    const onNewGroup = vi.fn();
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={onNewGroup} />);
    await user.click(screen.getByRole("button", { name: /\+ Group/ }));
    expect(onNewGroup).toHaveBeenCalled();
  });

  it("shows unread badge on the conversation row when unread_count > 0", () => {
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} />);
    const row = screen.getByRole("button", { name: /Assistant/ });
    expect(within(row).getByText("2")).toBeInTheDocument();
  });
});

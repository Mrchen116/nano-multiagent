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
    run_state: "idle",
    source_agent_id: null,
    source_jsonl_path: null,
    ...over
  };
}

const CONVS: Conversation[] = [
  conv({
    id: "c1",
    title: "Assistant",
    type: "direct",
    direct_kind: "agent",
    unread_count: 2,
    last_message_preview: "Hi",
    participants: [{ type: "user", id: "u1" }, { type: "agent", id: "a1" }]
  }),
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

  it("does not show run-state labels before skill distill mode", () => {
    render(
      <ConversationSidebar
        conversations={[
          conv({ id: "running", title: "Running chat", run_state: "running" })
        ]}
        activeConversationId={null}
        onSelect={() => {}}
        onNewGroup={() => {}}
      />
    );

    expect(screen.queryByText("Running")).not.toBeInTheDocument();
  });

  it("shows checkboxes in skill distill mode and disables running conversations", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(
      <ConversationSidebar
        conversations={[
          conv({
            id: "idle",
            title: "Idle chat",
            run_state: "idle",
            source_agent_id: "a1",
            source_jsonl_path: "/tmp/idle.jsonl"
          }),
          conv({
            id: "running",
            title: "Running chat",
            run_state: "running",
            source_agent_id: "a1",
            source_jsonl_path: "/tmp/running.jsonl"
          })
        ]}
        activeConversationId={null}
        onSelect={() => {}}
        onNewGroup={() => {}}
        distillMode
        selectedDistillConversationIds={new Set()}
        onToggleDistillConversation={onToggle}
        onEnterDistillMode={() => {}}
        onCancelDistillMode={() => {}}
        onStartDistill={() => {}}
      />
    );

    const idleCheckbox = screen.getByRole("checkbox", { name: /Idle chat/ });
    const runningCheckbox = screen.getByRole("checkbox", { name: /Running chat/ });
    expect(idleCheckbox).toBeEnabled();
    expect(runningCheckbox).toBeDisabled();
    expect(screen.getByText("Running")).toBeInTheDocument();

    await user.click(idleCheckbox);
    expect(onToggle).toHaveBeenCalledWith("idle");
  });

  it("opens a right-click menu entry that enters skill distill multi-select", async () => {
    const user = userEvent.setup();
    const onEnter = vi.fn();
    render(
      <ConversationSidebar
        conversations={[
          conv({
            id: "idle",
            title: "Idle chat",
            run_state: "idle",
            source_agent_id: "a1",
            source_jsonl_path: "/tmp/idle.jsonl"
          })
        ]}
        activeConversationId={null}
        onSelect={() => {}}
        onNewGroup={() => {}}
        onEnterDistillMode={onEnter}
      />
    );

    await user.pointer({ keys: "[MouseRight]", target: screen.getByRole("button", { name: /Idle chat/ }) });
    const menu = await screen.findByRole("menu", { name: /Conversation actions/i });
    await user.click(within(menu).getByRole("menuitem", { name: /Distill to skill/i }));

    expect(onEnter).toHaveBeenCalledWith("idle");
  });

  it("shows unread badge on the conversation row when unread_count > 0", () => {
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} />);
    const row = screen.getByRole("button", { name: /Assistant/ });
    expect(within(row).getByText("2")).toBeInTheDocument();
  });

  // R8.5 — R11-10 ConvItem visual rewrite on v2 production path.
  // Prototype source: docs/changes/feat-340-agent-native-im/attachments/prototype/project/im-chat-page.jsx::ConvItem
  //   no KindBadge uppercase chip in the row; avatar carries data-testid for visual audits.
  describe("R11-10 v2 ConvItem visual", () => {
    it("does NOT render a KindBadge / kind_label chip in each row", () => {
      render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} />);
      const row = screen.getByRole("button", { name: /Assistant/ });
      // KindBadge prototype renders uppercase strings like "DIRECT", "GROUP", "AGENT NETWORK"
      // inside the row meta. Asserting *element absence* via testid + className catches
      // both the legacy <KindBadge> wrapper and any stylistic replacement that re-introduces
      // the chip.
      expect(row.querySelector(".chat-kind-badge, .chat-sidebar-kind-badge, [data-testid^=\"conv-kind-\"]")).toBeNull();
      // Defence-in-depth: the literal text most KindBadge renderings produce.
      expect(within(row).queryByText(/^(DIRECT|GROUP|AGENT NETWORK)$/i)).not.toBeInTheDocument();
    });

    it("renders an avatar with conv-avatar-<id> testid in each row", () => {
      render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} />);
      expect(screen.getByTestId("conv-avatar-c1")).toBeInTheDocument();
      expect(screen.getByTestId("conv-avatar-c2")).toBeInTheDocument();
      expect(screen.getByTestId("conv-avatar-c3")).toBeInTheDocument();
    });

    it("only shows online/offline avatar status for direct-agent rows, not group rows", () => {
      render(
        <ConversationSidebar
          conversations={CONVS}
          activeConversationId={null}
          onSelect={() => {}}
          onNewGroup={() => {}}
          agents={[{ agent_id: "a1", status: "online" }]}
        />
      );
      expect(screen.getByTestId("conv-avatar-c1").querySelector(".chat-avatar-status")).not.toBeNull();
      expect(screen.getByTestId("conv-avatar-c2").querySelector(".chat-avatar-status")).toBeNull();
      expect(screen.getByTestId("conv-avatar-c3").querySelector(".chat-avatar-status")).toBeNull();
    });
  });
});

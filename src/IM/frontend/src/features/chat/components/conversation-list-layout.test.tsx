import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ConversationList } from "./conversation-list";
import { ConversationSummary } from "../types";

const sampleItems: ConversationSummary[] = [
  {
    conversation_id: "conv-main",
    title: "主 Agent · OpsBot",
    participants: ["You", "OpsBot"],
    unread_count: 1,
    kind: "direct-agent",
    kind_label: "主 Agent 会话",
    last_message_at: "2026-03-26T10:00:00Z"
  },
  {
    conversation_id: "conv-group",
    title: "Kernel Ops Crew",
    participants: ["You", "OpsBot", "Alex"],
    unread_count: 0,
    kind: "group",
    kind_label: "Group chat",
    last_message_at: "2026-03-26T09:00:00Z",
    is_pinned: true
  },
  {
    conversation_id: "conv-direct",
    title: "DesignBot",
    participants: ["You", "DesignBot"],
    unread_count: 0,
    kind: "direct-agent",
    kind_label: "Direct chat",
    target_label: "DesignBot",
    discoverability_hint: "Message this agent directly.",
    last_message_at: "2026-03-26T08:00:00Z"
  }
];

function renderList(items: ConversationSummary[] = sampleItems) {
  return render(
    <MemoryRouter>
      <ConversationList items={items} onCreateGroupChat={() => undefined} />
    </MemoryRouter>
  );
}

describe("ConversationList layout — create-group-chat button", () => {
  it("create group chat button wrapper does not use shrink-0 (which causes overflow)", () => {
    render(
      <MemoryRouter>
        <ConversationList items={[]} onCreateGroupChat={() => undefined} />
      </MemoryRouter>
    );

    const button = screen.getByRole("button", { name: "Create group chat" });
    const parent = button.parentElement as HTMLElement;
    expect(parent.className).not.toContain("shrink-0");
  });

  it("keeps the empty state compact", () => {
    render(
      <MemoryRouter>
        <ConversationList items={[]} onCreateGroupChat={() => undefined} />
      </MemoryRouter>
    );

    expect(screen.getByText("No conversations yet")).toBeInTheDocument();
    expect(screen.queryByText("Start a direct chat or create a shared thread")).not.toBeInTheDocument();
  });

  it("keeps priority chats above the recent feed", () => {
    renderList();

    expect(screen.getByText("Priority", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("Recent", { selector: "p" })).toBeInTheDocument();
    const links = screen.getAllByRole("link").map((node) => node.textContent ?? "");
    expect(links[0]).toContain("主 Agent · OpsBot");
    expect(links[1]).toContain("Kernel Ops Crew");
    expect(links[2]).toContain("DesignBot");
  });

  it("filters conversations by search and kind", () => {
    renderList();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search conversations" }), {
      target: { value: "Design" }
    });
    expect(screen.getByText("DesignBot")).toBeInTheDocument();
    expect(screen.queryByText("Kernel Ops Crew")).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search conversations" }), {
      target: { value: "" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Groups" }));
    expect(screen.getByText("Kernel Ops Crew")).toBeInTheDocument();
    expect(screen.queryByText("DesignBot")).not.toBeInTheDocument();
  });

  // M19/R11-10: prototype ConvItem 行内只有 avatar + 标题/时间 + 预览/未读 badge —
  // 没有 kind_label uppercase chip;direct-agent 在 avatar 上叠 online/offline status dot。
  it("R11-10: row does not render the kind_label uppercase chip", () => {
    render(
      <MemoryRouter>
        <ConversationList items={sampleItems} onCreateGroupChat={() => undefined} />
      </MemoryRouter>
    );

    expect(screen.queryByText("主 Agent 会话")).not.toBeInTheDocument();
    expect(screen.queryByText("Group chat")).not.toBeInTheDocument();
    expect(screen.queryByText("Direct chat")).not.toBeInTheDocument();
  });

  it("R11-10: direct-agent row carries an online/offline status dot on the avatar", () => {
    const items: ConversationSummary[] = [
      {
        conversation_id: "conv-online",
        title: "OpsBot",
        participants: ["You", "OpsBot"],
        unread_count: 0,
        kind: "direct-agent",
        kind_label: "Direct chat",
        node_status: "online",
        last_message_at: "2026-03-26T10:00:00Z"
      },
      {
        conversation_id: "conv-offline",
        title: "DesignBot",
        participants: ["You", "DesignBot"],
        unread_count: 0,
        kind: "direct-agent",
        kind_label: "Direct chat",
        node_status: "offline",
        last_message_at: "2026-03-26T08:00:00Z"
      }
    ];

    render(
      <MemoryRouter>
        <ConversationList items={items} onCreateGroupChat={() => undefined} />
      </MemoryRouter>
    );

    const onlineDot = screen.getByTestId("conv-status-dot-conv-online");
    expect(onlineDot.getAttribute("data-status-dot")).toBe("online");
    const offlineDot = screen.getByTestId("conv-status-dot-conv-offline");
    expect(offlineDot.getAttribute("data-status-dot")).toBe("offline");
  });

  it("R11-10: row renders an avatar with initials beside the title", () => {
    render(
      <MemoryRouter>
        <ConversationList items={sampleItems} onCreateGroupChat={() => undefined} />
      </MemoryRouter>
    );

    const avatar = screen.getByTestId("conv-avatar-conv-direct");
    expect(avatar.className).toMatch(/rounded-full/);
    expect(avatar.textContent).toMatch(/^DE$/i);
  });

  it("restores sidebar scroll position after switching conversations", () => {
    const items = [
      {
        conversation_id: "conv-1",
        title: "Alpha",
        participants: ["You", "Alpha"],
        unread_count: 0,
        kind_label: "Direct chat"
      },
      {
        conversation_id: "conv-2",
        title: "Beta",
        participants: ["You", "Beta"],
        unread_count: 0,
        kind_label: "Direct chat"
      }
    ];

    const { rerender } = render(
      <MemoryRouter>
        <ConversationList items={items} activeId="conv-1" onCreateGroupChat={() => undefined} />
      </MemoryRouter>
    );

    const scrollContainer = screen.getByTestId("conversation-list-scroll-container");
    Object.defineProperty(scrollContainer, "scrollTop", {
      value: 180,
      writable: true,
      configurable: true
    });
    fireEvent.scroll(scrollContainer, { target: { scrollTop: 180 } });

    rerender(
      <MemoryRouter>
        <ConversationList items={items} activeId="conv-2" onCreateGroupChat={() => undefined} />
      </MemoryRouter>
    );

    expect((screen.getByTestId("conversation-list-scroll-container") as HTMLDivElement).scrollTop).toBe(180);
  });
});

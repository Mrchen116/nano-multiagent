import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ConversationList } from "./conversation-list";

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

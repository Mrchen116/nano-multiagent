import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ConversationList } from "./conversation-list";

describe("ConversationList layout — create-group-chat button", () => {
  it("create group chat button wrapper does not use shrink-0 (which causes overflow)", () => {
    render(
      <MemoryRouter>
        <ConversationList
          items={[]}
          onCreateGroupChat={() => undefined}
        />
      </MemoryRouter>
    );

    const button = screen.getByRole("button", { name: "Create group chat" });
    // The button's direct parent must not carry shrink-0; that class pushes the
    // button outside the card boundary on narrow containers.
    const parent = button.parentElement as HTMLElement;
    expect(parent.className).not.toContain("shrink-0");
  });
});

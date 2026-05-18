import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import type { MentionCandidate } from "../chat-types";
import { MentionPicker } from "./mention-picker";

const CANDIDATES: MentionCandidate[] = [
  { agent_id: "a-planner", display_name: "Planner", initials: "PL", status: "online" },
  { agent_id: "a-coder", display_name: "Coder", initials: "CO", status: "online" },
  { agent_id: "a-reviewer", display_name: "Reviewer", initials: "RE", status: "offline" }
];

describe("MentionPicker", () => {
  it("renders all candidates when query is empty", () => {
    render(<MentionPicker candidates={CANDIDATES} query="" onSelect={() => {}} onClose={() => {}} />);
    expect(screen.getByRole("button", { name: /Planner/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Coder/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reviewer/ })).toBeInTheDocument();
    expect(document.querySelector(".chat-avatar-status")).toBeNull();
  });

  it("filters candidates by prefix match (case-insensitive)", () => {
    render(<MentionPicker candidates={CANDIDATES} query="p" onSelect={() => {}} onClose={() => {}} />);
    expect(screen.getByRole("button", { name: /Planner/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Coder/ })).not.toBeInTheDocument();
  });

  it("renders nothing when no candidate matches", () => {
    const { container } = render(
      <MentionPicker candidates={CANDIDATES} query="zzz" onSelect={() => {}} onClose={() => {}} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("calls onSelect with the chosen candidate when clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<MentionPicker candidates={CANDIDATES} query="" onSelect={onSelect} onClose={() => {}} />);
    await user.click(screen.getByRole("button", { name: /Coder/ }));
    expect(onSelect).toHaveBeenCalledWith(CANDIDATES[1]);
  });

  // bugfix-358: handle column shown only when display_name duplicates exist in the list
  describe("handle column conditional display (bugfix-358)", () => {
    const UNIQUE_NAMES: MentionCandidate[] = [
      { agent_id: "a-alpha", display_name: "Alpha", initials: "AL", status: "online" },
      { agent_id: "a-beta", display_name: "Beta", initials: "BE", status: "online" },
    ];

    const DUPLICATE_NAMES: MentionCandidate[] = [
      { agent_id: "a-assistant-1", display_name: "助手", initials: "AS", status: "online" },
      { agent_id: "a-assistant-2", display_name: "助手", initials: "AS", status: "online" },
      { agent_id: "a-unique", display_name: "Unique", initials: "UN", status: "online" },
    ];

    it("does not show handle column when all display_names are unique", () => {
      render(<MentionPicker candidates={UNIQUE_NAMES} query="" onSelect={() => {}} onClose={() => {}} />);
      // handle column items should not be visible
      const handles = document.querySelectorAll(".chat-mention-picker-handle");
      // All handle elements should be hidden or absent for unique-name candidates
      const visibleHandles = Array.from(handles).filter(
        (el) => (el as HTMLElement).style.display !== "none" && !el.classList.contains("hidden")
      );
      expect(visibleHandles).toHaveLength(0);
    });

    it("shows handle column for duplicate display_name candidates", () => {
      render(<MentionPicker candidates={DUPLICATE_NAMES} query="" onSelect={() => {}} onClose={() => {}} />);
      // The two "助手" rows must show their handles for disambiguation
      const handles = document.querySelectorAll(".chat-mention-picker-handle");
      const visibleHandles = Array.from(handles).filter(
        (el) => (el as HTMLElement).style.display !== "none" && !el.classList.contains("hidden")
      );
      // At least the duplicate-name rows must show a handle
      expect(visibleHandles.length).toBeGreaterThanOrEqual(2);
    });
  });
});

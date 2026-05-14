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
});

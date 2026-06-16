import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import type { MentionCandidate } from "../chat-types";
import { colorForAgent } from "./avatar";
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

  // bugfix-415: avatar color must come from colorForAgent(display_name) — not truncated initials.
  // If Avatar is called without `color`, it falls back to colorForAgentSeed(initials) which uses
  // a 2-char seed and diverges from the canonical display_name-seeded color used everywhere else.
  it("avatar background color matches colorForAgent for each candidate (bugfix-415 regression)", () => {
    render(<MentionPicker candidates={CANDIDATES} query="" onSelect={() => {}} onClose={() => {}} />);
    const faces = document.querySelectorAll<HTMLElement>(".chat-avatar-face");
    expect(faces).toHaveLength(CANDIDATES.length);
    CANDIDATES.forEach((c, i) => {
      expect(faces[i]!.style.background).toBe(colorForAgent({ display_name: c.display_name, agent_id: c.agent_id }));
    });
  });

  // bugfix-358: handle column (@agent_id) is always shown so the user can verify
  // the wire ID before sending; duplicate display_names are naturally disambiguated
  // by two visible distinct handles.
  describe("handle column always visible (bugfix-358)", () => {
    const UNIQUE_NAMES: MentionCandidate[] = [
      { agent_id: "a-alpha", display_name: "Alpha", initials: "AL", status: "online" },
      { agent_id: "a-beta", display_name: "Beta", initials: "BE", status: "online" },
    ];

    const DUPLICATE_NAMES: MentionCandidate[] = [
      { agent_id: "a-assistant-1", display_name: "助手", initials: "AS", status: "online" },
      { agent_id: "a-assistant-2", display_name: "助手", initials: "AS", status: "online" },
      { agent_id: "a-unique", display_name: "Unique", initials: "UN", status: "online" },
    ];

    it("renders a handle row for every candidate, even when display_names are unique", () => {
      render(<MentionPicker candidates={UNIQUE_NAMES} query="" onSelect={() => {}} onClose={() => {}} />);
      const handles = document.querySelectorAll(".chat-mention-picker-handle");
      expect(handles).toHaveLength(UNIQUE_NAMES.length);
      expect(handles[0].textContent).toBe("@a-alpha");
      expect(handles[1].textContent).toBe("@a-beta");
    });

    it("renders a handle row for every candidate when duplicates exist, surfacing distinct agent_ids", () => {
      render(<MentionPicker candidates={DUPLICATE_NAMES} query="" onSelect={() => {}} onClose={() => {}} />);
      const handles = document.querySelectorAll(".chat-mention-picker-handle");
      expect(handles).toHaveLength(DUPLICATE_NAMES.length);
      const texts = Array.from(handles).map((el) => el.textContent);
      expect(texts).toContain("@a-assistant-1");
      expect(texts).toContain("@a-assistant-2");
      expect(texts).toContain("@a-unique");
    });

    it("strips agent_ or agent- prefix from agent_id when rendering handle", () => {
      const PREFIXED: MentionCandidate[] = [
        { agent_id: "agent_legacy", display_name: "Legacy", initials: "LG", status: "online" },
        { agent_id: "agent-modern", display_name: "Modern", initials: "MD", status: "online" },
      ];
      render(<MentionPicker candidates={PREFIXED} query="" onSelect={() => {}} onClose={() => {}} />);
      const handles = Array.from(document.querySelectorAll(".chat-mention-picker-handle")).map(
        (el) => el.textContent
      );
      expect(handles).toContain("@legacy");
      expect(handles).toContain("@modern");
    });
  });
});

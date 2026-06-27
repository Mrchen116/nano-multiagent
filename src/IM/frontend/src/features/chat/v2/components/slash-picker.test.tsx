import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import type { SlashSkillCandidate } from "./slash-candidates";
import { SlashPicker } from "./slash-picker";

const SKILLS: SlashSkillCandidate[] = [
  { kind: "skill", name: "pr-review", description: "review PRs", location: "/a", fromAgents: ["code-reviewer"] },
  { kind: "skill", name: "doc", description: "docs", location: "/b", fromAgents: ["code-reviewer"] },
  { kind: "skill", name: "log-cleanup", description: "clean logs", location: "/c", fromAgents: ["code-reviewer"] },
];

function noop() {}

describe("SlashPicker", () => {
  it("shows /stop command and all skills when query is empty", () => {
    render(<SlashPicker skills={SKILLS} query="" skillMode={false} isGroup={false} onSelect={noop} onClose={noop} />);
    expect(screen.getByText("/stop")).toBeInTheDocument();
    expect(screen.getByText("pr-review")).toBeInTheDocument();
    expect(screen.getByText("doc")).toBeInTheDocument();
  });

  it("prefix-filters commands and skills together; non-matching /stop disappears", () => {
    render(<SlashPicker skills={SKILLS} query="pr" skillMode={false} isGroup={false} onSelect={noop} onClose={noop} />);
    expect(screen.getByText("pr-review")).toBeInTheDocument();
    expect(screen.queryByText("/stop")).not.toBeInTheDocument();
    expect(screen.queryByText("doc")).not.toBeInTheDocument();
  });

  it("in /skill: mode shows only skills (no /stop command)", () => {
    render(<SlashPicker skills={SKILLS} query="" skillMode={true} isGroup={false} onSelect={noop} onClose={noop} />);
    expect(screen.queryByText("/stop")).not.toBeInTheDocument();
    expect(screen.getByText("pr-review")).toBeInTheDocument();
  });

  it("renders an empty state when nothing matches", () => {
    render(<SlashPicker skills={SKILLS} query="zzz" skillMode={false} isGroup={false} onSelect={noop} onClose={noop} />);
    expect(screen.getByText(/No matching|没有匹配/)).toBeInTheDocument();
  });

  it("selects a skill on mousedown click", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<SlashPicker skills={SKILLS} query="" skillMode={false} isGroup={false} onSelect={onSelect} onClose={noop} />);
    await user.click(screen.getByText("pr-review"));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ kind: "skill", name: "pr-review" }));
  });

  it("selects the highlighted candidate on Enter", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<SlashPicker skills={SKILLS} query="" skillMode={false} isGroup={false} onSelect={onSelect} onClose={noop} />);
    await user.keyboard("{Enter}");
    // First candidate is the /stop command.
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ kind: "command", name: "stop" }));
  });

  it("ArrowDown then Enter selects the next candidate", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<SlashPicker skills={SKILLS} query="" skillMode={false} isGroup={false} onSelect={onSelect} onClose={noop} />);
    await user.keyboard("{ArrowDown}{Enter}");
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ kind: "skill", name: "pr-review" }));
  });

  it("Escape closes the picker", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<SlashPicker skills={SKILLS} query="" skillMode={false} isGroup={false} onSelect={noop} onClose={onClose} />);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("shows source agents for group skills with different locations as separate rows", () => {
    const groupSkills: SlashSkillCandidate[] = [
      { kind: "skill", name: "doc", description: "cr doc", location: "/cr/doc", fromAgents: ["code-reviewer"] },
      { kind: "skill", name: "doc", description: "tw doc", location: "/tw/doc", fromAgents: ["test-writer"] },
    ];
    render(<SlashPicker skills={groupSkills} query="" skillMode={false} isGroup={true} onSelect={noop} onClose={noop} />);
    expect(screen.getAllByText("doc")).toHaveLength(2);
    expect(screen.getByText(/code-reviewer/)).toBeInTheDocument();
    expect(screen.getByText(/test-writer/)).toBeInTheDocument();
  });

  // fix-r2 (verifier S2): Tab confirms the highlighted candidate like Enter.
  it("selects the highlighted candidate on Tab", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<SlashPicker skills={SKILLS} query="" skillMode={false} isGroup={false} onSelect={onSelect} onClose={noop} />);
    await user.keyboard("{Tab}");
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ kind: "command", name: "stop" }));
  });

  // fix-r2 (P1.2): a keydown during IME composition must NOT be hijacked as a selection.
  it("ignores Enter while IME is composing", () => {
    const onSelect = vi.fn();
    render(<SlashPicker skills={SKILLS} query="" skillMode={false} isGroup={false} onSelect={onSelect} onClose={noop} />);
    const ev = new KeyboardEvent("keydown", { key: "Enter", bubbles: true });
    Object.defineProperty(ev, "isComposing", { get: () => true });
    window.dispatchEvent(ev);
    expect(onSelect).not.toHaveBeenCalled();
  });

  // fix-r2 (P2.11): the listbox advertises the active option via aria-activedescendant,
  // and that id resolves to the selected option element.
  it("exposes aria-activedescendant pointing at the active option", async () => {
    const user = userEvent.setup();
    render(<SlashPicker skills={SKILLS} query="" skillMode={false} isGroup={false} onSelect={noop} onClose={noop} />);
    const listbox = screen.getByRole("listbox");
    const activeId = listbox.getAttribute("aria-activedescendant");
    expect(activeId).toBeTruthy();
    const active = document.getElementById(activeId!);
    expect(active).not.toBeNull();
    expect(active!.getAttribute("aria-selected")).toBe("true");
    // Moving the highlight updates aria-activedescendant to a different option.
    await user.keyboard("{ArrowDown}");
    expect(listbox.getAttribute("aria-activedescendant")).not.toBe(activeId);
  });

  // fix-r2 (P1.3): when the candidate *content* changes (same length, different items),
  // the highlight resets so Enter selects the visible first row — not a stale index.
  it("resets the highlight when candidate content changes at the same length", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const setA: SlashSkillCandidate[] = [
      { kind: "skill", name: "alpha", description: "", location: "/a", fromAgents: ["x"] },
      { kind: "skill", name: "beta", description: "", location: "/b", fromAgents: ["x"] },
    ];
    const setB: SlashSkillCandidate[] = [
      { kind: "skill", name: "gamma", description: "", location: "/g", fromAgents: ["x"] },
      { kind: "skill", name: "delta", description: "", location: "/d", fromAgents: ["x"] },
    ];
    const { rerender } = render(
      <SlashPicker skills={setA} query="" skillMode={true} isGroup={false} onSelect={onSelect} onClose={noop} />,
    );
    await user.keyboard("{ArrowDown}"); // highlight index 1 (beta)
    rerender(
      <SlashPicker skills={setB} query="" skillMode={true} isGroup={false} onSelect={onSelect} onClose={noop} />,
    );
    await user.keyboard("{Enter}");
    // Reset → index 0 of the new set (gamma), never the stale "beta"/out-of-range.
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ name: "gamma" }));
  });
});

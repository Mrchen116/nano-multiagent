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
});

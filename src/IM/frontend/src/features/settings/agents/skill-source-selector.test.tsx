import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { SkillSourceSelector } from "./skill-source-selector";

const options = [
  { name: "local-a", description: "", source_group: "workspace" as const },
  { name: "local-b", description: "", source_group: "workspace" as const },
  { name: "global-a", description: "", source_group: "global" as const },
];

describe("skill source selector", () => {
  it("renders default discovery as all selected and first edit becomes explicit", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SkillSourceSelector
        testId="skills"
        label="Skills"
        selected={[]}
        selectionMode="default_discovery"
        options={options}
        onChange={onChange}
      />,
    );

    expect(screen.getByTestId("skills-mode")).toHaveTextContent(/discoverable/i);
    expect(screen.getByRole("button", { name: "local-a" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "local-a" }));
    expect(onChange).toHaveBeenCalledWith(
      ["local-a"],
      "explicit_denylist",
    );
  });

  it("reports mixed group state and preserves names outside the group", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SkillSourceSelector
        testId="skills"
        label="Skills"
        selected={["local-a", "hidden-name"]}
        selectionMode="explicit_allowlist"
        options={options}
        onChange={onChange}
      />,
    );

    const group = screen.getByRole("checkbox", { name: /workspace.*1\/2/i });
    expect(group).toHaveAttribute("aria-checked", "mixed");
    await user.click(group);
    expect(onChange).toHaveBeenCalledWith(
      ["global-a"],
      "explicit_denylist",
    );
  });

  it("clears an all-selected group without removing other or hidden selections", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SkillSourceSelector
        testId="skills"
        label="Skills"
        selected={["local-a", "local-b", "global-a", "hidden-name"]}
        selectionMode="explicit_allowlist"
        options={options}
        onChange={onChange}
      />,
    );

    const group = screen.getByRole("checkbox", { name: /workspace.*2\/2/i });
    expect(group).toHaveAttribute("aria-checked", "true");
    await user.click(group);
    expect(onChange).toHaveBeenCalledWith(
      ["local-a", "local-b"],
      "explicit_denylist",
    );
  });

  it("falls back to legacy locations when source_group is absent", () => {
    render(
      <SkillSourceSelector
        testId="skills"
        label="Skills"
        selected={[]}
        selectionMode="explicit_allowlist"
        workspaceRoot="/srv/agent"
        options={[
          { name: "workspace-old", description: "", location: "/srv/agent/.claude/skills/workspace-old/SKILL.md" },
          { name: "global-old", description: "", default_on: true, location: "/home/u/.nanoassistant/skills/global-old/SKILL.md" },
          { name: "compat-old", description: "", location: "/home/u/.codex/skills/compat-old/SKILL.md" },
        ]}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("checkbox", { name: /workspace.*0\/1/i })).toBeVisible();
    expect(screen.getByRole("checkbox", { name: /global.*0\/1/i })).toBeVisible();
    expect(screen.getByRole("checkbox", { name: /compatibility.*0\/1/i })).toBeVisible();
  });
});

it('keeps new skills selected and persists only disabled names, including hidden ones', async () => {
  const user = userEvent.setup(); const onChange = vi.fn();
  render(<SkillSourceSelector testId="denylist" label="Skills" selected={['local-a', 'hidden-disabled']} selectionMode="explicit_denylist" options={options} onChange={onChange} />);
  expect(screen.getByRole('button', {name: 'local-a'})).toHaveAttribute('aria-pressed', 'false');
  expect(screen.getByRole('button', {name: 'local-a'})).toHaveClass('bg-[oklch(0.96_0.005_240)]');
  expect(screen.getByRole('button', {name: 'local-b'})).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByRole('button', {name: 'local-b'})).toHaveClass('bg-[oklch(0.93_0.08_180)]');
  await user.click(screen.getByRole('button', {name: 'local-b'}));
  expect(onChange).toHaveBeenCalledWith(['local-a', 'hidden-disabled', 'local-b'], 'explicit_denylist');
});

it("does not present unconfirmed inherited skill state as enabled", () => {
  render(<SkillSourceSelector testId="skills" label="Skills" selected={[]} selectionMode="default_discovery" options={[{name: "old-skill", description: "", source_group: "global", enabled: null}]} readOnly onChange={vi.fn()} />);
  expect(screen.getByRole("button", {name: "old-skill"})).not.toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("checkbox")).toHaveAttribute("aria-checked", "mixed");
  expect(screen.getByText("—/1")).toBeInTheDocument();
});

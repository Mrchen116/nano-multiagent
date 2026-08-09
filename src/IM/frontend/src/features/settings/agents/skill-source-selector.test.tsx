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
      ["local-b", "global-a"],
      "explicit_allowlist",
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
      ["local-a", "hidden-name", "local-b"],
      "explicit_allowlist",
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
      ["global-a", "hidden-name"],
      "explicit_allowlist",
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

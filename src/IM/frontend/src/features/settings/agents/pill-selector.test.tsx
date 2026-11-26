import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { PillSelector } from "./pill-selector";

it("collapses by default when collapsible, keeps sibling labelAction separate, and renders active workspace tools when expanded", async () => {
  const onChange = vi.fn();
  const onToggleOption = vi.fn();
  const onManagePlugins = vi.fn();
  render(
    <PillSelector
      testId="tools"
      collapsible
      defaultExpanded={false}
      label="Tools"
      labelAction={<button type="button" onClick={onManagePlugins}>Manage plugins →</button>}
      selected={["plugin_manager"]}
      fixed={["inbox"]}
      onChange={onChange}
      onToggleOption={onToggleOption}
      options={[
        { name: "plugin_manager" },
        { name: "read" },
        { name: "inbox" },
        { name: "expense_summary", source_group: "workspace", enabled: true },
      ]}
    />,
  );
  const toggle = screen.getByTestId("tools-toggle");
  const action = screen.getByRole("button", { name: "Manage plugins →" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(toggle).toHaveTextContent("3 / 4");
  expect(toggle.contains(action)).toBe(false);
  expect(screen.queryByTestId("tools")).not.toBeInTheDocument();

  await userEvent.click(action);
  expect(onManagePlugins).toHaveBeenCalledTimes(1);
  expect(toggle).toHaveAttribute("aria-expanded", "false");

  await userEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("button", { name: "expense_summary" })).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(screen.getByRole("button", { name: "expense_summary" }));
  expect(onToggleOption).toHaveBeenCalledWith(expect.objectContaining({ name: "expense_summary", source_group: "workspace" }), false);
  expect(onChange).not.toHaveBeenCalled();
});

import {render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {expect, it, vi} from "vitest";
import {setLanguage} from "../../../i18n";
import {ApprovalModeField} from "./approval-mode-field";

it.each([["nano", "CC"], ["codex", "Codex"], ["dsh", "DSH"], [null, "strategy unconfirmed"]] as const)("shows inherited %s independently of the Agent override", async (rules, label) => {
  setLanguage("en");
  const change = vi.fn();
  render(<ApprovalModeField value="cc" inheritedRules={rules} onChange={change} />);
  expect(screen.getByRole("option", {name: `Follow node (${label})`})).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox"), "");
  expect(change).toHaveBeenCalledWith(null);
});

it("shows the Chinese strategy in parentheses", () => {
  setLanguage("zh");
  render(<ApprovalModeField value={null} inheritedRules="codex" onChange={vi.fn()} />);
  expect(screen.getByRole("option", {name: "跟随节点（Codex）"})).toBeInTheDocument();
  setLanguage("en");
});

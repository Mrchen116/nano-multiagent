import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { PillSelector } from "./pill-selector";
import { normalizeAllowlistOptions } from "./im-agent-config-api";
import { setLanguage } from "../../../i18n";

it("shows workspace availability without adding automatic tools to saved choices", async () => {
  setLanguage("en");
  const onChange=vi.fn();
  const options=normalizeAllowlistOptions([
    {name:"plugin_manager",description:"Manage workspace tools"},
    {name:"read",description:"Read files"},
    {name:"expense_summary",description:"Summarize monthly expenses",source_group:"workspace",enabled:true},
  ]);
  const props={testId:"tools",label:"Tool Allowlist",selected:["plugin_manager"],options,onChange};
  const view=render(<PillSelector {...props}/>);
  const workspace=screen.getByRole("region",{name:"Workspace tools"});
  expect(within(workspace).getByText("expense_summary")).toBeVisible();
  expect(within(workspace).getByText("Enabled")).toBeVisible();
  expect(screen.queryByRole("button",{name:"expense_summary"})).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button",{name:"read"}));
  expect(onChange).toHaveBeenCalledWith(["plugin_manager","read"]);
  view.rerender(<PillSelector {...props} selected={[]} options={options.map(option=>option.name==="expense_summary"?{...option,enabled:false}:option)}/>);
  expect(within(workspace).getByText("Unavailable")).toBeVisible();
  expect(onChange).toHaveBeenCalledTimes(1);
});

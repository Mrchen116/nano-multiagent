import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { PillSelector } from "./pill-selector";

it("keeps static tool choices separate from installed plugin contributions", async () => {
  const onChange=vi.fn();
  render(<PillSelector testId="tools" label="Tools" selected={["plugin_manager"]} onChange={onChange} options={[
    {name:"plugin_manager"}, {name:"read"},
    {name:"expense_summary",source_group:"workspace",enabled:true},
  ]}/>);
  expect(screen.queryByText("expense_summary")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button",{name:"read"}));
  expect(onChange).toHaveBeenLastCalledWith(["plugin_manager","read"]);
});

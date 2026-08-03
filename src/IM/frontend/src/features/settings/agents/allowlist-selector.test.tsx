import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { AllowlistSelector } from "./allowlist-selector";

describe("allowlist selector", () => {
  it("shows selected options and reports user changes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <AllowlistSelector
        id="skills"
        label="Skills"
        selected={["plan"]}
        options={[
          { name: "plan", description: "Plan work" },
          { name: "playwright", description: "Drive browser checks" }
        ]}
        helpText="Choose only the access this agent needs."
        emptySelectionText="Nothing selected."
        onChange={onChange}
      />
    );

    expect(screen.getByRole("checkbox", { name: /plan/i })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /playwright/i })).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: /plan/i }));

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("shows unavailable saved tools inline with the main list", () => {
    render(
      <AllowlistSelector
        id="tools"
        label="Tools"
        selected={["bash", "legacy-tool"]}
        options={[
          { name: "read", description: "Read files" },
          { name: "bash", description: "Run shell commands" }
        ]}
        helpText="Choose only the access this agent needs."
        emptySelectionText="Nothing selected."
        onChange={() => undefined}
      />
    );

    expect(screen.getByRole("checkbox", { name: /bash/i })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /legacy-tool/i })).toBeChecked();
    expect(screen.getByText("Unavailable now")).toBeInTheDocument();
  });
});

import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

describe("agent edit page", () => {
  it("loads agent form and saves edited display name", async () => {
    const user = userEvent.setup();

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents/agent-core-1"]
    });

    const input = await screen.findByLabelText("Display Name");
    await user.clear(input);
    await user.type(input, "Core Planner X");
    await user.click(screen.getByRole("button", { name: "Save Agent" }));

    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });
});

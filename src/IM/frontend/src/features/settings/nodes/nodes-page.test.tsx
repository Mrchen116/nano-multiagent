import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

describe("nodes page", () => {
  it("edits node alias and persists in ui", async () => {
    const user = userEvent.setup();

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/nodes"]
    });

    const aliasInput = await screen.findByLabelText("Alias node-app-01");
    await user.clear(aliasInput);
    await user.type(aliasInput, "node-app-01-prod");
    await user.click(screen.getByRole("button", { name: "Save node-app-01" }));

    expect(await screen.findByDisplayValue("node-app-01-prod")).toBeInTheDocument();
  });
});

import { screen } from "@testing-library/react";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

describe("agents list mobile", () => {
  it("renders card list without desktop table on mobile", async () => {
    window.innerWidth = 375;
    window.dispatchEvent(new Event("resize"));

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText("Core Planner")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

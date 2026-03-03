import { screen } from "@testing-library/react";

import { appRoutes } from "../../app/router";
import { renderRouter } from "../../test/render-router";

describe("settings shell mobile", () => {
  it("provides labeled section navigation on mobile", async () => {
    window.innerWidth = 375;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });

    expect(await screen.findByRole("navigation", { name: "Settings Sections" })).toBeInTheDocument();
  });
});

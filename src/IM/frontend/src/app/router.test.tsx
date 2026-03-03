import { screen } from "@testing-library/react";

import { appRoutes } from "./router";
import { renderRouter } from "../test/render-router";

describe("app routes", () => {
  it("contains chat and settings root routes", () => {
    renderRouter({ routes: appRoutes, initialEntries: ["/chat"] });

    expect(screen.getByText("Conversations")).toBeInTheDocument();
  });
});

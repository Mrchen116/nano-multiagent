import { screen } from "@testing-library/react";

import { appRoutes } from "../../app/router";
import { renderRouter } from "../../test/render-router";

describe("chat routes", () => {
  it("renders conversation detail route and composer", async () => {
    window.innerWidth = 1280;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat/conv-kernel-ops"] });

    expect(await screen.findByRole("heading", { name: "Kernel Ops Crew" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Type message")).toBeInTheDocument();
    expect(screen.getByText("sent")).toBeInTheDocument();
  });

  it("shows agent semantics on the default starter conversation route", async () => {
    window.innerWidth = 1280;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat/conv-kernel-ops"] });

    expect(await screen.findByRole("heading", { name: "Kernel Ops Crew" })).toBeInTheDocument();
    expect(screen.getByText("OpsBot")).toBeInTheDocument();
  });
});

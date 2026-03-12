import { screen } from "@testing-library/react";

import { appRoutes } from "../../app/router";
import { renderRouter } from "../../test/render-router";

describe("chat routes", () => {
  it("renders conversation detail route and send blocker state", async () => {
    window.innerWidth = 1280;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat/conv-kernel-ops"] });

    expect(await screen.findByRole("heading", { name: "Kernel Ops Crew" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Gateway offline — chat disabled")).toBeDisabled();
    expect(screen.getByText("Chat unavailable")).toBeInTheDocument();
    expect(screen.getByText("Your bound Gateway is offline. Bring that node online or bind another online node to re-enable chat.")).toBeInTheDocument();
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

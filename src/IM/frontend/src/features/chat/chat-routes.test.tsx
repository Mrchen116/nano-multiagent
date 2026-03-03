import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";

import { appRoutes } from "../../app/router";
import { renderRouter } from "../../test/render-router";

describe("chat routes", () => {
  it("opens conversation detail route and renders composer", async () => {
    const user = userEvent.setup();
    window.innerWidth = 1280;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat"] });

    await user.click(screen.getByRole("link", { name: /Kernel Ops Crew/i }));

    expect(await screen.findByRole("heading", { name: "Kernel Ops Crew" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Type message")).toBeInTheDocument();
  });
});

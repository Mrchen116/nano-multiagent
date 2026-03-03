import { screen } from "@testing-library/react";

import { appRoutes } from "../../app/router";
import { renderRouter } from "../../test/render-router";

describe("chat layout", () => {
  it("shows desktop two-panel frame on /chat", async () => {
    window.innerWidth = 1280;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat"] });

    expect(await screen.findByRole("heading", { name: "Conversations" })).toBeInTheDocument();
    expect(screen.getByText("Select a conversation")).toBeInTheDocument();
  });

  it("shows single panel list on mobile /chat", async () => {
    window.innerWidth = 375;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat"] });

    expect(await screen.findByRole("heading", { name: "Conversations" })).toBeInTheDocument();
    expect(screen.queryByText("Select a conversation")).not.toBeInTheDocument();
  });

  it("anchors desktop conversation messages to the bottom", async () => {
    window.innerWidth = 1280;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat/conv-kernel-ops"] });

    const stack = await screen.findByTestId("message-list-stack");
    expect(stack).toHaveClass("justify-end");
  });
});

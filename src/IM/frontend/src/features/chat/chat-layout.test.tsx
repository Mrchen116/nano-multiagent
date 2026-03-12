import { screen } from "@testing-library/react";

import { appRoutes } from "../../app/router";
import { renderRouter } from "../../test/render-router";

describe("chat layout", () => {
  it("shows a default agent starter on desktop /chat", async () => {
    window.innerWidth = 1280;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat"] });

    expect(await screen.findByRole("heading", { name: "Conversations" })).toBeInTheDocument();
    expect(screen.getByText("OpsBot handles the default IM replies for this workspace.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Agent · OpsBot" })).toBeInTheDocument();
    expect(screen.queryByText("Select a conversation")).not.toBeInTheDocument();
  });

  it("shows the default agent starter on mobile /chat", async () => {
    window.innerWidth = 375;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat"] });

    expect(await screen.findByRole("heading", { name: "Conversations" })).toBeInTheDocument();
    expect(screen.getByText("OpsBot handles the default IM replies for this workspace.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Agent · OpsBot" })).toBeInTheDocument();
  });

  it("anchors desktop conversation messages to the bottom", async () => {
    window.innerWidth = 1280;
    window.dispatchEvent(new Event("resize"));

    renderRouter({ routes: appRoutes, initialEntries: ["/chat/conv-kernel-ops"] });

    const stack = await screen.findByTestId("message-list-stack");
    expect(stack).toHaveClass("justify-end");
  });
});

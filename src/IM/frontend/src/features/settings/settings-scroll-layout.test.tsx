import { screen } from "@testing-library/react";

import { appRoutes } from "../../app/router";
import { renderRouter } from "../../test/render-router";

function renderSettingsShell(initialEntry = "/settings/agents") {
  return renderRouter({ routes: appRoutes, initialEntries: [initialEntry] });
}

describe("settings scroll layout", () => {
  it("keeps the shell height-bounded and scroll ownership inside panels", () => {
    const { container } = renderSettingsShell();

    const shell = container.querySelector("section");
    const aside = container.querySelector("aside");
    const panel = aside?.nextElementSibling;

    expect(shell).toHaveClass("h-full");
    expect(shell).toHaveClass("overflow-hidden");
    expect(aside).toHaveClass("overflow-y-auto");
    expect(panel).toHaveClass("h-full");
    expect(panel).toHaveClass("overflow-y-auto");
  });

  it.each([
    ["/settings/agents", /Loading agents and the latest configuration snapshot/i],
    ["/settings/agents/new", /Back to Agents/i],
    ["/settings/agents/agent-1", /Loading agent profile/i],
    ["/settings/nodes", /Loading nodes/i],
    ["/settings/policies", /Loading policies/i],
    ["/settings/account", /Loading account/i]
  ])("renders %s inside a full-height column container", (entry, marker) => {
    const { container } = renderSettingsShell(entry);

    const panel = container.querySelector("aside")?.nextElementSibling;
    expect(screen.getByText(marker)).toBeInTheDocument();
    expect(panel).toHaveClass("h-full");
    expect(panel).toHaveClass("flex");
    expect(panel).toHaveClass("flex-col");
    expect(container.querySelector("nav")).toBeInTheDocument();
  });
});

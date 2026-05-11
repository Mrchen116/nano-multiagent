import { waitFor } from "@testing-library/react";

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
    ["/settings/agents", '[data-testid="agents-list"]'],
    ["/settings/nodes/node-1/agents/new", null],
    ["/settings/agents/agent-1", null],
    ["/settings/nodes", null],
    ["/settings/policies", null],
    ["/settings/account", null]
  ] as const)("renders %s inside a full-height column container", async (entry, marker) => {
    const { container } = renderSettingsShell(entry);

    const panel = container.querySelector("aside")?.nextElementSibling;
    if (marker) {
      await waitFor(() => {
        expect(panel?.querySelector(marker)).not.toBeNull();
      });
    } else {
      await waitFor(() => {
        expect(panel?.textContent?.length ?? 0).toBeGreaterThan(0);
      });
    }
    expect(panel).toHaveClass("h-full");
    expect(panel).toHaveClass("flex");
    expect(panel).toHaveClass("flex-col");
    expect(container.querySelector("nav")).toBeInTheDocument();
  });
});

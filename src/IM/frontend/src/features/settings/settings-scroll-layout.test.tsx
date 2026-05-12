import { waitFor } from "@testing-library/react";

import { appRoutes } from "../../app/router";
import { renderRouter } from "../../test/render-router";

function renderSettingsShell(initialEntry = "/settings/agents") {
  return renderRouter({ routes: appRoutes, initialEntries: [initialEntry] });
}

describe("settings page chrome (M19 R1 — no sub-nav)", () => {
  // M19/R11-2: 移除 Settings 二级侧栏/sub-nav pill — Agents/Nodes/Account 三页直渲,
  // 不再共享 SettingsPageShell 的 240px aside。每页需独立全高占满主区。
  it.each([
    ["/settings/agents", '[data-testid="agents-list"]'],
    ["/settings/nodes/node-1/agents/new", null],
    ["/settings/agents/agent-1", null],
    ["/settings/nodes", null],
    ["/settings/account", null]
  ] as const)("renders %s without the Settings sub-nav", async (entry, marker) => {
    const { container } = renderSettingsShell(entry);

    await waitFor(() => {
      expect(container.textContent?.length ?? 0).toBeGreaterThan(0);
    });

    if (marker) {
      await waitFor(() => {
        expect(container.querySelector(marker)).not.toBeNull();
      });
    }

    expect(container.querySelector('nav[aria-label="Settings Sections"]')).toBeNull();
  });
});

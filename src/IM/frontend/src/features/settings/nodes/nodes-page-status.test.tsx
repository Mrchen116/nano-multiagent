import { screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();

globalThis.fetch = fetchMock as typeof fetch;

afterEach(() => {
  fetchMock.mockReset();
});

function mockNodes(nodes: unknown[]) {
  // Settings page calls /im/v1/nodes; agent-list call comes from /im/v1/agents.
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url === "/im/v1/nodes") {
      return Promise.resolve(
        new Response(JSON.stringify(nodes), { status: 200, headers: { "Content-Type": "application/json" } })
      );
    }
    if (url === "/im/v1/agents") {
      return Promise.resolve(
        new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } })
      );
    }
    return Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
  });
}

describe("nodes page — status pill + last_error + empty state", () => {
  it("renders an online pill with green dot for online nodes and a red pill for offline nodes", async () => {
    mockNodes([
      {
        node_id: "node-a",
        owner_id: "owner-1",
        node_name: "node-a",
        status: "online",
        last_heartbeat_at: "2026-05-11T10:00:00Z",
        agent_count: 2,
        version: "1.8.2",
        relay_enabled: true,
        reporting_enabled: true,
        alias: null,
        last_error: null
      },
      {
        node_id: "node-b",
        owner_id: "owner-1",
        node_name: "node-b",
        status: "offline",
        last_heartbeat_at: "2026-05-08T10:00:00Z",
        agent_count: 0,
        version: "1.8.2",
        relay_enabled: false,
        reporting_enabled: false,
        alias: null,
        last_error: "connection refused"
      }
    ]);

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    const onlinePill = await screen.findByTestId("node-status-pill-node-a");
    expect(onlinePill).toHaveTextContent(/online/i);
    expect(onlinePill.querySelector('[data-status-dot="online"]')).toBeInTheDocument();

    const offlinePill = await screen.findByTestId("node-status-pill-node-b");
    expect(offlinePill).toHaveTextContent(/offline/i);
    expect(offlinePill.querySelector('[data-status-dot="offline"]')).toBeInTheDocument();

    // last_error should be rendered with a warning class (oklch warm-red prototype palette).
    const errorEl = screen.getByTestId("node-last-error-node-b");
    expect(errorEl).toHaveTextContent("connection refused");
    expect(errorEl.className).toMatch(/text-red-|0\.14_25|0\.45_0\.14/);
  });

  it("renders an empty-state message when the owner has no nodes", async () => {
    mockNodes([]);

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    expect(await screen.findByTestId("nodes-empty")).toBeInTheDocument();
  });
});

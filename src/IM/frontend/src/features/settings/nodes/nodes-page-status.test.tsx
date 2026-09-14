import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";
import { NodesPage } from "./nodes-page";

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
    if (url === "/im/v1/sync") {
      return Promise.resolve(
        new Response(JSON.stringify({ items: [], max_event_id: 0 }), { status: 200, headers: { "Content-Type": "application/json" } })
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

    const errorEl = screen.getByTestId("node-last-error-node-b");
    expect(errorEl).toHaveTextContent("connection refused");
  });

  it("explains binding when there are no devices and refreshes into the device list", async () => {
    mockNodes([]);

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    expect(await screen.findByTestId("nodes-empty")).toBeInTheDocument();
    expect(screen.getByText(/Open the binding link provided by Gateway/)).toBeInTheDocument();
    expect(screen.queryByTestId("nodes-kpi-grid")).not.toBeInTheDocument();

    mockNodes([{
      node_id: "new-device", node_name: "My laptop", owner_id: "owner-1", status: "online",
      last_heartbeat_at: null, agent_count: 0, version: "1.8.2", alias: null,
      relay_enabled: true, reporting_enabled: true, last_error: null
    }]);
    await userEvent.setup().click(screen.getByRole("button", { name: "Refresh devices" }));

    expect(await screen.findByRole("heading", { name: "My laptop" })).toBeInTheDocument();
    expect(screen.queryByTestId("nodes-empty")).not.toBeInTheDocument();
    expect(screen.getByText("Heartbeat")).toBeInTheDocument();
  });

  it("keeps loaded devices and Heartbeat visible when a background refresh fails", async () => {
    mockNodes([{
      node_id: "node-a", node_name: "My laptop", owner_id: "owner-1", status: "online",
      last_heartbeat_at: null, agent_count: 0, version: "1.8.2", alias: null,
      relay_enabled: true, reporting_enabled: true, last_error: null
    }]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter><NodesPage /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole("heading", { name: "My laptop" })).toBeInTheDocument();

    fetchMock.mockRejectedValue(new Error("Network unavailable"));
    await act(async () => {
      await client.refetchQueries({ queryKey: ["settings", "nodes"] });
      // React Query batches observer notifications on the next timer tick.
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(client.getQueryState(["settings", "nodes"])?.status).toBe("error");
    expect(screen.getByRole("heading", { name: "My laptop" })).toBeInTheDocument();
    expect(screen.getByText("Heartbeat")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    client.clear();
  });
});

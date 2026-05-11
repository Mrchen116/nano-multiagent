import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();

globalThis.fetch = fetchMock as typeof fetch;

afterEach(() => {
  fetchMock.mockReset();
});

describe("nodes page", () => {
  it("shows node-scoped create entry only for online nodes and edits aliases via IM APIs", async () => {
    const user = userEvent.setup();
    const nodes = [
      {
        node_id: "node-app-01",
        owner_id: "owner-1",
        node_name: "node-app-01",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 4,
        version: "1.8.2",
        relay_enabled: true,
        reporting_enabled: true,
        alias: null,
        last_error: null
      },
      {
        node_id: "node-app-02",
        owner_id: "owner-1",
        node_name: "node-app-02",
        status: "offline",
        last_heartbeat_at: "2026-03-13T09:00:00Z",
        agent_count: 1,
        version: "1.8.2",
        relay_enabled: true,
        reporting_enabled: true,
        alias: null,
        last_error: "gateway disconnected"
      }
    ];
    const patchedNode = { ...nodes[0], alias: "node-app-01-prod" };
    const nodesAfter = [patchedNode];

    let nodesCallCount = 0;
    let patchCall: { url: string; init?: RequestInit } | null = null;
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes" && (init?.method ?? "GET") === "GET") {
        nodesCallCount += 1;
        const payload = nodesCallCount === 1 ? nodes : nodesAfter;
        return Promise.resolve(
          new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } })
        );
      }
      if (url === "/im/v1/nodes/node-app-01/config" && init?.method === "PATCH") {
        patchCall = { url, init };
        return Promise.resolve(
          new Response(JSON.stringify(patchedNode), { status: 200, headers: { "Content-Type": "application/json" } })
        );
      }
      if (url === "/im/v1/agents") {
        return Promise.resolve(
          new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } })
        );
      }
      return Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
    });

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/nodes"]
    });

    expect(await screen.findByRole("link", { name: "Create agent on node-app-01" })).toHaveAttribute("href", "/settings/nodes/node-app-01/agents/new");
    expect(screen.queryByRole("link", { name: "Create agent on node-app-02" })).not.toBeInTheDocument();

    const aliasInput = await screen.findByLabelText("Alias node-app-01");
    await user.clear(aliasInput);
    await user.type(aliasInput, "node-app-01-prod");
    await user.click(screen.getByRole("button", { name: "Save node-app-01" }));

    expect(await screen.findByDisplayValue("node-app-01-prod")).toBeInTheDocument();
    expect(patchCall).not.toBeNull();
    expect(patchCall!.init!.body).toBe(
      JSON.stringify({ alias: "node-app-01-prod", relay_enabled: true, reporting_enabled: true })
    );
  });
});

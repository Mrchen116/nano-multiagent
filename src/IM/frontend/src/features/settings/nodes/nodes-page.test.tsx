import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as typeof fetch;

afterEach(() => fetchMock.mockReset());

describe("nodes page", () => {
  it("offers creation only on online nodes and saves an alias through the node API", async () => {
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
    let patchCall: RequestInit | undefined;
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes/node-app-01/config" && init?.method === "PATCH") {
        patchCall = init;
        return Promise.resolve(jsonResponse(patchedNode));
      }
      if (url === "/im/v1/nodes") return Promise.resolve(jsonResponse(nodes));
      if (url === "/im/v1/agents") return Promise.resolve(jsonResponse({ items: [] }));
      if (url === "/im/v1/sync") return Promise.resolve(jsonResponse({ items: [], max_event_id: 0 }));
      if (url === "/im/v1/conversations") return Promise.resolve(jsonResponse({ items: [] }));
      return Promise.resolve(new Response(null, { status: 404 }));
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    expect(await screen.findByRole("link", { name: "+ New agent on node" })).toHaveAttribute(
      "href",
      "/settings/nodes/node-app-01/agents/new"
    );
    expect(screen.queryByTestId("nodes-card-new-agent-node-app-02")).toBeNull();

    const alias = await screen.findByLabelText("Alias node-app-01");
    await user.clear(alias);
    await user.type(alias, "node-app-01-prod");
    await user.click(screen.getByRole("button", { name: "Save node-app-01" }));

    expect(await screen.findByDisplayValue("node-app-01-prod")).toBeInTheDocument();
    expect(JSON.parse(String(patchCall?.body))).toEqual({
      alias: "node-app-01-prod",
      relay_enabled: true,
      reporting_enabled: true
    });
  });
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

import { screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as typeof fetch;

afterEach(() => {
  fetchMock.mockReset();
});

describe("nodes page — prototype-aligned node cards", () => {
  it("omits the node-scoped agent list because the prototype only shows aggregate counts", async () => {
    let agentsRequested = false;
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes") {
        return Promise.resolve(
          new Response(
            JSON.stringify([
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
                status: "online",
                last_heartbeat_at: "2026-05-11T10:00:00Z",
                agent_count: 0,
                version: "1.8.2",
                relay_enabled: true,
                reporting_enabled: true,
                alias: null,
                last_error: null
              }
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      if (url === "/im/v1/agents") {
        agentsRequested = true;
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      return Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    expect(await screen.findByTestId("node-agent-count-node-a")).toHaveTextContent("2");
    expect(screen.queryByTestId("node-agents-node-a")).toBeNull();
    expect(screen.queryByRole("link", { name: "Ops Bot" })).toBeNull();
    expect(agentsRequested).toBe(false);
  });
});

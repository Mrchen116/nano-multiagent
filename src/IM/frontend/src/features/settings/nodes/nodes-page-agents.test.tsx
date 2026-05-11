import { screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as typeof fetch;

afterEach(() => {
  fetchMock.mockReset();
});

describe("nodes page — node-scoped agent list", () => {
  it("renders the agents that live on each node with a link to the agent detail page", async () => {
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
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  agent_id: "agent-1",
                  owner_id: "owner-1",
                  display_name: "Ops Bot",
                  description: "",
                  profile_version: 1,
                  default_model: null,
                  workspace_root: "/tmp",
                  workspace_is_default: true,
                  node_id: "node-a"
                },
                {
                  agent_id: "agent-2",
                  owner_id: "owner-1",
                  display_name: "Code Bot",
                  description: "",
                  profile_version: 1,
                  default_model: null,
                  workspace_root: "/tmp",
                  workspace_is_default: true,
                  node_id: "node-a"
                }
              ]
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    // node-a should list two agents, each linking to its detail page.
    const opsLink = await screen.findByRole("link", { name: "Ops Bot" });
    expect(opsLink).toHaveAttribute("href", "/settings/agents/agent-1");
    const codeLink = await screen.findByRole("link", { name: "Code Bot" });
    expect(codeLink).toHaveAttribute("href", "/settings/agents/agent-2");

    // node-b has no agents; the per-node section must show the empty hint.
    const nodeBSection = await screen.findByTestId("node-agents-node-b");
    expect(nodeBSection).toHaveTextContent(/No agents on this node yet|本节点上还没有/);
  });
});

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
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
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
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            node_id: "node-app-01",
            owner_id: "owner-1",
            node_name: "node-app-01",
            status: "online",
            last_heartbeat_at: "2026-03-13T10:00:00Z",
            agent_count: 4,
            version: "1.8.2",
            relay_enabled: true,
            reporting_enabled: true,
            alias: "node-app-01-prod",
            last_error: null
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
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
              alias: "node-app-01-prod",
              last_error: null
            }
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );

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
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/im/v1/nodes", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/im/v1/nodes/node-app-01/config",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ alias: "node-app-01-prod", relay_enabled: true, reporting_enabled: true })
      })
    );
  });
});

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

describe("account page", () => {
  it("loads and saves account settings through IM APIs (Bearer auth, no user_id query)", async () => {
    const user = userEvent.setup();
    let displayName = "CZJ";
    let defaultEntryNodeId = "node-app-01";

    const meResponse = () =>
      new Response(
        JSON.stringify({
          id: "user-1",
          user_id: "user-1",
          username: "you",
          display_name: displayName,
          owner_id: "owner-1",
          owned_node_ids: ["node-app-01", "node-app-02"],
          default_entry_node_id: defaultEntryNodeId,
          created_at: "2026-03-13T10:00:00Z"
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );

    fetchMock.mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/me" && init?.method === "PATCH") {
        const payload = JSON.parse(String(init.body)) as { display_name: string; default_entry_node_id: string };
        displayName = payload.display_name;
        defaultEntryNodeId = payload.default_entry_node_id;
        return meResponse();
      }
      if (url === "/im/v1/me") {
        return meResponse();
      }
      if (url === "/im/v1/nodes") {
        return new Response(
          JSON.stringify([
            {
              node_id: "node-app-01",
              owner_id: "owner-1",
              node_name: "MacBook",
              status: "online",
              last_heartbeat_at: "2026-03-13T10:00:00Z",
              agent_count: 2,
              version: "1.0.0",
              relay_enabled: true,
              reporting_enabled: true,
              alias: "MacBook",
              last_error: null
            },
            {
              node_id: "node-app-02",
              owner_id: "owner-1",
              node_name: "Mini",
              status: "online",
              last_heartbeat_at: "2026-03-13T10:01:00Z",
              agent_count: 1,
              version: "1.0.1",
              relay_enabled: true,
              reporting_enabled: true,
              alias: "Mini",
              last_error: null
            }
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(null, { status: 404 });
    });

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/account"]
    });

    const displayNameInput = await screen.findByLabelText("Display Name");
    await user.clear(displayNameInput);
    await user.type(displayNameInput, "CZJ Ops");
    await user.selectOptions(screen.getByLabelText("Default Entry Node"), "node-app-02");
    await user.click(screen.getByRole("button", { name: "Save Account" }));

    expect(await screen.findByDisplayValue("CZJ Ops")).toBeInTheDocument();
    expect(screen.getByLabelText("Default Entry Node")).toHaveValue("node-app-02");
    expect(fetchMock).toHaveBeenCalledWith("/im/v1/me", expect.any(Object));
    expect(fetchMock).toHaveBeenCalledWith(
      "/im/v1/me",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ display_name: "CZJ Ops", default_entry_node_id: "node-app-02" })
      })
    );
    // Ensure no legacy endpoints were called
    for (const call of fetchMock.mock.calls) {
      expect(String(call[0])).not.toContain("/im/v1/users");
      expect(String(call[0])).not.toContain("user_id=");
    }
  });
});

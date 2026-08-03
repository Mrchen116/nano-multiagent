import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { setLanguage } from "../../../i18n";
import { renderRouter } from "../../../test/render-router";
import { useAuthStore } from "../../auth/auth-store";

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as typeof fetch;

const SAMPLE_USER = {
  id: "user-1",
  username: "alex",
  display_name: "Alex Chen",
  owner_id: "user-1",
  locale: "en",
  default_entry_node_id: "node-app-01",
  owned_node_ids: ["node-app-01", "node-app-02"],
  created_at: "2026-03-13T10:00:00Z"
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function meBody(overrides: Partial<typeof SAMPLE_USER> = {}) {
  return {
    ...SAMPLE_USER,
    user_id: SAMPLE_USER.id,
    ...overrides
  };
}

function nodesBody() {
  return [
    {
      node_id: "node-app-01",
      owner_id: "user-1",
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
      owner_id: "user-1",
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
  ];
}

function mockAccountApi() {
  let stored = meBody();
  fetchMock.mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url === "/im/v1/me" && init?.method === "PATCH") {
      stored = { ...stored, ...JSON.parse(String(init.body)) };
      return jsonResponse(stored);
    }
    if (url === "/im/v1/me") return jsonResponse(stored);
    if (url === "/im/v1/nodes") return jsonResponse(nodesBody());
    if (url === "/im/v1/sync") return jsonResponse({ items: [], max_event_id: 0 });
    if (url === "/im/v1/conversations") return jsonResponse({ items: [] });
    return new Response(null, { status: 404 });
  });
}

beforeEach(() => {
  localStorage.clear();
  setLanguage("en");
  useAuthStore.getState().setSession({
    access_token: "t",
    refresh_token: "r",
    user: SAMPLE_USER
  });
});

afterEach(() => {
  fetchMock.mockReset();
  localStorage.clear();
  useAuthStore.getState().clear();
});

describe("account settings", () => {
  it("loads account defaults and saves profile and entry-node changes", async () => {
    const user = userEvent.setup();
    mockAccountApi();

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/account"] });

    const displayName = await screen.findByLabelText(/display name/i);
    expect(displayName).toHaveValue("Alex Chen");
    expect(screen.getByLabelText(/default entry node/i)).toHaveValue("node-app-01");

    await user.clear(displayName);
    await user.type(displayName, "Alex Ops");
    await user.selectOptions(screen.getByLabelText(/default entry node/i), "node-app-02");
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(
        ([url, init]) => url === "/im/v1/me" && (init as RequestInit)?.method === "PATCH"
      );
      expect(JSON.parse(String((patchCall?.[1] as RequestInit).body))).toEqual({
        display_name: "Alex Ops",
        default_entry_node_id: "node-app-02",
        locale: "en"
      });
    });
    expect(useAuthStore.getState().user?.display_name).toBe("Alex Ops");
  });

  it("discards pending edits and disables saving again", async () => {
    const user = userEvent.setup();
    mockAccountApi();

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/account"] });

    const displayName = await screen.findByLabelText(/display name/i);
    await user.clear(displayName);
    await user.type(displayName, "Changed");
    expect(screen.getByRole("button", { name: /save/i })).not.toBeDisabled();

    await user.click(screen.getByRole("button", { name: /discard/i }));

    expect(await screen.findByDisplayValue("Alex Chen")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });
});

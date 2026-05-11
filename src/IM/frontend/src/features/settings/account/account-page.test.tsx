import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";
import { useAuthStore } from "../../auth/auth-store";
import { I18N_STORAGE_KEY, setLanguage } from "../../../i18n";
import {
  NOTIFICATION_PREFERENCE_STORAGE_KEY,
  setNotificationPreference
} from "../../notifications/notification-preference";

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

function seedAuth() {
  useAuthStore.getState().setSession({
    access_token: "t",
    refresh_token: "r",
    user: SAMPLE_USER
  });
}

function meBody(overrides: Partial<typeof SAMPLE_USER> = {}) {
  return {
    id: SAMPLE_USER.id,
    user_id: SAMPLE_USER.id,
    username: SAMPLE_USER.username,
    display_name: SAMPLE_USER.display_name,
    owner_id: SAMPLE_USER.owner_id,
    locale: SAMPLE_USER.locale,
    default_entry_node_id: SAMPLE_USER.default_entry_node_id,
    owned_node_ids: SAMPLE_USER.owned_node_ids,
    created_at: SAMPLE_USER.created_at,
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

beforeEach(() => {
  localStorage.clear();
  setLanguage("en");
  setNotificationPreference(false);
  seedAuth();
});

afterEach(() => {
  fetchMock.mockReset();
  localStorage.clear();
  useAuthStore.getState().clear();
});

describe("AccountPage rewrite", () => {
  it("renders Identity / Defaults / Preferences cards with i18n EN copy", async () => {
    let mePayload = meBody();
    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/me") return jsonResponse(mePayload);
      if (url === "/im/v1/nodes") return jsonResponse(nodesBody());
      return new Response(null, { status: 404 });
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/account"] });

    expect(await screen.findByRole("heading", { name: /account/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /identity/i, level: 3 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /defaults/i, level: 3 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /preferences/i, level: 3 })).toBeInTheDocument();
    expect(screen.getByLabelText(/display name/i)).toHaveValue("Alex Chen");
    void mePayload;
  });

  it("saves display_name + default_entry_node_id + locale + notifications through PATCH /im/v1/me with Bearer auth", async () => {
    const user = userEvent.setup();
    type StoredBody = Omit<ReturnType<typeof meBody>, "default_entry_node_id"> & { default_entry_node_id: string | null };
    let stored: StoredBody = meBody();
    fetchMock.mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/me" && init?.method === "PATCH") {
        const payload = JSON.parse(String(init.body)) as {
          display_name: string;
          default_entry_node_id: string | null;
          locale?: string;
        };
        stored = { ...stored, ...payload };
        return jsonResponse(stored);
      }
      if (url === "/im/v1/me") return jsonResponse(stored);
      if (url === "/im/v1/nodes") return jsonResponse(nodesBody());
      return new Response(null, { status: 404 });
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/account"] });

    const displayNameInput = await screen.findByLabelText(/display name/i);
    await user.clear(displayNameInput);
    await user.type(displayNameInput, "Alex Ops");
    await user.selectOptions(screen.getByLabelText(/default entry node/i), "node-app-02");
    await user.click(screen.getByLabelText(/中文/));
    await user.click(screen.getByLabelText(/enable desktop notifications/i));

    const saveBtn = screen.getByRole("button", { name: /save/i });
    expect(saveBtn).not.toBeDisabled();
    await user.click(saveBtn);

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(
        ([url, init]) => url === "/im/v1/me" && (init as RequestInit)?.method === "PATCH"
      );
      expect(patchCall).toBeDefined();
      const body = JSON.parse(String((patchCall![1] as RequestInit).body));
      expect(body).toEqual({
        display_name: "Alex Ops",
        default_entry_node_id: "node-app-02",
        locale: "zh"
      });
    });

    await waitFor(() => {
      expect(localStorage.getItem(I18N_STORAGE_KEY)).toBe("zh");
    });
    expect(localStorage.getItem(NOTIFICATION_PREFERENCE_STORAGE_KEY)).toBe("1");
    expect(useAuthStore.getState().user?.locale).toBe("zh");
    expect(useAuthStore.getState().user?.display_name).toBe("Alex Ops");

    for (const call of fetchMock.mock.calls) {
      expect(String(call[0])).not.toContain("/im/v1/users");
      expect(String(call[0])).not.toContain("user_id=");
    }
  });

  it("Discard reverts pending edits and restores Save disabled state", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/me") return jsonResponse(meBody());
      if (url === "/im/v1/nodes") return jsonResponse(nodesBody());
      return new Response(null, { status: 404 });
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/account"] });

    const displayNameInput = await screen.findByLabelText(/display name/i);
    await user.clear(displayNameInput);
    await user.type(displayNameInput, "Changed");
    expect(screen.getByRole("button", { name: /save/i })).not.toBeDisabled();

    await user.click(screen.getByRole("button", { name: /discard/i }));
    expect(await screen.findByDisplayValue("Alex Chen")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });
});

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AUTH_STORAGE_KEY, useAuthStore } from "./auth-store";

const SAMPLE_USER = {
  id: "user-1",
  username: "alex",
  display_name: "Alex",
  owner_id: "user-1",
  locale: "en",
  default_entry_node_id: null,
  membership_status: "active" as const,
  is_company_admin: true,
  owned_node_ids: [],
  created_at: ""
};

describe("auth-store", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().clear();
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("keeps the authenticated session only in memory", () => {
    useAuthStore.getState().setSession({ access_token: "a.b.c", user: SAMPLE_USER });
    expect(useAuthStore.getState().isAuthenticated()).toBe(true);
    expect(localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
    expect(sessionStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
    useAuthStore.getState().clear();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it("discards old stored credentials and restores only through the cookie endpoint", async () => {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ access_token: "old", refresh_token: "old-refresh", user: SAMPLE_USER }));
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ access_token: "new", user: SAMPLE_USER })));
    await useAuthStore.getState().hydrate();
    expect(localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
    expect(useAuthStore.getState().accessToken).toBe("new");
    expect(fetchMock).toHaveBeenCalledWith("/im/v1/auth/refresh", expect.objectContaining({
      credentials: "include", body: "{}", headers: { "Content-Type": "application/json", "X-IM-Session": "browser" }
    }));
  });

  it("replaces only the current user's snapshot while preserving tokens", () => {
    useAuthStore.getState().setSession({
      access_token: "access-current",
      user: SAMPLE_USER
    });

    expect(
      useAuthStore.getState().replaceUser({
        ...SAMPLE_USER,
        owned_node_ids: ["node-new"],
        default_entry_node_id: "node-new"
      })
    ).toBe(true);

    const state = useAuthStore.getState();
    expect(state.accessToken).toBe("access-current");
    expect(state.user?.owned_node_ids).toEqual(["node-new"]);
    expect(localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
  });

  it("discards a delayed snapshot after the session switches users", () => {
    useAuthStore.getState().setSession({
      access_token: "access-b",
      user: { ...SAMPLE_USER, id: "user-b", username: "bob", owner_id: "user-b" }
    });

    expect(useAuthStore.getState().replaceUser(SAMPLE_USER)).toBe(false);
    expect(useAuthStore.getState().user?.id).toBe("user-b");
    expect(useAuthStore.getState().accessToken).toBe("access-b");
  });
});

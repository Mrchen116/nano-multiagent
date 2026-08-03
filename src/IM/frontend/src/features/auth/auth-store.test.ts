import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AUTH_STORAGE_KEY, useAuthStore } from "./auth-store";

const SAMPLE_USER = {
  id: "user-1",
  username: "alex",
  display_name: "Alex",
  owner_id: "user-1",
  locale: "en",
  default_entry_node_id: null,
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
  });

  it("persists and clears the authenticated session", () => {
    useAuthStore.getState().setSession({
      access_token: "a.b.c",
      refresh_token: "r.t",
      user: SAMPLE_USER
    });

    expect(useAuthStore.getState().isAuthenticated()).toBe(true);
    expect(useAuthStore.getState().user?.id).toBe("user-1");
    expect(useAuthStore.getState().accessToken).toBe("a.b.c");

    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed.access_token).toBe("a.b.c");
    expect(parsed.user.id).toBe("user-1");

    useAuthStore.getState().clear();

    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
  });

  it("rehydrates from localStorage via hydrate()", () => {
    localStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({
        access_token: "a.b.c",
        refresh_token: "r.t",
        user: SAMPLE_USER
      })
    );

    useAuthStore.getState().hydrate();

    expect(useAuthStore.getState().accessToken).toBe("a.b.c");
    expect(useAuthStore.getState().user?.username).toBe("alex");
  });

  it("ignores malformed localStorage payloads instead of crashing", () => {
    localStorage.setItem(AUTH_STORAGE_KEY, "not-json");
    useAuthStore.getState().hydrate();
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("replaces only the current user's snapshot while preserving tokens", () => {
    useAuthStore.getState().setSession({
      access_token: "access-current",
      refresh_token: "refresh-current",
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
    expect(state.refreshToken).toBe("refresh-current");
    expect(state.user?.owned_node_ids).toEqual(["node-new"]);
    expect(JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) ?? "{}")).toMatchObject({
      access_token: "access-current",
      refresh_token: "refresh-current",
      user: { id: "user-1", default_entry_node_id: "node-new" }
    });
  });

  it("discards a delayed snapshot after the session switches users", () => {
    useAuthStore.getState().setSession({
      access_token: "access-b",
      refresh_token: "refresh-b",
      user: { ...SAMPLE_USER, id: "user-b", username: "bob", owner_id: "user-b" }
    });

    expect(useAuthStore.getState().replaceUser(SAMPLE_USER)).toBe(false);
    expect(useAuthStore.getState().user?.id).toBe("user-b");
    expect(useAuthStore.getState().accessToken).toBe("access-b");
  });
});

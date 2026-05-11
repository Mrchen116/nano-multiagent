import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authFetch } from "./auth-fetch";
import { useAuthStore } from "./auth-store";

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

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("authFetch", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("injects Authorization header from the auth store", async () => {
    useAuthStore.getState().setSession({
      access_token: "tok-1",
      refresh_token: "r-1",
      user: SAMPLE_USER
    });

    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(makeResponse(200, { ok: true }));

    await authFetch("/im/v1/agents");

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer tok-1");
  });

  it("on 401 calls /im/v1/auth/refresh once and retries the original request with the new token", async () => {
    useAuthStore.getState().setSession({
      access_token: "expired",
      refresh_token: "r-1",
      user: SAMPLE_USER
    });

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(makeResponse(401, { detail: "expired" }))
      .mockResolvedValueOnce(
        makeResponse(200, {
          access_token: "fresh",
          refresh_token: "r-2",
          user: SAMPLE_USER
        })
      )
      .mockResolvedValueOnce(makeResponse(200, { ok: true }));

    const res = await authFetch("/im/v1/agents");
    expect(res.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);

    const refreshCall = fetchMock.mock.calls[1];
    expect(String(refreshCall[0])).toContain("/im/v1/auth/refresh");
    expect((refreshCall[1] as RequestInit).method).toBe("POST");

    const retryHeaders = new Headers((fetchMock.mock.calls[2][1] as RequestInit).headers);
    expect(retryHeaders.get("Authorization")).toBe("Bearer fresh");
    expect(useAuthStore.getState().accessToken).toBe("fresh");
    expect(useAuthStore.getState().refreshToken).toBe("r-2");
  });

  it("clears the session if refresh fails", async () => {
    useAuthStore.getState().setSession({
      access_token: "expired",
      refresh_token: "stale",
      user: SAMPLE_USER
    });

    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(makeResponse(401, { detail: "expired" }))
      .mockResolvedValueOnce(makeResponse(401, { detail: "refresh failed" }));

    const res = await authFetch("/im/v1/agents");
    expect(res.status).toBe(401);
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it("does not attempt refresh when no refresh_token is present", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(makeResponse(401, { detail: "unauth" }));

    const res = await authFetch("/im/v1/agents");
    expect(res.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

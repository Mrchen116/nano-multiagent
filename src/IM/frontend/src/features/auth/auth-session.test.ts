import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authFetch } from "./auth-fetch";
import { ensureFreshSession } from "./auth-session";
import { useAuthStore, type AuthUser } from "./auth-store";

const USER_A: AuthUser = {
  id: "user-a",
  username: "alice",
  display_name: "Alice",
  owner_id: "user-a",
  locale: "en",
  default_entry_node_id: null,
  owned_node_ids: [],
  created_at: ""
};

const USER_B: AuthUser = { ...USER_A, id: "user-b", username: "bob", display_name: "Bob", owner_id: "user-b" };

function accessToken(expiresInSeconds: number): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + expiresInSeconds }));
  return `${header}.${payload}.signature`;
}

function response(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function session(user: AuthUser, access: string, refresh: string): void {
  useAuthStore.getState().setSession({ access_token: access, refresh_token: refresh, user });
}

describe("auth session readiness", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("returns a fresh access token without refreshing", async () => {
    const token = accessToken(120);
    session(USER_A, token, "refresh-a");
    const fetchMock = vi.spyOn(globalThis, "fetch");

    await expect(ensureFreshSession()).resolves.toEqual({ status: "ready", userId: "user-a", accessToken: token });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("single-flights refresh when the access token is near expiry", async () => {
    session(USER_A, accessToken(10), "refresh-a");
    const fresh = accessToken(120);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response(200, { access_token: fresh, refresh_token: "refresh-a2", user: USER_A })
    );

    const [left, right] = await Promise.all([ensureFreshSession(), ensureFreshSession()]);

    expect(left).toEqual({ status: "ready", userId: "user-a", accessToken: fresh });
    expect(right).toEqual(left);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shares the in-tab refresh between WebSocket readiness and authFetch 401 recovery", async () => {
    session(USER_A, accessToken(-1), "refresh-a");
    const fresh = accessToken(120);
    let refreshCalls = 0;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/auth/refresh")) {
        refreshCalls += 1;
        return response(200, { access_token: fresh, refresh_token: "refresh-a2", user: USER_A });
      }
      const authorization = new Headers(init?.headers).get("Authorization");
      return authorization === `Bearer ${fresh}` ? response(200, { ok: true }) : response(401, { detail: "expired" });
    });

    const [readiness, httpResponse] = await Promise.all([ensureFreshSession(), authFetch("/im/v1/agents")]);

    expect(readiness).toEqual({ status: "ready", userId: "user-a", accessToken: fresh });
    expect(httpResponse.ok).toBe(true);
    expect(refreshCalls).toBe(1);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("returns retry and keeps the session when refresh has a temporary server failure", async () => {
    const expired = accessToken(-1);
    session(USER_A, expired, "refresh-a");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response(503, { detail: "temporary" }));

    await expect(ensureFreshSession()).resolves.toEqual({ status: "retry" });
    expect(useAuthStore.getState().accessToken).toBe(expired);
    expect(useAuthStore.getState().user?.id).toBe("user-a");
  });

  it("returns retry and keeps the session when refresh cannot reach the server", async () => {
    const expired = accessToken(-1);
    session(USER_A, expired, "refresh-a");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network down"));

    await expect(ensureFreshSession()).resolves.toEqual({ status: "retry" });
    expect(useAuthStore.getState().accessToken).toBe(expired);
  });

  it("clears only the matching session when the refresh credential is rejected", async () => {
    session(USER_A, accessToken(-1), "refresh-a");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response(401, { detail: "invalid refresh" }));

    await expect(ensureFreshSession()).resolves.toEqual({ status: "signed_out" });
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("does not let user A's delayed refresh overwrite user B", async () => {
    session(USER_A, accessToken(-1), "refresh-a");
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      await gate;
      return response(200, {
        access_token: accessToken(120),
        refresh_token: "refresh-a2",
        user: USER_A
      });
    });

    const pending = ensureFreshSession();
    session(USER_B, accessToken(120), "refresh-b");
    release();

    await expect(pending).resolves.toEqual({ status: "retry" });
    expect(useAuthStore.getState().user?.id).toBe("user-b");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-b");
  });

  it("does not share user A's rejected refresh flight with user B", async () => {
    session(USER_A, accessToken(-1), "refresh-a");
    let releaseA!: () => void;
    const gateA = new Promise<void>((resolve) => {
      releaseA = resolve;
    });
    const freshB = accessToken(120);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      const refreshToken = JSON.parse(String(init?.body)) as { refresh_token: string };
      if (refreshToken.refresh_token === "refresh-a") {
        await gateA;
        return response(401, { detail: "invalid refresh" });
      }
      return response(200, {
        access_token: freshB,
        refresh_token: "refresh-b2",
        user: USER_B
      });
    });

    const pendingA = ensureFreshSession();
    session(USER_B, accessToken(-1), "refresh-b");
    const pendingB = ensureFreshSession();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    releaseA();

    await expect(pendingA).resolves.toEqual({ status: "signed_out" });
    await expect(pendingB).resolves.toEqual({ status: "ready", userId: "user-b", accessToken: freshB });
    expect(useAuthStore.getState().user?.id).toBe("user-b");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-b2");
  });
});

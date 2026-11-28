import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authFetch } from "./auth-fetch";
import { AuthApiError } from "./auth-api";
import { ensureFreshSession, logout, login, adoptPageSession, restoreSession } from "./auth-session";
import { useAuthStore, type AuthUser } from "./auth-store";

const USER_A: AuthUser = {
  id: "user-a",
  username: "alice",
  display_name: "Alice",
  owner_id: "user-a",
  locale: "en",
  default_entry_node_id: null,
  membership_status: "active" as const,
  is_company_admin: true,
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

function session(user: AuthUser, access: string, _refresh: string): void {
  useAuthStore.getState().setSession({ access_token: access, user });
}

describe("auth session readiness", () => {
  const originalLocks = Object.getOwnPropertyDescriptor(window.navigator, "locks");
  const originalBroadcastChannel = Object.getOwnPropertyDescriptor(globalThis, "BroadcastChannel");

  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    if (originalLocks) Object.defineProperty(window.navigator, "locks", originalLocks);
    if (originalBroadcastChannel) Object.defineProperty(globalThis, "BroadcastChannel", originalBroadcastChannel);
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("keeps document sessions subscribed to cross-tab logout",()=>{
    adoptPageSession({access_token:accessToken(120),user:USER_A});
    const other=new BroadcastChannel('im-session');
    other.postMessage('logout');
    expect(useAuthStore.getState().user).toBeNull();
    other.close();
  });

  it('rejects HTML from before a completed login during document loading',async()=>{
    vi.spyOn(globalThis,'fetch').mockResolvedValue(response(200,{access_token:'account-b',user:USER_B}));
    await login({username:'bob',password:'password'});
    // Simulate the new document whose listener missed that login broadcast.
    useAuthStore.getState().clear();useAuthStore.setState({hydrated:false});
    expect(adoptPageSession({access_token:'old-account-a',user:USER_A})).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().hydrated).toBe(false);
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
      response(200, { access_token: fresh, user: USER_A })
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
        return response(200, { access_token: fresh, user: USER_A });
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

  it.each([200, 401])("does not let user A's delayed %s refresh overwrite user B", async (status) => {
    session(USER_A, accessToken(-1), "refresh-a");
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      await gate;
      return response(status, {
        access_token: accessToken(120),
        user: USER_A
      });
    });

    const pending = ensureFreshSession();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    session(USER_B, accessToken(120), "refresh-b");
    release();

    await expect(pending).resolves.toEqual({ status: "retry" });
    expect(useAuthStore.getState().user?.id).toBe("user-b");

  });

  it("serializes logout after an in-flight refresh and ignores its stale result", async () => {
    session(USER_A, accessToken(-1), "unused");
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async input => {
      if (String(input).endsWith("/refresh")) {
        await gate;
        return response(200, { access_token: "stale", user: USER_A });
      }
      return response(200, { ok: true });
    });
    const pending = ensureFreshSession();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const signingOut = logout();
    expect(useAuthStore.getState().user).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    release();
    await expect(pending).resolves.toEqual({ status: "retry" });
    await signingOut;
    expect(String(fetchMock.mock.calls[1][0])).toContain("/logout");
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("broadcasts only explicit session changes without credentials", async () => {
    const observer = new BroadcastChannel("im-session");
    const messages: unknown[] = [];
    observer.onmessage = event => messages.push(event.data);
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => response(200, { access_token: "fresh", user: USER_A }));
    await login({ username: "alice", password: "password" });
    await ensureFreshSession();
    expect(messages).toEqual(["login"]);
    await logout();
    expect(messages).toEqual(["login", "logout"]);
    observer.close();
  });

  it("drops the previous identity on another tab's login and restores the new cookie session", async () => {
    session(USER_A, accessToken(120), "unused");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(200, { access_token: "b", user: USER_B }));
    const other = new BroadcastChannel("im-session");
    other.postMessage("login");
    expect(useAuthStore.getState().user).toBeNull();
    await vi.waitFor(() => expect(useAuthStore.getState().user?.id).toBe(USER_B.id));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    other.postMessage("logout");
    expect(useAuthStore.getState().user).toBeNull();
    other.close();
  });

  it("aborts a stuck cross-tab Web Lock and degrades to refreshing once", async () => {
    vi.useFakeTimers();
    useAuthStore.setState({ hydrated: false, hydrationError: false, user: null, accessToken: null });
    let capturedSignal: AbortSignal | undefined;
    let grantStuckLock: (() => void) | undefined;
    Object.defineProperty(window.navigator, "locks", {
      configurable: true,
      value: {
        request(_name: string, optionsOrOp: { signal?: AbortSignal } | (() => Promise<unknown>), maybeOp?: () => Promise<unknown>) {
          const op = typeof optionsOrOp === "function" ? optionsOrOp : maybeOp!;
          const signal = typeof optionsOrOp === "function" ? undefined : optionsOrOp?.signal;
          capturedSignal = signal;
          return new Promise((resolve, reject) => {
            signal?.addEventListener("abort", () => reject(signal.reason ?? new DOMException("Aborted", "AbortError")), { once: true });
            grantStuckLock = () => resolve(op());
          });
        }
      }
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response(200, { access_token: accessToken(120), user: USER_A })
    );

    const restoring = restoreSession();
    await vi.advanceTimersByTimeAsync(8_000);
    await restoring;

    expect(capturedSignal?.aborted).toBe(true);
    expect(useAuthStore.getState().hydrated).toBe(true);
    expect(useAuthStore.getState().user?.id).toBe(USER_A.id);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    grantStuckLock?.();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("recovers even if a non-standard Web Lock ignores AbortSignal and never settles", async () => {
    vi.useFakeTimers();
    useAuthStore.setState({ hydrated: false, hydrationError: false, user: null, accessToken: null });
    let lateGrant: (() => Promise<unknown>) | undefined;
    Object.defineProperty(window.navigator, "locks", {
      configurable: true,
      value: {
        request(_name: string, optionsOrOp: unknown, maybeOp?: () => Promise<unknown>) {
          const op = typeof optionsOrOp === "function" ? (optionsOrOp as () => Promise<unknown>) : maybeOp!;
          lateGrant = op;
          return new Promise(() => {});
        }
      }
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(401, { detail: "no session" }));

    const restoring = restoreSession();
    await vi.advanceTimersByTimeAsync(8_000);
    await restoring;

    expect(useAuthStore.getState().hydrated).toBe(true);
    expect(useAuthStore.getState().user).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await lateGrant?.();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not replay an operation that failed after acquiring the session lock", async () => {
    Object.defineProperty(window.navigator, "locks", {
      configurable: true,
      value: {
        request(_name: string, optionsOrOp: unknown, maybeOp?: () => Promise<unknown>) {
          const op = typeof optionsOrOp === "function" ? (optionsOrOp as () => Promise<unknown>) : maybeOp!;
          return op();
        }
      }
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(401, { detail: "invalid credentials" }));

    await expect(login({ username: "alice", password: "wrong" })).rejects.toBeInstanceOf(AuthApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("completes restore, login, refresh, and logout when Web Locks and BroadcastChannel are unavailable", async () => {
    Object.defineProperty(window.navigator, "locks", { configurable: true, value: undefined });
    Object.defineProperty(globalThis, "BroadcastChannel", { configurable: true, value: undefined });
    useAuthStore.setState({ hydrated: false, hydrationError: false, user: null, accessToken: null });

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response(401, { detail: "no cookie" }))
      .mockResolvedValueOnce(response(200, { access_token: accessToken(10), user: USER_A }))
      .mockResolvedValueOnce(response(200, { access_token: accessToken(120), user: USER_A }))
      .mockResolvedValueOnce(response(200, { ok: true }));

    await restoreSession();
    expect(useAuthStore.getState().hydrated).toBe(true);
    expect(useAuthStore.getState().user).toBeNull();

    await login({ username: "alice", password: "password" });
    expect(useAuthStore.getState().user?.id).toBe(USER_A.id);

    await expect(ensureFreshSession()).resolves.toMatchObject({ status: "ready", userId: USER_A.id });
    await logout();
    expect(useAuthStore.getState().user).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("keeps revision protection when lock acquisition times out after a newer session arrives", async () => {
    vi.useFakeTimers();
    useAuthStore.setState({ hydrated: false, hydrationError: false, user: null, accessToken: null });
    Object.defineProperty(window.navigator, "locks", {
      configurable: true,
      value: { request: () => new Promise(() => {}) }
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(200, { ok: true }));

    const staleRestore = restoreSession();
    const staleLogout = logout();
    useAuthStore.getState().setSession({ access_token: accessToken(120), user: USER_B }, true);

    await vi.advanceTimersByTimeAsync(8_000);
    await Promise.all([staleRestore, staleLogout]);

    expect(useAuthStore.getState().user?.id).toBe(USER_B.id);
    expect(useAuthStore.getState().hydrationError).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("aborts a hung refresh request so hydration converges to hydrationError", async () => {
    vi.useFakeTimers();
    useAuthStore.setState({ hydrated: false, hydrationError: false, user: null, accessToken: null });
    let requestSignal: AbortSignal | null | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      requestSignal = init?.signal;
      return new Promise((_, reject) => {
        init?.signal?.addEventListener("abort", () => reject(init.signal?.reason ?? new DOMException("Aborted", "AbortError")), { once: true });
      });
    });

    const restoring = restoreSession();
    await vi.advanceTimersByTimeAsync(10_000);
    await restoring;

    expect(requestSignal?.aborted).toBe(true);
    expect(useAuthStore.getState().hydrated).toBe(false);
    expect(useAuthStore.getState().hydrationError).toBe(true);
  });
});

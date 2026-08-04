import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "../auth/auth-store";
import { confirmBindToken, getAccount, updateAccount } from "./im-settings-api";

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

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("im-settings-api", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().setSession({
      access_token: "tok-1",
      refresh_token: "r-1",
      user: SAMPLE_USER
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("reads the authenticated account from /im/v1/me", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(200, {
        id: "user-1",
        user_id: "user-1",
        username: "alex",
        display_name: "Alex",
        owner_id: "user-1",
        owned_node_ids: [],
        default_entry_node_id: null,
        created_at: ""
      })
    );

    const result = await getAccount();
    expect(result.user_id).toBe("user-1");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    const urlStr = String(url);
    expect(urlStr).toContain("/im/v1/me");
    expect(urlStr).not.toContain("user_id=");
    const headers = new Headers((init as RequestInit | undefined)?.headers);
    expect(headers.get("Authorization")).toBe("Bearer tok-1");
  });

  it("confirms a bind token using bearer ownership without a user_id payload", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(201, { node_id: "node-new" })
    );

    await expect(confirmBindToken("bind-once")).resolves.toEqual({ node_id: "node-new" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/im/v1/bind");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      action: "confirm",
      bind_token: "bind-once"
    });
  });

  it("updateAccount PATCHes /im/v1/me with Bearer token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(200, {
        id: "user-1",
        user_id: "user-1",
        username: "alex",
        display_name: "Alex 2",
        owner_id: "user-1",
        owned_node_ids: [],
        default_entry_node_id: "node-1",
        created_at: ""
      })
    );

    const result = await updateAccount({ display_name: "Alex 2", default_entry_node_id: "node-1" });
    expect(result.display_name).toBe("Alex 2");

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/im/v1/me");
    expect((init as RequestInit).method).toBe("PATCH");
    const headers = new Headers((init as RequestInit).headers);
    expect(headers.get("Authorization")).toBe("Bearer tok-1");
  });
});

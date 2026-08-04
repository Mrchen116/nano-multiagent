import { act, render } from "@testing-library/react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { useAuthStore } from "../features/auth/auth-store";
import { App } from "./App";
import { AppProviders } from "./providers";
import * as streamModule from "../realtime/user-stream";

const SAMPLE_USER = {
  id: "user-1",
  username: "you",
  display_name: "You",
  owner_id: "user-1",
  locale: "en",
  default_entry_node_id: null,
  owned_node_ids: [],
  created_at: ""
};

let capturedQueryClient: QueryClient | null = null;

function QueryClientCapture() {
  capturedQueryClient = useQueryClient();
  return null;
}

describe("App shell", () => {
  beforeEach(() => {
    capturedQueryClient = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    localStorage.clear();
    useAuthStore.getState().setSession({
      access_token: "t",
      refresh_token: "r",
      user: SAMPLE_USER
    });
    Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 1280 });
  });

  afterEach(() => vi.restoreAllMocks());

  it("uses one notification stream coordinator even off the chat route", () => {
    const fake = vi.fn(() => ({ onclick: null, close: vi.fn() })) as unknown as typeof Notification & {
      permission: NotificationPermission;
      requestPermission: () => Promise<NotificationPermission>;
    };
    fake.permission = "granted";
    fake.requestPermission = vi.fn(async (): Promise<NotificationPermission> => "granted");
    (globalThis as unknown as { Notification: unknown }).Notification = fake;
    const spy = vi.spyOn(streamModule, "subscribeUserStream").mockImplementation(() => () => undefined);
    render(
      <AppProviders>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </AppProviders>
    );
    expect(spy).toHaveBeenCalledTimes(1);
    spy.mockRestore();
    delete (globalThis as unknown as { Notification?: unknown }).Notification;
  });

  it("keeps cache for same-user refresh and clears it when the authenticated identity changes or leaves", () => {
    render(
      <AppProviders>
        <QueryClientCapture />
      </AppProviders>
    );
    capturedQueryClient!.setQueryData(["chat", "conversations"], ["cached"]);

    act(() => useAuthStore.getState().setTokens({ access_token: "t-2", refresh_token: "r-2" }));
    expect(capturedQueryClient!.getQueryData(["chat", "conversations"])).toEqual(["cached"]);

    capturedQueryClient!.setQueryData(["settings", "nodes"], ["user-a-node"]);
    act(() => useAuthStore.getState().setSession({
      access_token: "user-b-token",
      refresh_token: "user-b-refresh",
      user: { ...SAMPLE_USER, id: "user-2", username: "other", owner_id: "user-2" }
    }));

    expect(capturedQueryClient!.getQueryData(["settings", "nodes"])).toBeUndefined();

    capturedQueryClient!.setQueryData(["chat", "conversations"], ["user-b-cache"]);
    act(() => useAuthStore.getState().clear());
    expect(capturedQueryClient!.getQueryData(["chat", "conversations"])).toBeUndefined();
  });
});

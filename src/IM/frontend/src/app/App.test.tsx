import { act, render, screen } from "@testing-library/react";
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

  it("renders the Chat and Agents top-level navigation entries", () => {
    render(
      <AppProviders>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </AppProviders>
    );

    expect(screen.getByRole("link", { name: /chat/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /agents/i })).toBeInTheDocument();
  });

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

  it("keeps server cache for same-user token refresh and clears it on logout", () => {
    render(
      <AppProviders>
        <QueryClientCapture />
      </AppProviders>
    );
    capturedQueryClient!.setQueryData(["chat", "conversations"], ["cached"]);

    act(() => useAuthStore.getState().setTokens({ access_token: "t-2", refresh_token: "r-2" }));
    expect(capturedQueryClient!.getQueryData(["chat", "conversations"])).toEqual(["cached"]);

    act(() => useAuthStore.getState().clear());
    expect(capturedQueryClient!.getQueryData(["chat", "conversations"])).toBeUndefined();
  });

  it("clears server cache when the authenticated user changes", () => {
    render(
      <AppProviders>
        <QueryClientCapture />
      </AppProviders>
    );
    capturedQueryClient!.setQueryData(["settings", "nodes"], ["user-a-node"]);

    act(() => useAuthStore.getState().setSession({
      access_token: "user-b-token",
      refresh_token: "user-b-refresh",
      user: { ...SAMPLE_USER, id: "user-2", username: "other", owner_id: "user-2" }
    }));

    expect(capturedQueryClient!.getQueryData(["settings", "nodes"])).toBeUndefined();
  });

  it("renders a banner and a main region so the shell wraps routed content", () => {
    render(
      <AppProviders>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </AppProviders>
    );

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { useAuthStore } from "../features/auth/auth-store";
import { App } from "./App";
import { AppProviders } from "./providers";
import * as streamModule from "../features/chat/v2/chat-stream";

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

describe("App shell", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().setSession({
      access_token: "t",
      refresh_token: "r",
      user: SAMPLE_USER
    });
    Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 1280 });
  });

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

  it("mounts AgentCompletionNotifier so it can fire desktop notifications even off the chat route", () => {
    const fake = vi.fn(() => ({ onclick: null, close: vi.fn() })) as unknown as typeof Notification & {
      permission: NotificationPermission;
      requestPermission: () => Promise<NotificationPermission>;
    };
    fake.permission = "granted";
    fake.requestPermission = vi.fn(async (): Promise<NotificationPermission> => "granted");
    (globalThis as unknown as { Notification: unknown }).Notification = fake;
    const spy = vi.spyOn(streamModule, "openChatStream").mockImplementation(() => ({ close: () => {} }));
    render(
      <AppProviders>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </AppProviders>
    );
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
    delete (globalThis as unknown as { Notification?: unknown }).Notification;
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

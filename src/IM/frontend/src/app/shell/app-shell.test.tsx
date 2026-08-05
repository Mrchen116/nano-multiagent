import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { useAuthStore } from "../../features/auth/auth-store";
import { LoginPage } from "../../features/auth/login-page";
import { setLanguage } from "../../i18n";
import { AppShell } from "./app-shell";

vi.mock("../../features/chat/chat-api", async () => {
  const actual = await vi.importActual<typeof import("../../features/chat/chat-api")>(
    "../../features/chat/chat-api"
  );
  return { ...actual, listConversations: vi.fn() };
});

import { listConversations } from "../../features/chat/chat-api";

const SAMPLE_USER = {
  id: "user-1",
  username: "alex",
  display_name: "Alex Chen",
  owner_id: "user-1",
  locale: "en",
  default_entry_node_id: null,
  owned_node_ids: [],
  created_at: ""
};

function setViewportWidth(width: number) {
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: width });
  window.dispatchEvent(new Event("resize"));
}

function renderShell(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/*" element={<AppShell>{<div data-testid="content">main-content</div>}</AppShell>} />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AppShell", () => {
  beforeEach(() => {
    localStorage.clear();
    setLanguage("en");
    useAuthStore.getState().setSession({
      access_token: "t",
      refresh_token: "r",
      user: SAMPLE_USER
    });
    setViewportWidth(1280);
    (listConversations as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("renders the desktop top banner with Chat/Agents tabs and a UserMenu trigger", () => {
    renderShell("/chat");
    const banner = screen.getByRole("banner");
    expect(banner).toBeInTheDocument();
    expect(within(banner).getByText(/nano im/i)).toBeInTheDocument();
    expect(within(banner).getByRole("link", { name: /chat/i })).toHaveAttribute("href", "/chat");
    expect(within(banner).getByRole("link", { name: /agents/i })).toHaveAttribute("href", "/settings/agents");
    expect(within(banner).getByRole("button", { name: /alex chen/i })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: /mobile/i })).not.toBeInTheDocument();
  });

  it("renders the mobile bottom nav with three tabs below 768px", () => {
    setViewportWidth(640);
    renderShell("/chat");
    const mobile = screen.getByRole("navigation", { name: /mobile/i });
    expect(within(mobile).getByRole("link", { name: /chat/i })).toHaveAttribute("href", "/chat");
    expect(within(mobile).getByRole("link", { name: /agents/i })).toHaveAttribute("href", "/settings/agents");
    expect(within(mobile).getByRole("link", { name: /me/i })).toHaveAttribute("href", "/me");
  });

  it("UserMenu sign-out clears auth store", async () => {
    renderShell("/chat");
    await userEvent.click(screen.getByRole("button", { name: /alex chen/i }));
    await userEvent.click(screen.getByRole("menuitem", { name: /sign out/i }));
    await waitFor(() => {
      expect(useAuthStore.getState().user).toBeNull();
    });
  });

  it("shows the summed unread count on the mobile Chat tab", async () => {
    (listConversations as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      { id: "c1", title: "A", kind: "agent-user", participants: [], unread_count: 2, last_message_at: null },
      { id: "c2", title: "B", kind: "agent-user", participants: [], unread_count: 3, last_message_at: null }
    ]);
    setViewportWidth(640);
    renderShell("/chat");
    const mobile = screen.getByRole("navigation", { name: /mobile/i });
    await waitFor(() => {
      expect(within(mobile).getByTestId("shell-chat-unread")).toHaveTextContent("5");
    });
  });
});

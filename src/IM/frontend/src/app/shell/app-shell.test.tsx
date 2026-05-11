import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { useAuthStore } from "../../features/auth/auth-store";
import { setLanguage } from "../../i18n";
import { AppShell } from "./app-shell";

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
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/*" element={<AppShell>{<div data-testid="content">main-content</div>}</AppShell>} />
      </Routes>
    </MemoryRouter>
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
    expect(useAuthStore.getState().user).toBeNull();
  });
});

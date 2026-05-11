import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { useAuthStore } from "../auth/auth-store";
import { I18N_STORAGE_KEY, setLanguage } from "../../i18n";
import { MePage } from "./me-page";

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

function renderMe() {
  return render(
    <MemoryRouter initialEntries={["/me"]}>
      <Routes>
        <Route path="/me" element={<MePage />} />
        <Route path="/login" element={<div data-testid="login-page" />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("MePage", () => {
  beforeEach(() => {
    localStorage.clear();
    setLanguage("en");
    useAuthStore.getState().setSession({
      access_token: "t",
      refresh_token: "r",
      user: SAMPLE_USER
    });
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("shows account / nodes / language / sign-out entries with EN copy by default", () => {
    renderMe();
    expect(screen.getByRole("heading", { name: /me/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /account/i })).toHaveAttribute("href", "/settings/account");
    expect(screen.getByRole("link", { name: /nodes/i })).toHaveAttribute("href", "/settings/nodes");
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("switching language to 中文 changes visible copy and persists to localStorage", async () => {
    renderMe();
    await userEvent.click(screen.getByLabelText(/中文/));
    expect(screen.getByRole("heading", { name: "我" })).toBeInTheDocument();
    expect(localStorage.getItem(I18N_STORAGE_KEY)).toBe("zh");
  });

  it("sign-out clears the auth store and redirects to /login", async () => {
    renderMe();
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(useAuthStore.getState().user).toBeNull();
    expect(screen.getByTestId("login-page")).toBeInTheDocument();
  });
});

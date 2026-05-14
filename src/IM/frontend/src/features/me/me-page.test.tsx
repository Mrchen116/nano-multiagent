import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { useAuthStore } from "../auth/auth-store";
import { I18N_STORAGE_KEY, setLanguage } from "../../i18n";
import { MePage } from "./me-page";

vi.mock("../settings/im-settings-api", () => ({
  listNodes: vi.fn(async () => [])
}));

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
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/me"]}>
        <Routes>
          <Route path="/me" element={<MePage />} />
          <Route path="/login" element={<div data-testid="login-page" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
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
    await userEvent.click(screen.getByRole("button", { name: /^中$/ }));
    expect(screen.getByRole("heading", { name: "我" })).toBeInTheDocument();
    expect(localStorage.getItem(I18N_STORAGE_KEY)).toBe("zh");
  });

  it("sign-out clears the auth store and redirects to /login", async () => {
    renderMe();
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(useAuthStore.getState().user).toBeNull();
    expect(screen.getByTestId("login-page")).toBeInTheDocument();
  });

  // M20/R12-bis-6: Notifications row removed from Me page (prototype has no
  // notifications row; toggle lives in UserMenu / browser permission flow).

  it("R8-4: surfaces the user identity card with display_name + user_id in monospace", () => {
    renderMe();
    const identity = screen.getByTestId("me-identity-card");
    expect(identity.textContent).toMatch(/Alex Chen/);
    expect(identity.textContent).toMatch(/user-1/);
    const idElement = screen.getByTestId("me-identity-user-id");
    // user_id should be set in monospace per prototype.
    expect(idElement.className).toMatch(/mono|font-mono/);
  });

  it("R8-4: language picker renders a pill toggle (buttons), not radio inputs", () => {
    renderMe();
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.getByRole("button", { name: /^EN$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^中$/ })).toBeInTheDocument();
  });

  it("R8-4: each menu row carries a leading icon glyph", () => {
    renderMe();
    expect(screen.getByTestId("me-row-nodes").textContent).toMatch(/🖥/);
    expect(screen.getByTestId("me-row-account").textContent).toMatch(/👤/);
    expect(screen.getByTestId("me-row-signout").textContent).toMatch(/↗/);
  });

  // M19/R11-1: prototype `im-mypage.jsx` AggregatedMePage 是白卡 list 视觉,
  // 当前实现使用未定义的 im-me-* CSS 类,渲染结果是裸文字粘连无样式("视觉 0")。
  // 必须保证每张卡片都带可见的视觉容器类 (rounded + bg-white + 分隔线 / 阴影),
  // Sign out 必须 danger 红色,Language pill toggle 必须有 active 视觉状态,
  // identity 卡的大 avatar 必须有圆形几何。

  it("R11-1: identity card has avatar circle + name + monospace user_id", () => {
    renderMe();
    const identity = screen.getByTestId("me-identity-card");
    const avatar = identity.querySelector('[data-testid="me-identity-avatar"]');
    expect(avatar).not.toBeNull();
    expect(avatar?.className).toMatch(/rounded-full/);
    expect(identity.querySelector('[data-testid="me-identity-chevron"]')?.textContent).toBe("›");
  });

  it("R11-1: each row container renders a white rounded card with visible classes", () => {
    renderMe();
    for (const testId of ["me-row-nodes", "me-row-account", "me-row-language", "me-row-signout"]) {
      const row = screen.getByTestId(testId);
      const card = row.closest('[data-testid^="me-card-"]');
      expect(card).not.toBeNull();
      expect(card?.className).toMatch(/bg-white/);
      expect(card?.className).toMatch(/rounded/);
    }
  });

  it("R11-1: sign-out row uses danger red text", () => {
    renderMe();
    const row = screen.getByTestId("me-row-signout");
    expect(row.className).toMatch(/text-red|text-rose/);
  });

  it("R11-1: every row carries a trailing chevron except language", () => {
    renderMe();
    for (const testId of ["me-row-nodes", "me-row-account"]) {
      const row = screen.getByTestId(testId);
      const chevrons = row.querySelectorAll('[data-testid="me-row-chevron"]');
      expect(chevrons.length).toBeGreaterThan(0);
      expect(chevrons[0].textContent).toBe("›");
    }
  });

  it("R11-1: language pill toggle marks the active option visually", () => {
    renderMe();
    const enBtn = screen.getByRole("button", { name: /^EN$/ });
    const zhBtn = screen.getByRole("button", { name: /^中$/ });
    expect(enBtn.getAttribute("aria-pressed")).toBe("true");
    expect(zhBtn.getAttribute("aria-pressed")).toBe("false");
    // active option must carry a non-empty distinguishing class set
    expect(enBtn.className).toMatch(/bg-white|bg-slate-50|shadow/);
  });
});

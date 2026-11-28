import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { useAuthStore } from "../auth/auth-store";
import { I18N_STORAGE_KEY, setLanguage } from "../../i18n";
import { LoginPage } from "../auth/login-page";
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
  membership_status: "active" as const,
  is_company_admin: true,
  owned_node_ids: [],
  created_at: ""
};

function setViewportWidth(width: number) {
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: width });
  window.dispatchEvent(new Event("resize"));
}

function renderMe() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/me"]}>
        <Routes>
          <Route path="/me" element={<MePage />} />
          <Route path="/settings/account" element={<div data-testid="desktop-account-dest">Account settings</div>} />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("MePage", () => {
  beforeEach(() => {
    localStorage.clear();
    setLanguage("en");
    setViewportWidth(390);
    useAuthStore.getState().setSession({
      access_token: "t",
      user: SAMPLE_USER
    });
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("shows @username without leaking internal user.id and renders clear user-facing titles and subtitles in EN", () => {
    renderMe();
    expect(screen.getByRole("heading", { name: /me/i })).toBeInTheDocument();
    expect(screen.getByText("Alex Chen")).toBeInTheDocument();
    expect(screen.getByText("@alex")).toBeInTheDocument();
    expect(screen.queryByText("user-1")).not.toBeInTheDocument();
    expect(screen.getByTestId("me-row-account")).toHaveAttribute("href", "/settings/account");
    expect(screen.getByTestId("me-row-nodes")).toHaveAttribute("href", "/settings/nodes");
    expect(screen.getByTestId("me-row-nodes")).toHaveTextContent("Nodes");
    expect(screen.getByTestId("me-row-nodes")).toHaveTextContent(/Computers and servers running your assistants/i);
    expect(screen.getByRole("link", { name: /AI Models & API/i })).toHaveAttribute("href", "/settings/models");
    expect(screen.getByRole("link", { name: /AI Models & API/i })).toHaveTextContent(/AI model providers and API keys/i);
    expect(screen.getByTestId("me-row-policies")).toHaveAttribute("href", "/settings/policies");
    expect(screen.getByTestId("me-row-policies")).toHaveTextContent("Usage & Policies");
    expect(screen.getByTestId("me-row-policies")).toHaveTextContent(/Attachment storage usage and team presets/i);
    expect(screen.getByRole("link", { name: /Team members/i })).toHaveAttribute("href", "/settings/company");
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("gracefully omits @ handle when username is blank without falling back to internal user.id", () => {
    useAuthStore.getState().setSession({
      access_token: "t",
      user: { ...SAMPLE_USER, id: "uuid-secret-999", username: "" }
    });
    renderMe();
    expect(screen.getByText("Alex Chen")).toBeInTheDocument();
    expect(screen.queryByText(/uuid-secret-999/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("me-identity-username")).not.toBeInTheDocument();
  });

  it("redirects desktop viewports away from /me to /settings/account", () => {
    setViewportWidth(1280);
    renderMe();
    expect(screen.getByTestId("desktop-account-dest")).toBeInTheDocument();
    expect(screen.queryByTestId("me-page")).not.toBeInTheDocument();
  });

  it("switching language to 中文 changes visible copy to plain Chinese terms and persists to localStorage", async () => {
    renderMe();
    await userEvent.click(screen.getByRole("button", { name: /^中$/ }));
    expect(screen.getByRole("heading", { name: "我" })).toBeInTheDocument();
    expect(screen.getByTestId("me-row-nodes")).toHaveTextContent("节点");
    expect(screen.getByTestId("me-row-nodes")).toHaveTextContent("运行助手的电脑与服务器");
    expect(screen.getByRole("link", { name: /AI 模型与 API/ })).toHaveTextContent("模型接入与 API 密钥配置");
    expect(screen.getByTestId("me-row-policies")).toHaveTextContent("用量与团队规则");
    expect(screen.getByTestId("me-row-policies")).toHaveTextContent("附件存储用量与团队运行预设");
    expect(screen.getByRole("link", { name: /成员管理/ })).toHaveTextContent("成员审批与团队访问权限");
    expect(localStorage.getItem(I18N_STORAGE_KEY)).toBe("zh");
  });

  it("sign-out clears the auth store and redirects to /login", async () => {
    renderMe();
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(useAuthStore.getState().user).toBeNull();
    expect(screen.getByRole("heading", { name: /welcome back/i })).toBeInTheDocument();
  });

});

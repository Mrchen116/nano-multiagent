import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RequireAuth } from "./require-auth";
import { MembershipPage } from "./membership-page";
import { LoginPage } from "./login-page";
import { useAuthStore } from "./auth-store";
import { TEST_AUTH_USER } from "../../test/render-router";
import { CompanyMembersPage } from "../settings/company/company-members-page";
import { PoliciesPage } from "../settings/policies/policies-page";
import { setLanguage } from "../../i18n";

function mount(entry = "/chat") {
  const router = createMemoryRouter([
    { path: "/chat", element: <RequireAuth><p>Company secrets</p></RequireAuth> },
    { path: "/membership", element: <MembershipPage /> },
    { path: "/login", element: <LoginPage /> },
    { path: "/settings/company", element: <CompanyMembersPage /> },
    { path: "/settings/policies", element: <PoliciesPage /> }
  ], { initialEntries: [entry] });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}
const response = (value: unknown, status = 200, headers = {}) => new Response(JSON.stringify(value), { status, headers });

describe("company access", () => {
  beforeEach(() => {
    localStorage.clear(); setLanguage("en");
    useAuthStore.getState().setSession({ access_token: "active-token", refresh_token: "refresh", user: TEST_AUTH_USER });
  });
  afterEach(() => vi.restoreAllMocks());

  it("does not flash cached company content before current membership is verified", async () => {
    let resolve!: (response: Response) => void;
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => new Promise(done => { resolve = done; }));
    mount();
    expect(screen.queryByText("Company secrets")).not.toBeInTheDocument();
    resolve(response({ ...TEST_AUTH_USER, membership_status: "pending" }));
    expect(await screen.findByRole("heading", { name: "Waiting for approval" })).toBeInTheDocument();
    expect(screen.queryByText("Company secrets")).not.toBeInTheDocument();
  });

  it("refreshes approval and returns to the original company destination", async () => {
    useAuthStore.getState().replaceUser({ ...TEST_AUTH_USER, membership_status: "pending" });
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => response(TEST_AUTH_USER));
    mount("/membership");
    await userEvent.click(screen.getByRole("button", { name: "Refresh status" }));
    expect(await screen.findByText("Company secrets")).toBeInTheDocument();
  });

  it("keeps entered credentials during server cooldown and disables retries", async () => {
    useAuthStore.getState().clear();
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ detail: "limited" }, 429, { "Retry-After": "30" }));
    mount("/login");
    await userEvent.type(screen.getByLabelText(/username/i), "alex");
    await userEvent.type(screen.getByLabelText(/^password$/i), "kept-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Try again in 30 seconds/);
    expect(screen.getByLabelText(/^password$/i)).toHaveValue("kept-password");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeDisabled();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("ordinary members cannot load the administrator member list", async () => {
    useAuthStore.getState().replaceUser({ ...TEST_AUTH_USER, is_company_admin: false });
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ ...TEST_AUTH_USER, is_company_admin: false }));
    mount("/settings/company");
    await screen.findByText("Company secrets");
    expect(fetch.mock.calls.some(([url]) => String(url).includes("/company/members"))).toBe(false);
  });

  it("keeps all six policy fields read-only for ordinary members", async () => {
    useAuthStore.getState().replaceUser({ ...TEST_AUTH_USER, is_company_admin: false });
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ default_model: "model", audit_level: "basic", max_turn_per_run: 10, rate_limit_per_min: 60, max_attachment_size_mb: 10, retention_days: 30 }));
    mount("/settings/policies");
    await screen.findByText("Only company administrators can edit policies.");
    expect(screen.getAllByRole("spinbutton")).toHaveLength(4);
    for (const field of [...screen.getAllByRole("spinbutton"), screen.getByRole("textbox"), screen.getByRole("combobox")]) expect(field).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  });
});

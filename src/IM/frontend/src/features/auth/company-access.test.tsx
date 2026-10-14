import { render, screen, waitFor, within } from "@testing-library/react";
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
    { path: "/chat", element: <RequireAuth><p>Protected app</p></RequireAuth> },
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
    useAuthStore.getState().setSession({ access_token: "active-token", user: TEST_AUTH_USER });
  });
  afterEach(() => vi.restoreAllMocks());

  it("does not flash cached company content before current membership is verified", async () => {
    let resolve!: (response: Response) => void;
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => new Promise(done => { resolve = done; }));
    mount();
    expect(screen.queryByText("Protected app")).not.toBeInTheDocument();
    resolve(response({ ...TEST_AUTH_USER, membership_status: "pending" }));
    expect(await screen.findByRole("heading", { name: "Waiting for approval" })).toBeInTheDocument();
    expect(screen.queryByText("Protected app")).not.toBeInTheDocument();
  });

  it("lets a personal user continue using the app while team approval is pending", async () => {
    const personal = { ...TEST_AUTH_USER, membership_status: "pending" as const, personal_space_enabled: true, account_status: "active" as const, is_company_admin: false };
    useAuthStore.getState().replaceUser(personal);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response(personal));
    mount();
    expect(await screen.findByText("Protected app")).toBeInTheDocument();
    expect(screen.queryByRole("heading", {name: "Waiting for approval"})).not.toBeInTheDocument();
  });

  it("does not retain company administration when a personal administrator is suspended", async () => {
    const personal = { ...TEST_AUTH_USER, membership_status: "suspended" as const, personal_space_enabled: true, account_status: "active" as const };
    useAuthStore.getState().replaceUser(personal);
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(personal));
    mount("/settings/company");
    await screen.findByText("Protected app");
    expect(fetch.mock.calls.some(([url]) => String(url).includes("/company/members"))).toBe(false);
  });

  it("refreshes approval and returns to the original company destination", async () => {
    useAuthStore.getState().replaceUser({ ...TEST_AUTH_USER, membership_status: "pending" });
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => response(TEST_AUTH_USER));
    mount("/membership");
    await userEvent.click(screen.getByRole("button", { name: "Refresh status" }));
    expect(await screen.findByText("Protected app")).toBeInTheDocument();
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
    await screen.findByText("Protected app");
    expect(fetch.mock.calls.some(([url]) => String(url).includes("/company/members"))).toBe(false);
  });

  it("keeps all six policy fields read-only for ordinary members", async () => {
    useAuthStore.getState().replaceUser({ ...TEST_AUTH_USER, is_company_admin: false });
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ default_model: "model", audit_level: "basic", max_turn_per_run: 10, rate_limit_per_min: 60, max_attachment_size_mb: 10, retention_days: 30 }));
    mount("/settings/policies");
    await screen.findByText("Only company administrators can edit policies.");
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(await screen.findByText("model")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  });

  it("identifies storage owners by display name and username, including duplicate names", async () => {
    useAuthStore.getState().replaceUser({ ...TEST_AUTH_USER, is_company_admin: true });
    const usage = { used_bytes: 1048576, reserved_bytes: 0, limit_bytes: 10485760, full: false };
    vi.spyOn(globalThis, "fetch").mockImplementation(async input => response(String(input).includes("/attachments/capacity") ? {
      service: usage,
      owners: [
        { ...usage, owner_id: "u_first", display_name: "Alex", username: "alex.design" },
        { ...usage, owner_id: "u_second", display_name: "Alex", username: "alex.engineering" }
      ]
    } : { default_model: "model", audit_level: "basic", max_turn_per_run: 10, rate_limit_per_min: 60, max_attachment_size_mb: 10, retention_days: 30 }));
    mount("/settings/policies");
    expect(await screen.findByText("@alex.design")).toBeInTheDocument();
    expect(screen.getByText("@alex.engineering")).toBeInTheDocument();
    expect(screen.getAllByText("Alex")).toHaveLength(2);
    expect(screen.queryByText("u_first")).not.toBeInTheDocument();
    expect(screen.queryByText("u_second")).not.toBeInTheDocument();
  });

  it("updates admission visibly and allows cancelling suspension without changing access", async () => {
    useAuthStore.getState().replaceUser({ ...TEST_AUTH_USER, is_company_admin: true });
    let member = { id: "member-1", username: "alex", display_name: "Alex", membership_status: "pending", is_company_admin: false, node_count: 2, agent_count: 3 };
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (init?.method === "POST") {
        member = { ...member, membership_status: "active" };
        return response(member);
      }
      return response({ members: [member], next_cursor: null });
    });
    mount("/settings/company");
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Alex can now access the company workspace.");
    await userEvent.click(await screen.findByRole("button", { name: "Suspend member" }));
    const dialog = screen.getByRole("dialog", { name: "Suspend Alex?" });
    expect(dialog).toHaveTextContent("2 nodes and 3 agents");
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(fetch.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
  });

  it("explains why the last administrator cannot be suspended", async () => {
    useAuthStore.getState().replaceUser({ ...TEST_AUTH_USER, is_company_admin: true });
    vi.spyOn(globalThis, "fetch").mockImplementation(async (_, init) => init?.method === "POST"
      ? response({ detail: "cannot suspend the last active administrator" }, 409)
      : response({ members: [{ ...TEST_AUTH_USER, is_company_admin: true, node_count: 1, agent_count: 2 }], next_cursor: null }));
    mount("/settings/company");
    await userEvent.click(await screen.findByRole("button", { name: "Suspend member" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm suspension" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The company must keep at least one active administrator.");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

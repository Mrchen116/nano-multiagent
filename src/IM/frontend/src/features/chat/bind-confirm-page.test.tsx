import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore, type AuthUser } from "../auth/auth-store";

const mocks = vi.hoisted(() => ({
  confirmBindToken: vi.fn(),
  getAccount: vi.fn(),
  navigate: vi.fn()
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => mocks.navigate };
});

vi.mock("../settings/im-settings-api", async () => {
  const actual = await vi.importActual<typeof import("../settings/im-settings-api")>(
    "../settings/im-settings-api"
  );
  return {
    ...actual,
    confirmBindToken: mocks.confirmBindToken,
    getAccount: mocks.getAccount
  };
});

import { BindConfirmPage } from "./bind-confirm-page";

const CURRENT_USER: AuthUser = {
  id: "user-1",
  username: "nano",
  display_name: "Test User",
  owner_id: "user-1",
  locale: "en",
  default_entry_node_id: null,
  owned_node_ids: [],
  created_at: "2026-07-13T00:00:00Z"
};

const NEXT_ACCOUNT = {
  ...CURRENT_USER,
  user_id: CURRENT_USER.id,
  owned_node_ids: ["node-new"],
  default_entry_node_id: "node-new"
};

const OWNER_DERIVED_KEYS = [
  ["chat", "conversations"],
  ["chat", "agents"],
  ["chat", "nodes"],
  ["settings", "account"],
  ["settings", "nodes"],
  ["settings", "agents"]
] as const;

function deferred() {
  let resolve!: () => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<void>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function renderPage(queryClient: QueryClient) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/bind/confirm?token=bind-once"]}>
        <BindConfirmPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("BindConfirmPage reconciliation", () => {
  beforeEach(() => {
    localStorage.clear();
    mocks.confirmBindToken.mockReset();
    mocks.getAccount.mockReset();
    mocks.navigate.mockReset();
    useAuthStore.getState().clear();
    useAuthStore.getState().setSession({
      access_token: "access-current",
      refresh_token: "refresh-current",
      user: CURRENT_USER
    });
  });

  it("replaces the user snapshot and waits for all six hot caches before navigating", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    OWNER_DERIVED_KEYS.forEach((queryKey) => queryClient.setQueryData(queryKey, { stale: true }));
    const refetches = OWNER_DERIVED_KEYS.map(() => deferred());
    const invalidateSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockImplementation(() => refetches[invalidateSpy.mock.calls.length - 1]!.promise);
    mocks.confirmBindToken.mockResolvedValue({ node_id: "node-new" });
    mocks.getAccount.mockResolvedValue(NEXT_ACCOUNT);
    renderPage(queryClient);

    await user.click(screen.getByRole("button", { name: "Continue to chat" }));

    await waitFor(() => expect(invalidateSpy).toHaveBeenCalledTimes(6));
    expect(mocks.confirmBindToken).toHaveBeenCalledTimes(1);
    expect(mocks.getAccount).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().user).toMatchObject({
      id: "user-1",
      owned_node_ids: ["node-new"],
      default_entry_node_id: "node-new"
    });
    expect(useAuthStore.getState().accessToken).toBe("access-current");
    expect(invalidateSpy.mock.calls.map(([filters]) => filters)).toEqual(
      OWNER_DERIVED_KEYS.map((queryKey) => ({ queryKey, refetchType: "all" }))
    );
    expect(mocks.navigate).not.toHaveBeenCalled();

    refetches.slice(0, 5).forEach((item) => item.resolve());
    await Promise.resolve();
    expect(mocks.navigate).not.toHaveBeenCalled();
    refetches[5]!.resolve();
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledWith("/chat", { replace: true }));
  });

  it("retries reconciliation without consuming the bind token again", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    OWNER_DERIVED_KEYS.forEach((queryKey) => queryClient.setQueryData(queryKey, { stale: true }));
    vi.spyOn(queryClient, "invalidateQueries").mockResolvedValue(undefined);
    mocks.confirmBindToken.mockResolvedValue({ node_id: "node-new" });
    mocks.getAccount
      .mockRejectedValueOnce(new Error("GET /im/v1/me failed: 503 (temporarily unavailable)"))
      .mockResolvedValueOnce(NEXT_ACCOUNT);
    renderPage(queryClient);

    await user.click(screen.getByRole("button", { name: "Continue to chat" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("temporarily unavailable");
    expect(mocks.confirmBindToken).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Continue to chat" }));
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledWith("/chat", { replace: true }));
    expect(mocks.confirmBindToken).toHaveBeenCalledTimes(1);
    expect(mocks.getAccount).toHaveBeenCalledTimes(2);
  });
});

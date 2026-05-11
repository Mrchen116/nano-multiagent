import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { AUTH_STORAGE_KEY, useAuthStore } from "./auth-store";
import { LoginPage } from "./login-page";
import { RequireAuth } from "./require-auth";

const SAMPLE_USER = {
  id: "user-7",
  username: "alex",
  display_name: "Alex",
  owner_id: "user-7",
  locale: "en",
  default_entry_node_id: null,
  owned_node_ids: [],
  created_at: ""
};

function ProtectedHello() {
  return <div data-testid="protected">welcome alex</div>;
}

function renderAt(initialPath: string) {
  const router = createMemoryRouter(
    [
      { path: "/login", element: <LoginPage /> },
      {
        path: "/",
        element: (
          <RequireAuth>
            <ProtectedHello />
          </RequireAuth>
        )
      },
      {
        path: "/chat",
        element: (
          <RequireAuth>
            <ProtectedHello />
          </RequireAuth>
        )
      }
    ],
    { initialEntries: [initialPath] }
  );
  return render(<RouterProvider router={router} />);
}

describe("auth gate", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("redirects to /login when unauthenticated", async () => {
    renderAt("/chat");
    expect(await screen.findByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
  });

  it("renders protected children when authenticated", async () => {
    useAuthStore.getState().setSession({
      access_token: "tok",
      refresh_token: "r",
      user: SAMPLE_USER
    });
    renderAt("/chat");
    expect(await screen.findByTestId("protected")).toBeInTheDocument();
  });

  it("logs in via POST /im/v1/auth/login and stores session", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          access_token: "tok-new",
          refresh_token: "r-new",
          user: SAMPLE_USER
        }),
        { status: 200, headers: { "content-type": "application/json" } }
      )
    );

    renderAt("/login");

    await userEvent.type(screen.getByLabelText(/username/i), "alex");
    await userEvent.type(screen.getByLabelText(/password/i), "secret");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(useAuthStore.getState().accessToken).toBe("tok-new");
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("/im/v1/auth/login");
    expect(localStorage.getItem(AUTH_STORAGE_KEY)).toContain("tok-new");
  });

  it("shows inline error on 401 login response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "invalid credentials" }), {
        status: 401,
        headers: { "content-type": "application/json" }
      })
    );

    renderAt("/login");

    await userEvent.type(screen.getByLabelText(/username/i), "alex");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid/i);
    expect(useAuthStore.getState().accessToken).toBeNull();
  });
});

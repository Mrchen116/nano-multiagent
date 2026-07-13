import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouteObject, RouterProvider } from "react-router-dom";

import { useAuthStore, type AuthUser } from "../features/auth/auth-store";

export const TEST_AUTH_USER: AuthUser = {
  id: "user-1",
  username: "you",
  display_name: "You",
  owner_id: "user-1",
  locale: "en",
  default_entry_node_id: "node-1",
  owned_node_ids: ["node-1"],
  created_at: ""
};

// Structurally valid test JWT with only an exp claim (2100-01-01). Runtime
// freshness tests own expiry behavior; route fixtures should stay authenticated.
export const TEST_ACCESS_TOKEN =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjQxMDI0NDQ4MDB9.test-signature";

/**
 * Test helper that wraps RouterProvider with QueryClient and seeds the auth store
 * with a default authenticated session, so RequireAuth-protected routes render
 * without each test having to wire up a login flow. Pass `auth: null` to test the
 * unauthenticated path (redirect to /login).
 */
export function renderRouter(options: {
  routes: RouteObject[];
  initialEntries: string[];
  auth?: AuthUser | null;
}) {
  const auth = options.auth === undefined ? TEST_AUTH_USER : options.auth;
  if (auth) {
    useAuthStore.getState().setSession({
      access_token: TEST_ACCESS_TOKEN,
      refresh_token: "test-refresh",
      user: auth
    });
  } else {
    useAuthStore.getState().clear();
  }

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  });

  const router = createMemoryRouter(options.routes, {
    initialEntries: options.initialEntries
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

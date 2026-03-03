import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouteObject, RouterProvider } from "react-router-dom";

export function renderRouter(options: { routes: RouteObject[]; initialEntries: string[] }) {
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

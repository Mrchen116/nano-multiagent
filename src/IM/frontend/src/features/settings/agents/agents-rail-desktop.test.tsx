import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({ listPublicAgents: vi.fn() }));
vi.mock("./public-agents", () => apiMocks);

import { AgentsRailDesktop } from "./agents-rail-desktop";

const SAMPLE_AGENTS = [
  { agent_id: "agent-one", user_id: "user-one", owner_id: "owner-1", display_name: "Planner", description: "Planning", node_name: "Mini", node_status: "online", work_mode: "single_thread" },
  { agent_id: "agent-two", user_id: "user-two", owner_id: "owner-2", display_name: "Researcher", description: "Research", node_name: "Laptop", node_status: "offline", work_mode: "global" }
];

function renderRail(onSelectAgent = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AgentsRailDesktop activeId="agent-one" onSelectAgent={onSelectAgent} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => apiMocks.listPublicAgents.mockReset());

it("pairs public Agent device fields with their rows and selects the clicked Agent", async () => {
  apiMocks.listPublicAgents.mockResolvedValue(SAMPLE_AGENTS);
  const onSelect = vi.fn();
  renderRail(onSelect);

  const planner = await screen.findByRole("button", { name: "Planner" });
  const researcher = screen.getByRole("button", { name: "Researcher" });
  expect(within(planner).getByText("Mini")).toBeVisible();
  expect(within(planner).queryByText("Laptop")).not.toBeInTheDocument();
  expect(within(researcher).getByText("Laptop")).toBeVisible();
  expect(planner).toHaveAttribute("aria-current", "page");
  expect(researcher).not.toHaveAttribute("aria-current");
  await userEvent.click(researcher);
  expect(onSelect).toHaveBeenCalledExactlyOnceWith("agent-two");
});

it("remains a desktop-only rail", async () => {
  apiMocks.listPublicAgents.mockResolvedValue([]);
  renderRail();
  expect(await screen.findByTestId("agents-rail-desktop")).toHaveClass("hidden", "lg:flex");
});

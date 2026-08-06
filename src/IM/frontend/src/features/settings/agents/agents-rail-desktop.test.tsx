import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

const listAgentSummaries = vi.hoisted(() => vi.fn());

vi.mock("./im-agent-config-api", () => ({
  listAgentSummaries
}));

import { AgentsRailDesktop } from "./agents-rail-desktop";

function renderRail() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AgentsRailDesktop activeId="agent-one" />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  listAgentSummaries.mockReset();
});

it("uses readable normal, hover, and active identity colors on the dark desktop rail", async () => {
  listAgentSummaries.mockResolvedValue([
    { agent_id: "agent-one", display_name: "Planner", node_status: "online" },
    { agent_id: "agent-two", display_name: "Researcher", node_status: "offline" }
  ]);

  renderRail();

  const activeRow = await screen.findByRole("button", { name: /Planner/i });
  const normalRow = screen.getByRole("button", { name: /Researcher/i });
  expect(activeRow).toHaveClass("bg-[oklch(0.31_0.015_240)]");
  expect(activeRow).toHaveClass("ring-1");
  expect(normalRow).toHaveClass("hover:bg-[oklch(0.29_0.012_240)]");
  expect(within(activeRow).getByText("Planner")).toHaveClass("text-white");
  expect(within(normalRow).getByText("Researcher")).toHaveClass("text-[oklch(0.86_0.01_240)]");
  expect(within(normalRow).getByText("agent-two")).toHaveClass("text-[oklch(0.64_0.01_240)]");
});

it("remains a desktop-only rail", async () => {
  listAgentSummaries.mockResolvedValue([]);

  renderRail();

  expect(await screen.findByTestId("agents-rail-desktop")).toHaveClass("hidden", "lg:flex");
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  listAgentSummaries: vi.fn(),
  listNodes: vi.fn()
}));

vi.mock("./im-agent-config-api", () => ({
  listAgentSummaries: apiMocks.listAgentSummaries,
  listNodes: apiMocks.listNodes
}));

import { AgentsRailDesktop } from "./agents-rail-desktop";

const SAMPLE_AGENTS = [
  { agent_id: "agent-one", display_name: "Planner", node_id: "node-1", node_status: "online" },
  { agent_id: "agent-two", display_name: "Researcher", node_id: "node-1", node_status: "offline" }
];

const SAMPLE_NODES = [
  {
    node_id: "node-1",
    owner_id: "owner-1",
    node_name: "mac-mini",
    status: "online",
    last_heartbeat_at: "2026-08-18T00:00:00Z",
    agent_count: 2,
    version: "1.0.0"
  }
];

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
  apiMocks.listAgentSummaries.mockReset();
  apiMocks.listNodes.mockReset();
});

it("uses readable normal and active identity colors on the dark desktop rail", async () => {
  apiMocks.listAgentSummaries.mockResolvedValue(SAMPLE_AGENTS);
  apiMocks.listNodes.mockResolvedValue(SAMPLE_NODES);

  renderRail();

  const activeRow = await screen.findByRole("button", { name: /Planner/i });
  const normalRow = screen.getByRole("button", { name: /Researcher/i });
  expect(within(activeRow).getByText("Planner")).toHaveClass("text-white");
  expect(within(normalRow).getByText("Researcher")).toHaveClass("text-[oklch(0.86_0.01_240)]");
  expect(within(normalRow).getByText("agent-two")).toHaveClass("text-[oklch(0.64_0.01_240)]");
});

it("labels each row with the owning device name resolved from the nodes table", async () => {
  apiMocks.listAgentSummaries.mockResolvedValue(SAMPLE_AGENTS);
  apiMocks.listNodes.mockResolvedValue(SAMPLE_NODES);

  renderRail();

  const row = await screen.findByRole("button", { name: /Planner/i });
  expect(within(row).getByText("mac-mini")).toBeInTheDocument();
});

it("remains a desktop-only rail", async () => {
  apiMocks.listAgentSummaries.mockResolvedValue([]);
  apiMocks.listNodes.mockResolvedValue([]);

  renderRail();

  expect(await screen.findByTestId("agents-rail-desktop")).toHaveClass("hidden", "lg:flex");
});

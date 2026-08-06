import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getAgentDetailState: vi.fn(),
  isMobile: false
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ agentId: "agent-two" })
  };
});

vi.mock("../../../hooks/use-is-mobile", () => ({
  useIsMobile: () => mocks.isMobile
}));

vi.mock("./agent-status-ws-consumer", () => ({
  useAgentStatusBroadcastConsumer: () => undefined
}));

vi.mock("./agents-rail-desktop", () => ({
  AgentsRailDesktop: ({ activeId }: { activeId?: string }) => (
    <aside data-testid="agents-rail-desktop" data-active-id={activeId} />
  )
}));

vi.mock("./im-agent-config-api", () => ({
  getAgentDetailState: mocks.getAgentDetailState
}));

import { AgentDetailPage } from "./agent-detail-page";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AgentDetailPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  mocks.getAgentDetailState.mockReset();
  mocks.isMobile = false;
});

describe("agent detail asynchronous shell", () => {
  it("keeps the desktop agent rail while the selected agent is loading", async () => {
    mocks.getAgentDetailState.mockReturnValue(new Promise(() => undefined));

    renderPage();

    expect(screen.getByTestId("agents-rail-desktop")).toHaveAttribute("data-active-id", "agent-two");
    expect(screen.getByTestId("agent-detail-loading")).toHaveAttribute("role", "status");
    expect(screen.getByTestId("agent-detail-state-panel")).toContainElement(
      screen.getByTestId("agent-detail-loading")
    );
  });

  it("keeps the desktop agent rail around an initial request error", async () => {
    mocks.getAgentDetailState.mockRejectedValue(new Error("agent detail unavailable"));

    renderPage();

    expect(await screen.findByTestId("agent-detail-error")).toBeInTheDocument();
    expect(screen.getByTestId("agents-rail-desktop")).toHaveAttribute("data-active-id", "agent-two");
    expect(screen.getByTestId("agent-detail-state-panel")).toContainElement(
      screen.getByTestId("agent-detail-error")
    );
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("keeps the mobile loading state single-column", () => {
    mocks.isMobile = true;
    mocks.getAgentDetailState.mockReturnValue(new Promise(() => undefined));

    renderPage();

    expect(screen.queryByTestId("agents-rail-desktop")).not.toBeInTheDocument();
    expect(screen.getByTestId("agent-detail-loading")).toBeInTheDocument();
  });
});

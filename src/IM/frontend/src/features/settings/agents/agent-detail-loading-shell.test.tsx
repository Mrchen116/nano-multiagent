import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getAgentDetailState: vi.fn(),
  isMobile: false,
  agentId: "agent-two"
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ agentId: mocks.agentId })
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
  const page = () => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AgentDetailPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
  const rendered = render(page());
  return { ...rendered, rerenderPage: () => rendered.rerender(page()) };
}

function makeDetailState(agentId: string, displayName: string) {
  return {
    config: {
      agent_id: agentId,
      owner_id: "owner-1",
      display_name: displayName,
      description: "",
      system_prompt: "",
      custom_prompt: "",
      skills: [],
      tool_allowlist: [],
      group_reply_policy: "MENTION",
      default_model: null,
      workspace_root: `/tmp/${agentId}`,
      workspace_is_default: false,
      profile_version: 1,
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      updated_at: "2026-08-06T00:00:00Z"
    },
    capabilities: {
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      capabilities_updated_at: "2026-08-06T00:00:00Z",
      skills: [],
      tools: [],
      model_options: [],
      platform_default_model: null,
      default_system_prompt: "",
      features: []
    },
    owningNode: null
  };
}

afterEach(() => {
  mocks.getAgentDetailState.mockReset();
  mocks.isMobile = false;
  mocks.agentId = "agent-two";
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
    mocks.getAgentDetailState.mockRejectedValue(new Error(`agent detail unavailable: ${"backend detail ".repeat(80)}`));

    renderPage();

    expect(await screen.findByTestId("agent-detail-error")).toBeInTheDocument();
    expect(screen.getByTestId("agents-rail-desktop")).toHaveAttribute("data-active-id", "agent-two");
    const statePanel = screen.getByTestId("agent-detail-state-panel");
    expect(statePanel).toContainElement(screen.getByTestId("agent-detail-error"));
    expect(statePanel).toHaveClass("min-h-0", "overflow-y-auto");
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it.each([
    ["desktop", false],
    ["mobile", true]
  ])("shows agent B's error after agent A loaded on %s", async (_viewport, isMobile) => {
    mocks.agentId = "agent-one";
    mocks.isMobile = isMobile;
    mocks.getAgentDetailState.mockImplementation((agentId: string) => {
      if (agentId === "agent-one") return Promise.resolve(makeDetailState("agent-one", "Agent One"));
      return Promise.reject(new Error("agent B unavailable"));
    });
    const view = renderPage();
    expect(await screen.findByRole("heading", { name: "Agent One" })).toBeInTheDocument();

    mocks.agentId = "agent-two";
    view.rerenderPage();

    expect(await screen.findByTestId("agent-detail-error")).toHaveTextContent("agent B unavailable");
    expect(screen.queryByRole("heading", { name: "Agent One" })).not.toBeInTheDocument();
    if (isMobile) {
      expect(screen.queryByTestId("agents-rail-desktop")).not.toBeInTheDocument();
    } else {
      expect(screen.getByTestId("agents-rail-desktop")).toHaveAttribute("data-active-id", "agent-two");
    }
  });

  it("keeps the mobile loading state single-column", () => {
    mocks.isMobile = true;
    mocks.getAgentDetailState.mockReturnValue(new Promise(() => undefined));

    renderPage();

    expect(screen.queryByTestId("agents-rail-desktop")).not.toBeInTheDocument();
    expect(screen.getByTestId("agent-detail-loading")).toBeInTheDocument();
  });
});

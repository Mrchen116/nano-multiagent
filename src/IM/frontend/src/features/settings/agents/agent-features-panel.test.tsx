import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getAgentDetailState: vi.fn(),
  listAgentSummaries: vi.fn(),
  listNodes: vi.fn(),
  listAgents: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ agentId: "agent-1" }),
    useNavigate: () => apiMocks.navigate,
  };
});

vi.mock("../../chat/chat-api", () => ({
  createConversation: vi.fn(),
  listAgents: apiMocks.listAgents,
}));

vi.mock("../../../hooks/use-is-mobile", () => ({ useIsMobile: () => false }));

vi.mock("./im-agent-config-api", () => ({
  getAgentDetailState: apiMocks.getAgentDetailState,
  listAgentSummaries: apiMocks.listAgentSummaries,
  listNodes: apiMocks.listNodes,
  promptPreview: vi.fn(),
  updateAgentConfig: vi.fn(),
}));

import { AgentDetailPage } from "./agent-detail-page";

const HEARTBEAT = {
  key: "heartbeat",
  label_i18n: "Heartbeat",
  help_i18n: "Run periodic checks",
  default_on: false,
  available: true,
  requires_tool: null,
};

const CRON = {
  key: "cron_scheduling",
  label_i18n: "Cron scheduling",
  help_i18n: "Run scheduled jobs",
  default_on: false,
  available: true,
  requires_tool: "cron",
};

function agentState(feature: typeof HEARTBEAT | typeof CRON) {
  return {
    config: {
      agent_id: "agent-1",
      owner_id: "owner-1",
      display_name: "Settings Agent",
      description: "",
      custom_prompt: "",
      features: {},
      skills: [],
      tool_allowlist: [],
      group_reply_policy: "MENTION" as const,
      default_model: null,
      workspace_root: "/tmp",
      workspace_is_default: false,
      profile_version: 1,
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      updated_at: "2026-03-13T10:00:00Z",
      heartbeat: { every: "1h" },
    },
    capabilities: {
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      capabilities_updated_at: "2026-03-13T10:00:00Z",
      skills: [],
      tools: [{ name: "cron", description: "Cron scheduling", default_on: false }],
      model_options: [],
      platform_default_model: null,
      features: [feature],
    },
    owningNode: null,
  };
}

function renderDetail() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AgentDetailPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  apiMocks.listNodes.mockResolvedValue([]);
  apiMocks.listAgentSummaries.mockResolvedValue([
    {
      agent_id: "agent-1",
      display_name: "Settings Agent",
      owner_id: "owner-1",
      description: "",
      profile_version: 1,
      default_model: null,
      workspace_root: "",
      workspace_is_default: false,
    },
  ]);
  apiMocks.listAgents.mockResolvedValue([]);
});

afterEach(() => vi.clearAllMocks());

describe("agent feature settings", () => {
  it("reveals heartbeat cadence after the user enables heartbeat", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailState.mockResolvedValue(agentState(HEARTBEAT));

    renderDetail();
    await screen.findByRole("heading", { name: "Settings Agent" });
    expect(screen.queryByRole("heading", { name: /Heartbeat/i })).toBeNull();

    await user.click(document.querySelector<HTMLInputElement>('[data-feature-key="heartbeat"]')!);

    expect(await screen.findByRole("heading", { name: /Heartbeat/i })).toBeInTheDocument();
    expect(document.querySelector<HTMLInputElement>("#heartbeat-every")).toHaveValue(1);
  });

  it("reveals cron jobs after the user enables scheduling", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailState.mockResolvedValue(agentState(CRON));

    renderDetail();
    await screen.findByRole("heading", { name: "Settings Agent" });
    expect(screen.queryByRole("heading", { name: /Cron Jobs/i })).toBeNull();

    await user.click(
      document.querySelector<HTMLInputElement>('[data-feature-key="cron_scheduling"]')!,
    );

    expect(await screen.findByRole("heading", { name: /Cron Jobs/i })).toBeInTheDocument();
  });
});

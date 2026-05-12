import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getAgentDetailStateMock: vi.fn(),
  updateAgentConfigMock: vi.fn(),
  createDirectConversationMock: vi.fn(),
  navigateMock: vi.fn()
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ agentId: "agent-core-1" }),
    useNavigate: () => apiMocks.navigateMock
  };
});

vi.mock("../../chat/chat-api", () => ({
  createDirectConversation: apiMocks.createDirectConversationMock
}));

vi.mock("./im-agent-config-api", () => ({
  getAgentDetailState: apiMocks.getAgentDetailStateMock,
  updateAgentConfig: apiMocks.updateAgentConfigMock
}));

import { AgentDetailPage } from "./agent-detail-page";

function renderDetailPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
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
  apiMocks.getAgentDetailStateMock.mockReset();
  apiMocks.updateAgentConfigMock.mockReset();
  apiMocks.createDirectConversationMock.mockReset();
  apiMocks.navigateMock.mockReset();
});

describe("agent detail page", () => {
  it("opens the canonical direct chat for the current agent", async () => {
    const user = userEvent.setup();

    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      config: {
        agent_id: "agent-core-1",
        owner_id: "owner-1",
        display_name: "Core Planner",
        description: "Milestone execution coordinator",
        system_prompt: "You are the planning core for IM and SDK tasks.",
        skills: ["tdd-execution-worker"],
        tool_allowlist: ["read"],
        group_reply_policy: "MENTION",
        default_model: "codex_oauth:gpt-5.4",
        workspace_root: "/tmp/agent-core-1",
        workspace_is_default: false,
        profile_version: 12,
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        bound_nodes: ["node-1"],
        updated_at: "2026-03-13T10:00:00Z"
      },
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-03-13T10:00:00Z",
        skills: [{ name: "tdd-execution-worker", description: "Execute TDD tasks" }],
        tools: [{ name: "read", description: "Read files" }],
        model_options: ["codex_oauth:gpt-5.4", "moonshotAnthropic:kimi-k2.5"],
        platform_default_model: "codex_oauth:gpt-5.4",
        default_system_prompt: "You are the personal_assistant default template."
      },
      owningNode: {
        node_id: "node-1",
        node_name: "MacBook",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 1,
        version: "1.0.0"
      }
    });
    apiMocks.updateAgentConfigMock.mockResolvedValue(undefined);
    apiMocks.createDirectConversationMock.mockResolvedValue({ conversation_id: "conv-agent-core-1" });

    renderDetailPage();

    expect(await screen.findByRole("heading", { name: "Core Planner" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Identity" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Behavior" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Access & Model" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Workspace & Runtime" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open chat/i })).toBeInTheDocument();

    const panel = screen.getByTestId("agent-detail");
    expect(panel.className).toContain("im-agent-panel");
    expect(panel.querySelectorAll(".im-agent-card").length).toBeGreaterThanOrEqual(4);

    await user.click(screen.getByRole("button", { name: /Open chat/i }));

    await waitFor(() => {
      expect(apiMocks.createDirectConversationMock).toHaveBeenCalledWith({ agentId: "agent-core-1" });
    });
    await waitFor(() => {
      expect(apiMocks.navigateMock).toHaveBeenCalledWith("/chat/conv-agent-core-1");
    });
  });

  it("R7-4: invalidates the v2 chat conversations cache so the freshly created conv is visible after navigation", async () => {
    const user = userEvent.setup();

    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      config: {
        agent_id: "agent-core-1",
        owner_id: "owner-1",
        display_name: "Core Planner",
        description: "",
        system_prompt: "",
        skills: [],
        tool_allowlist: [],
        group_reply_policy: "MENTION",
        default_model: null,
        workspace_root: "/tmp",
        workspace_is_default: false,
        profile_version: 1,
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        bound_nodes: ["node-1"],
        updated_at: "2026-03-13T10:00:00Z"
      },
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-03-13T10:00:00Z",
        skills: [],
        tools: [],
        model_options: [],
        platform_default_model: null,
        default_system_prompt: ""
      },
      owningNode: null
    });
    apiMocks.createDirectConversationMock.mockResolvedValue({ conversation_id: "conv-x" });

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AgentDetailPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await screen.findByRole("heading", { name: "Core Planner" });
    await user.click(screen.getByRole("button", { name: /Open chat/i }));

    await waitFor(() => {
      const calls = invalidateSpy.mock.calls.map((c) => JSON.stringify(c[0]));
      const hitV2 = calls.some((s) => s.includes(`"chat-v2"`) && s.includes(`"conversations"`));
      expect(hitV2, `Expected chat-v2/conversations invalidation; got ${calls.join(" | ")}`).toBe(true);
    });
  });
});

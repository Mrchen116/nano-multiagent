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
        default_model: "codexOAuth:gpt-5.2-codex",
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
        model_options: ["codexOAuth:gpt-5.2-codex", "claude-3-5-sonnet-20241022"],
        platform_default_model: "codexOAuth:gpt-5.2-codex",
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

    expect(await screen.findByRole("heading", { name: "Agent settings" })).toBeInTheDocument();
    expect(screen.getByText("Review the saved role, access, and runtime details without losing the current profile state.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Identity" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Behavior" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Access & model" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Workspace" })).toBeInTheDocument();
    expect(screen.getByText("Current workspace")).toBeInTheDocument();
    expect(screen.getByText("Owning node")).toBeInTheDocument();
    expect(screen.getByText("Capabilities updated")).toBeInTheDocument();
    expect(screen.queryByLabelText("Workspace setting")).not.toBeInTheDocument();
    expect(screen.getByText(/Read-only runtime path/i)).toBeInTheDocument();
    expect(screen.queryByText("Start chatting now")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open direct chat" })).toBeInTheDocument();
    expect(screen.getByLabelText("Default Model")).toHaveDisplayValue("codexOAuth:gpt-5.2-codex (platform default)");

    await user.click(screen.getByRole("button", { name: "Open direct chat" }));

    await waitFor(() => {
      expect(apiMocks.createDirectConversationMock).toHaveBeenCalledWith({ agentId: "agent-core-1" });
    });
    await waitFor(() => {
      expect(apiMocks.navigateMock).toHaveBeenCalledWith("/chat/conv-agent-core-1");
    });
  });
});

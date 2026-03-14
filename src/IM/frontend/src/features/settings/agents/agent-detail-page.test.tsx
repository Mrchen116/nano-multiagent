import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getAgentConfigMock: vi.fn(),
  listNodesMock: vi.fn(),
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
  getAgentConfig: apiMocks.getAgentConfigMock,
  listNodes: apiMocks.listNodesMock,
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
  apiMocks.getAgentConfigMock.mockReset();
  apiMocks.listNodesMock.mockReset();
  apiMocks.updateAgentConfigMock.mockReset();
  apiMocks.createDirectConversationMock.mockReset();
  apiMocks.navigateMock.mockReset();
});

describe("agent detail page", () => {
  it("opens the canonical direct chat for the current agent", async () => {
    const user = userEvent.setup();

    apiMocks.getAgentConfigMock.mockResolvedValue({
      agent_id: "agent-core-1",
      owner_id: "owner-1",
      display_name: "Core Planner",
      description: "Milestone execution coordinator",
      system_prompt: "You are the planning core for IM and SDK tasks.",
      skills: ["tdd-execution-worker"],
      tool_allowlist: ["read"],
      group_reply_policy: "MENTION",
      default_model: "gpt-5.2-codex",
      profile_version: 12,
      bound_nodes: ["node-1"],
      updated_at: "2026-03-13T10:00:00Z"
    });
    apiMocks.listNodesMock.mockResolvedValue([
      {
        node_id: "node-1",
        owner_id: "owner-1",
        node_name: "MacBook",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 1,
        version: "1.0.0"
      }
    ]);
    apiMocks.updateAgentConfigMock.mockResolvedValue(undefined);
    apiMocks.createDirectConversationMock.mockResolvedValue({ conversation_id: "conv-agent-core-1" });

    renderDetailPage();

    expect(await screen.findByRole("heading", { name: "Agent Detail" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open direct chat" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open direct chat" }));

    await waitFor(() => {
      expect(apiMocks.createDirectConversationMock).toHaveBeenCalledWith({ agentId: "agent-core-1" });
    });
    await waitFor(() => {
      expect(apiMocks.navigateMock).toHaveBeenCalledWith("/chat/conv-agent-core-1");
    });
  });
});

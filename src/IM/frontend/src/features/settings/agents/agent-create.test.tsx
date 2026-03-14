import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  listNodesMock: vi.fn(),
  getAgentAllowlistOptionsMock: vi.fn(),
  createAgentMock: vi.fn(),
  createDirectConversationMock: vi.fn(),
  navigateMock: vi.fn()
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => apiMocks.navigateMock
  };
});

vi.mock("../../chat/chat-api", () => ({
  createDirectConversation: apiMocks.createDirectConversationMock
}));

vi.mock("./im-agent-config-api", () => ({
  listNodes: apiMocks.listNodesMock,
  getAgentAllowlistOptions: apiMocks.getAgentAllowlistOptionsMock,
  createAgent: apiMocks.createAgentMock
}));

import { AgentCreatePage, DEFAULT_AGENT_SYSTEM_PROMPT } from "./agent-create-page";

function renderCreatePage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AgentCreatePage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  apiMocks.listNodesMock.mockReset();
  apiMocks.getAgentAllowlistOptionsMock.mockReset();
  apiMocks.createAgentMock.mockReset();
  apiMocks.createDirectConversationMock.mockReset();
  apiMocks.navigateMock.mockReset();
});

describe("agent create page", () => {
  it("creates a new agent, redirects to detail, and exposes a reusable direct-chat follow-up", async () => {
    const user = userEvent.setup();

    apiMocks.listNodesMock.mockResolvedValue([
      {
        node_id: "node-1",
        owner_id: "owner-1",
        node_name: "MacBook",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 0,
        version: "1.0.0"
      }
    ]);
    apiMocks.getAgentAllowlistOptionsMock.mockResolvedValue({
      skills: [
        { name: "plan", description: "Plan work" },
        { name: "review", description: "Review work" }
      ],
      tools: [
        { name: "read", description: "Read files" },
        { name: "bash", description: "Run shell commands" }
      ]
    });
    apiMocks.createAgentMock.mockResolvedValue({
      agent_id: "agent-new",
      owner_id: "",
      display_name: "Agent New",
      description: "runtime-created helper",
      system_prompt: "You are Agent New.",
      skills: ["plan"],
      tool_allowlist: ["read"],
      group_reply_policy: "MENTION",
      default_model: "claude-sonnet-4",
      workspace_root: "/tmp/agent-new-workspace",
      workspace_is_default: false,
      profile_version: 1,
      bound_nodes: ["node-1"],
      updated_at: "2026-03-13T10:00:00Z"
    });
    apiMocks.createDirectConversationMock.mockResolvedValue({ conversation_id: "conv-agent-new" });

    renderCreatePage();

    expect(await screen.findByRole("heading", { name: "New Agent" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Back to Agents" })).toHaveAttribute("href", "/settings/agents");
    expect(screen.getByLabelText("System Prompt")).toHaveValue(DEFAULT_AGENT_SYSTEM_PROMPT);
    expect(
      screen.getByText("We prefill a standard template for role, goals, guardrails, and tone. Edit it before saving so it matches this agent.")
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("Agent ID"), "agent-new");
    await user.type(screen.getByLabelText("Display Name"), "Agent New");
    await user.type(screen.getByLabelText("Description"), "runtime-created helper");
    await user.clear(screen.getByLabelText("System Prompt"));
    await user.type(screen.getByLabelText("System Prompt"), "You are Agent New.");
    await user.click(screen.getByRole("checkbox", { name: /plan/i }));
    await user.click(screen.getByRole("checkbox", { name: /read/i }));
    await user.selectOptions(screen.getByLabelText("Node"), "node-1");
    await user.type(screen.getByLabelText("Default Model"), "claude-sonnet-4");
    await user.type(screen.getByLabelText("Workspace Path Setting"), "/tmp/agent-new-workspace");

    expect(screen.getByText("MacBook")).toBeInTheDocument();
    expect(screen.getByText("/tmp/agent-new-workspace")).toBeInTheDocument();
    expect(screen.getByText("Assigned agents")).toBeInTheDocument();
    expect(screen.getByText("online")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Create Agent" }));

    await waitFor(() => {
      expect(apiMocks.createAgentMock).toHaveBeenCalledWith({
        agent_id: "agent-new",
        owner_id: "",
        display_name: "Agent New",
        description: "runtime-created helper",
        system_prompt: "You are Agent New.",
        skills: ["plan"],
        tool_allowlist: ["read"],
        group_reply_policy: "MENTION",
        default_model: "claude-sonnet-4",
        workspace_root: "/tmp/agent-new-workspace",
        node_id: "node-1"
      });
    });

    expect(await screen.findByText("Agent created. Open its dedicated direct chat now or keep editing in Settings.")).toBeInTheDocument();
    expect(screen.getByText("Each agent keeps one stable reusable direct chat window. Reopen this same thread anytime instead of starting a new direct chat.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open direct chat" }));

    await waitFor(() => {
      expect(apiMocks.createDirectConversationMock).toHaveBeenCalledWith({ agentId: "agent-new" });
    });

    await waitFor(() => {
      expect(apiMocks.navigateMock).toHaveBeenNthCalledWith(1, "/settings/agents/agent-new");
      expect(apiMocks.navigateMock).toHaveBeenNthCalledWith(2, "/chat/conv-agent-new");
    });
  });

  it("blocks submission and explains required fields", async () => {
    const user = userEvent.setup();

    apiMocks.listNodesMock.mockResolvedValue([]);
    apiMocks.getAgentAllowlistOptionsMock.mockResolvedValue({ skills: [], tools: [] });

    renderCreatePage();

    await screen.findByRole("heading", { name: "New Agent" });
    await user.clear(screen.getByLabelText("System Prompt"));
    await user.click(screen.getByRole("button", { name: "Create Agent" }));

    expect(screen.getByText("Agent ID is required.")).toBeInTheDocument();
    expect(screen.getByText("Display name is required.")).toBeInTheDocument();
    expect(screen.getByText("System prompt is required.")).toBeInTheDocument();
    expect(screen.getByText("Complete the required fields before creating this agent.")).toBeInTheDocument();
    expect(apiMocks.createAgentMock).not.toHaveBeenCalled();
  });

  it("surfaces API errors without leaving the form", async () => {
    const user = userEvent.setup();

    apiMocks.listNodesMock.mockResolvedValue([]);
    apiMocks.getAgentAllowlistOptionsMock.mockResolvedValue({ skills: [], tools: [] });
    apiMocks.createAgentMock.mockRejectedValue(new Error("POST /im/v1/agents failed: 409 (agent already exists)"));

    renderCreatePage();

    await user.type(await screen.findByLabelText("Agent ID"), "agent-new");
    await user.type(screen.getByLabelText("Display Name"), "Agent New");
    await user.clear(screen.getByLabelText("System Prompt"));
    await user.type(screen.getByLabelText("System Prompt"), "You are Agent New.");
    await user.click(screen.getByRole("button", { name: "Create Agent" }));

    expect(await screen.findByText("409 (agent already exists)")).toBeInTheDocument();
    expect(apiMocks.navigateMock).not.toHaveBeenCalled();
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

import { AgentCreatePage } from "./agent-create-page";

function renderCreatePage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  });

  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AgentCreatePage />
        </MemoryRouter>
      </QueryClientProvider>
    )
  };
}

afterEach(() => {
  apiMocks.listNodesMock.mockReset();
  apiMocks.getAgentAllowlistOptionsMock.mockReset();
  apiMocks.createAgentMock.mockReset();
  apiMocks.createDirectConversationMock.mockReset();
  apiMocks.navigateMock.mockReset();
});

describe("agent create page", () => {
  it("creates a new agent, keeps the success CTA reachable, and opens the reusable direct chat", async () => {
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
      ],
      model_options: ["codexOAuth:gpt-5.2-codex", "claude-3-5-sonnet-20241022"],
      platform_default_model: "codexOAuth:gpt-5.2-codex",
      default_system_prompt: "You are the personal_assistant default template."
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
      default_model: "claude-3-5-sonnet-20241022",
      workspace_root: "/tmp/agent-new-workspace",
      workspace_is_default: false,
      profile_version: 1,
      bound_nodes: ["node-1"],
      updated_at: "2026-03-13T10:00:00Z"
    });
    apiMocks.createDirectConversationMock.mockResolvedValue({ conversation_id: "conv-agent-new" });

    const { queryClient } = renderCreatePage();

    expect(await screen.findByRole("heading", { name: "New Agent" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Back to Agents" })).toHaveAttribute("href", "/settings/agents");
    expect(screen.getByText("Set the identity, behavior, and runtime defaults before anyone starts using this agent.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Identity" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Behavior" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Access & model" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Runtime placement" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Before you create" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("System Prompt")).toHaveValue("You are the personal_assistant default template.");
    });
    expect(screen.getByText("We prefill the personal_assistant product template here. Edit it before saving so it matches this agent.")).toBeInTheDocument();
    expect(screen.getByLabelText("Default Model")).toHaveDisplayValue("Platform default (codexOAuth:gpt-5.2-codex)");
    expect(screen.getAllByText("Selected 0")).toHaveLength(2);
    expect(screen.getByText("Show advanced options (1 hidden)")).toBeInTheDocument();
    expect(screen.getByText("Workspace preview")).toBeInTheDocument();
    expect(screen.getByLabelText("Workspace Path Setting")).toBeInTheDocument();
    expect(screen.queryByText(/advanced\/internal/i)).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /bash/i })).not.toBeChecked();

    fireEvent.change(screen.getByLabelText("Agent ID"), { target: { value: "agent-new" } });
    fireEvent.change(screen.getByLabelText("Display Name"), { target: { value: "Agent New" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "runtime-created helper" } });
    fireEvent.change(screen.getByLabelText("System Prompt"), { target: { value: "You are Agent New." } });
    await user.click(screen.getByRole("checkbox", { name: /plan/i }));
    await user.click(screen.getByRole("checkbox", { name: /read/i }));
    await user.selectOptions(screen.getByLabelText("Node"), "node-1");
    await user.selectOptions(screen.getByLabelText("Default Model"), "claude-3-5-sonnet-20241022");
    fireEvent.change(screen.getByLabelText("Workspace Path Setting"), { target: { value: "/tmp/agent-new-workspace" } });

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
        default_model: "claude-3-5-sonnet-20241022",
        workspace_root: "/tmp/agent-new-workspace",
        node_id: "node-1"
      });
    });

    expect(await screen.findByText("Agent created. Open its dedicated direct chat now or keep editing in Settings.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Each agent keeps one stable reusable direct chat window. From inside chat you can start a fresh session later when you need a new prompt snapshot without disturbing older threads."
      )
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Agent New" })).toHaveAttribute("href", "/settings/agents/agent-new");
    expect(apiMocks.navigateMock).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Open direct chat" }));

    await waitFor(() => {
      expect(apiMocks.createDirectConversationMock).toHaveBeenCalledWith({ agentId: "agent-new" });
    });

    await waitFor(() => {
      expect(apiMocks.navigateMock).toHaveBeenNthCalledWith(1, "/chat/conv-agent-new");
    });

    expect(screen.getByRole("link", { name: "Agent New" })).toHaveAttribute("href", "/settings/agents/agent-new");


    expect(queryClient.getQueryData(["settings", "agents"])).toEqual([
      expect.objectContaining({
        agent_id: "agent-new",
        display_name: "Agent New"
      })
    ]);
  }, 10_000);

  it("blocks submission and explains required fields", async () => {
    const user = userEvent.setup();

    apiMocks.listNodesMock.mockResolvedValue([]);
    apiMocks.getAgentAllowlistOptionsMock.mockResolvedValue({
      skills: [],
      tools: [],
      model_options: ["codexOAuth:gpt-5.2-codex"],
      platform_default_model: "codexOAuth:gpt-5.2-codex",
      default_system_prompt: ""
    });

    renderCreatePage();

    await screen.findByRole("heading", { name: "New Agent" });
    const promptInput = screen.getByLabelText("System Prompt");
    fireEvent.change(promptInput, { target: { value: "" } });
    await user.click(screen.getByRole("button", { name: "Create Agent" }));

    expect(await screen.findByText("Agent ID is required.")).toBeInTheDocument();
    expect(screen.getByText("Display name is required.")).toBeInTheDocument();
    expect(screen.getByText("System prompt is required.")).toBeInTheDocument();
    expect(screen.getByText("Complete the required fields before creating this agent.")).toBeInTheDocument();
    expect(apiMocks.createAgentMock).not.toHaveBeenCalled();
  });

  it("surfaces API errors without leaving the form", async () => {
    const user = userEvent.setup();

    apiMocks.listNodesMock.mockResolvedValue([]);
    apiMocks.getAgentAllowlistOptionsMock.mockResolvedValue({
      skills: [],
      tools: [],
      model_options: ["codexOAuth:gpt-5.2-codex"],
      platform_default_model: "codexOAuth:gpt-5.2-codex",
      default_system_prompt: ""
    });
    apiMocks.createAgentMock.mockRejectedValue(new Error("POST /im/v1/agents failed: 409 (agent already exists)"));

    renderCreatePage();

    fireEvent.change(await screen.findByLabelText("Agent ID"), { target: { value: "agent-new" } });
    fireEvent.change(screen.getByLabelText("Display Name"), { target: { value: "Agent New" } });
    fireEvent.change(screen.getByLabelText("System Prompt"), { target: { value: "You are Agent New." } });
    await user.click(screen.getByRole("button", { name: "Create Agent" }));

    expect(await screen.findByText("409 (agent already exists)")).toBeInTheDocument();
    expect(apiMocks.navigateMock).not.toHaveBeenCalled();
  });
});

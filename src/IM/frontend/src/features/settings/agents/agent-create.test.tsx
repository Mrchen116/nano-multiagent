import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  listNodesMock: vi.fn(),
  createAgentMock: vi.fn(),
  navigateMock: vi.fn()
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => apiMocks.navigateMock
  };
});

vi.mock("./im-agent-config-api", () => ({
  listNodes: apiMocks.listNodesMock,
  createAgent: apiMocks.createAgentMock
}));

import { AgentCreatePage } from "./agent-create-page";

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
  apiMocks.createAgentMock.mockReset();
  apiMocks.navigateMock.mockReset();
});

describe("agent create page", () => {
  it("creates a new agent and redirects to its detail page", async () => {
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
      profile_version: 1,
      bound_nodes: ["node-1"],
      updated_at: "2026-03-13T10:00:00Z"
    });

    renderCreatePage();

    expect(await screen.findByRole("heading", { name: "New Agent" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Back to Agents" })).toHaveAttribute("href", "/settings/agents");

    await user.type(screen.getByLabelText("Agent ID"), "agent-new");
    await user.type(screen.getByLabelText("Display Name"), "Agent New");
    await user.type(screen.getByLabelText("Description"), "runtime-created helper");
    await user.type(screen.getByLabelText("System Prompt"), "You are Agent New.");
    await user.type(screen.getByLabelText("Skills Allowlist"), "plan");
    await user.type(screen.getByLabelText("Tool Allowlist"), "read");
    await user.selectOptions(screen.getByLabelText("Node"), "node-1");
    await user.type(screen.getByLabelText("Default Model"), "claude-sonnet-4");

    expect(screen.getByText("MacBook")).toBeInTheDocument();
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
        node_id: "node-1"
      });
    });

    await waitFor(() => {
      expect(apiMocks.navigateMock).toHaveBeenCalledWith("/settings/agents/agent-new");
    });
  });

  it("blocks submission and explains required fields", async () => {
    const user = userEvent.setup();

    apiMocks.listNodesMock.mockResolvedValue([]);

    renderCreatePage();

    await screen.findByRole("heading", { name: "New Agent" });
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
    apiMocks.createAgentMock.mockRejectedValue(new Error("POST /im/v1/agents failed: 409 (agent already exists)"));

    renderCreatePage();

    await user.type(await screen.findByLabelText("Agent ID"), "agent-new");
    await user.type(screen.getByLabelText("Display Name"), "Agent New");
    await user.type(screen.getByLabelText("System Prompt"), "You are Agent New.");
    await user.click(screen.getByRole("button", { name: "Create Agent" }));

    expect(await screen.findByText("409 (agent already exists)")).toBeInTheDocument();
    expect(apiMocks.navigateMock).not.toHaveBeenCalled();
  });
});

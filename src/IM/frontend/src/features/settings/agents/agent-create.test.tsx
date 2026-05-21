import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getNodeCreateStateMock: vi.fn(),
  createNodeAgentMock: vi.fn(),
  listNodesMock: vi.fn(),
  navigateMock: vi.fn()
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => apiMocks.navigateMock,
    useParams: () => ({ nodeId: "node-1" })
  };
});

vi.mock("./im-agent-config-api", () => ({
  getNodeCreateState: apiMocks.getNodeCreateStateMock,
  createNodeAgent: apiMocks.createNodeAgentMock,
  listNodes: apiMocks.listNodesMock
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
  apiMocks.getNodeCreateStateMock.mockReset();
  apiMocks.createNodeAgentMock.mockReset();
  apiMocks.listNodesMock.mockReset();
  apiMocks.navigateMock.mockReset();
});

function mockNodes() {
  apiMocks.listNodesMock.mockResolvedValue([
    {
      node_id: "node-1",
      owner_id: "owner-1",
      node_name: "MacBook",
      alias: "MacBook",
      status: "online",
      last_heartbeat_at: "2026-03-13T10:00:00Z",
      agent_count: 0,
      version: "1.0.0"
    }
  ]);
}

describe("agent create page (three-card)", () => {
  it("renders only Identity/Behavior/Access&Model cards, creates the agent, and navigates to its detail page on save", async () => {
    const user = userEvent.setup();
    mockNodes();

    apiMocks.getNodeCreateStateMock.mockResolvedValue({
      node: {
        node_id: "node-1",
        owner_id: "owner-1",
        node_name: "MacBook",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 0,
        version: "1.0.0"
      },
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-03-13T10:00:00Z",
        skills: [
          { name: "plan", description: "Plan work" },
          { name: "review", description: "Review work" }
        ],
        tools: [
          { name: "read", description: "Read files" },
          { name: "bash", description: "Run shell commands" }
        ],
        model_options: ["codex_oauth:gpt-5.5", "kimiCoding:K2.6"],
        platform_default_model: "codex_oauth:gpt-5.5",
        default_system_prompt: "You are the personal_assistant default template."
      }
    });
    apiMocks.createNodeAgentMock.mockResolvedValue({
      agent_id: "agent-new",
      owner_id: "",
      display_name: "Agent New",
      description: "runtime-created helper",
      system_prompt: "You are Agent New.",
      skills: ["plan"],
      tool_allowlist: ["read"],
      group_reply_policy: "MENTION",
      default_model: "kimiCoding:K2.6",
      workspace_root: "/tmp/agent-new-workspace",
      workspace_is_default: false,
      profile_version: 1,
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      bound_nodes: ["node-1"],
      updated_at: "2026-03-13T10:00:00Z"
    });

    const { queryClient } = renderCreatePage();

    expect(await screen.findByRole("heading", { name: /New agent/i })).toBeInTheDocument();

    const panel = screen.getByTestId("agent-create");
    expect(panel.className).toContain("im-agent-panel");
    const cards = panel.querySelectorAll(".im-agent-card");
    expect(cards.length).toBe(3);

    expect(screen.getByRole("heading", { name: "Identity" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Behavior" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Access & Model" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Workspace/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Workspace Root/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Workspace preview/i)).not.toBeInTheDocument();

    expect(screen.getByLabelText(/Owning Node/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText(/^System Prompt/)).toHaveValue("You are the personal_assistant default template.");
    });

    fireEvent.change(screen.getByLabelText(/^Agent ID/), { target: { value: "agent-new" } });
    fireEvent.change(screen.getByLabelText(/^Display Name/), { target: { value: "Agent New" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "runtime-created helper" } });
    fireEvent.change(screen.getByLabelText(/^System Prompt/), { target: { value: "You are Agent New." } });
    await user.click(screen.getByRole("button", { name: /plan/i }));
    await user.click(screen.getByRole("button", { name: /read/i }));
    await user.selectOptions(screen.getByLabelText("Default Model"), "kimiCoding:K2.6");

    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    await waitFor(() => {
      expect(apiMocks.createNodeAgentMock).toHaveBeenCalledWith("node-1", {
        agent_id: "agent-new",
        owner_id: "",
        display_name: "Agent New",
        description: "runtime-created helper",
        system_prompt: "You are Agent New.",
        // feat-379-M3: custom_prompt is always included (empty string when not filled)
        custom_prompt: "",
        skills: ["plan"],
        tool_allowlist: ["read"],
        group_reply_policy: "MENTION",
        default_model: "kimiCoding:K2.6",
        workspace_root: null
      });
    });

    await waitFor(() => {
      expect(apiMocks.navigateMock).toHaveBeenCalledWith("/settings/agents/agent-new");
    });

    expect(queryClient.getQueryData(["settings", "agents"])).toEqual([
      expect.objectContaining({
        agent_id: "agent-new",
        display_name: "Agent New"
      })
    ]);
  }, 10_000);

  it("blocks submission and explains required fields", async () => {
    const user = userEvent.setup();
    mockNodes();

    apiMocks.getNodeCreateStateMock.mockResolvedValue({
      node: {
        node_id: "node-1",
        owner_id: "owner-1",
        node_name: "MacBook",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 0,
        version: "1.0.0"
      },
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-03-13T10:00:00Z",
        skills: [],
        tools: [],
        model_options: ["codex_oauth:gpt-5.5"],
        platform_default_model: "codex_oauth:gpt-5.5",
        default_system_prompt: ""
      }
    });

    renderCreatePage();

    await screen.findByRole("heading", { name: /New agent/i });
    // feat-379-M3: system_prompt is no longer required; submit with all fields blank
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    expect(await screen.findByText(/Agent ID is required/i)).toBeInTheDocument();
    expect(screen.getByText(/Display name is required/i)).toBeInTheDocument();
    // system_prompt required check removed — segment system provides defaults (feat-379-M3)
    expect(apiMocks.createNodeAgentMock).not.toHaveBeenCalled();
    expect(apiMocks.navigateMock).not.toHaveBeenCalled();
  });

  it("surfaces API errors without leaving the form", async () => {
    const user = userEvent.setup();
    mockNodes();

    apiMocks.getNodeCreateStateMock.mockResolvedValue({
      node: {
        node_id: "node-1",
        owner_id: "owner-1",
        node_name: "MacBook",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 0,
        version: "1.0.0"
      },
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-03-13T10:00:00Z",
        skills: [],
        tools: [],
        model_options: ["codex_oauth:gpt-5.5"],
        platform_default_model: "codex_oauth:gpt-5.5",
        default_system_prompt: ""
      }
    });
    apiMocks.createNodeAgentMock.mockRejectedValue(
      new Error("POST /im/v1/nodes/node-1/agents failed: 409 (agent already exists)")
    );

    renderCreatePage();

    fireEvent.change(await screen.findByLabelText(/^Agent ID/), { target: { value: "agent-new" } });
    fireEvent.change(screen.getByLabelText(/^Display Name/), { target: { value: "Agent New" } });
    fireEvent.change(screen.getByLabelText(/^System Prompt/), { target: { value: "You are Agent New." } });
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    expect(await screen.findByText(/409.*agent already exists/i)).toBeInTheDocument();
    expect(apiMocks.navigateMock).not.toHaveBeenCalled();
  });

  it("offers a Cancel back to the agents list", async () => {
    mockNodes();

    apiMocks.getNodeCreateStateMock.mockResolvedValue({
      node: {
        node_id: "node-1",
        owner_id: "owner-1",
        node_name: "MacBook",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 0,
        version: "1.0.0"
      },
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-03-13T10:00:00Z",
        skills: [],
        tools: [],
        model_options: ["codex_oauth:gpt-5.5"],
        platform_default_model: "codex_oauth:gpt-5.5",
        default_system_prompt: ""
      }
    });

    renderCreatePage();

    const cancels = await screen.findAllByRole("link", { name: /^Cancel$/i });
    expect(cancels.length).toBeGreaterThanOrEqual(1);
    expect(cancels[0]).toHaveAttribute("href", "/settings/agents");
  });
});

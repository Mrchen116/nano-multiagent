import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Link, createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getNodeCreateStateMock: vi.fn(),
  createNodeAgentMock: vi.fn(),
  listNodesMock: vi.fn(),
  listAgentSummariesMock: vi.fn(),
  promptPreviewMock: vi.fn(),
  nodePromptPreviewMock: vi.fn()
}));

vi.mock("./im-agent-config-api", () => ({
  getNodeCreateState: apiMocks.getNodeCreateStateMock,
  createNodeAgent: apiMocks.createNodeAgentMock,
  listNodes: apiMocks.listNodesMock,
  listAgentSummaries: apiMocks.listAgentSummariesMock,
  promptPreview: apiMocks.promptPreviewMock,
  nodePromptPreview: apiMocks.nodePromptPreviewMock,
  isConfigApplyPendingError: (error: unknown) => error instanceof Error && error.message.includes("config_apply_pending"),
  getAgentConfigRequestStatus: (error: unknown) => {
    const match = error instanceof Error ? error.message.match(/failed:\s*(\d{3})\b/) : null;
    return match ? Number(match[1]) : null;
  },
  getAgentConfigRequestDetail: (error: unknown) =>
    error instanceof Error ? error.message.split(" failed: ").at(-1) ?? error.message : "request failed",
}));

import { AgentCreatePage } from "./agent-create-page";

function renderCreatePage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  });

  const router = createMemoryRouter(
    [
      {
        path: "/settings/nodes/:nodeId/agents/new",
        element: (
          <>
            <Link to="/chat">Chat</Link>
            <AgentCreatePage />
          </>
        )
      },
      { path: "/settings/agents", element: <p>Agent list</p> },
      { path: "/settings/agents/:agentId", element: <p>Agent detail</p> },
      { path: "/chat", element: <p>Chat</p> }
    ],
    { initialEntries: ["/settings/nodes/node-1/agents/new"] }
  );

  return {
    queryClient,
    router,
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    )
  };
}

afterEach(() => {
  apiMocks.getNodeCreateStateMock.mockReset();
  apiMocks.createNodeAgentMock.mockReset();
  apiMocks.listNodesMock.mockReset();
  apiMocks.listAgentSummariesMock.mockReset();
  apiMocks.promptPreviewMock.mockReset();
  apiMocks.nodePromptPreviewMock.mockReset();
});

beforeEach(() => {
  apiMocks.listAgentSummariesMock.mockResolvedValue([]);
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

function mockCreateState() {
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
      model_options: [{ name: "codex_oauth:gpt-5.5", provider: "openai_compat" }],
      platform_default_model: "codex_oauth:gpt-5.5",
    }
  });
}

function mockAgentSummaries() {
  apiMocks.listAgentSummariesMock.mockResolvedValue([
    {
      agent_id: "existing-agent",
      owner_id: "owner-1",
      display_name: "Existing Agent",
      description: "",
      profile_version: 1,
      default_model: null,
      workspace_root: "",
      workspace_is_default: false,
      node_status: "online"
    }
  ]);
}

describe("agent create page", () => {
  it("creates an agent from the selected node capabilities and opens its settings", async () => {
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
        model_options: [
          {
            name: "codex_oauth:gpt-5.5",
            provider: "openai_compat",
            reasoning: { kind: "selectable", default: "high", levels: ["high", "max"] },
          },
          {
            name: "kimiCoding:K2.6",
            provider: "anthropic",
            reasoning: { kind: "selectable", default: "high", levels: ["high", "max"] },
          },
        ],
        platform_default_model: "codex_oauth:gpt-5.5",
      }
    });
    apiMocks.createNodeAgentMock.mockResolvedValue({
      agent_id: "agent-new",
      owner_id: "",
      display_name: "Agent New",
      description: "runtime-created helper",
      skills: ["plan"],
      tool_allowlist: ["read"],
      group_reply_policy: "MENTION",
      default_model: null,
      reasoning_effort: "max",
      workspace_root: "/tmp/agent-new-workspace",
      workspace_is_default: false,
      profile_version: 1,
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      bound_nodes: ["node-1"],
      updated_at: "2026-03-13T10:00:00Z"
    });
    apiMocks.listAgentSummariesMock.mockResolvedValue([
      {
        agent_id: "agent-new",
        owner_id: "",
        display_name: "Agent New",
        description: "runtime-created helper",
        profile_version: 1,
        default_model: null,
        workspace_root: "/tmp/agent-new-workspace",
        workspace_is_default: false,
        node_status: "online"
      }
    ]);

    const { queryClient, router } = renderCreatePage();

    expect(await screen.findByRole("heading", { name: /New agent/i })).toBeInTheDocument();

    expect(screen.getByLabelText(/Owning Node/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Custom Instructions/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^Agent ID/), { target: { value: "agent-new" } });
    fireEvent.change(screen.getByLabelText(/^Display Name/), { target: { value: "Agent New" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "runtime-created helper" } });
    fireEvent.change(screen.getByLabelText(/^Custom Instructions/), { target: { value: "You are Agent New." } });
    await user.click(screen.getByRole("button", { name: /plan/i }));
    await user.click(screen.getByRole("button", { name: /read/i }));
    await user.selectOptions(screen.getByLabelText("Reasoning effort"), "max");

    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    await waitFor(() => {
      expect(apiMocks.createNodeAgentMock).toHaveBeenCalledWith("node-1", {
        agent_id: "agent-new",
        owner_id: "",
        display_name: "Agent New",
        description: "runtime-created helper",
        custom_prompt: "You are Agent New.",
        features: {},
        skills: ["plan"],
        tool_allowlist: ["read"],
        group_reply_policy: "MENTION",
        default_model: null,
        reasoning_effort: "max",
        workspace_root: null,
        confirm_existing_workspace: false
      });
    });

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/settings/agents/agent-new");
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
        model_options: [{ name: "codex_oauth:gpt-5.5", provider: "openai_compat" }],
        platform_default_model: "codex_oauth:gpt-5.5",
      }
    });

    const { router } = renderCreatePage();

    await screen.findByRole("heading", { name: /New agent/i });
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    expect(await screen.findByText(/Agent ID is required/i)).toBeInTheDocument();
    expect(screen.getByText(/Display name is required/i)).toBeInTheDocument();
    expect(apiMocks.createNodeAgentMock).not.toHaveBeenCalled();
    expect(router.state.location.pathname).toBe("/settings/nodes/node-1/agents/new");
  });

  it("materializes default-on global skills into the create payload", async () => {
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
          {
            name: "pa-global",
            description: "PA global",
            default_on: true,
            location: "/Users/test/.nanoassistant/skills/pa-global/SKILL.md"
          },
          {
            name: "compat-claude",
            description: "Compat",
            default_on: false,
            location: "/Users/test/.claude/skills/compat-claude/SKILL.md"
          }
        ],
        tools: [],
        model_options: [{ name: "codex_oauth:gpt-5.5", provider: "openai_compat" }],
        platform_default_model: "codex_oauth:gpt-5.5",
      }
    });
    apiMocks.createNodeAgentMock.mockResolvedValue({
      agent_id: "agent-default-skills",
      owner_id: "",
      display_name: "Agent Default Skills",
      description: "",
      skills: ["pa-global"],
      tool_allowlist: [],
      group_reply_policy: "MENTION",
      default_model: null,
      workspace_root: "/tmp/agent-default-skills",
      workspace_is_default: false,
      profile_version: 1,
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      bound_nodes: ["node-1"],
      updated_at: "2026-03-13T10:00:00Z"
    });

    renderCreatePage();

    await screen.findByRole("heading", { name: /New agent/i });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "pa-global" })).toHaveAttribute("aria-pressed", "true");
    });
    expect(screen.getByText(/Global|全局/)).toBeInTheDocument();
    expect(screen.getByText(/Compatibility|兼容来源/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/^Agent ID/), { target: { value: "agent-default-skills" } });
    fireEvent.change(screen.getByLabelText(/^Display Name/), { target: { value: "Agent Default Skills" } });
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    await waitFor(() => {
      expect(apiMocks.createNodeAgentMock).toHaveBeenCalledWith(
        "node-1",
        expect.objectContaining({
          agent_id: "agent-default-skills",
          skills: ["pa-global"]
        })
      );
    });
  });

  it("resets auto default skills when switching nodes", async () => {
    const user = userEvent.setup();
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
      },
      {
        node_id: "node-2",
        owner_id: "owner-1",
        node_name: "Linux Box",
        alias: "Linux Box",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 0,
        version: "1.0.0"
      }
    ]);
    apiMocks.getNodeCreateStateMock.mockImplementation(async (nodeId: string) => ({
      node: {
        node_id: nodeId,
        owner_id: "owner-1",
        node_name: nodeId === "node-1" ? "MacBook" : "Linux Box",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 0,
        version: "1.0.0"
      },
      capabilities: {
        node_id: nodeId,
        node_name: nodeId === "node-1" ? "MacBook" : "Linux Box",
        node_status: "online",
        capabilities_updated_at: "2026-03-13T10:00:00Z",
        skills:
          nodeId === "node-1"
            ? [
                { name: "node-one-global", description: "", default_on: true, location: "/Users/test/.nanoassistant/skills/node-one-global/SKILL.md" },
                { name: "node-one-compat", description: "", location: "/Users/test/.claude/skills/node-one-compat/SKILL.md" }
              ]
            : [
                { name: "node-two-global", description: "", default_on: true, location: "/Users/test/.nanoassistant/skills/node-two-global/SKILL.md" }
              ],
        tools: [],
        model_options: [{ name: "codex_oauth:gpt-5.5", provider: "openai_compat" }],
        platform_default_model: "codex_oauth:gpt-5.5",
      }
    }));
    apiMocks.createNodeAgentMock.mockResolvedValue({
      agent_id: "agent-node-two",
      owner_id: "",
      display_name: "Agent Node Two",
      description: "",
      skills: ["node-two-global"],
      tool_allowlist: [],
      group_reply_policy: "MENTION",
      default_model: null,
      workspace_root: "/tmp/agent-node-two",
      workspace_is_default: false,
      profile_version: 1,
      node_id: "node-2",
      node_name: "Linux Box",
      node_status: "online",
      bound_nodes: ["node-2"],
      updated_at: "2026-03-13T10:00:00Z"
    });

    renderCreatePage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "node-one-global" })).toHaveAttribute("aria-pressed", "true");
    });
    await user.click(screen.getByRole("button", { name: "node-one-compat" }));
    expect(screen.getByRole("button", { name: "node-one-compat" })).toHaveAttribute("aria-pressed", "true");

    await user.selectOptions(screen.getByLabelText(/^Owning Node/), "node-2");

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "node-two-global" })).toHaveAttribute("aria-pressed", "true");
    });
    expect(screen.queryByRole("button", { name: "node-one-compat" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^Agent ID/), { target: { value: "agent-node-two" } });
    fireEvent.change(screen.getByLabelText(/^Display Name/), { target: { value: "Agent Node Two" } });
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    await waitFor(() => {
      expect(apiMocks.createNodeAgentMock).toHaveBeenCalledWith(
        "node-2",
        expect.objectContaining({
          agent_id: "agent-node-two",
          skills: ["node-two-global"]
        })
      );
    });
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
        model_options: [{ name: "codex_oauth:gpt-5.5", provider: "openai_compat" }],
        platform_default_model: "codex_oauth:gpt-5.5",
      }
    });
    apiMocks.createNodeAgentMock.mockRejectedValue(
      new Error("POST /im/v1/nodes/node-1/agents failed: 409 (agent already exists)")
    );

    const { router } = renderCreatePage();

    fireEvent.change(await screen.findByLabelText(/^Agent ID/), { target: { value: "agent-new" } });
    fireEvent.change(screen.getByLabelText(/^Display Name/), { target: { value: "Agent New" } });
    fireEvent.change(screen.getByLabelText(/^Custom Instructions/), { target: { value: "You are Agent New." } });
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    expect(await screen.findByText(/409.*agent already exists/i)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/settings/nodes/node-1/agents/new");
  });

  it("retries a pending create and opens the recovered agent", async () => {
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
        version: "1.0.0",
      },
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        skills: [],
        tools: [],
        model_options: [{
          name: "adjustable",
          provider: "provider-a",
          reasoning: { kind: "selectable", default: "medium", levels: ["medium", "high"] },
        }],
        platform_default_model: null,
      },
    });
    apiMocks.createNodeAgentMock
      .mockRejectedValueOnce(
        new Error("POST /im/v1/nodes/node-1/agents failed: 503 (config_apply_pending)"),
      )
      .mockResolvedValueOnce({
        agent_id: "pending-agent",
        owner_id: "owner-1",
        display_name: "Pending Agent",
        description: "",
        skills: [],
        tool_allowlist: [],
        group_reply_policy: "MENTION",
        default_model: "adjustable",
        reasoning_effort: "high",
        workspace_root: "/tmp/pending-agent",
        workspace_is_default: true,
        profile_version: 1,
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        bound_nodes: ["node-1"],
        updated_at: "2026-03-13T10:00:00Z",
      });

    const { router } = renderCreatePage();
    fireEvent.change(await screen.findByLabelText(/^Agent ID/), { target: { value: "pending-agent" } });
    fireEvent.change(screen.getByLabelText(/^Display Name/), { target: { value: "Pending Agent" } });
    await user.selectOptions(screen.getByLabelText("Default Model"), "adjustable");
    await user.selectOptions(screen.getByLabelText("Reasoning effort"), "high");
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: /^Create agent$/i }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByRole("status")).toHaveTextContent(/Confirming the previous save/i);
    expect(screen.getByLabelText(/^Agent ID/)).toHaveValue("pending-agent");
    expect(screen.getByLabelText("Reasoning effort")).toHaveValue("high");
    for (const button of screen.getAllByRole("button", { name: /Create agent/i })) {
      expect(button).toBeDisabled();
    }

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });
    expect(apiMocks.createNodeAgentMock).toHaveBeenCalledTimes(2);
    expect(router.state.location.pathname).toBe("/settings/agents/pending-agent");
    vi.useRealTimers();
  });

  it("shows the desktop agent rail and switches immediately from an untouched form", async () => {
    const user = userEvent.setup();
    mockNodes();
    mockCreateState();
    mockAgentSummaries();

    const { router } = renderCreatePage();

    expect(await screen.findByTestId("agents-rail-desktop")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: /Existing Agent/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/settings/agents/existing-agent");
    });
    expect(screen.queryByRole("dialog", { name: /Unsaved changes/i })).not.toBeInTheDocument();
  });

  it("keeps an edited form until the user confirms leaving", async () => {
    const user = userEvent.setup();
    mockNodes();
    mockCreateState();
    mockAgentSummaries();

    const { router } = renderCreatePage();

    const agentId = await screen.findByLabelText(/^Agent ID/);
    await user.type(agentId, "draft-agent");
    await user.click(screen.getByRole("button", { name: /Existing Agent/i }));

    expect(await screen.findByRole("dialog", { name: /Unsaved changes/i })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/settings/nodes/node-1/agents/new");
    expect(agentId).toHaveValue("draft-agent");

    await user.click(screen.getByRole("button", { name: /Keep editing/i }));
    expect(screen.queryByRole("dialog", { name: /Unsaved changes/i })).not.toBeInTheDocument();
    expect(agentId).toHaveValue("draft-agent");

    await user.click(screen.getByRole("button", { name: /Existing Agent/i }));
    await user.click(screen.getByRole("button", { name: /Leave without saving/i }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/settings/agents/existing-agent");
    });
  });

  it("asks before global in-app navigation leaves an edited form", async () => {
    const user = userEvent.setup();
    mockNodes();
    mockCreateState();

    const { router } = renderCreatePage();

    await user.type(await screen.findByLabelText(/^Agent ID/), "draft-agent");
    await user.click(screen.getByRole("link", { name: "Chat" }));

    expect(await screen.findByRole("dialog", { name: /Unsaved changes/i })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/settings/nodes/node-1/agents/new");

    await user.click(screen.getByRole("button", { name: /Leave without saving/i }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/chat");
    });
  });

  it("asks before Cancel leaves an edited form", async () => {
    const user = userEvent.setup();
    mockNodes();
    mockCreateState();

    const { router } = renderCreatePage();

    await user.type(await screen.findByLabelText(/^Agent ID/), "draft-agent");
    await user.click(screen.getAllByRole("link", { name: /^Cancel$/i })[0]);

    expect(await screen.findByRole("dialog", { name: /Unsaved changes/i })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/settings/nodes/node-1/agents/new");
  });
});

describe("agent create prompt preview", () => {
  function mockCreateState() {
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
          { name: "read", description: "Read files" }
        ],
        model_options: [{ name: "codex_oauth:gpt-5.5", provider: "openai_compat" }],
        platform_default_model: "codex_oauth:gpt-5.5",
      }
    });
  }

  it("passes the draft skill selection to the preview API", async () => {
    const user = userEvent.setup();
    mockNodes();
    mockCreateState();
    apiMocks.nodePromptPreviewMock.mockResolvedValue("## Preview");

    renderCreatePage();
    await screen.findByText(/Select a node/i);

    const previewToggle = await screen.findByRole("button", { name: /Preview stable system prompt/i });
    await user.click(previewToggle);

    await waitFor(() => {
      expect(apiMocks.nodePromptPreviewMock).toHaveBeenCalled();
    });

    const calls = apiMocks.nodePromptPreviewMock.mock.calls;
    const lastCall = calls[calls.length - 1];
    const body = lastCall[1] as {
      skill_ids?: string[];
      agent_id_hint?: string;
      workspace_mode?: string;
      workspace_root?: string | null;
    };
    expect(body).toHaveProperty("skill_ids");
    expect(body.workspace_mode).toBe("default");
    expect(body.workspace_root).toBeNull();
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getAgentDetailStateMock: vi.fn(),
  updateAgentConfigMock: vi.fn(),
  createConversationMock: vi.fn(),
  listAgentsMock: vi.fn(),
  listAgentSummariesMock: vi.fn(),
  navigateMock: vi.fn(),
  promptPreviewMock: vi.fn(),
  listAgentCronJobsMock: vi.fn(),
  deleteAgentCronJobMock: vi.fn(),
  getAgentHeartbeatMdMock: vi.fn(),
  getAgentSkillsUsageMock: vi.fn(),
  listAgentChannelsMock: vi.fn(),
  createAgentChannelMock: vi.fn(),
  updateAgentChannelMock: vi.fn()
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
  createConversation: apiMocks.createConversationMock,
  listAgents: apiMocks.listAgentsMock
}));

vi.mock("../../../hooks/use-is-mobile", () => ({
  useIsMobile: () => false
}));

vi.mock("./im-agent-config-api", () => ({
  getAgentDetailState: apiMocks.getAgentDetailStateMock,
  updateAgentConfig: apiMocks.updateAgentConfigMock,
  listAgentSummaries: apiMocks.listAgentSummariesMock,
  promptPreview: apiMocks.promptPreviewMock,
  listAgentCronJobs: apiMocks.listAgentCronJobsMock,
  deleteAgentCronJob: apiMocks.deleteAgentCronJobMock,
  getAgentHeartbeatMd: apiMocks.getAgentHeartbeatMdMock,
  getAgentSkillsUsage: apiMocks.getAgentSkillsUsageMock,
  listAgentChannels: apiMocks.listAgentChannelsMock,
  createAgentChannel: apiMocks.createAgentChannelMock,
  updateAgentChannel: apiMocks.updateAgentChannelMock
}));

import { AgentDetailPage } from "./agent-detail-page";
import { setLanguage } from "../../../i18n";

function renderDetailPage(queryClient?: QueryClient) {
  const client =
    queryClient ??
    new QueryClient({
      defaultOptions: {
        queries: { retry: false }
      }
    });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AgentDetailPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  setLanguage("en");
  apiMocks.getAgentDetailStateMock.mockReset();
  apiMocks.updateAgentConfigMock.mockReset();
  apiMocks.createConversationMock.mockReset();
  apiMocks.listAgentsMock.mockReset();
  apiMocks.listAgentSummariesMock.mockReset();
  apiMocks.navigateMock.mockReset();
  apiMocks.promptPreviewMock.mockReset();
  apiMocks.listAgentCronJobsMock.mockReset();
  apiMocks.deleteAgentCronJobMock.mockReset();
  apiMocks.getAgentHeartbeatMdMock.mockReset();
  apiMocks.getAgentSkillsUsageMock.mockReset();
  apiMocks.listAgentChannelsMock.mockReset();
  apiMocks.createAgentChannelMock.mockReset();
  apiMocks.updateAgentChannelMock.mockReset();
});

// Default listAgentSummaries so the desktop rail (R12-bis-1) doesn't break tests.
beforeEach(() => {
  apiMocks.listAgentChannelsMock.mockResolvedValue([]);
  apiMocks.listAgentSummariesMock.mockResolvedValue([
    { agent_id: "agent-core-1", display_name: "Core Planner", owner_id: "owner-1", description: "", profile_version: 1, default_model: null, workspace_root: "", workspace_is_default: false }
  ]);
});

describe("agent detail page", () => {
  function makeDashboardDetailState() {
    return {
      config: {
        agent_id: "agent-core-1",
        owner_id: "owner-1",
        display_name: "Core Planner",
        description: "",
        skills: [],
        tool_allowlist: [],
        group_reply_policy: "MENTION",
        default_model: null,
        workspace_root: "/tmp/agent-core-1",
        workspace_is_default: false,
        profile_version: 1,
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        updated_at: "2026-07-02T10:00:00Z"
      },
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-07-02T10:00:00Z",
        skills: [],
        tools: [],
        model_options: [],
        platform_default_model: null,
      },
      owningNode: {
        node_id: "node-1",
        node_name: "MacBook",
        status: "online",
        last_heartbeat_at: "2026-07-02T10:00:00Z",
        agent_count: 1,
        version: "1.0.0"
      }
    };
  }

  function makeSkillsUsage() {
    return {
      agent_id: "agent-core-1",
      node_id: "node-1",
      node_online: true,
      skills: [
        {
          skill_id: "deploy-check",
          name: "deploy-check",
          source: "F3",
          state: "active",
          use_count: 3,
          last_used_at: "2026-07-02T10:00:00Z",
          created_at: "2026-07-01T10:00:00Z",
          session_refs: [{ timestamp: "2026-07-01T12:00:00Z" }],
          recent_call_keys: ["s1:tc1"],
          trend_buckets: [0, 0, 1, 2]
        },
        {
          skill_id: "old-skill",
          name: "old-skill",
          source: "F4",
          state: "archived",
          use_count: 1,
          last_used_at: "2026-06-01T10:00:00Z",
          created_at: "2026-06-01T08:00:00Z",
          session_refs: [{ timestamp: "2026-06-01T09:00:00Z" }],
          recent_call_keys: [],
          trend_buckets: [0, 1, 0, 0]
        }
      ],
      heatmap_data: [0, 1, 2, 0],
      health: {
        created_auto_total: 2,
        active_auto_total: 1,
        used_auto_total: 2
      }
    };
  }

  it("shows skills usage list with use counts, status, trend, and archived filter", async () => {
    const user = userEvent.setup();
    await act(async () => {
      setLanguage("zh");
    });
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeDashboardDetailState());
    apiMocks.listAgentsMock.mockResolvedValue([]);
    apiMocks.getAgentSkillsUsageMock.mockResolvedValue(makeSkillsUsage());

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });
    expect(screen.getByRole("button", { name: "概览" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "配置" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "通道" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "会话" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "概览" }));
    expect(screen.getByRole("heading", { name: "概览" })).toBeInTheDocument();
    expect(screen.getByText("本期不设计概览页。保持空态，后续单独设计。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "通道" }));
    expect(screen.getByRole("heading", { name: "外部通道" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "会话" }));
    expect(screen.getByRole("heading", { name: "会话" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "技能" }));

    expect(apiMocks.getAgentSkillsUsageMock).toHaveBeenCalledWith("agent-core-1");
    expect(await screen.findByRole("heading", { name: "全部 Skill" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "名字" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "来源" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "状态" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "使用次数" })).toBeInTheDocument();
    expect(await screen.findByText("deploy-check")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("自动沉淀")).toBeInTheDocument();
    const trend = screen.getByTestId("skill-trend-deploy-check");
    expect(trend).toBeInTheDocument();
    const trendBars = within(trend).getAllByLabelText(/skill uses/);
    await user.hover(trendBars[trendBars.length - 1]);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(/skill uses on/);
    await user.unhover(trendBars[trendBars.length - 1]);
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(screen.queryByText("old-skill")).toBeNull();

    await user.click(screen.getByRole("button", { name: /显示 archived/i }));
    expect(await screen.findByText("old-skill")).toBeInTheDocument();
    expect(screen.getByText("archived")).toBeInTheDocument();
    expect(screen.getByText("批量复盘")).toBeInTheDocument();
  });

  it("opens skill statistics from the Access card entry in the real config flow", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      ...makeDashboardDetailState(),
      capabilities: {
        ...makeDashboardDetailState().capabilities,
        skills: [{ name: "conversation-skill-distiller", description: "Distill sessions" }],
        tools: [{ name: "skill_view", description: "View skills", default_on: true }]
      }
    });
    apiMocks.listAgentsMock.mockResolvedValue([]);
    apiMocks.getAgentSkillsUsageMock.mockResolvedValue(makeSkillsUsage());

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });
    expect(screen.getByRole("heading", { name: "Access & Model" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /View skill statistics/i }));

    expect(apiMocks.getAgentSkillsUsageMock).toHaveBeenCalledWith("agent-core-1");
    expect(await screen.findByTestId("agent-skills-usage-panel")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Skills" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows agent heatmap, health funnel, and lifecycle timeline views", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeDashboardDetailState());
    apiMocks.listAgentsMock.mockResolvedValue([]);
    apiMocks.getAgentSkillsUsageMock.mockResolvedValue(makeSkillsUsage());

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });
    await user.click(screen.getByRole("button", { name: "Skills" }));
    await screen.findByText("deploy-check");

    await user.click(screen.getByRole("button", { name: "Agent 维度" }));
    expect(screen.getByText("使用热力图")).toBeInTheDocument();
    expect(screen.getByText(/次 · 最近 30 天 · 悬停查看/)).toBeInTheDocument();
    expect(screen.getByTestId("skills-agent-heatmap")).toBeInTheDocument();
    expect(screen.getByText("Less")).toBeInTheDocument();
    expect(screen.getByText("More")).toBeInTheDocument();
    expect(screen.getByText("Mon")).toBeInTheDocument();
    expect(screen.getByText("Wed")).toBeInTheDocument();
    expect(screen.getByText("Fri")).toBeInTheDocument();
    expect(screen.getByText("自动创建的 Skill")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "使用次数" })).toBeInTheDocument();
    const contributionCells = screen.getAllByLabelText(/skill uses/);
    await user.hover(contributionCells[contributionCells.length - 1]);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(/skill uses on/);
    await user.unhover(contributionCells[contributionCells.length - 1]);
    expect(screen.queryByRole("tooltip")).toBeNull();

    await user.click(screen.getByRole("button", { name: "自进化健康度" }));
    expect(screen.getByText("自进化存活率")).toBeInTheDocument();
    expect(screen.getByText("自动创建总数")).toBeInTheDocument();
    expect(screen.getByText("still active")).toBeInTheDocument();
    expect(screen.getByText("use_count > 0")).toBeInTheDocument();
    expect(screen.getAllByText(/存活率/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("生命周期时间线")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "首次使用" })).toBeInTheDocument();
    expect(screen.getAllByText("2").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows an empty state when usage exists but has no skills", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeDashboardDetailState());
    apiMocks.listAgentsMock.mockResolvedValue([]);
    apiMocks.getAgentSkillsUsageMock.mockResolvedValue({
      ...makeSkillsUsage(),
      skills: [],
      heatmap_data: [],
      health: { created_auto_total: 0, active_auto_total: 0, used_auto_total: 0 }
    });

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });
    await user.click(screen.getByRole("button", { name: "Skills" }));
    expect(await screen.findByText("No skill usage yet")).toBeInTheDocument();
  });

  it("shows an offline state when skills usage RPC fails", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeDashboardDetailState());
    apiMocks.listAgentsMock.mockResolvedValue([]);
    apiMocks.getAgentSkillsUsageMock.mockRejectedValue(
      new Error("GET /im/v1/agents/agent-core-1/skills/usage failed: 503 (target_node_id is not connected)")
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });
    await user.click(screen.getByRole("button", { name: "Skills" }));
    expect(await screen.findByText(/Gateway offline/i)).toBeInTheDocument();
  });

  it("opens the canonical direct chat for the current agent", async () => {
    const user = userEvent.setup();

    // The canonical list cache belongs to the desktop rail. Its snapshot may lag
    // behind the detail draft and must not create a second query or name the chat.
    apiMocks.listAgentSummariesMock.mockResolvedValue([
      {
        agent_id: "agent-core-1",
        display_name: "Stale Summary Name",
        owner_id: "owner-1",
        description: "",
        profile_version: 1,
        default_model: null,
        workspace_root: "",
        workspace_is_default: false
      }
    ]);

    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      config: {
        agent_id: "agent-core-1",
        owner_id: "owner-1",
        display_name: "Core Planner",
        description: "Milestone execution coordinator",
        skills: ["tdd-execution-worker"],
        tool_allowlist: ["read"],
        group_reply_policy: "MENTION",
        default_model: "codex_oauth:gpt-5.5",
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
        model_options: [{ name: "codex_oauth:gpt-5.5", provider: "openai_compat" }, { name: "kimiCoding:K2.6", provider: "anthropic" }],
        platform_default_model: "codex_oauth:gpt-5.5",
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
    apiMocks.listAgentsMock.mockResolvedValue([
      { agent_id: "agent-core-1", display_name: "Core Planner", user_id: "user-agent-core-1" }
    ]);
    apiMocks.createConversationMock.mockResolvedValue({ id: "conv-agent-core-1" });

    renderDetailPage();

    expect(await screen.findByRole("heading", { name: "Core Planner" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Identity" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Behavior" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Access & Model" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Workspace & Runtime" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open chat/i })).toBeInTheDocument();
    await waitFor(() => expect(apiMocks.listAgentSummariesMock).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: /Open chat/i }));

    await waitFor(() => {
      expect(apiMocks.createConversationMock).toHaveBeenCalledWith({
        title: "Core Planner",
        agentIds: ["agent-core-1"]
      });
    });
    await waitFor(() => {
      expect(apiMocks.navigateMock).toHaveBeenCalledWith("/chat/conv-agent-core-1");
    });
  });

  it("labels each model option with its provider", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      config: {
        agent_id: "agent-core-1",
        owner_id: "owner-1",
        display_name: "Core Planner",
        description: "",
        skills: [],
        tool_allowlist: [],
        group_reply_policy: "MENTION",
        default_model: "codex_oauth:gpt-5.5",
        workspace_root: "/tmp/agent-core-1",
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
        model_options: [
          { name: "codex_oauth:gpt-5.5", provider: "openai_compat" },
          { name: "kimiCoding:K2.6", provider: "anthropic" }
        ],
        platform_default_model: "kimiCoding:K2.6",
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
    apiMocks.listAgentsMock.mockResolvedValue([
      { agent_id: "agent-core-1", display_name: "Core Planner", user_id: "user-agent-core-1" }
    ]);

    renderDetailPage();

    const select = (await screen.findByLabelText(/model/i)) as HTMLSelectElement;
    const optionText = Array.from(select.querySelectorAll("option")).map((o) => o.textContent ?? "");
    // gpt model labelled openai_compat; kimi (also platform default) labelled anthropic.
    expect(optionText.some((txt) => txt.includes("codex_oauth:gpt-5.5") && txt.includes("openai_compat"))).toBe(true);
    expect(optionText.some((txt) => txt.includes("kimiCoding:K2.6") && txt.includes("anthropic"))).toBe(true);
  });

  it("invalidates the canonical chat conversations cache before navigating to a new direct chat", async () => {
    const user = userEvent.setup();

    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      config: {
        agent_id: "agent-core-1",
        owner_id: "owner-1",
        display_name: "Core Planner",
        description: "",
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
      },
      owningNode: null
    });
    apiMocks.listAgentsMock.mockResolvedValue([
      { agent_id: "agent-core-1", display_name: "Core Planner", user_id: "user-agent-core-1" }
    ]);
    apiMocks.createConversationMock.mockResolvedValue({ id: "conv-x" });

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
      const hitCanonical = calls.some((s) => s.includes(`"chat"`) && s.includes(`"conversations"`));
      expect(hitCanonical, `Expected chat/conversations invalidation; got ${calls.join(" | ")}`).toBe(true);
    });
  });

  it("shows the conversation API error when opening chat fails", async () => {
    const user = userEvent.setup();

    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      config: {
        agent_id: "agent-core-1",
        owner_id: "owner-1",
        display_name: "Core Planner",
        description: "",
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
      },
      owningNode: null
    });
    apiMocks.listAgentsMock.mockResolvedValue([
      { agent_id: "agent-core-1", display_name: "Core Planner", user_id: "user-agent-core-1" }
    ]);
    apiMocks.createConversationMock.mockRejectedValue(
      new Error("POST /im/v1/conversations failed: participant_ids contains unknown users")
    );

    renderDetailPage();

    await screen.findByRole("heading", { name: "Core Planner" });
    await user.click(screen.getByRole("button", { name: /Open chat/i }));

    const errorBanner = await screen.findByTestId("open-chat-error");
    expect(errorBanner.textContent).toContain("participant_ids contains unknown users");
    expect(apiMocks.navigateMock).not.toHaveBeenCalled();
  });

  it("keeps fallbacks collapsed on the default model label row", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentSkillsUsageMock.mockResolvedValue(makeSkillsUsage());
    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      ...makeDashboardDetailState(),
      config: {
        ...makeDashboardDetailState().config,
        default_model: "primary",
        model_fallbacks: ["backup"],
      },
      capabilities: {
        ...makeDashboardDetailState().capabilities,
        model_options: [
          { name: "primary", provider: "p1" },
          { name: "backup", provider: "p2" },
          { name: "third", provider: "p3" },
        ],
      },
    });

    renderDetailPage();
    const toggle = await screen.findByRole("button", { name: /Fallbacks 1/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: /\+ Add fallback/i })).toBeNull();

    await user.click(toggle);
    expect(await screen.findByRole("button", { name: /\+ Add fallback/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /\+ Add fallback/i }));
    expect(screen.getByLabelText("Fallback 2")).toBeInTheDocument();
  });
});

describe("agent behavior settings", () => {
  function makeDetailState(
    overrides: {
      features?: Array<{ key: string; label_i18n: string; help_i18n: string; default_on: boolean; available: boolean; requires_tool?: string | null }>;
      configFeatures?: Record<string, boolean>;
      customPrompt?: string;
    } = {}
  ) {
    return {
      config: {
        agent_id: "agent-core-1",
        owner_id: "owner-1",
        display_name: "Core Planner",
        description: "",
        custom_prompt: overrides.customPrompt ?? "",
        features: overrides.configFeatures ?? {},
        skills: [],
        tool_allowlist: overrides.features?.filter((f) => f.requires_tool).map((f) => f.requires_tool as string) ?? [],
        group_reply_policy: "MENTION" as const,
        default_model: null,
        workspace_root: "/tmp",
        workspace_is_default: false,
        profile_version: 1,
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        updated_at: "2026-03-13T10:00:00Z"
      },
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-03-13T10:00:00Z",
        skills: [],
        tools: [{ name: "memory", description: "Memory tool" }],
        model_options: [],
        platform_default_model: null,
        features: overrides.features ?? [
          { key: "memory_curation", label_i18n: "记忆自进化", help_i18n: "让 agent 主动把偏好/事实写入长期记忆", default_on: true, available: true, requires_tool: "memory" },
          { key: "skill_creation", label_i18n: "技能自进化", help_i18n: "复杂任务后自动沉淀/修补 skill", default_on: true, available: false, requires_tool: "skill_manage" }
        ]
      },
      owningNode: null
    };
  }

  beforeEach(() => {
    apiMocks.listAgentSummariesMock.mockResolvedValue([
      { agent_id: "agent-core-1", display_name: "Core Planner", owner_id: "owner-1", description: "", profile_version: 1, default_model: null, workspace_root: "", workspace_is_default: false }
    ]);
    apiMocks.listAgentsMock.mockResolvedValue([]);
  });

  it("saves custom instructions with the selected features", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeDetailState({ configFeatures: { memory_curation: true, skill_creation: true } })
    );
    apiMocks.updateAgentConfigMock.mockResolvedValue({
      agent_id: "agent-core-1",
      owner_id: "owner-1",
      display_name: "Core Planner",
      description: "",
      custom_prompt: "我是法律顾问",
      features: { memory_curation: true, skill_creation: true },
      skills: [],
      tool_allowlist: ["memory", "skill_manage"],
      group_reply_policy: "MENTION",
      default_model: null,
      workspace_root: "/tmp",
      workspace_is_default: false,
      profile_version: 2,
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      updated_at: "2026-03-13T10:01:00Z"
    });

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });

    const customTextarea = screen.getByLabelText(/Custom Instructions/i);
    await user.clear(customTextarea);
    await user.type(customTextarea, "我是法律顾问");

    await user.click(screen.getByRole("button", { name: /Save Agent/i }));

    await waitFor(() => {
      expect(apiMocks.updateAgentConfigMock).toHaveBeenCalledWith(
        "agent-core-1",
        expect.objectContaining({
          custom_prompt: "我是法律顾问",
          features: expect.any(Object)
        })
      );
    });
  });

  it("opens the stable prompt preview on demand", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeDetailState());

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });

    const previewToggle = screen.getByRole("button", { name: /Preview stable system prompt/i });
    expect(previewToggle).toBeInTheDocument();
    expect(previewToggle.getAttribute("aria-expanded")).toBe("false");

    await userEvent.click(previewToggle);

    expect(previewToggle.getAttribute("aria-expanded")).toBe("true");
  });

});

describe("agent prompt preview", () => {
  const memoryCapFeature = {
    key: "memory_curation",
    label_i18n: "agents.features.memory_curation.label",
    help_i18n: "agents.features.memory_curation.help",
    default_on: true,
    available: true,
    requires_tool: "memory"
  };

  function makeStateWithMemoryInAllowlist() {
    return {
      config: {
        agent_id: "agent-core-1",
        owner_id: "owner-1",
        display_name: "Mem Agent",
        description: "",
        custom_prompt: "",
        features: {},
        skills: [],
        tool_allowlist: ["memory"] as string[],
        group_reply_policy: "MENTION" as const,
        default_model: null,
        workspace_root: "/tmp",
        workspace_is_default: false,
        profile_version: 1,
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        updated_at: "2026-03-13T10:00:00Z"
      },
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-03-13T10:00:00Z",
        skills: [],
        tools: [{ name: "memory", description: "Memory tool" }],
        model_options: [],
        platform_default_model: null,
        features: [memoryCapFeature]
      },
      owningNode: null
    };
  }

  function makeStateWithSkillSelection(
    mode: "default_discovery" | "explicit_allowlist",
    skills: string[],
  ) {
    const state = makeStateWithMemoryInAllowlist();
    return {
      ...state,
      config: {
        ...state.config,
        skills,
        skills_selection_mode: mode,
      },
      capabilities: {
        ...state.capabilities,
        skills: [
          { name: "workspace-skill", description: "Workspace" },
          { name: "shared-skill", description: "Shared" },
        ],
      },
    };
  }

  beforeEach(() => {
    apiMocks.listAgentSummariesMock.mockResolvedValue([
      { agent_id: "agent-core-1", display_name: "Mem Agent", owner_id: "owner-1", description: "", profile_version: 1, default_model: null, workspace_root: "", workspace_is_default: false }
    ]);
    apiMocks.listAgentsMock.mockResolvedValue([]);
  });

  it("sends the selected tools to the preview API", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeStateWithMemoryInAllowlist());
    apiMocks.promptPreviewMock.mockResolvedValue("## Preview\n\nMemory guidance here.");

    renderDetailPage();
    await screen.findByRole("heading", { name: "Mem Agent" });

    const previewToggle = screen.getByRole("button", { name: /Preview stable system prompt/i });
    await user.click(previewToggle);

    await waitFor(() => {
      expect(apiMocks.promptPreviewMock).toHaveBeenCalled();
    });

    const calls = apiMocks.promptPreviewMock.mock.calls;
    const lastCall = calls[calls.length - 1];
    const body = lastCall[1] as { tool_ids?: string[] };
    expect(body.tool_ids).toEqual(["memory"]);
  });

  it.each([
    ["default discovery", "default_discovery", [], ["workspace-skill", "shared-skill"]],
    ["explicit names", "explicit_allowlist", ["shared-skill", "hidden-skill"], ["shared-skill", "hidden-skill"]],
    ["explicit empty", "explicit_allowlist", [], []],
  ] as const)("projects %s into the preview skill ids", async (_case, mode, skills, expected) => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeStateWithSkillSelection(mode, [...skills]),
    );
    apiMocks.promptPreviewMock.mockResolvedValue("## Preview");

    renderDetailPage();
    await screen.findByRole("heading", { name: "Mem Agent" });
    await user.click(
      screen.getByRole("button", { name: /Preview stable system prompt/i }),
    );

    await waitFor(() => expect(apiMocks.promptPreviewMock).toHaveBeenCalled());
    const lastCall = apiMocks.promptPreviewMock.mock.calls.at(-1);
    const body = lastCall?.[1] as { skill_ids?: string[] };
    expect(body.skill_ids).toEqual([...expected]);
  });
});

describe("feature tool linkage with an empty allowlist", () => {
  function makeFeatureToggleConfig(overrides: Partial<{
    agent_id: string; display_name: string; tool_allowlist: string[]
  }> = {}) {
    return {
      agent_id: overrides.agent_id ?? "bugfix-cron-1",
      owner_id: "owner-1",
      display_name: overrides.display_name ?? "Bugfix Agent",
      description: "",
      custom_prompt: "",
      features: {} as Record<string, boolean>,
      skills: [] as string[],
      tool_allowlist: overrides.tool_allowlist ?? ([] as string[]),
      group_reply_policy: "MENTION" as const,
      default_model: null,
      workspace_root: "/tmp",
      workspace_is_default: false,
      profile_version: 1,
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online" as const,
      updated_at: "2026-03-13T10:00:00Z"
    };
  }

  it("adds only the required tool when enabling a tool-backed feature", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const baseConfig = makeFeatureToggleConfig({ agent_id: "bugfix-cron-1", display_name: "Cron Agent" });
    const state = {
      config: baseConfig,
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-03-13T10:00:00Z",
        skills: [],
        tools: [
          { name: "read", description: "Read tool", default_on: true },
          { name: "bash", description: "Bash tool", default_on: true },
          { name: "cron_tool", description: "Cron tool", default_on: false }
        ],
        model_options: [],
        platform_default_model: null,
        features: [
          {
            key: "cron_scheduling",
            label_i18n: "agents.features.cron_scheduling.label",
            help_i18n: "agents.features.cron_scheduling.help",
            default_on: false,
            available: true,
            requires_tool: "cron_tool"
          }
        ]
      },
      owningNode: null
    };

    apiMocks.getAgentDetailStateMock.mockResolvedValue(state);
    apiMocks.listAgentCronJobsMock.mockResolvedValue([]);
    apiMocks.listAgentSummariesMock.mockResolvedValue([
      { agent_id: "bugfix-cron-1", display_name: "Cron Agent", owner_id: "owner-1", description: "", profile_version: 1, default_model: null, workspace_root: "", workspace_is_default: false }
    ]);
    apiMocks.listAgentsMock.mockResolvedValue([]);
    apiMocks.updateAgentConfigMock.mockResolvedValue(baseConfig);

    renderDetailPage(queryClient);
    await screen.findByRole("heading", { name: "Cron Agent" });

    const cronCheckbox = document.querySelector<HTMLInputElement>(
      '[data-feature-key="cron_scheduling"]'
    );
    expect(cronCheckbox, "cron_scheduling checkbox 应存在").not.toBeNull();
    await user.click(cronCheckbox!);

    const saveBtn = document.querySelector<HTMLButtonElement>('button[type="submit"]');
    expect(saveBtn, "submit 按钮应存在").not.toBeNull();
    await user.click(saveBtn!);

    await waitFor(() => {
      expect(apiMocks.updateAgentConfigMock).toHaveBeenCalled();
    });

    const calls = apiMocks.updateAgentConfigMock.mock.calls;
    const lastCall = calls[calls.length - 1];
    const patchBody = lastCall[1] as { tool_allowlist?: string[] };

    expect(patchBody.tool_allowlist).toEqual(["cron_tool"]);
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["chat", "slash-candidates"],
    });
  });

  it("does not add default tools for a feature without a tool requirement", async () => {
    const user = userEvent.setup();

    const baseConfig = makeFeatureToggleConfig({ agent_id: "bugfix-hb-1", display_name: "HB Agent" });
    const state = {
      config: baseConfig,
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-03-13T10:00:00Z",
        skills: [],
        tools: [
          { name: "read", description: "Read tool", default_on: true },
          { name: "bash", description: "Bash tool", default_on: true }
        ],
        model_options: [],
        platform_default_model: null,
        features: [
          {
            key: "heartbeat",
            label_i18n: "agents.features.heartbeat.label",
            help_i18n: "agents.features.heartbeat.help",
            default_on: false,
            available: true,
            requires_tool: null
          }
        ]
      },
      owningNode: null
    };

    apiMocks.getAgentDetailStateMock.mockResolvedValue(state);
    apiMocks.listAgentCronJobsMock.mockResolvedValue([]);
    apiMocks.getAgentHeartbeatMdMock.mockResolvedValue({ content: "" });
    apiMocks.listAgentSummariesMock.mockResolvedValue([
      { agent_id: "bugfix-hb-1", display_name: "HB Agent", owner_id: "owner-1", description: "", profile_version: 1, default_model: null, workspace_root: "", workspace_is_default: false }
    ]);
    apiMocks.listAgentsMock.mockResolvedValue([]);
    apiMocks.updateAgentConfigMock.mockResolvedValue(baseConfig);

    renderDetailPage();
    await screen.findByRole("heading", { name: "HB Agent" });

    const hbCheckbox = document.querySelector<HTMLInputElement>(
      '[data-feature-key="heartbeat"]'
    );
    expect(hbCheckbox, "heartbeat checkbox 应存在").not.toBeNull();
    await user.click(hbCheckbox!);

    const saveBtn = document.querySelector<HTMLButtonElement>('button[type="submit"]');
    expect(saveBtn, "submit 按钮应存在").not.toBeNull();
    await user.click(saveBtn!);

    await waitFor(() => {
      expect(apiMocks.updateAgentConfigMock).toHaveBeenCalled();
    });

    const calls = apiMocks.updateAgentConfigMock.mock.calls;
    const lastCall = calls[calls.length - 1];
    const patchBody = lastCall[1] as { tool_allowlist?: string[] };

    expect(
      patchBody.tool_allowlist,
      "heartbeat 无 requires_tool，tool_allowlist 应保持为空"
    ).toEqual([]);
  });
});

describe("explicit empty tool allowlist", () => {
  function makeClearConfig(toolAllowlist: string[], profileVersion: number) {
    return {
      agent_id: "agent-core-1",
      owner_id: "owner-1",
      display_name: "Core Planner",
      description: "",
      custom_prompt: "",
      skills: [] as string[],
      tool_allowlist: toolAllowlist,
      group_reply_policy: "MENTION" as const,
      default_model: null,
      workspace_root: "/tmp/agent-core-1",
      workspace_is_default: false,
      profile_version: profileVersion,
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      updated_at: "2026-07-17T10:00:00Z",
      features: {}
    };
  }

  function makeClearState(toolAllowlist: string[], profileVersion: number) {
    return {
      config: makeClearConfig(toolAllowlist, profileVersion),
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: "online",
        capabilities_updated_at: "2026-07-17T10:00:00Z",
        skills: [],
        tools: [
          { name: "read", description: "Read tool", default_on: true },
          { name: "write", description: "Write tool", default_on: true },
          { name: "edit", description: "Edit tool", default_on: true }
        ],
        model_options: [],
        platform_default_model: null,
        features: []
      },
      owningNode: null
    };
  }

  function pill(name: string) {
    return document.querySelector<HTMLButtonElement>(
      `[data-testid="pill-selector-tools"] [data-pill-name="${name}"]`
    );
  }

  it("persists an empty tool selection after refetch", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeClearState(["read", "write"], 1));
    apiMocks.updateAgentConfigMock.mockResolvedValue(makeClearConfig([], 2));

    renderDetailPage(queryClient);
    await screen.findByRole("heading", { name: "Core Planner" });

    await waitFor(() => {
      expect(pill("read")?.getAttribute("aria-pressed")).toBe("true");
    });
    expect(pill("write")?.getAttribute("aria-pressed")).toBe("true");

    // 显式取消所有选中的 tool pill。
    for (const name of ["read", "write"]) {
      await user.click(pill(name)!);
    }
    await waitFor(() => {
      expect(pill("read")?.getAttribute("aria-pressed")).toBe("false");
    });
    expect(pill("write")?.getAttribute("aria-pressed")).toBe("false");

    // 保存。
    await user.click(screen.getByRole("button", { name: /Save Agent/i }));

    await waitFor(() => {
      expect(apiMocks.updateAgentConfigMock).toHaveBeenCalled();
    });

    const calls = apiMocks.updateAgentConfigMock.mock.calls;
    const patchBody = calls[calls.length - 1][1] as { tool_allowlist?: string[] };
    expect(patchBody.tool_allowlist).toEqual([]);

    // 模拟 refetch 返回空名单后重渲染，断言所有 pill 未选中（不回弹 default_on）。
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeClearState([], 2));
    await act(async () => {
      await queryClient.refetchQueries({ queryKey: ["settings", "agents", "agent-core-1", "detail-state"] });
    });

    await waitFor(() => {
      expect(pill("read")?.getAttribute("aria-pressed")).toBe("false");
    });
    expect(pill("write")?.getAttribute("aria-pressed")).toBe("false");
    expect(pill("edit")?.getAttribute("aria-pressed")).toBe("false");
  });
});

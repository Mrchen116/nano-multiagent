import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getAgentDetailStateMock: vi.fn(),
  updateAgentConfigMock: vi.fn(),
  createDirectConversationMock: vi.fn(),
  createDirectChatByAgentUserIdMock: vi.fn(),
  listAgentsMock: vi.fn(),
  listAgentSummariesMock: vi.fn(),
  navigateMock: vi.fn(),
  promptPreviewMock: vi.fn()
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
  createDirectConversation: apiMocks.createDirectConversationMock,
  createDirectChatByAgentUserId: apiMocks.createDirectChatByAgentUserIdMock,
  listAgents: apiMocks.listAgentsMock
}));

vi.mock("../../../hooks/use-is-mobile", () => ({
  useIsMobile: () => false
}));

vi.mock("./im-agent-config-api", () => ({
  getAgentDetailState: apiMocks.getAgentDetailStateMock,
  updateAgentConfig: apiMocks.updateAgentConfigMock,
  listAgentSummaries: apiMocks.listAgentSummariesMock,
  promptPreview: apiMocks.promptPreviewMock
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
  apiMocks.createDirectChatByAgentUserIdMock.mockReset();
  apiMocks.listAgentsMock.mockReset();
  apiMocks.listAgentSummariesMock.mockReset();
  apiMocks.navigateMock.mockReset();
  apiMocks.promptPreviewMock.mockReset();
});

// Default listAgentSummaries so the desktop rail (R12-bis-1) doesn't break tests.
beforeEach(() => {
  apiMocks.listAgentSummariesMock.mockResolvedValue([
    { agent_id: "agent-core-1", display_name: "Core Planner", owner_id: "owner-1", description: "", profile_version: 1, default_model: null, workspace_root: "", workspace_is_default: false }
  ]);
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
        model_options: ["codex_oauth:gpt-5.5", "kimiCoding:K2.6"],
        platform_default_model: "codex_oauth:gpt-5.5",
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
    apiMocks.listAgentsMock.mockResolvedValue([
      { agent_id: "agent-core-1", display_name: "Core Planner", user_id: "user-agent-core-1" }
    ]);
    apiMocks.createDirectChatByAgentUserIdMock.mockResolvedValue({ conversation_id: "conv-agent-core-1" });

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
      expect(apiMocks.createDirectChatByAgentUserIdMock).toHaveBeenCalledWith({
        agentId: "agent-core-1",
        agentUserId: "user-agent-core-1",
        agentDisplayName: "Core Planner"
      });
    });
    await waitFor(() => {
      expect(apiMocks.navigateMock).toHaveBeenCalledWith("/chat/conv-agent-core-1");
    });
    // M18 R9-2: the legacy bootstrap-based path must not be invoked anymore.
    expect(apiMocks.createDirectConversationMock).not.toHaveBeenCalled();
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
    apiMocks.listAgentsMock.mockResolvedValue([
      { agent_id: "agent-core-1", display_name: "Core Planner", user_id: "user-agent-core-1" }
    ]);
    apiMocks.createDirectChatByAgentUserIdMock.mockResolvedValue({ conversation_id: "conv-x" });

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

  it("R9-2: surfaces an inline error when the open-chat request fails (no silent swallow)", async () => {
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
    apiMocks.listAgentsMock.mockResolvedValue([
      { agent_id: "agent-core-1", display_name: "Core Planner", user_id: "user-agent-core-1" }
    ]);
    apiMocks.createDirectChatByAgentUserIdMock.mockRejectedValue(
      new Error("POST /im/v1/conversations failed: participant_ids contains unknown users")
    );

    renderDetailPage();

    await screen.findByRole("heading", { name: "Core Planner" });
    await user.click(screen.getByRole("button", { name: /Open chat/i }));

    // R9-2: the failure must show up to the user, not get swallowed.
    const errorBanner = await screen.findByTestId("open-chat-error");
    expect(errorBanner.textContent).toContain("participant_ids contains unknown users");
    expect(apiMocks.navigateMock).not.toHaveBeenCalled();
  });

  // M19/R11-4: Identity row1 字段是 `Agent ID + Display Name`, 而不是
  // `Agent ID + Owner(裸 UUID)`。owner_id 对最终用户毫无意义,prototype
  // 的 AgentForm Identity row1 只放 Agent ID + Display Name (Description 下移到下一行)。
  it("R11-4: Identity row1 is Agent ID + Display Name (no Owner UUID column)", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      config: {
        agent_id: "agent-core-1",
        owner_id: "owner-uuid-DEADBEEF",
        display_name: "Core Planner",
        description: "",
        system_prompt: "p",
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
    apiMocks.listAgentsMock.mockResolvedValue([]);

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });

    // Owner UUID 不应作为表单字段值出现 (header subtitle 里可能仍含 agent_id,但不应有 owner_id 裸值)。
    const ownerInput = document.querySelector("#owner-id") as HTMLInputElement | null;
    expect(ownerInput, "M19/R11-4: #owner-id 字段应被移除").toBeNull();

    // Display Name 应作为 row1 第二列, 与 Agent ID 同 grid。
    const identityGrid = document.querySelector('[data-testid="agent-identity-row1"]');
    expect(identityGrid, "expected an Identity row1 grid").not.toBeNull();
    expect(identityGrid?.querySelector("#agent-id")).not.toBeNull();
    expect(identityGrid?.querySelector("#display-name")).not.toBeNull();
  });

  // M19/R11-3: Skills / Tool Allowlist 不再是 60+ checkbox grid, 而是 prototype
  // `MultiSelect` 风格的平铺 pill — 每项一个 toggle button,选中态青色背景。
  it("R11-3: Skills / Tool allowlists render as pill toggles (no checkbox grid)", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      config: {
        agent_id: "agent-core-1",
        owner_id: "owner-1",
        display_name: "Core Planner",
        description: "",
        system_prompt: "p",
        skills: ["tdd"],
        tool_allowlist: ["read"],
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
        skills: [
          { name: "tdd", description: "" },
          { name: "review", description: "" }
        ],
        tools: [
          { name: "read", description: "" },
          { name: "write", description: "" }
        ],
        model_options: [],
        platform_default_model: null,
        default_system_prompt: ""
      },
      owningNode: null
    });
    apiMocks.listAgentsMock.mockResolvedValue([]);

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });

    // pill selector 容器存在
    const skillsPill = document.querySelector('[data-testid="pill-selector-skills"]');
    expect(skillsPill, "expected pill selector for skills").not.toBeNull();
    const toolsPill = document.querySelector('[data-testid="pill-selector-tools"]');
    expect(toolsPill, "expected pill selector for tools").not.toBeNull();

    // 不应再有 allowlist-selector 的 checkbox + fieldset 结构
    expect(skillsPill?.querySelector('input[type="checkbox"]')).toBeNull();
    expect(toolsPill?.querySelector('input[type="checkbox"]')).toBeNull();

    // 每项渲染为 <button>,选中 selected 有 aria-pressed=true
    const tddBtn = skillsPill?.querySelector('button[data-pill-name="tdd"]') as HTMLButtonElement | null;
    expect(tddBtn).not.toBeNull();
    expect(tddBtn?.getAttribute("aria-pressed")).toBe("true");
    const reviewBtn = skillsPill?.querySelector('button[data-pill-name="review"]') as HTMLButtonElement | null;
    expect(reviewBtn?.getAttribute("aria-pressed")).toBe("false");
  });
});

// feat-379-M3: Behavior card 重构 — features checkbox + custom_prompt + 折叠预览
describe("feat-379-M3 Behavior card", () => {
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
        system_prompt: "legacy prompt",
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
        default_system_prompt: "",
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

  it("M3-R1: 不再显示 system_prompt textarea，改为 custom_prompt 和 features 区块", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeDetailState());

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });

    // 旧的 system_prompt textarea 不应存在
    expect(screen.queryByLabelText("System Prompt")).toBeNull();
    expect(screen.queryByLabelText(/System Prompt \*/)).toBeNull();

    // 新的 custom_prompt textarea 应存在
    expect(screen.getByLabelText(/Custom Instructions/i)).toBeInTheDocument();

    // features 区块标题
    expect(screen.getByText(/Features/i)).toBeInTheDocument();
  });

  it("M3-R1: features checkbox 按 capabilities.features 渲染，所有特性可勾选（feat-379-M9 决策12 删除 disabled）", async () => {
    // feat-379-M9 (決策 12): disabled 态已删除 — 所有特性均可勾选，tool 联动是权威。
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeDetailState());

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });

    // memory_curation: available=true, default_on=true → 勾选可用
    const memoryCheckbox = document.querySelector<HTMLInputElement>('[data-feature-key="memory_curation"]');
    expect(memoryCheckbox, "memory_curation checkbox 应存在").not.toBeNull();
    expect(memoryCheckbox?.disabled).toBe(false);

    // skill_creation: available=false, 但 M9 后 disabled 已删除 → 同样可勾选
    const skillCheckbox = document.querySelector<HTMLInputElement>('[data-feature-key="skill_creation"]');
    expect(skillCheckbox, "skill_creation checkbox 应存在").not.toBeNull();
    expect(skillCheckbox?.disabled).toBe(false);
  });

  it("M3-R1: 空 features 列表时不渲染 Features 区块", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeDetailState({ features: [] }));

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });

    // features 区块不应出现（无可用特性）
    expect(document.querySelector("[data-testid='features-section']")).toBeNull();
  });

  it("M3-R1: custom_prompt 编辑后保存时 PATCH payload 包含 features 和 custom_prompt", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeDetailState({ configFeatures: { memory_curation: true, skill_creation: true } })
    );
    apiMocks.updateAgentConfigMock.mockResolvedValue({
      agent_id: "agent-core-1",
      owner_id: "owner-1",
      display_name: "Core Planner",
      description: "",
      system_prompt: "",
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

  it("M3-R1: 折叠预览区块初始收起，点击展开后 aria-expanded=true", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeDetailState());

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });

    // 折叠按钮应存在，初始 aria-expanded=false
    const previewToggle = screen.getByRole("button", { name: /Preview full system prompt/i });
    expect(previewToggle).toBeInTheDocument();
    expect(previewToggle.getAttribute("aria-expanded")).toBe("false");

    await userEvent.click(previewToggle);

    expect(previewToggle.getAttribute("aria-expanded")).toBe("true");
  });

  it("M3-R1: group_reply_policy select 保留在 Behavior card 中", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeDetailState());

    renderDetailPage();
    await screen.findByRole("heading", { name: "Core Planner" });

    expect(screen.getByLabelText(/Group Reply Policy/i)).toBeInTheDocument();
  });
});

// feat-379-M9: preview tool_ids 来自 draft.tool_allowlist（決策 14 删除 effectiveToolIds hack）
// 根因回顾：M8 用 effectiveToolIds = union(capabilityFeatures.available.requires_tool, draft.tool_allowlist)
// 绕过了 M8 缺陷；M9 R1 修复了 _build_tool_names()，capabilities.tools 现在含 memory，
// 联动逻辑（决策 12）确保勾特性时工具自动进 allowlist，故直接用 draft.tool_allowlist 即正确。
describe("feat-379-M9 preview tool_ids regression", () => {
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
        system_prompt: "",
        custom_prompt: "",
        features: {},
        skills: [],
        // M9 後 tool_allowlist 含 memory（由联动逻辑加入）
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
        default_system_prompt: "",
        features: [memoryCapFeature]
      },
      owningNode: null
    };
  }

  beforeEach(() => {
    apiMocks.listAgentSummariesMock.mockResolvedValue([
      { agent_id: "agent-core-1", display_name: "Mem Agent", owner_id: "owner-1", description: "", profile_version: 1, default_model: null, workspace_root: "", workspace_is_default: false }
    ]);
    apiMocks.listAgentsMock.mockResolvedValue([]);
  });

  it("M9: preview 请求 tool_ids 直接来自 draft.tool_allowlist（決策 14 删除 effectiveToolIds）", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeStateWithMemoryInAllowlist());
    apiMocks.promptPreviewMock.mockResolvedValue("## Preview\n\nMemory guidance here.");

    renderDetailPage();
    await screen.findByRole("heading", { name: "Mem Agent" });

    const previewToggle = screen.getByRole("button", { name: /Preview full system prompt/i });
    await user.click(previewToggle);

    await waitFor(() => {
      expect(apiMocks.promptPreviewMock).toHaveBeenCalled();
    });

    const calls = apiMocks.promptPreviewMock.mock.calls;
    const lastCall = calls[calls.length - 1];
    const body = lastCall[1] as { tool_ids?: string[] };
    // tool_ids 来自 draft.tool_allowlist=["memory"]，不再从 capabilityFeatures 推断
    expect(body.tool_ids, "tool_ids 应来自 draft.tool_allowlist").toContain("memory");
  });

  // feat-394-M1/R4: heartbeat 开关测试
  it("feat-394-M9-E: Heartbeat card 显示并可开关 (enable via features)", async () => {
    // feat-394 M9-E: enable is in features["heartbeat"]; heartbeat only has cadence.
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      ...makeStateWithMemoryInAllowlist(),
      config: {
        ...makeStateWithMemoryInAllowlist().config,
        features: { heartbeat: false },
        heartbeat: { every: "30m" }
      }
    });

    renderDetailPage();
    await screen.findByRole("heading", { name: "Mem Agent" });

    // Heartbeat card 应有 "Heartbeat" 标题
    expect(screen.getByRole("heading", { name: /Heartbeat/i })).toBeInTheDocument();

    // 开关应存在且初始为关闭 (reads features["heartbeat"])
    const toggle = document.querySelector<HTMLInputElement>('[data-testid="heartbeat-enabled-toggle"]');
    expect(toggle, "heartbeat-enabled-toggle 应存在").not.toBeNull();
    expect(toggle?.checked).toBe(false);

    // 打开开关
    if (toggle) await user.click(toggle);

    expect(document.querySelector<HTMLInputElement>('[data-testid="heartbeat-enabled-toggle"]')?.checked).toBe(true);
  });

  it("feat-394-M9-E: Heartbeat 开关开启后保存时 PATCH payload 包含 features.heartbeat=true", async () => {
    // feat-394 M9-E: enable lives in features["heartbeat"], not heartbeat.enabled.
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      ...makeStateWithMemoryInAllowlist(),
      config: {
        ...makeStateWithMemoryInAllowlist().config,
        features: { heartbeat: false },
        heartbeat: { every: "30m" }
      }
    });
    apiMocks.updateAgentConfigMock.mockResolvedValue({
      ...makeStateWithMemoryInAllowlist().config,
      features: { heartbeat: true },
      heartbeat: { every: "30m" },
      profile_version: 2
    });

    renderDetailPage();
    await screen.findByRole("heading", { name: "Mem Agent" });

    // 打开开关 (inline toggle when not in capabilityFeatures)
    const toggle = document.querySelector<HTMLInputElement>('[data-testid="heartbeat-enabled-toggle"]');
    if (toggle) await user.click(toggle);

    // 保存
    await user.click(screen.getByRole("button", { name: /Save Agent/i }));

    await waitFor(() => {
      expect(apiMocks.updateAgentConfigMock).toHaveBeenCalledWith(
        "agent-core-1",
        expect.objectContaining({
          features: expect.objectContaining({ heartbeat: true })
        })
      );
    });
  });

  // feat-383-M1: preview 请求必须包含 skill_ids
  it("feat-383-M1: preview 请求 skill_ids 来自 draft.skills", async () => {
    const user = userEvent.setup();
    const stateWithSkills = {
      ...makeStateWithMemoryInAllowlist(),
      config: {
        ...makeStateWithMemoryInAllowlist().config,
        skills: ["code-review", "plan"] as string[],
      }
    };
    apiMocks.getAgentDetailStateMock.mockResolvedValue(stateWithSkills);
    apiMocks.promptPreviewMock.mockResolvedValue("## Preview");

    renderDetailPage();
    await screen.findByRole("heading", { name: "Mem Agent" });

    const previewToggle = screen.getByRole("button", { name: /Preview full system prompt/i });
    await user.click(previewToggle);

    await waitFor(() => {
      expect(apiMocks.promptPreviewMock).toHaveBeenCalled();
    });

    const calls = apiMocks.promptPreviewMock.mock.calls;
    const lastCall = calls[calls.length - 1];
    const body = lastCall[1] as { skill_ids?: string[] };
    expect(body.skill_ids, "skill_ids 必须来自 draft.skills").toEqual(
      expect.arrayContaining(["code-review", "plan"])
    );
  });

  // feat-394-M2/R7: cron 开关测试
  it("feat-394-M9-E: Cron card 显示并可开关 (enable via features)", async () => {
    // feat-394 M9-E: enable is in features["cron_scheduling"]; no cron config object.
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      ...makeStateWithMemoryInAllowlist(),
      config: {
        ...makeStateWithMemoryInAllowlist().config,
        features: { cron_scheduling: false }
      }
    });

    renderDetailPage();
    await screen.findByRole("heading", { name: "Mem Agent" });

    // Cron card 应有 "Cron Jobs" 标题
    expect(screen.getByRole("heading", { name: /Cron Jobs/i })).toBeInTheDocument();

    // 开关应存在且初始为关闭 (reads features["cron_scheduling"])
    const toggle = document.querySelector<HTMLInputElement>('[data-testid="cron-enabled-toggle"]');
    expect(toggle, "cron-enabled-toggle 应存在").not.toBeNull();
    expect(toggle?.checked).toBe(false);

    // 打开开关
    if (toggle) await user.click(toggle);

    expect(document.querySelector<HTMLInputElement>('[data-testid="cron-enabled-toggle"]')?.checked).toBe(true);
  });

  it("feat-394-M9-E: Cron 开关开启后保存时 PATCH payload 包含 features.cron_scheduling=true", async () => {
    // feat-394 M9-E: enable lives in features["cron_scheduling"]; no cron config object.
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      ...makeStateWithMemoryInAllowlist(),
      config: {
        ...makeStateWithMemoryInAllowlist().config,
        features: { cron_scheduling: false }
      }
    });
    apiMocks.updateAgentConfigMock.mockResolvedValue({
      ...makeStateWithMemoryInAllowlist().config,
      features: { cron_scheduling: true },
      profile_version: 2
    });

    renderDetailPage();
    await screen.findByRole("heading", { name: "Mem Agent" });

    // 打开开关 (inline toggle when not in capabilityFeatures)
    const toggle = document.querySelector<HTMLInputElement>('[data-testid="cron-enabled-toggle"]');
    if (toggle) await user.click(toggle);

    // 保存
    await user.click(screen.getByRole("button", { name: /Save Agent/i }));

    await waitFor(() => {
      expect(apiMocks.updateAgentConfigMock).toHaveBeenCalledWith(
        "agent-core-1",
        expect.objectContaining({
          features: expect.objectContaining({ cron_scheduling: true })
        })
      );
    });
  });

  // feat-394 M9-E round-trip: features["heartbeat"]=true 重开配置页时开关应显示「开」
  it("feat-394-M9-E round-trip: heartbeat 已启用(features)时重开配置页开关初始态为 checked=true", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      ...makeStateWithMemoryInAllowlist(),
      config: {
        ...makeStateWithMemoryInAllowlist().config,
        features: { heartbeat: true },
        heartbeat: { every: "30m" }
      }
    });

    renderDetailPage();
    await screen.findByRole("heading", { name: "Mem Agent" });

    const toggle = document.querySelector<HTMLInputElement>('[data-testid="heartbeat-enabled-toggle"]');
    expect(toggle, "heartbeat-enabled-toggle 应存在").not.toBeNull();
    expect(toggle?.checked).toBe(true);
  });

  // feat-394-M9-E round-trip: features["cron_scheduling"]=true 重开配置页时开关应显示「开」
  it("feat-394-M9-E round-trip: cron 已启用(features)时重开配置页开关初始态为 checked=true", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue({
      ...makeStateWithMemoryInAllowlist(),
      config: {
        ...makeStateWithMemoryInAllowlist().config,
        features: { cron_scheduling: true }
      }
    });

    renderDetailPage();
    await screen.findByRole("heading", { name: "Mem Agent" });

    const toggle = document.querySelector<HTMLInputElement>('[data-testid="cron-enabled-toggle"]');
    expect(toggle, "cron-enabled-toggle 应存在").not.toBeNull();
    expect(toggle?.checked).toBe(true);
  });
});

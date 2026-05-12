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
  listAgentSummaries: apiMocks.listAgentSummariesMock
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

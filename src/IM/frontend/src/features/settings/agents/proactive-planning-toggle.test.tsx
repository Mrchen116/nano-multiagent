import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { featureDependencies } from "@nano/product-contracts/capabilities";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { setLanguage } from "../../../i18n";
import { TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../../../test/render-router";
import { useAuthStore } from "../../auth/auth-store";
import { AgentCreatePage } from "./agent-create-page";
import { AgentDetailPage } from "./agent-detail-page";

const SCHEDULE_TOOLS = [
  "schedule_create",
  "schedule_list",
  "schedule_update",
  "schedule_delete",
  "schedule_run",
  "schedule_history",
];

let mockNodeStatus: "online" | "offline" = "online";
let mockWorkMode: "global" | "single_thread" = "global";
let mockConfigFeatures: Record<string, boolean> = {
  task_graph: true,
  cron_scheduling: true,
  proactive_planning: true,
};
const updateCalls: Array<{ agentId: string; payload: Record<string, unknown> }> = [];
const createCalls: Array<{ nodeId: string; payload: Record<string, unknown> }> = [];

vi.mock("../../../realtime/user-stream", () => ({
  subscribeUserStream: () => () => undefined,
}));

vi.mock("./agents-rail-desktop", () => ({
  AgentsRailDesktop: () => null,
}));

vi.mock("../../personal-agent/personal-agent-settings", () => ({
  PersonalAgentSettings: () => null,
}));

vi.mock("../nodes/browser-pairing-section", () => ({
  BrowserPairingSection: () => null,
}));

vi.mock("../../chat/chat-api", () => ({
  createConversation: vi.fn(async () => ({ id: "conv-1" })),
}));

vi.mock("./agent-lifecycle", () => ({
  useAgentLifecycle: () => ({
    query: { data: { desired: "enabled", observed: "enabled", revision: 1, applied_revision: 1 }, isError: false },
    mutation: { isError: false, isPending: false },
  }),
  AgentLifecycleStatus: () => null,
  AgentLifecycleAction: () => null,
}));

vi.mock("./agent-deletion", () => ({
  useAgentDeletion: () => ({ query: { data: null } }),
  AgentDeletionControls: () => null,
  AgentDeletionStatus: () => null,
}));

function buildMockCapabilities() {
  return {
    node_id: "node-1",
    node_name: "MacBook",
    node_status: mockNodeStatus,
    model_options: [],
    platform_default_model: "gpt-5.4",
    inherited_approval_rules: "codex" as const,
    default_workspace_template: "/tmp/agents/{agent_id}",
    skills: [{ name: "nano-proactive-care", description: "Proactive care", default_on: true }],
    fixed_tools: [],
    tools: ["task_graph", ...SCHEDULE_TOOLS].map(name => ({ name, default_on: true })),
    features: featureDependencies
      .filter(feat => ["task_graph", "cron_scheduling", "proactive_planning"].includes(feat.key))
      .map(feat => ({
        ...feat,
        label_i18n: `feature.${feat.key}.label`,
        help_i18n: `feature.${feat.key}.help`,
      })),
  };
}

vi.mock("./im-agent-config-api", async importOriginal => {
  const actual = await importOriginal<typeof import("./im-agent-config-api")>();
  return {
    ...actual,
    listNodes: vi.fn(async () => [
      { node_id: "node-1", node_name: "MacBook", status: mockNodeStatus },
    ]),
    getNodeCreateState: vi.fn(async () => ({
      node: { node_id: "node-1", node_name: "MacBook", status: mockNodeStatus },
      capabilities: buildMockCapabilities(),
    })),
    getNodeApprovalRules: vi.fn(async () => ({ inherited_approval_rules: "codex" })),
    nodePromptPreview: vi.fn(async () => "preview"),
    createNodeAgent: vi.fn(async (nodeId: string, payload: Record<string, unknown>) => {
      createCalls.push({ nodeId, payload });
      return {
        ...payload,
        agent_id: String(payload.agent_id ?? "agent-q"),
        display_name: String(payload.display_name ?? "Agent Q"),
        owner_id: TEST_AUTH_USER.id,
        profile_version: 1,
        node_id: nodeId,
        updated_at: "2026-11-25T10:05:00Z",
      };
    }),
    getAgentCapabilityUsage: vi.fn(async () => ({ active_tasks: 0, active_schedules: 0, busy: [] })),
    getAgentRole: vi.fn(async () => ({ content: "照应日常安排", version: 1 })),
    getAgentSettingsSection: vi.fn(async () => ({
      source: "current",
      captured_at: "2026-11-25T10:00:00Z",
      data: [],
      error: null,
    })),
    updateAgentConfig: vi.fn(async (agentId: string, payload: Record<string, unknown>) => {
      updateCalls.push({ agentId, payload });
      return {
        ...payload,
        agent_id: agentId,
        owner_id: TEST_AUTH_USER.id,
        profile_version: 4,
        updated_at: "2026-11-25T10:05:00Z",
      };
    }),
    getAgentDetailState: vi.fn(async (agentId: string) => ({
      ready: mockNodeStatus === "online",
      liveCapabilities: mockNodeStatus === "online",
      pendingOperation: false,
      owningNode: {
        node_id: "node-1",
        node_name: "MacBook",
        status: mockNodeStatus,
      },
      display: {
        source: mockNodeStatus === "online" ? "current" : "last_known",
        captured_at: "2026-11-25T10:00:00Z",
        error: null,
        data: { derived_current: mockNodeStatus === "online", features: [] },
      },
      config: {
        agent_id: agentId,
        owner_id: TEST_AUTH_USER.id,
        display_name: "小满",
        description: "团队数字员工",
        work_mode: mockWorkMode,
        approval_mode: "inherit",
        collaboration_scope: "team",
        default_model: null,
        model_fallbacks: [],
        reasoning_effort: null,
        skills: [],
        skills_selection_mode: "default_discovery",
        tool_allowlist: ["task_graph", ...SCHEDULE_TOOLS, "memory"],
        features: { ...mockConfigFeatures },
        profile_version: 3,
        workspace_root: "/tmp/pa-1",
        workspace_is_default: true,
        node_id: "node-1",
        node_name: "MacBook",
        node_status: mockNodeStatus,
        updated_at: "2026-11-25T10:00:00Z",
      },
      capabilities: buildMockCapabilities(),
    })),
  };
});

function renderAgentConfig({ personal }: { personal: boolean }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const router = createMemoryRouter(
    [{ path: "/settings/agents/:agentId", element: <AgentDetailPage personal={personal} /> }],
    { initialEntries: ["/settings/agents/pa-1?view=config"] },
  );
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

function renderAgentCreate() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const router = createMemoryRouter(
    [
      { path: "/settings/agents/new/:nodeId", element: <AgentCreatePage /> },
      { path: "/chat/:conversationId", element: <div data-testid="chat-dest" /> },
      { path: "/settings/agents/:agentId", element: <div data-testid="detail-dest" /> },
    ],
    { initialEntries: ["/settings/agents/new/node-1"] },
  );
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("Global-mode proactive_planning toggle and task_graph dependency", () => {
  beforeEach(() => {
    setLanguage("zh");
    mockNodeStatus = "online";
    mockWorkMode = "global";
    mockConfigFeatures = { task_graph: true, cron_scheduling: true, proactive_planning: true };
    updateCalls.length = 0;
    createCalls.length = 0;
    useAuthStore.getState().setSession({ access_token: TEST_ACCESS_TOKEN, user: TEST_AUTH_USER });
  });

  it("renders proactive_planning on PA, blocks turning off task_graph first with toast, and saves without leaking personal_agent", async () => {
    renderAgentConfig({ personal: true });

    const proactiveCheckbox = await screen.findByRole("checkbox", { name: "主动筹划" });
    const taskGraphCheckbox = screen.getByRole("checkbox", { name: "任务图" });
    expect(proactiveCheckbox).toBeChecked();
    expect(taskGraphCheckbox).toBeChecked();
    expect(screen.getByText(/03:00/)).toBeInTheDocument();

    await userEvent.click(taskGraphCheckbox);
    expect(taskGraphCheckbox).toBeChecked();
    expect(await screen.findByText("请先关闭「主动筹划」")).toBeInTheDocument();

    await userEvent.click(proactiveCheckbox);
    await waitFor(() => expect(proactiveCheckbox).not.toBeChecked());
    expect(taskGraphCheckbox).toBeChecked();

    await userEvent.click(screen.getByRole("button", { name: "保存 Agent" }));
    await waitFor(() => expect(updateCalls).toHaveLength(1));
    expect(updateCalls[0]!.payload.features).toMatchObject({
      task_graph: true,
      proactive_planning: false,
    });
    expect(updateCalls[0]!.payload).not.toHaveProperty("personal_agent");
  });

  it("renders proactive_planning with role-scoped help on global non-PA digital employees and hides it on single_thread agents", async () => {
    const view = renderAgentConfig({ personal: false });

    const proactiveCheckbox = await screen.findByRole("checkbox", { name: "主动筹划" });
    const taskGraphCheckbox = screen.getByRole("checkbox", { name: "任务图" });
    expect(proactiveCheckbox).toBeChecked();
    expect(screen.getByText(/各协作会话/)).toBeInTheDocument();

    await userEvent.click(taskGraphCheckbox);
    expect(taskGraphCheckbox).toBeChecked();
    expect(await screen.findByText("请先关闭「主动筹划」")).toBeInTheDocument();

    view.unmount();

    mockWorkMode = "single_thread";
    mockConfigFeatures = { task_graph: true, cron_scheduling: true };
    renderAgentConfig({ personal: false });

    const singleTaskGraph = await screen.findByRole("checkbox", { name: "任务图" });
    expect(screen.queryByRole("checkbox", { name: "主动筹划" })).not.toBeInTheDocument();
    await userEvent.click(singleTaskGraph);
    await waitFor(() => expect(singleTaskGraph).not.toBeChecked());
  });

  it("strips proactive_planning when switching create mode to single_thread, restores default on return to global, and honors explicit disable", async () => {
    renderAgentCreate();

    const proactiveCheckbox = await screen.findByRole("checkbox", { name: "主动筹划" });
    expect(proactiveCheckbox).toBeChecked();

    const radios = screen.getAllByRole("radio");
    const globalRadio = radios.find(el => (el as HTMLInputElement).value === "global")!;
    const singleRadio = radios.find(el => (el as HTMLInputElement).value === "single_thread")!;

    // Switch global -> single_thread -> global: hides proactive_planning & nano-proactive-care in single_thread and restores in global
    expect(screen.getByText(/nano-proactive-care/)).toBeInTheDocument();
    await userEvent.click(singleRadio);
    expect(screen.queryByRole("checkbox", { name: "主动筹划" })).not.toBeInTheDocument();
    expect(screen.queryByText(/nano-proactive-care/)).not.toBeInTheDocument();

    await userEvent.click(globalRadio);
    const restoredProactive = await screen.findByRole("checkbox", { name: "主动筹划" });
    expect(restoredProactive).toBeChecked();
    expect(screen.getByText(/nano-proactive-care/)).toBeInTheDocument();

    // Explicitly uncheck in global, then switch global -> single_thread -> global: remains unchecked
    await userEvent.click(restoredProactive);
    await waitFor(() => expect(restoredProactive).not.toBeChecked());
    await userEvent.click(singleRadio);
    await userEvent.click(globalRadio);
    expect(await screen.findByRole("checkbox", { name: "主动筹划" })).not.toBeChecked();

    // Switch back to single_thread and submit creation: payload must not carry proactive_planning
    await userEvent.click(singleRadio);
    await userEvent.type(screen.getByLabelText(/Agent ID/), "single-helper");
    await userEvent.type(screen.getByLabelText(/显示名/), "Single Helper");
    await userEvent.click(screen.getByRole("button", { name: /创建 Agent/ }));

    await waitFor(() => expect(createCalls).toHaveLength(1));
    expect(createCalls[0]!.payload.work_mode).toBe("single_thread");
    expect(createCalls[0]!.payload.features).not.toHaveProperty("proactive_planning");
  });

  it("locks proactive_planning checkbox and Save button read-only when the owning node is offline", async () => {
    mockNodeStatus = "offline";
    renderAgentConfig({ personal: false });

    const proactiveCheckbox = await screen.findByRole("checkbox", { name: "主动筹划" });
    expect(proactiveCheckbox).toBeDisabled();
    expect(screen.getByRole("button", { name: "保存 Agent" })).toBeDisabled();
    expect(screen.getByTestId("settings-availability")).toHaveTextContent("电脑离线 · 只读");
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { featureDependencies } from "@nano/product-contracts/capabilities";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { setLanguage } from "../../../i18n";
import { TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../../../test/render-router";
import { useAuthStore } from "../../auth/auth-store";
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
let mockConfigFeatures: Record<string, boolean> = {
  task_graph: true,
  cron_scheduling: true,
  proactive_planning: true,
};
const updateCalls: Array<{ agentId: string; payload: Record<string, unknown> }> = [];

vi.mock("../../../realtime/user-stream", () => ({
  subscribeUserStream: () => () => undefined,
}));

vi.mock("./agents-rail-desktop", () => ({
  AgentsRailDesktop: () => null,
}));

vi.mock("../../personal-agent/personal-agent-settings", () => ({
  PersonalAgentSettings: () => null,
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

vi.mock("./im-agent-config-api", async importOriginal => {
  const actual = await importOriginal<typeof import("./im-agent-config-api")>();
  return {
    ...actual,
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
        description: "我的个人助手",
        work_mode: "global",
        approval_mode: "inherit",
        collaboration_scope: "owner_only",
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
      capabilities: {
        node_id: "node-1",
        node_name: "MacBook",
        node_status: mockNodeStatus,
        model_options: [],
        platform_default_model: "gpt-5.4",
        inherited_approval_rules: "codex",
        skills: [],
        fixed_tools: [],
        tools: ["task_graph", ...SCHEDULE_TOOLS].map(name => ({ name })),
        features: featureDependencies
          .filter(feat => ["task_graph", "cron_scheduling", "proactive_planning"].includes(feat.key))
          .map(feat => ({
            ...feat,
            label_i18n: `feature.${feat.key}.label`,
            help_i18n: `feature.${feat.key}.help`,
          })),
      },
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

describe("PA proactive_planning toggle and task_graph dependency", () => {
  beforeEach(() => {
    setLanguage("zh");
    mockNodeStatus = "online";
    mockConfigFeatures = { task_graph: true, cron_scheduling: true, proactive_planning: true };
    updateCalls.length = 0;
    useAuthStore.getState().setSession({ access_token: TEST_ACCESS_TOKEN, user: TEST_AUTH_USER });
  });

  it("renders proactive_planning on PA, blocks turning off task_graph first with toast, and saves without leaking personal_agent", async () => {
    renderAgentConfig({ personal: true });

    const proactiveCheckbox = await screen.findByRole("checkbox", { name: "主动筹划" });
    const taskGraphCheckbox = screen.getByRole("checkbox", { name: "任务图" });
    expect(proactiveCheckbox).toBeChecked();
    expect(taskGraphCheckbox).toBeChecked();
    expect(screen.getByText(/03:00/)).toBeInTheDocument();

    // Attempting to turn off 任务图 while 主动筹划 is enabled keeps 任务图 checked and shows dependency toast
    await userEvent.click(taskGraphCheckbox);
    expect(taskGraphCheckbox).toBeChecked();
    expect(await screen.findByText("请先关闭「主动筹划」")).toBeInTheDocument();

    // Turn off 主动筹划 and save
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

  it("hides proactive_planning on ordinary non-PA agents", async () => {
    renderAgentConfig({ personal: false });

    expect(await screen.findByRole("checkbox", { name: "任务图" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "主动筹划" })).not.toBeInTheDocument();
  });

  it("locks proactive_planning checkbox and Save button read-only when the PA node is offline", async () => {
    mockNodeStatus = "offline";
    renderAgentConfig({ personal: true });

    const proactiveCheckbox = await screen.findByRole("checkbox", { name: "主动筹划" });
    expect(proactiveCheckbox).toBeDisabled();
    expect(screen.getByRole("button", { name: "保存 Agent" })).toBeDisabled();
    expect(screen.getByTestId("settings-availability")).toHaveTextContent("电脑离线 · 只读");
  });
});

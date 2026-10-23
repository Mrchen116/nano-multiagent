import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getAgentDetailState: vi.fn(),
  getAgentCapabilityUsage: vi.fn(),
  listAgentSummaries: vi.fn(),
  listNodes: vi.fn(),
  listAgents: vi.fn(),
  navigate: vi.fn(),
  updateAgentConfig: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ agentId: "agent-1" }),
    useNavigate: () => apiMocks.navigate,
  };
});

vi.mock("../../chat/chat-api", () => ({
  createConversation: vi.fn(),
  listAgents: apiMocks.listAgents,
}));

vi.mock("../../../hooks/use-is-mobile", () => ({ useIsMobile: () => false }));

vi.mock("./im-agent-config-api", async (importOriginal) => ({
  ...await importOriginal<typeof import("./im-agent-config-api")>(),
  getAgentDetailState: apiMocks.getAgentDetailState,
  getAgentCapabilityUsage: apiMocks.getAgentCapabilityUsage,
  listAgentSummaries: apiMocks.listAgentSummaries,
  listNodes: apiMocks.listNodes,
  promptPreview: vi.fn(),
  updateAgentConfig: apiMocks.updateAgentConfig,
}));

import { AgentDetailPage } from "./agent-detail-page";
import type { AgentDetailState } from "./im-agent-config-api";

const HEARTBEAT = {
  key: "heartbeat",
  label_i18n: "Heartbeat",
  help_i18n: "Run periodic checks",
  default_on: false,
  available: true,
  requires: { features: [], tools: [], skills: [] },
};

const CRON = {
  key: "cron_scheduling",
  label_i18n: "Cron scheduling",
  help_i18n: "Run scheduled jobs",
  default_on: false,
  available: true,
  requires: { features: [], tools: ["cron"], skills: [] },
};

function agentState(feature: typeof HEARTBEAT | typeof CRON): AgentDetailState {
  return {
    config: {
      agent_id: "agent-1",
      owner_id: "owner-1",
      display_name: "Settings Agent",
      description: "",
      custom_prompt: "",
      features: {},
      skills: [],
      tool_allowlist: [] as string[],
      group_reply_policy: "MENTION" as const,
      default_model: null,
      model_fallbacks: [],
      reasoning_effort: null,
      workspace_root: "/tmp",
      workspace_is_default: false,
      profile_version: 1,
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      updated_at: "2026-03-13T10:00:00Z",
      heartbeat: { every: "1h" },
    },
    capabilities: {
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      capabilities_updated_at: "2026-03-13T10:00:00Z",
      skills: [],
      tools: [{ name: "cron", description: "Cron scheduling", default_on: false }],
      model_options: [],
      platform_default_model: null,
      features: [feature],
    },
    owningNode: null,
  };
}

function renderDetail() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AgentDetailPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  apiMocks.getAgentCapabilityUsage.mockResolvedValue({ checked_at: "now", active_tasks: 0, active_schedules: 0, busy: [] });
  apiMocks.listNodes.mockResolvedValue([]);
  apiMocks.listAgentSummaries.mockResolvedValue([
    {
      agent_id: "agent-1",
      display_name: "Settings Agent",
      owner_id: "owner-1",
      description: "",
      profile_version: 1,
      default_model: null,
      workspace_root: "",
      workspace_is_default: false,
    },
  ]);
  apiMocks.listAgents.mockResolvedValue([]);
});

afterEach(() => vi.clearAllMocks());

it("keeps a busy named Skill selected before saving", async () => {
  const state = agentState(CRON);
  state.capabilities.features = [];
  state.config.features = {};
  state.config.skills = [];
  state.config.skills_selection_mode = "explicit_denylist";
  state.capabilities.skills = [{name:"ordinary-method",description:"Method",default_on:true}];
  apiMocks.getAgentDetailState.mockResolvedValue(state);
  apiMocks.getAgentCapabilityUsage.mockResolvedValue({checked_at:"now",active_tasks:0,active_schedules:0,busy:[{kind:"skill",name:"ordinary-method"}]});
  renderDetail();
  const skill = await screen.findByRole("button", {name:"ordinary-method"});
  await userEvent.click(skill);
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/in use/i));
  expect(skill).toHaveAttribute("aria-pressed","true");
  expect(apiMocks.updateAgentConfig).not.toHaveBeenCalled();
});

describe("agent feature settings", () => {
  it("reveals heartbeat cadence after the user enables heartbeat", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailState.mockResolvedValue(agentState(HEARTBEAT));

    renderDetail();
    await screen.findByRole("heading", { name: "Settings Agent" });
    expect(screen.queryByRole("heading", { name: /Heartbeat/i })).toBeNull();

    await user.click(document.querySelector<HTMLInputElement>('[data-feature-key="heartbeat"]')!);

    expect(await screen.findByRole("heading", { name: /Heartbeat/i })).toBeInTheDocument();
    expect(document.querySelector<HTMLInputElement>("#heartbeat-every")).toHaveValue(1);
  });

  it("reveals cron jobs after the user enables scheduling", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailState.mockResolvedValue(agentState(CRON));

    renderDetail();
    await screen.findByRole("heading", { name: "Settings Agent" });
    expect(screen.queryByRole("heading", { name: /Cron Jobs/i })).toBeNull();

    await user.click(
      document.querySelector<HTMLInputElement>('[data-feature-key="cron_scheduling"]')!,
    );

    expect(await screen.findByRole("heading", { name: /Cron Jobs/i })).toBeInTheDocument();
  });
});

it("saves a single Goal tool without a feature or selecting its siblings", async () => {
  const user = userEvent.setup();
  const state = agentState(CRON);
  state.capabilities.features = [];
  const names = ['create_goal', 'get_goal', 'update_goal'];
  state.capabilities.tools = names.map(name => ({name, description:name, default_on:false}));
  apiMocks.getAgentDetailState.mockResolvedValue(state);
  apiMocks.updateAgentConfig.mockImplementation(async (_id, payload) => ({...state.config,...payload}));
  renderDetail();
  await screen.findByRole('heading', {name:'Settings Agent'});
  const pill = (name: string) => document.querySelector<HTMLButtonElement>(`[data-testid="pill-selector-tools"] [data-pill-name="${name}"]`)!;
  expect(screen.queryByRole('checkbox', {name:/DSH Goal/})).toBeNull();
  for (const name of names) expect(pill(name)).toHaveAttribute('aria-pressed', 'false');
  await user.click(pill('get_goal'));
  expect(pill('create_goal')).toHaveAttribute('aria-pressed', 'false');
  expect(pill('update_goal')).toHaveAttribute('aria-pressed', 'false');
  await user.click(screen.getByRole('button', {name:/^Save$/i}));
  await waitFor(() => expect(apiMocks.updateAgentConfig).toHaveBeenCalledWith('agent-1', expect.objectContaining({features:{},tool_allowlist:['get_goal']})));
});

// A protected capability must remain selected without disabling its parent feature.
it("keeps required tools selected and presents a transient overlay", async () => {
  const state = agentState(HEARTBEAT);
  state.config.features = { heartbeat: true };
  state.config.tool_allowlist = ["read"];
  state.capabilities.tools = [{ name: "read", description: "Read", default_on: true }];
  state.capabilities.features = [{ ...HEARTBEAT, requires: { features: [], tools: ["read"], skills: [] } }];
  apiMocks.getAgentDetailState.mockResolvedValue(state);
  renderDetail();
  const tool = await screen.findByRole("button", { name: "read" });
  await userEvent.click(tool);
  expect(tool).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("status")).toHaveTextContent("Heartbeat");
});


it("keeps Task on while checking usage and when active responsibilities block closing", async () => {
  const state = agentState({ ...HEARTBEAT, key: "task_graph", label_i18n: "Task", default_on: true, requires: { features: [], tools: ["task_graph"], skills: [] } });
  state.config.features = {};
  state.config.tool_allowlist = ["task_graph"];
  state.capabilities.tools = [{ name: "task_graph", description: "Task", default_on: true }];
  let resolve!: (value: unknown) => void;
  apiMocks.getAgentCapabilityUsage.mockImplementation(() => new Promise(done => { resolve = done; }));
  apiMocks.getAgentDetailState.mockResolvedValue(state);
  renderDetail();
  await screen.findByRole("heading", { name: "Settings Agent" });
  const toggle = document.querySelector<HTMLInputElement>('[data-feature-key="task_graph"]')!;
  await userEvent.click(toggle);
  expect(toggle).toBeChecked();
  expect(apiMocks.getAgentCapabilityUsage).toHaveBeenCalledWith("agent-1");
  await act(async () => { resolve({ checked_at: "now", active_tasks: 1, active_schedules: 0, busy: [] }); });
  expect(toggle).toBeChecked();
  expect(screen.getByRole("status")).toHaveTextContent("Task");
  expect(apiMocks.updateAgentConfig).not.toHaveBeenCalled();
});

it("restores a rejected capability and retains other draft changes", async () => {
  const state = agentState(HEARTBEAT);
  state.config.features = { heartbeat: true };
  apiMocks.getAgentDetailState.mockResolvedValue(state);
  apiMocks.updateAgentConfig.mockRejectedValue(Object.assign(new Error("busy"), { blocks: [{ code: "capability_busy", target: {kind: "feature", name: "heartbeat"} }] }));
  renderDetail();
  await screen.findByRole("heading", { name: "Settings Agent" });
  const name = screen.getByLabelText(/Display name/i);
  await userEvent.clear(name);
  await userEvent.type(name, "Edited name");
  const toggle = document.querySelector<HTMLInputElement>('[data-feature-key="heartbeat"]')!;
  await userEvent.click(toggle);
  await waitFor(() => expect(toggle).not.toBeChecked());
  await userEvent.click(screen.getByRole("button", { name: /^Save$/i }));
  await waitFor(() => expect(toggle).toBeChecked());
  expect(name).toHaveValue("Edited name");
  expect(screen.getByRole("status")).toBeInTheDocument();
});


it("extends one overlay on repeated attempts and fades it after two seconds", async () => {
  const state = agentState(HEARTBEAT);
  state.config.features = { heartbeat: true };
  state.config.tool_allowlist = ["read"];
  state.capabilities.tools = [{ name: "read", description: "Read", default_on: true }];
  state.capabilities.features = [{ ...HEARTBEAT, requires: { features: [], tools: ["read"], skills: [] } }];
  apiMocks.getAgentDetailState.mockResolvedValue(state);
  renderDetail();
  const tool = await screen.findByRole("button", { name: "read" });
  vi.useFakeTimers();
  try {
    tool.focus();
    fireEvent.click(tool);
    expect(screen.getAllByRole("status")).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1000));
    fireEvent.click(tool);
    act(() => vi.advanceTimersByTime(1500));
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(tool).toHaveFocus();
    act(() => vi.advanceTimersByTime(600));
    expect(screen.queryByRole("status")).toBeNull();
    expect(tool).toHaveAttribute("aria-pressed", "true");
  } finally { vi.useRealTimers(); }
});

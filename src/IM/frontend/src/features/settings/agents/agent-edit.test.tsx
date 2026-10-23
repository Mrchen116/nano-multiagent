import userEvent from "@testing-library/user-event";
import {act, fireEvent, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, vi} from "vitest";
import {useAuthStore} from "../../auth/auth-store";
import {appRoutes} from "../../../app/router";
import {renderRouter} from "../../../test/render-router";
import type {UserStreamSubscriber} from "../../../realtime/user-stream";
import type {AgentConfig} from "./im-agent-config-api";

const stream = vi.hoisted(() => ({subscribers: new Set<UserStreamSubscriber>()}));
vi.mock("../../../realtime/user-stream", () => ({subscribeUserStream: (subscriber: UserStreamSubscriber) => {
  stream.subscribers.add(subscriber); return () => stream.subscribers.delete(subscriber);
}}));
const fetchMock = vi.fn();
const path = "/im/v1/agents/agent-core-1";
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status, headers: {"Content-Type": "application/json"}});
const capabilities = {
  node_id: "node-1", node_name: "MacBook", node_status: "online",
  skills: ["tdd-execution-worker", "playwright", "plan"].map(name => ({name, description: name})),
  tools: ["bash", "read_file", "task"].map(name => ({name, description: name})),
  features: [],
  model_options: [{name: "codex_oauth:gpt-5.5", provider: "openai_compat", reasoning: {kind: "selectable", default: "high", levels: ["high", "max"]}}],
  platform_default_model: "codex_oauth:gpt-5.5",
};
let config: AgentConfig;
let online: boolean;
let pending: boolean;
let settingsRead: () => Promise<Response>;
let save: (body: Record<string, unknown>) => Response;
function settings() {
  return {
    config, node: {node_id: "node-1", state: online ? "online" : "offline"},
    display: {source: "unavailable", captured_at: null, data: null, error: null},
    live_capabilities: online ? capabilities : null,
    pending_operation: pending ? {operation_id: "op-1", status: "pending"} : null,
    ready: online && !pending,
  };
}
function open() { return renderRouter({routes: appRoutes, initialEntries: ["/settings/agents/agent-core-1"]}); }
async function presence(status: "online" | "offline") {
  online = status === "online";
  await act(async () => { for (const s of stream.subscribers) s.onEvent({eventType: "agent.status_changed", payload: {agent_id: config.agent_id, status}}); });
}
const patches = () => fetchMock.mock.calls.filter(([url, init]) => url === `${path}/config` && init?.method === "PATCH");

beforeEach(() => {
  online = true; pending = false;
  config = {
    agent_id: "agent-core-1", owner_id: "owner-1", display_name: "Core Planner", description: "Milestone execution coordinator",
    skills: ["tdd-execution-worker", "playwright"], tool_allowlist: ["bash", "read_file"],
    group_reply_policy: "MENTION", default_model: null, model_fallbacks: [], reasoning_effort: null,
    workspace_root: "/Users/demo/nano-assistant/workspace/agent-core-1", workspace_is_default: true,
    profile_version: 12, node_id: "node-1", node_name: "MacBook", updated_at: "2026-03-13T10:00:00Z",
  };
  settingsRead = async () => json(settings());
  save = body => {config = {...config, ...body, profile_version: config.profile_version + 1}; return json(config);};
  globalThis.fetch = fetchMock as typeof fetch;
  fetchMock.mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === `${path}/settings`) return settingsRead();
    if (url === `${path}/config` && init?.method === "PATCH") return save(JSON.parse(init.body));
    if (url.includes("/settings/sections/")) return json({source: "current", captured_at: "2026-10-23T00:00:00Z", data: [], error: null});
    if (url.includes("/im/v1/contacts?")) return json({items: [{user_id: "agent-user", kind: "agent", agent_id: config.agent_id, display_name: "Core Planner", owner_id: useAuthStore.getState().user?.id, work_mode: "single_thread", node_name: "MacBook", status: "online"}], next_cursor: null});
    if (url === "/im/v1/agents" || url === "/im/v1/nodes") return json([]);
    return new Response(null, {status: 404});
  });
});
afterEach(() => {vi.useRealTimers(); fetchMock.mockReset(); stream.subscribers.clear();});

it("loads settings and saves edited profile, allowlists and the explicit model effort", async () => {
  const user = userEvent.setup(); open();
  const input = await screen.findByLabelText("Display Name");
  expect(screen.getByLabelText("Workspace Root")).toHaveValue(config.workspace_root);
  expect(screen.getByRole("button", {name: /^Save Agent$/})).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Approval strategy"), "codex");
  await user.selectOptions(screen.getByLabelText("Reasoning effort"), "max");
  fireEvent.change(input, {target: {value: "Core Planner X"}});
  await user.click(screen.getByRole("button", {name: /^playwright$/i}));
  await user.click(screen.getByRole("button", {name: /^plan$/i}));
  await user.click(screen.getByRole("button", {name: /^bash$/i}));
  await user.click(screen.getByRole("button", {name: /^Save Agent$/}));
  await waitFor(() => expect(screen.getByLabelText("Profile Version")).toHaveValue("v13"));
  expect(JSON.parse(patches()[0][1].body)).toMatchObject({profile_version: 12, display_name: "Core Planner X", approval_mode: "codex", skills: ["playwright"], skills_selection_mode: "explicit_denylist", tool_allowlist: ["read_file"], default_model: null, reasoning_effort: "max"});
});

it("keeps saved settings readable and blocks editing when live capabilities are unavailable", async () => {
  online = false;
  config.default_model = "codex_oauth:gpt-5.5"; config.reasoning_effort = "high";
  open();
  expect(await screen.findByLabelText("Display Name")).toBeDisabled();
  expect(screen.getByLabelText("Default Model")).toHaveValue(config.default_model);
  expect(screen.getByLabelText("Reasoning effort")).toHaveValue("high");
  expect(screen.getByRole("button", {name: /^Save Agent$/})).toBeDisabled();
  expect(screen.queryByText(/no longer accepts|Remove unavailable/i)).not.toBeInTheDocument();
  expect(patches()).toHaveLength(0);
});

it("blocks save when required fields are empty", async () => {
  const user = userEvent.setup(); open();
  await user.clear(await screen.findByLabelText("Display Name"));
  await user.click(screen.getByRole("button", {name: /^Save Agent$/}));
  expect(await screen.findByText(/Display name is required/i)).toBeInTheDocument();
  expect(patches()).toHaveLength(0);
});

it("surfaces a version conflict without replacing the draft or its base version", async () => {
  const user = userEvent.setup();
  save = () => json({detail: "profile_version conflict"}, 409);
  open(); fireEvent.change(await screen.findByLabelText("Display Name"), {target: {value: "Draft"}});
  await user.click(screen.getByRole("button", {name: /^Save Agent$/}));
  expect(await screen.findByTestId("agent-save-error")).toHaveTextContent(/409.*profile_version conflict/i);
  expect(screen.getByLabelText("Display Name")).toHaveValue("Draft");
  expect(screen.getByLabelText("Profile Version")).toHaveValue("v12");
});

it("confirms an accepted pending save without replaying it or losing its paired effort", async () => {
  const user = userEvent.setup();
  config.default_model = "codex_oauth:gpt-5.5"; config.reasoning_effort = "high";
  save = () => {pending = true; return json({detail: {code: "config_apply_pending", message: "Awaiting receipt"}}, 503);};
  open(); await user.selectOptions(await screen.findByLabelText("Reasoning effort"), "max");
  await user.click(screen.getByRole("button", {name: /^Save Agent$/}));
  await waitFor(() => expect(screen.getByRole("button", {name: /^Save Agent$/})).toBeDisabled());
  expect(screen.getByLabelText("Reasoning effort")).toHaveValue("max");
  config = {...config, reasoning_effort: "max", profile_version: 13}; pending = false;
  await waitFor(() => expect(screen.getByLabelText("Profile Version")).toHaveValue("v13"), {timeout: 2500});
  expect(patches()).toHaveLength(1);
});

it("preserves a dirty draft through disconnect, delayed refresh and a remote version change", async () => {
  const user = userEvent.setup(); open();
  fireEvent.change(await screen.findByLabelText("Display Name"), {target: {value: "Unsubmitted draft"}});
  await user.selectOptions(screen.getByLabelText("Reasoning effort"), "max");
  await presence("offline");
  expect(screen.getByLabelText("Display Name")).toHaveValue("Unsubmitted draft");
  await waitFor(() => expect(screen.getByLabelText("Display Name")).toBeDisabled());
  let finish!: (response: Response) => void;
  settingsRead = () => new Promise(resolve => {finish = resolve;});
  await presence("online");
  expect(screen.getByLabelText("Display Name")).toBeDisabled();
  config = {...config, display_name: "Changed elsewhere", profile_version: 13};
  await act(async () => {finish(json(settings()));});
  expect(screen.getByLabelText("Display Name")).toHaveValue("Unsubmitted draft");
  expect(screen.getByLabelText("Reasoning effort")).toHaveValue("max");
  expect(screen.getByRole("button", {name: /^Save Agent$/})).toBeDisabled();
  expect(screen.getByText(/Settings changed elsewhere/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", {name: /Discard/i}));
  expect(screen.getByLabelText("Display Name")).toHaveValue("Changed elsewhere");
  expect(screen.getByLabelText("Profile Version")).toHaveValue("v13");
  expect(patches()).toHaveLength(0);
});

it("does not save a capability default when only the name was edited", async () => {
  const user = userEvent.setup(); open();
  fireEvent.change(await screen.findByLabelText("Display Name"), {target: {value: "Renamed"}});
  await user.click(screen.getByRole("button", {name: /^Save Agent$/}));
  await waitFor(() => expect(patches()).toHaveLength(1));
  expect(JSON.parse(patches()[0][1].body).reasoning_effort).toBeNull();
});

it("discards a late response from the previous connection and waits for stream recovery", async () => {
  open(); await screen.findByLabelText("Display Name");
  const oldResponse = settings();
  let late!: (response: Response) => void;
  settingsRead = () => new Promise(resolve => {late = resolve;});
  await presence("online");
  await waitFor(() => expect(late).toBeDefined());
  settingsRead = async () => json(settings());
  await presence("offline");
  await waitFor(() => expect(screen.getByLabelText("Display Name")).toBeDisabled());
  await act(async () => {late(json(oldResponse));});
  expect(screen.getByLabelText("Display Name")).toBeDisabled();
  expect(screen.getByTestId("settings-availability")).toHaveTextContent(/computer is offline/i);
  await presence("online");
  await waitFor(() => expect(screen.getByLabelText("Display Name")).toBeEnabled());
  await act(async () => {for (const s of stream.subscribers) s.onConnectionStatus?.({kind: "reconnecting", retryAt: Date.now() + 1000});});
  await waitFor(() => expect(screen.getByLabelText("Display Name")).toBeDisabled());
  expect(screen.getByTestId("settings-availability")).toHaveTextContent(/connection is not confirmed/i);
  await act(async () => {for (const s of stream.subscribers) s.onConnectionStatus?.(null);});
  await waitFor(() => expect(screen.getByLabelText("Display Name")).toBeEnabled());
  expect(patches()).toHaveLength(0);
});

it("shows an unavailable cron observation instead of claiming there are no jobs", async () => {
  online = false; config.features = {cron_scheduling: true};
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((input, init) => String(input).endsWith("/settings/sections/cron")
    ? Promise.resolve(json({source: "unavailable", captured_at: null, data: null, error: {code: "offline", message: "offline"}}))
    : original(input, init));
  open(); await screen.findByLabelText("Display Name");
  await waitFor(() => expect(screen.getByTestId("cron-jobs-list")).toHaveTextContent(/no previously confirmed/i));
  expect(screen.getByTestId("cron-jobs-list")).not.toHaveTextContent(/no scheduled jobs/i);
});

it("shows an accepted pending operation after reopening offline", async () => {
  online = false; pending = true; open();
  await screen.findByLabelText("Display Name");
  expect(screen.getByTestId("settings-availability")).toHaveTextContent(/waiting for.*confirm|awaiting.*confirm/i);
  expect(screen.getByRole("button", {name: /^Save Agent$/})).toBeDisabled();
  expect(patches()).toHaveLength(0);
});

it("lets offline users expand saved fallback models without editing", async () => {
  online = false; config.model_fallbacks = ["retired:fallback"];
  const user = userEvent.setup(); open(); await screen.findByLabelText("Display Name");
  await user.click(screen.getByRole("button", {name: /Fallbacks.*1/i}));
  const fallback = screen.getByRole("combobox", {name: /Fallback.*1/i});
  expect(fallback).toHaveValue("retired:fallback");
  expect(fallback).toBeDisabled();
});

it("retains missing catalog selections and requires explicit correction before save", async () => {
  config.default_model = "retired:primary"; config.model_fallbacks = ["retired:fallback"];
  config.tool_allowlist = ["retired-tool"]; config.skills = ["retired-skill"]; config.skills_selection_mode = "explicit_allowlist";
  const user = userEvent.setup(); open();
  fireEvent.change(await screen.findByLabelText("Display Name"), {target: {value: "Kept draft"}});
  expect(screen.getByRole("button", {name: "retired-tool"})).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", {name: "retired-skill"})).toHaveAttribute("aria-pressed", "true");
  expect(screen.getAllByText(/unavailable in the current catalog/i)).toHaveLength(3);
  expect(screen.getByRole("button", {name: /^Save Agent$/})).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Default Model"), "codex_oauth:gpt-5.5");
  await user.click(screen.getByRole("button", {name: /Fallbacks.*1/i}));
  await user.click(screen.getByRole("button", {name: /^Remove$/i}));
  await user.click(screen.getByRole("button", {name: "retired-tool"}));
  await user.click(screen.getByRole("button", {name: "retired-skill"}));
  await user.click(screen.getByRole("button", {name: /^Save Agent$/}));
  await waitFor(() => expect(patches()).toHaveLength(1));
  expect(JSON.parse(patches()[0][1].body)).toMatchObject({display_name: "Kept draft", skills: ["tdd-execution-worker", "playwright", "plan", "retired-skill"], skills_selection_mode: "explicit_denylist", tool_allowlist: [], model_fallbacks: []});
});

it("keeps independently captured heartbeat and prompt bodies after online read failures", async () => {
  config.features = {heartbeat: true};
  let fail = false;
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((input, init) => {
    const url = String(input);
    if (url.endsWith("/heartbeat-md") || url.endsWith("/prompt-preview")) {
      if (fail) return Promise.resolve(json({detail: "temporary read failure"}, 503));
      return Promise.resolve(json(url.endsWith("/heartbeat-md") ? {node_online: true, content: "Remember weekly review"} : {prompt: "Confirmed stable prompt"}));
    }
    return original(input, init);
  });
  const user = userEvent.setup(); open(); await screen.findByLabelText("Display Name");
  await user.click(screen.getByRole("button", {name: /View HEARTBEAT.md/i}));
  await user.click(screen.getByRole("button", {name: /Preview stable system prompt/i}));
  expect(await screen.findByText("Remember weekly review")).toBeInTheDocument();
  expect(await screen.findByText("Confirmed stable prompt")).toBeInTheDocument();
  await presence("offline");
  await waitFor(() => expect(screen.getAllByText(/Last confirmed:/i).length).toBeGreaterThanOrEqual(2));
  fail = true; await presence("online");
  await waitFor(() => expect(screen.getByLabelText("Display Name")).toBeEnabled());
  await user.click(screen.getByRole("button", {name: /View HEARTBEAT.md/i}));
  await user.click(screen.getByRole("button", {name: /View HEARTBEAT.md/i}));
  await waitFor(() => expect(screen.getAllByText(/Could not refresh this information/i).length).toBeGreaterThanOrEqual(2));
  expect(screen.getByText("Remember weekly review")).toBeInTheDocument();
  expect(screen.getByText("Confirmed stable prompt")).toBeInTheDocument();
  expect(screen.queryByText(/Node is offline/i)).not.toBeInTheDocument();
});

it("preserves a last successful usage read when only the next usage request fails", async () => {
  let fail = false;
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((input, init) => {
    if (String(input).endsWith("/settings/sections/usage")) return fail ? Promise.reject(new Error("usage transport failed")) : Promise.resolve(json({source: "current", captured_at: "2026-10-23T00:00:00Z", error: null, data: {agent_id: config.agent_id, node_id: "node-1", node_online: true, skills: [], heatmap_data: [], health: {created_auto_total: 0, active_auto_total: 0, used_auto_total: 0}}}));
    return original(input, init);
  });
  const user = userEvent.setup(); open(); await screen.findByLabelText("Display Name");
  await user.click(screen.getByRole("button", {name: /View skill statistics/i}));
  expect(await screen.findByText("No skill usage yet")).toBeInTheDocument();
  fail = true; await presence("online");
  expect(await screen.findByText(/Last confirmed:.*Could not refresh/i)).toBeInTheDocument();
  expect(screen.getByText("No skill usage yet")).toBeInTheDocument();
  expect(screen.queryByText(/Gateway offline/i)).not.toBeInTheDocument();
});

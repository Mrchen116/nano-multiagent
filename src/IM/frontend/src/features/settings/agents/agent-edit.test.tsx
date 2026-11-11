import userEvent from "@testing-library/user-event";
import {focusManager} from "@tanstack/react-query";
import {act, fireEvent, screen, waitFor, within} from "@testing-library/react";
import {afterEach, beforeEach, vi} from "vitest";
import {useAuthStore} from "../../auth/auth-store";
import {appRoutes} from "../../../app/router";
import {renderRouter} from "../../../test/render-router";
import type {UserStreamSubscriber} from "../../../realtime/user-stream";
import type {AgentConfig, AgentRoleDocument} from "./im-agent-config-api";

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
  inherited_approval_rules: "codex", features: [],
  model_options: [{name: "codex_oauth:gpt-5.5", provider: "openai_compat", reasoning: {kind: "selectable", default: "high", levels: ["high", "max"]}}],
  platform_default_model: "codex_oauth:gpt-5.5",
};
let config: AgentConfig;
let role: AgentRoleDocument;
let online: boolean;
let pending: boolean;
let settingsRead: () => Promise<Response>;
let savedRead: (() => Promise<Response>) | undefined;
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
const roleWrites = () => fetchMock.mock.calls.filter(([url, init]) => url === `${path}/role` && init?.method === "PUT");
const patches = () => fetchMock.mock.calls.filter(([url, init]) => url === `${path}/config` && init?.method === "PATCH");

beforeEach(() => {
  online = true; pending = false;
  role = {content: "", version: null};
  config = {
    agent_id: "agent-core-1", owner_id: "owner-1", display_name: "Core Planner", description: "Milestone execution coordinator",
    skills: ["tdd-execution-worker", "playwright"], skills_selection_mode: "explicit_allowlist", tool_allowlist: ["bash", "read_file"],
    group_reply_policy: "MENTION", default_model: null, model_fallbacks: [], reasoning_effort: null,
    workspace_root: "/Users/demo/nano-assistant/workspace/agent-core-1", workspace_is_default: true,
    profile_version: 12, node_id: "node-1", node_name: "MacBook", updated_at: "2026-03-13T10:00:00Z",
  };
  settingsRead = async () => json(settings());
  savedRead = undefined;
  save = body => {config = {...config, ...body, profile_version: config.profile_version + 1}; return json(config);};
  globalThis.fetch = fetchMock as typeof fetch;
  fetchMock.mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === `${path}/capability-usage`) return json({checked_at: "now", active_tasks: 0, active_schedules: 0, busy: []});
    if (url === `${path}/settings`) return settingsRead();
    if (url === `${path}/settings?view=saved` && savedRead) return savedRead();
    if (url === `${path}/role`) {
      if (!online) return json({code:"role_unavailable", message:"Unavailable"}, 503);
      if (init?.method !== "PUT") return json(role);
      const update = JSON.parse(init.body) as AgentRoleDocument;
      if (update.version !== role.version) return json({code:"role_conflict", message:"Role conflict"}, 409);
      role = {...update, version:"next-role-version"};
      return json(role);
    }
    if (url === `${path}/config` && init?.method === "PATCH") return save(JSON.parse(init.body));
    if (url.includes("/settings/sections/")) return json({source: "current", captured_at: "2026-10-23T00:00:00Z", data: [], error: null});
    if (url.includes("/im/v1/contacts?")) return json({items: [{user_id: "agent-user", kind: "agent", agent_id: config.agent_id, display_name: "Core Planner", owner_id: useAuthStore.getState().user?.id, work_mode: config.work_mode ?? "single_thread", node_name: "MacBook", status: "online"}], next_cursor: null});
    if (url.includes('/work?view=summary')) return json({root_agent_id:config.agent_id,main_session_id:null,revision:1,node_connection_state:'online',main_execution:'idle',latest_main_usage:null,other_executions:[],turns:[],next_cursor:null});
    if (url === "/im/v1/agents" || url === "/im/v1/nodes") return json([]);
    return new Response(null, {status: 404});
  });
});
afterEach(() => {vi.useRealTimers(); fetchMock.mockReset(); stream.subscribers.clear();});

it("shows an editable saved draft during inspection and retains edits after confirmation", async () => {
  let finish!: (value: Response) => void;
  settingsRead = () => new Promise(resolve => {finish = resolve;});
  savedRead = async () => json({...settings(), ready:false, live_capabilities:null});
  open();
  const input = await screen.findByLabelText("Display Name");
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, {target:{value:"Draft before confirmation"}});
  expect(screen.getByRole("button", {name:/^Save Agent$/})).toBeDisabled();
  await act(async () => finish(json(settings())));
  expect(input).toHaveValue("Draft before confirmation");
  await waitFor(() => expect(screen.getByRole("button", {name:/^Save Agent$/})).toBeEnabled());
});

it("retains an unsaved configuration draft when switching through the independent Work view",async()=>{
  config.work_mode='global';
  const user=userEvent.setup(); open();
  fireEvent.change(await screen.findByLabelText('Display Name'),{target:{value:'Unsubmitted draft'}});
  await user.click(screen.getByRole('button',{name:/^Work$/}));
  expect(screen.queryByRole('textbox',{name:/^Display Name$/})).toBeNull();
  await user.click(screen.getByRole('button',{name:/^Config$/}));
  expect(await screen.findByRole('textbox',{name:/^Display Name$/})).toHaveValue('Unsubmitted draft');
});

it("keeps a freshly read online draft editable when capability confirmation fails, without allowing save",async()=>{
  let finish!: (value:Response)=>void;
  settingsRead=()=>new Promise(resolve=>{finish=resolve;});
  savedRead=async()=>json({...settings(),ready:false,live_capabilities:null});
  open();const input=await screen.findByLabelText('Display Name');
  await waitFor(()=>expect(input).toBeEnabled());
  await act(async()=>{
    for(const subscriber of stream.subscribers) if(subscriber.onConnectionStatus && subscriber.onRecovery)
      void Promise.resolve(subscriber.onRecovery()).catch(()=>{});
    await new Promise(resolve=>setTimeout(resolve,0));
  });
  expect(input).toBeEnabled();
  expect(fetchMock.mock.calls.filter(([url])=>url===`${path}/settings`)).toHaveLength(1);
  fireEvent.change(input,{target:{value:'Keep my draft'}});
  await act(async()=>finish(json({...settings(),ready:false,live_capabilities:null,display:{source:'unavailable',captured_at:null,data:null,error:{code:'timeout',message:'Confirmation failed'}}})));
  await waitFor(()=>expect(screen.getByTestId('settings-availability')).toHaveTextContent(/Confirmation failed/));
  expect(input).toBeEnabled();expect(input).toHaveValue('Keep my draft');
  expect(screen.getByRole('button',{name:/^Save Agent$/})).toBeDisabled();
});

it.each([403,404])('locks a saved draft when confirmation reports access loss (%s)',async status=>{
  let finish!: (value:Response)=>void;
  settingsRead=()=>new Promise(resolve=>{finish=resolve;});
  savedRead=async()=>json({...settings(),ready:false,live_capabilities:null});
  open();const input=await screen.findByLabelText('Display Name');
  await waitFor(()=>expect(input).toBeEnabled());
  await act(async()=>finish(json({detail:'Resource not accessible'},status)));
  await waitFor(()=>expect(input).toBeDisabled());
  expect(screen.getByRole('button',{name:/^Save Agent$/})).toBeDisabled();
});

it("loads settings and saves edited profile, allowlists and the explicit model effort", async () => {
  const user = userEvent.setup(); open();
  const input = await screen.findByLabelText("Display Name");
  expect(screen.getByLabelText("Workspace Root")).toHaveValue(config.workspace_root);
  expect(screen.getByRole("option", {name: "Follow node (Codex)"})).toBeInTheDocument();
  expect(screen.getByRole("button", {name: /^Save Agent$/})).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Approval strategy"), "codex");
  await user.selectOptions(screen.getByLabelText("Reasoning effort"), "max");
  fireEvent.change(input, {target: {value: "Core Planner X"}});
  await user.click(screen.getByRole("button", {name: /^playwright$/i}));
  await user.click(screen.getByRole("button", {name: /^plan$/i}));
  await user.click(screen.getByRole("button", {name: /^bash$/i}));
  await user.click(screen.getByRole("button", {name: /^Save Agent$/}));
  await waitFor(() => expect(screen.getByLabelText("Profile Version")).toHaveValue("v13"));
  expect(JSON.parse(patches()[0][1].body)).toMatchObject({profile_version: 12, display_name: "Core Planner X", approval_mode: "codex", skills: ["tdd-execution-worker", "plan"], skills_selection_mode: "explicit_allowlist", tool_allowlist: ["read_file"], default_model: null, reasoning_effort: "max"});
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

it.each([{disabled: []}, {disabled: ["hidden-disabled-skill"]}])("distinguishes an unconfirmed discovered Skill count from confirmed empty results ($disabled)", async ({disabled}) => {
  online = false;
  config.skills = disabled; config.skills_selection_mode = "explicit_denylist";
  open();
  await screen.findByLabelText("Display Name");
  expect(screen.getByTestId("pill-selector-skills-mode")).toHaveTextContent(/State unconfirmed/i);
  for (const name of disabled) expect(screen.getByRole("button", {name})).toBeDisabled();
  settingsRead = async () => json({...settings(), live_capabilities: {...capabilities, skills: []}});
  await presence("online");
  await waitFor(() => expect(screen.getByTestId("pill-selector-skills-mode")).toHaveTextContent("0 selected"));
});

it("blocks save when required fields are empty", async () => {
  const user = userEvent.setup(); open();
  await user.clear(await screen.findByLabelText("Display Name"));
  await user.click(screen.getByRole("button", {name: /^Save Agent$/}));
  expect(await screen.findByText(/Display name is required/i)).toBeInTheDocument();
  expect(patches()).toHaveLength(0);
});

it("keeps a confirmed draft editable during a focus refresh but blocks save until it finishes", async () => {
  open();
  const input = await screen.findByLabelText("Display Name");
  await waitFor(() => expect(input).toBeEnabled());
  let finish!: (response: Response) => void;
  settingsRead = () => new Promise(resolve => {finish = resolve;});
  act(() => {focusManager.setFocused(false); focusManager.setFocused(true);});
  await waitFor(() => expect(finish).toBeDefined());
  expect(input).toBeEnabled();
  expect(screen.getByTestId("settings-availability")).toHaveTextContent(/You can edit/);
  fireEvent.change(input, {target: {value: "During refresh"}});
  expect(screen.getByRole("button", {name: /^Save Agent$/})).toBeDisabled();
  await act(async () => {finish(json(settings()));});
  await waitFor(() => expect(screen.getByRole("button", {name: /^Save Agent$/})).toBeEnabled());
  expect(input).toHaveValue("During refresh");
  focusManager.setFocused(undefined);
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
  expect(screen.getByTestId("settings-availability")).not.toHaveTextContent(/You can edit/);
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
  expect(screen.getByTestId("settings-availability")).toHaveTextContent(/Computer offline/i);
  await presence("online");
  await waitFor(() => expect(screen.getByLabelText("Display Name")).toBeEnabled());
  await act(async () => {for (const s of stream.subscribers) s.onConnectionStatus?.({kind: "reconnecting", retryAt: Date.now() + 1000});});
  await waitFor(() => expect(screen.getByLabelText("Display Name")).toBeDisabled());
  expect(screen.getByTestId("settings-availability")).toHaveTextContent(/Connection unconfirmed/i);
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
  await waitFor(() => expect(screen.getByTestId("cron-jobs-list")).toHaveTextContent(/No confirmed information/i));
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
  expect(screen.getAllByText(/No longer available/i)).toHaveLength(3);
  expect(screen.getByRole("button", {name: /^Save Agent$/})).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Default Model"), "codex_oauth:gpt-5.5");
  await user.click(screen.getByRole("button", {name: /Fallbacks.*1/i}));
  await user.click(screen.getByRole("button", {name: /^Remove$/i}));
  await user.click(screen.getByRole("button", {name: "retired-tool"}));
  await user.click(screen.getByRole("button", {name: "retired-skill"}));
  await user.click(screen.getByRole("button", {name: /^Save Agent$/}));
  await waitFor(() => expect(patches()).toHaveLength(1));
  expect(JSON.parse(patches()[0][1].body)).toMatchObject({display_name: "Kept draft", skills: [], skills_selection_mode: "explicit_allowlist", tool_allowlist: [], model_fallbacks: []});
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
  await user.click(screen.getByRole("button", {name: /View scheduled checklist/i}));
  await user.click(screen.getByRole("button", {name: /Preview stable system prompt/i}));
  expect(await screen.findByText("Remember weekly review")).toBeInTheDocument();
  expect(await screen.findByText("Confirmed stable prompt")).toBeInTheDocument();
  await presence("offline");
  await waitFor(() => expect(screen.getAllByText(/Last confirmed/i).length).toBeGreaterThanOrEqual(2));
  fail = true; await presence("online");
  await waitFor(() => expect(screen.getByLabelText("Display Name")).toBeEnabled());
  await user.click(screen.getByRole("button", {name: /View scheduled checklist/i}));
  await user.click(screen.getByRole("button", {name: /View scheduled checklist/i}));
  await waitFor(() => expect(screen.getAllByText(/Refresh failed/i).length).toBeGreaterThanOrEqual(2));
  expect(screen.getByText("Remember weekly review")).toBeInTheDocument();
  expect(screen.getByText("Confirmed stable prompt")).toBeInTheDocument();
  expect(screen.queryByText(/Node is offline/i)).not.toBeInTheDocument();
});

it.each(["transport", "envelope"] as const)("preserves a last successful usage read when the next usage request fails (%s)", async (failure) => {
  let fail = false;
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((input, init) => {
    if (String(input).endsWith("/settings/sections/usage")) return fail && failure === "transport" ? Promise.reject(new Error("usage transport failed")) : Promise.resolve(json({source: fail ? "last_known" : "current", captured_at: "2026-10-23T00:00:00Z", error: fail ? {code: "read_failed", message: "RPC timeout"} : null, data: {agent_id: config.agent_id, node_id: "node-1", node_online: true, skills: [], heatmap_data: [], health: {created_auto_total: 0, active_auto_total: 0, used_auto_total: 0}}}));
    return original(input, init);
  });
  const user = userEvent.setup(); open(); await screen.findByLabelText("Display Name");
  await user.click(screen.getByRole("button", {name: /View skill activity/i}));
  expect(await screen.findByText("No skill usage yet")).toBeInTheDocument();
  fail = true; await presence("online");
  expect(await screen.findByText(/Last confirmed.*Refresh failed/i)).toBeInTheDocument();
  expect(within(screen.getByText("No skill usage yet").closest("section")!).getByRole("button", {name: /^Retry$/i})).toBeEnabled();
  expect(screen.getByText("No skill usage yet")).toBeInTheDocument();
  expect(screen.queryByText(/Gateway offline/i)).not.toBeInTheDocument();
});


it("saves role and ordinary configuration with one Save Agent action", async () => {
  config.owner_id = "user-1";
  open();
  const editor = await screen.findByRole("textbox", {name: "Role agreement"}, {timeout: 5000});
  expect(screen.queryByRole("button", {name: "Save role agreement"})).not.toBeInTheDocument();
  fireEvent.change(editor, {target:{value:"Coordinate the team's long-term planning."}});
  fireEvent.change(screen.getByLabelText("Display Name"), {target:{value:"New name"}});
  const save = screen.getByRole("button", {name:"Save Agent"});
  await waitFor(() => expect(save).toBeEnabled());
  fireEvent.click(save);
  await waitFor(() => expect(patches()).toHaveLength(1));
  expect(roleWrites()).toHaveLength(1);
  expect(JSON.parse(roleWrites()[0]![1].body)).toEqual({content:"Coordinate the team's long-term planning.", version:null});
  await waitFor(() => expect(save).toBeDisabled());
}, 15_000);

it("blocks an oversized role draft until it fits the save limit", async () => {
  config.owner_id = "user-1";
  open();
  const editor = await screen.findByRole("textbox", {name: "Role agreement"});
  const save = screen.getByRole("button", {name: "Save Agent"});
  fireEvent.change(editor, {target: {value: "💡".repeat(1000) + "x"}});
  expect(editor).toHaveAttribute("aria-invalid", "true");
  expect(save).toBeDisabled();
  expect(roleWrites()).toHaveLength(0);
  fireEvent.change(editor, {target: {value: "💡".repeat(1000)}});
  expect(save).toBeEnabled();
});

it("keeps the role draft and shows the latest saved agreement after a conflict", async () => {
  config.owner_id = "user-1";
  role = {content:"Original role", version:"old"};
  open();
  const editor = await screen.findByRole("textbox", {name: "Role agreement"}, {timeout: 5000});
  expect(editor).toHaveValue("Original role");
  fireEvent.change(editor, {target:{value:"My draft"}});
  role = {content:"Changed in chat", version:"current"};
  fireEvent.click(screen.getByRole("button", {name:"Save Agent"}));
  expect(await screen.findByText("Changed in chat", {}, {timeout: 5000})).toBeVisible();
  expect(editor).toHaveValue("My draft");
  expect(roleWrites()).toHaveLength(1);
  const roleSave = screen.getByRole("button", {name:"Save Agent"});
  await waitFor(() => expect(roleSave).toBeEnabled());
  fireEvent.click(roleSave);
  expect(await screen.findByText("Role agreement saved.", {}, {timeout: 5000})).toBeVisible();
  expect(JSON.parse(roleWrites()[1]![1].body)).toEqual({content:"My draft", version:"current"});
}, 15_000);

it("keeps a role draft offline and refreshes the file before unlocking save", async () => {
  config.owner_id = "user-1";
  role = {content:"Original role", version:"old"};
  open();
  const editor = await screen.findByRole("textbox", {name:"Role agreement"}, {timeout: 5000});
  fireEvent.change(editor, {target:{value:"Draft during outage"}});
  await presence("offline");
  await waitFor(() => expect(editor).toBeDisabled());
  expect(editor).toHaveValue("Draft during outage");
  expect(screen.getByText("Last read agreement")).toBeVisible();
  role = {content:"Updated during outage", version:"after-outage"};
  await presence("online");
  expect(await screen.findByText("Updated during outage", {}, {timeout: 5000})).toBeVisible();
  expect(editor).toHaveValue("Draft during outage");
  expect(roleWrites()).toHaveLength(0);
  await waitFor(() => expect(screen.getByRole("button", {name:"Save Agent"})).toBeEnabled());
}, 15_000);

it("saves a role-only change without resubmitting configuration and discards role edits", async () => {
  config.owner_id = "user-1";
  open();
  const editor = await screen.findByRole("textbox", {name: "Role agreement"});
  fireEvent.change(editor, {target: {value: "Help with long-term planning."}});
  const save = screen.getByRole("button", {name: "Save Agent"});
  await waitFor(() => expect(save).toBeEnabled());
  fireEvent.click(save);
  await waitFor(() => expect(roleWrites()).toHaveLength(1));
  await waitFor(() => expect(save).toBeDisabled());
  expect(patches()).toHaveLength(0);
  fireEvent.change(editor, {target: {value: "Unsaved revision"}});
  fireEvent.click(screen.getByRole("button", {name: /Discard/i}));
  expect(editor).toHaveValue("Help with long-term planning.");
  expect(save).toBeDisabled();
});

it("keeps both drafts after a role conflict without submitting ordinary configuration", async () => {
  config.owner_id = "user-1";
  open();
  const editor = await screen.findByRole("textbox", {name: "Role agreement"});
  fireEvent.change(editor, {target: {value: "Role draft"}});
  fireEvent.change(screen.getByLabelText("Display Name"), {target: {value: "Name draft"}});
  role = {content: "Updated elsewhere", version: "new-version"};
  fireEvent.click(screen.getByRole("button", {name: "Save Agent"}));
  expect(await screen.findByText("Updated elsewhere")).toBeVisible();
  expect(editor).toHaveValue("Role draft");
  expect(screen.getByLabelText("Display Name")).toHaveValue("Name draft");
  expect(patches()).toHaveLength(0);
});

it("retries only unsaved configuration if it fails after the role was saved", async () => {
  config.owner_id = "user-1";
  const originalSave = save;
  save = () => json({code: "config_save_failed", message: "Configuration save failed"}, 503);
  open();
  const editor = await screen.findByRole("textbox", {name: "Role agreement"});
  fireEvent.change(editor, {target: {value: "Saved role"}});
  fireEvent.change(screen.getByLabelText("Display Name"), {target: {value: "Name draft"}});
  fireEvent.click(screen.getByRole("button", {name: "Save Agent"}));
  expect(await screen.findByTestId("agent-save-error")).toHaveTextContent("Configuration save failed");
  expect(roleWrites()).toHaveLength(1);
  expect(editor).toHaveValue("Saved role");
  expect(screen.getByLabelText("Display Name")).toHaveValue("Name draft");
  save = originalSave;
  const button = screen.getByRole("button", {name: "Save Agent"});
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  await waitFor(() => expect(patches()).toHaveLength(2));
  expect(roleWrites()).toHaveLength(1);
  await waitFor(() => expect(button).toBeDisabled());
});

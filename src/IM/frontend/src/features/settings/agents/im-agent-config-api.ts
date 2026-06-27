import { authFetch } from "../../auth/auth-fetch";
import { normalizeItemsEnvelope } from "../../chat/im-chat-api";

export interface AgentSummary {
  agent_id: string;
  owner_id: string;
  display_name: string;
  description: string;
  profile_version: number;
  default_model: string | null;
  workspace_root: string;
  workspace_is_default: boolean;
  node_id?: string | null;
  node_name?: string | null;
  node_status?: string | null;
  updated_at?: string | null;
}

// feat-394 M9-E decision 5: heartbeat cadence config — enable lives in features["heartbeat"].
export interface HeartbeatConfig {
  every?: string;
  active_hours?: {
    start?: string;
    end?: string;
    timezone?: string;
  };
}

// feat-394 M9-E: CronConfig removed — cron has no per-agent config; enable lives in features["cron_scheduling"].

export interface AgentConfig {
  agent_id: string;
  owner_id: string;
  display_name: string;
  description: string;
  system_prompt: string;
  // feat-379-M3: per-agent feature flags (key → bool); absent in old IM responses → treat as {}
  features?: Record<string, boolean>;
  // feat-379-M3: user custom instructions appended as pa.user_custom segment
  custom_prompt?: string;
  // feat-394 M9-E: heartbeat carries only cadence; enable lives in features["heartbeat"].
  heartbeat?: HeartbeatConfig;
  // feat-394 M9-E: cron field removed — no per-agent cron config; enable in features["cron_scheduling"].
  skills: string[];
  tool_allowlist: string[];
  group_reply_policy: "ALWAYS" | "MENTION" | "NO_REPLY" | string;
  default_model: string | null;
  workspace_root: string;
  workspace_is_default: boolean;
  profile_version: number;
  node_id?: string | null;
  node_name?: string | null;
  node_status?: string | null;
  updated_at?: string | null;
}

export interface AgentAllowlistOption {
  name: string;
  description: string;
  // feat-394 M9 R5/R6: default_on=true → rendered as selected when tool_allowlist is empty.
  default_on?: boolean;
  // feat-430: SKILL.md path (skills only) so the slash picker distinguishes
  // same-named skills at different paths. Absent/null for tools and older Gateways.
  location?: string | null;
}

// bugfix-429 R5: a selectable model with its registered provider/format, so the
// agent-config dropdown can label each option (e.g. "codex_oauth:gpt-5.5 · openai_compat").
export interface ModelOption {
  name: string;
  provider: string;
}

// feat-379-M3: feature toggle descriptor from FEATURE_REGISTRY (decision 7).
// Projection served by GET /im/v1/agents/{id}/capabilities.features.
// available=false when requires_tool is not in the agent's tool_allowlist.
export interface AgentFeature {
  key: string;
  label_i18n: string;
  help_i18n: string;
  default_on: boolean;
  available: boolean;
  requires_tool: string | null;
}

export interface CapabilitySnapshot {
  node_id: string;
  node_name: string;
  node_status: string;
  capabilities_updated_at?: string | null;
  skills: AgentAllowlistOption[];
  tools: AgentAllowlistOption[];
  model_options: ModelOption[];
  platform_default_model: string | null;
  default_system_prompt: string;
  // feat-379-M3: feature toggle list; absent from older Gateway versions → treat as []
  features?: AgentFeature[];
}

export interface NodeCapabilities extends CapabilitySnapshot {}

export interface AgentCapabilities extends CapabilitySnapshot {}

export interface NodeSummary {
  node_id: string;
  owner_id: string;
  node_name: string;
  status: string;
  last_heartbeat_at: string;
  agent_count: number;
  version: string;
  relay_enabled?: boolean;
  reporting_enabled?: boolean;
  alias?: string | null;
  last_error?: string | null;
}

export interface AgentDetailNodeView {
  node_id: string;
  node_name: string;
  status: string;
  last_heartbeat_at: string;
  agent_count: number;
  version: string;
}

export interface NodeAgentCreateRequest {
  agent_id: string;
  owner_id: string;
  display_name: string;
  description: string;
  system_prompt: string;
  // feat-379-M3: per-agent feature flags for new agents
  features?: Record<string, boolean>;
  custom_prompt?: string;
  skills: string[];
  tool_allowlist: string[];
  group_reply_policy: "ALWAYS" | "MENTION" | "NO_REPLY" | string;
  default_model: string | null;
  workspace_root: string | null;
}

export interface CreateAgentRequest extends NodeAgentCreateRequest {
  node_id?: string | null;
}

export interface UpdateAgentConfigRequest {
  profile_version: number;
  display_name: string;
  description: string;
  system_prompt: string;
  // feat-379-M3: per-agent feature flags; omitted → server keeps existing
  features?: Record<string, boolean>;
  custom_prompt?: string;
  // feat-394 M9-E: heartbeat carries only cadence; enable in features["heartbeat"].
  heartbeat?: HeartbeatConfig;
  // feat-394 M9-E: cron removed from update request; enable in features["cron_scheduling"].
  skills: string[];
  tool_allowlist: string[];
  group_reply_policy: "ALWAYS" | "MENTION" | "NO_REPLY" | string;
  default_model: string | null;
}

export interface AgentDetailState {
  config: AgentConfig;
  capabilities: AgentCapabilities;
  owningNode: AgentDetailNodeView | null;
}

interface AgentCapabilitiesWire {
  agent_id?: string;
  node_id: string;
  workspace_root?: string;
  node_name?: string;
  node_status?: string;
  capabilities_updated_at?: string | null;
  models?: Array<string | ModelOption>;
  model_options?: Array<string | ModelOption>;
  skills: Array<string | AgentAllowlistOption>;
  tools: Array<string | AgentAllowlistOption>;
  platform_default_model?: string | null;
  default_system_prompt?: string;
  // feat-379-M3: feature toggle projection from FEATURE_REGISTRY
  features?: AgentFeature[];
}

interface NodeCapabilitiesWire {
  node_id: string;
  node_name?: string;
  node_status?: string;
  capabilities_updated_at?: string | null;
  models?: Array<string | ModelOption>;
  model_options?: Array<string | ModelOption>;
  skills: Array<string | AgentAllowlistOption>;
  tools: Array<string | AgentAllowlistOption>;
  platform_default_model?: string | null;
  default_system_prompt?: string;
  // feat-379-M7 (ISSUE-1): node capabilities now carry FEATURE_REGISTRY projection
  // so the agent-create page can render feature toggles without a per-agent context.
  features?: AgentFeature[];
}

export function normalizeAllowlistOptions(values: Array<string | AgentAllowlistOption> | undefined): AgentAllowlistOption[] {
  return (values ?? []).flatMap((value) => {
    if (typeof value === "string") {
      const name = value.trim();
      return name ? [{ name, description: "" }] : [];
    }
    if (value && typeof value.name === "string" && value.name.trim()) {
      // feat-394 M9 R5/R6: preserve default_on if the backend provides it.
      // feat-430: preserve location (skill SKILL.md path) for the slash picker.
      return [{
        name: value.name.trim(),
        description: value.description ?? "",
        default_on: value.default_on,
        location: value.location ?? null,
      }];
    }
    return [];
  });
}

function normalizeModelOptions(raw: {
  models?: Array<string | ModelOption>;
  model_options?: Array<string | ModelOption>;
}): ModelOption[] {
  // bugfix-429 R5: keep each model's provider. Tolerate bare strings (older
  // Gateway) by emitting an empty provider so the dropdown degrades to name-only.
  const seen = new Set<string>();
  const options: ModelOption[] = [];
  for (const value of raw.model_options ?? raw.models ?? []) {
    const name = (typeof value === "string" ? value : value?.name ?? "").trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    const provider = typeof value === "string" ? "" : value?.provider ?? "";
    options.push({ name, provider });
  }
  return options;
}

function normalizeNodeStatus(node: NodeSummary | null, rawStatus?: string): string {
  return node?.status ?? rawStatus ?? "unknown";
}

function normalizeNodeName(node: NodeSummary | null, nodeId: string, rawName?: string): string {
  return node?.node_name ?? rawName ?? nodeId;
}

function normalizeCapabilitiesUpdatedAt(node: NodeSummary | null, rawUpdatedAt?: string | null): string | null {
  return rawUpdatedAt ?? node?.last_heartbeat_at ?? null;
}

function toCapabilitySnapshot(
  raw: AgentCapabilitiesWire | NodeCapabilitiesWire,
  node: NodeSummary | null
): CapabilitySnapshot {
  return {
    node_id: raw.node_id,
    node_name: normalizeNodeName(node, raw.node_id, raw.node_name),
    node_status: normalizeNodeStatus(node, raw.node_status),
    capabilities_updated_at: normalizeCapabilitiesUpdatedAt(node, raw.capabilities_updated_at),
    skills: normalizeAllowlistOptions(raw.skills),
    tools: normalizeAllowlistOptions(raw.tools),
    model_options: normalizeModelOptions(raw),
    platform_default_model: raw.platform_default_model ?? null,
    default_system_prompt: raw.default_system_prompt ?? "",
    // feat-379-M3: carry through feature toggles; NodeCapabilitiesWire has no features field → []
    features: "features" in raw && Array.isArray(raw.features) ? raw.features : [],
  };
}

function toAllowlistOptions(values: string[]): AgentAllowlistOption[] {
  return values.map((name) => ({ name, description: "" }));
}

function enrichCapabilitySnapshot(
  raw: { node_id: string; skills: string[]; tools: string[]; models: Array<string | ModelOption> },
  node: NodeSummary | null
): CapabilitySnapshot {
  return {
    node_id: raw.node_id,
    node_name: node?.node_name ?? raw.node_id,
    node_status: node?.status ?? "unknown",
    capabilities_updated_at: node?.last_heartbeat_at ?? null,
    skills: toAllowlistOptions(raw.skills ?? []),
    tools: toAllowlistOptions(raw.tools ?? []),
    model_options: normalizeModelOptions(raw),
    platform_default_model: null,
    default_system_prompt: "",
  };
}

export interface NodeCreateState {
  node: NodeSummary | null;
  capabilities: NodeCapabilities;
}

function getApiBaseUrl() {
  return (import.meta.env.VITE_IM_API_BASE_URL ?? "").replace(/\/$/, "");
}

function withBase(path: string) {
  return `${getApiBaseUrl()}${path}`;
}

class AgentConfigRequestError extends Error {
  status: number;
  detail: string;

  constructor(input: { status: number; detail: string; method: string; path: string }) {
    super(`${input.method} ${input.path} failed: ${input.status} (${input.detail})`);
    this.name = "AgentConfigRequestError";
    this.status = input.status;
    this.detail = input.detail;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authFetch(withBase(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const method = init?.method ?? "GET";
    let detail = response.statusText || "request failed";
    const rawBody = await response.text();
    if (rawBody) {
      try {
        const parsed = JSON.parse(rawBody) as { detail?: string };
        detail = typeof parsed.detail === "string" && parsed.detail.length > 0 ? parsed.detail : rawBody;
      } catch {
        detail = rawBody;
      }
    }
    throw new AgentConfigRequestError({ status: response.status, detail, method, path });
  }
  return (await response.json()) as T;
}

export async function listAgentSummaries() {
  const payload = await requestJson<{ items: AgentSummary[] } | AgentSummary[]>("/im/v1/agents");
  return normalizeItemsEnvelope(payload);
}

/**
 * Normalize a raw backend AgentConfig response: parse heartbeat_json raw JSON string
 * back into a structured HeartbeatConfig object (cadence only) so HeartbeatCard reads
 * correct cadence.
 *
 * feat-394 M9-E: heartbeat enable lives in features["heartbeat"]; heartbeat_json only
 * carries cadence fields (every / active_hours). cron has no config object.
 *
 * Exported for unit testing only — prefer calling getAgentConfig / updateAgentConfig.
 */
/** Response shape that includes the backend's raw heartbeat_json string field. */
type AgentConfigRaw = AgentConfig & { heartbeat_json?: string | null };

export function normalizeAgentConfigResponse(raw: Record<string, unknown>): AgentConfig {
  // Two-step cast: Record<string,unknown> → unknown → target type avoids the TS2352
  // error that a direct overlap-insufficient cast would produce (minor Issue 3 fix).
  const config = raw as unknown as AgentConfigRaw;

  // Parse heartbeat_json → heartbeat cadence when present and not already set.
  // feat-394 M9-E: only extract cadence fields; enabled is not stored in heartbeat_json.
  let heartbeat: HeartbeatConfig | undefined = config.heartbeat;
  if (heartbeat === undefined && typeof config.heartbeat_json === "string" && config.heartbeat_json.trim()) {
    try {
      const parsed = JSON.parse(config.heartbeat_json) as Record<string, unknown>;
      // Only keep cadence fields — drop any legacy "enabled" field that may be in stored JSON.
      const { every, active_hours } = parsed;
      const cadence: HeartbeatConfig = {};
      if (typeof every === "string") cadence.every = every;
      if (active_hours && typeof active_hours === "object") {
        cadence.active_hours = active_hours as HeartbeatConfig["active_hours"];
      }
      heartbeat = Object.keys(cadence).length > 0 ? cadence : undefined;
    } catch {
      // malformed JSON: leave as undefined
    }
  }

  return { ...config, heartbeat };
}

export async function getAgentConfig(agentId: string): Promise<AgentConfig> {
  const raw = await requestJson<Record<string, unknown>>(`/im/v1/agents/${agentId}/config?source=mirror`);
  return normalizeAgentConfigResponse(raw);
}

export async function getAgentCapabilities(agentId: string) {
  return requestJson<AgentCapabilitiesWire>(`/im/v1/agents/${agentId}/capabilities`);
}

export async function listNodes() {
  return requestJson<NodeSummary[]>("/im/v1/nodes");
}

export async function getNodeCapabilities(nodeId: string) {
  return requestJson<NodeCapabilitiesWire>(`/im/v1/nodes/${nodeId}/capabilities`);
}

export async function createNodeAgent(nodeId: string, next: NodeAgentCreateRequest) {
  return requestJson<AgentConfig>(`/im/v1/nodes/${nodeId}/agents`, {
    method: "POST",
    body: JSON.stringify(next),
  });
}

export async function getAgentDetailState(agentId: string): Promise<AgentDetailState> {
  const config = await getAgentConfig(agentId);
  const [capabilitiesResult, nodesResult] = await Promise.allSettled([getAgentCapabilities(agentId), listNodes()]);
  const nodes = nodesResult.status === "fulfilled" ? nodesResult.value : [];
  const fallbackNodeId = config.node_id ?? "";
  const fallbackCapabilities: AgentCapabilitiesWire = {
    agent_id: config.agent_id,
    node_id: fallbackNodeId,
    models: config.default_model ? [config.default_model] : [],
    skills: config.skills,
    tools: config.tool_allowlist,
    platform_default_model: null,
    default_system_prompt: "",
  };
  const capabilities = capabilitiesResult.status === "fulfilled" ? capabilitiesResult.value : fallbackCapabilities;
  const owningNodeId = config.node_id ?? capabilities.node_id;
  const owningNode = owningNodeId ? (nodes.find((node) => node.node_id === owningNodeId) ?? null) : null;
  const enrichedConfig: AgentConfig = {
    ...config,
    node_id: config.node_id ?? owningNode?.node_id ?? capabilities.node_id,
    node_name: owningNode?.node_name ?? null,
    node_status: owningNode?.status ?? null,
  };
  return {
    config: enrichedConfig,
    capabilities: toCapabilitySnapshot(capabilities, owningNode),
    owningNode,
  };
}

export async function getNodeCreateState(nodeId: string): Promise<NodeCreateState> {
  const [capabilities, nodes] = await Promise.all([getNodeCapabilities(nodeId), listNodes()]);
  const node = nodes.find((item) => item.node_id === nodeId) ?? null;
  return { node, capabilities: toCapabilitySnapshot(capabilities, node) };
}

export async function updateAgentConfig(agentId: string, next: UpdateAgentConfigRequest): Promise<AgentConfig> {
  const raw = await requestJson<Record<string, unknown>>(`/im/v1/agents/${agentId}/config`, {
    method: "PATCH",
    body: JSON.stringify({
      profile_version: next.profile_version,
      display_name: next.display_name,
      description: next.description,
      system_prompt: next.system_prompt,
      // feat-379-M3: pass features and custom_prompt when present
      ...(next.features !== undefined ? { features: next.features } : {}),
      ...(next.custom_prompt !== undefined ? { custom_prompt: next.custom_prompt } : {}),
      // feat-394 M9-E: pass heartbeat cadence when present; enable is in features.
      ...(next.heartbeat !== undefined ? { heartbeat: next.heartbeat } : {}),
      // feat-394 M9-E: cron has no config object; enable is in features["cron_scheduling"].
      skills: next.skills,
      tool_allowlist: next.tool_allowlist,
      group_reply_policy: next.group_reply_policy,
      default_model: next.default_model,
    }),
  });
  return normalizeAgentConfigResponse(raw);
}

// feat-379-M3: preview assembled system prompt for an agent with given feature flags and custom text.
// Calls POST /im/v1/agents/{id}/prompt-preview (IM proxies to Gateway → agent core assembler).
// scenario is fixed to "direct" — group/heartbeat runtime segments are excluded from previews.
// feat-379-M6 (ISSUE-3): tool_ids must be forwarded so the assembler's has_tool() gate works.
// Without tool_ids, features like memory_curation that require a tool are never active.
export async function promptPreview(
  agentId: string,
  body: {
    features: Record<string, boolean>;
    custom_prompt: string;
    tool_ids?: string[];
    skill_ids?: string[];
  }
): Promise<string> {
  const result = await requestJson<{ prompt: string }>(`/im/v1/agents/${agentId}/prompt-preview`, {
    method: "POST",
    body: JSON.stringify({
      ...body,
      scenario: "direct",
      tool_ids: body.tool_ids ?? [],
      skill_ids: body.skill_ids ?? [],
    }),
  });
  return result.prompt;
}

// feat-379-M9 (決策 11): node-level prompt-preview — used by agent-create page before
// the agent exists.  No agent_id needed; Gateway uses its default kernel to assemble.
// feat-383-M1: skill_ids and agent_id_hint added so kernel can resolve real skills and workspace.
export async function nodePromptPreview(
  nodeId: string,
  body: {
    features: Record<string, boolean>;
    custom_prompt: string;
    tool_ids?: string[];
    skill_ids?: string[];
    agent_id_hint?: string;
  }
): Promise<string> {
  const result = await requestJson<{ prompt: string }>(`/im/v1/nodes/${nodeId}/prompt-preview`, {
    method: "POST",
    body: JSON.stringify({
      ...body,
      scenario: "direct",
      tool_ids: body.tool_ids ?? [],
      skill_ids: body.skill_ids ?? [],
    }),
  });
  return result.prompt;
}

// ---------------------------------------------------------------------------
// feat-394-M3 WARNING-3: cron job list + delete APIs
// (spec Scenario: 配置页查看并手动删除任务)
// ---------------------------------------------------------------------------

export interface CronJobSummary {
  id: string;
  name: string;
  schedule: Record<string, unknown>;
  instruction: string;
  enabled: boolean;
  delete_after_run: boolean;
}

export async function listAgentCronJobs(agentId: string): Promise<CronJobSummary[]> {
  return requestJson<CronJobSummary[]>(`/im/v1/agents/${agentId}/cron/jobs`);
}

export async function deleteAgentCronJob(agentId: string, jobId: string): Promise<void> {
  const res = await authFetch(`/im/v1/agents/${agentId}/cron/jobs/${jobId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    throw new Error(`delete cron job failed: ${res.status}`);
  }
}

// ---------------------------------------------------------------------------
// feat-394-M13 (决策 G): HEARTBEAT.md read-only preview via WS RPC.
// Data comes from the gateway node — IM never reads workspace files directly.
// ---------------------------------------------------------------------------

export interface HeartbeatMdResponse {
  /** Raw HEARTBEAT.md content from the gateway workspace, empty when absent. */
  content: string;
  /** False when the gateway node is offline or timed out. */
  node_online: boolean;
}

/** Fetch the raw HEARTBEAT.md content for an agent via the WS RPC path. */
export async function getAgentHeartbeatMd(agentId: string): Promise<HeartbeatMdResponse> {
  return requestJson<HeartbeatMdResponse>(`/im/v1/agents/${agentId}/heartbeat-md`);
}

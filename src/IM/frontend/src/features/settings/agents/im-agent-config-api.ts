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
  model_options: string[];
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
  models?: string[];
  model_options?: string[];
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
  models?: string[];
  model_options?: string[];
  skills: Array<string | AgentAllowlistOption>;
  tools: Array<string | AgentAllowlistOption>;
  platform_default_model?: string | null;
  default_system_prompt?: string;
}

function normalizeAllowlistOptions(values: Array<string | AgentAllowlistOption> | undefined): AgentAllowlistOption[] {
  return (values ?? []).flatMap((value) => {
    if (typeof value === "string") {
      const name = value.trim();
      return name ? [{ name, description: "" }] : [];
    }
    if (value && typeof value.name === "string" && value.name.trim()) {
      return [{ name: value.name.trim(), description: value.description ?? "" }];
    }
    return [];
  });
}

function normalizeModelOptions(raw: { models?: string[]; model_options?: string[] }): string[] {
  return Array.from(new Set((raw.model_options ?? raw.models ?? []).map((value) => value.trim()).filter(Boolean)));
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
    features: "features" in raw && Array.isArray(raw.features) ? raw.features : []
  };
}

function toAllowlistOptions(values: string[]): AgentAllowlistOption[] {
  return values.map((name) => ({ name, description: "" }));
}

function enrichCapabilitySnapshot(
  raw: { node_id: string; skills: string[]; tools: string[]; models: string[] },
  node: NodeSummary | null
): CapabilitySnapshot {
  return {
    node_id: raw.node_id,
    node_name: node?.node_name ?? raw.node_id,
    node_status: node?.status ?? "unknown",
    capabilities_updated_at: node?.last_heartbeat_at ?? null,
    skills: toAllowlistOptions(raw.skills ?? []),
    tools: toAllowlistOptions(raw.tools ?? []),
    model_options: raw.models ?? [],
    platform_default_model: null,
    default_system_prompt: ""
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
      ...(init?.headers ?? {})
    }
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

export async function getAgentConfig(agentId: string) {
  return requestJson<AgentConfig>(`/im/v1/agents/${agentId}/config?source=mirror`);
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
    body: JSON.stringify(next)
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
    default_system_prompt: ""
  };
  const capabilities = capabilitiesResult.status === "fulfilled" ? capabilitiesResult.value : fallbackCapabilities;
  const owningNodeId = config.node_id ?? capabilities.node_id;
  const owningNode = owningNodeId ? nodes.find((node) => node.node_id === owningNodeId) ?? null : null;
  const enrichedConfig: AgentConfig = {
    ...config,
    node_id: config.node_id ?? owningNode?.node_id ?? capabilities.node_id,
    node_name: owningNode?.node_name ?? null,
    node_status: owningNode?.status ?? null
  };
  return {
    config: enrichedConfig,
    capabilities: toCapabilitySnapshot(capabilities, owningNode),
    owningNode
  };
}

export async function getNodeCreateState(nodeId: string): Promise<NodeCreateState> {
  const [capabilities, nodes] = await Promise.all([getNodeCapabilities(nodeId), listNodes()]);
  const node = nodes.find((item) => item.node_id === nodeId) ?? null;
  return { node, capabilities: toCapabilitySnapshot(capabilities, node) };
}

export async function updateAgentConfig(agentId: string, next: UpdateAgentConfigRequest) {
  return requestJson<AgentConfig>(`/im/v1/agents/${agentId}/config`, {
    method: "PATCH",
    body: JSON.stringify({
      profile_version: next.profile_version,
      display_name: next.display_name,
      description: next.description,
      system_prompt: next.system_prompt,
      // feat-379-M3: pass features and custom_prompt when present
      ...(next.features !== undefined ? { features: next.features } : {}),
      ...(next.custom_prompt !== undefined ? { custom_prompt: next.custom_prompt } : {}),
      skills: next.skills,
      tool_allowlist: next.tool_allowlist,
      group_reply_policy: next.group_reply_policy,
      default_model: next.default_model
    })
  });
}

// feat-379-M3: preview assembled system prompt for an agent with given feature flags and custom text.
// Calls POST /im/v1/agents/{id}/prompt-preview (IM proxies to Gateway → agent core assembler).
// scenario is fixed to "direct" — group/heartbeat runtime segments are excluded from previews.
export async function promptPreview(
  agentId: string,
  body: { features: Record<string, boolean>; custom_prompt: string }
): Promise<string> {
  const result = await requestJson<{ prompt: string }>(`/im/v1/agents/${agentId}/prompt-preview`, {
    method: "POST",
    body: JSON.stringify({ ...body, scenario: "direct" })
  });
  return result.prompt;
}

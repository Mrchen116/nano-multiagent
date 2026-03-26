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
  bound_nodes?: string[];
  updated_at?: string | null;
}

export interface AgentConfig {
  agent_id: string;
  owner_id: string;
  display_name: string;
  description: string;
  system_prompt: string;
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
  bound_nodes?: string[];
  updated_at?: string | null;
}

export interface AgentAllowlistOption {
  name: string;
  description: string;
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
  skills: string[];
  tool_allowlist: string[];
  group_reply_policy: "ALWAYS" | "MENTION" | "NO_REPLY" | string;
  default_model: string | null;
}

export interface CreateAgentRequest extends NodeAgentCreateRequest {
  node_id?: string | null;
}

export interface UpdateAgentConfigRequest {
  profile_version: number;
  display_name: string;
  description: string;
  system_prompt: string;
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
  const response = await fetch(withBase(path), {
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
  return requestJson<AgentConfig>(`/im/v1/agents/${agentId}/config`);
}

export async function getAgentCapabilities(agentId: string) {
  return requestJson<AgentCapabilities>(`/im/v1/agents/${agentId}/capabilities`);
}

export async function listNodes() {
  return requestJson<NodeSummary[]>("/im/v1/nodes");
}

export async function getNodeCapabilities(nodeId: string) {
  return requestJson<NodeCapabilities>(`/im/v1/nodes/${nodeId}/capabilities`);
}

export async function createNodeAgent(nodeId: string, next: NodeAgentCreateRequest) {
  return requestJson<AgentConfig>(`/im/v1/nodes/${nodeId}/agents`, {
    method: "POST",
    body: JSON.stringify(next)
  });
}

export async function getAgentDetailState(agentId: string): Promise<AgentDetailState> {
  const [config, capabilities, nodes] = await Promise.all([getAgentConfig(agentId), getAgentCapabilities(agentId), listNodes()]);
  const owningNodeId = config.node_id ?? capabilities.node_id;
  const owningNode = owningNodeId ? nodes.find((node) => node.node_id === owningNodeId) ?? null : null;
  return { config, capabilities, owningNode };
}

export async function getNodeCreateState(nodeId: string): Promise<NodeCreateState> {
  const [capabilities, nodes] = await Promise.all([getNodeCapabilities(nodeId), listNodes()]);
  const node = nodes.find((item) => item.node_id === nodeId) ?? null;
  return { node, capabilities };
}

export async function updateAgentConfig(agentId: string, next: UpdateAgentConfigRequest) {
  return requestJson<AgentConfig>(`/im/v1/agents/${agentId}/config`, {
    method: "PATCH",
    body: JSON.stringify({
      profile_version: next.profile_version,
      display_name: next.display_name,
      description: next.description,
      system_prompt: next.system_prompt,
      skills: next.skills,
      tool_allowlist: next.tool_allowlist,
      group_reply_policy: next.group_reply_policy,
      default_model: next.default_model
    })
  });
}

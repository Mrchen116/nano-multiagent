export interface AgentProfile {
  agent_id: string;
  display_name: string;
  description?: string;
  system_prompt: string;
  skills_allowlist: string[];
  group_reply_policy: "ALWAYS" | "MENTION" | "NO_REPLY";
  no_reply_token?: string;
  default_model?: string;
  tool_allowlist: string[];
  profile_version: string;
  enabled: boolean;
  bound_nodes: string[];
  updated_at: string;
}

export interface NodeProfile {
  node_id: string;
  node_name: string;
  status: "online" | "offline" | "degraded";
  last_heartbeat_at?: string;
  agent_count: number;
  node_version?: string;
  desired_config_version: string;
  relay_enabled: boolean;
  report_enabled: boolean;
  last_error?: string;
}

export interface PolicyProfile {
  default_model: string;
  max_turn_per_run: number;
  max_attachment_size_mb: number;
  retention_days: number;
  audit_level: "off" | "basic" | "strict";
  rate_limit_per_min: number;
}

export interface AccountProfile {
  user_id: string;
  display_name: string;
  owned_node_ids: string[];
  default_entry_node_id: string;
  created_at: string;
}

const wait = (ms = 70) => new Promise((resolve) => setTimeout(resolve, ms));

const initialAgents: AgentProfile[] = [
  {
    agent_id: "agent-core-1",
    display_name: "Core Planner",
    description: "Milestone execution coordinator",
    system_prompt: "You are the planning core for IM and SDK tasks.",
    skills_allowlist: ["tdd-execution-worker", "playwright"],
    group_reply_policy: "MENTION",
    no_reply_token: "NO_REPLY",
    default_model: "codex_oauth:gpt-5.4",
    tool_allowlist: ["bash", "read_file"],
    profile_version: "v12",
    enabled: true,
    bound_nodes: ["node-app-01", "node-app-02"],
    updated_at: "2026-03-03T22:00:00+08:00"
  },
  {
    agent_id: "agent-audit-2",
    display_name: "Audit Sentry",
    description: "Checks policy and logging boundaries",
    system_prompt: "Detect unsafe operations and produce concise guidance.",
    skills_allowlist: ["policy-checker"],
    group_reply_policy: "NO_REPLY",
    no_reply_token: "NO_REPLY",
    default_model: "gpt-4.1-mini",
    tool_allowlist: ["read_file"],
    profile_version: "v3",
    enabled: true,
    bound_nodes: ["node-app-02"],
    updated_at: "2026-03-03T21:42:00+08:00"
  }
];

const initialNodes: NodeProfile[] = [
  {
    node_id: "node-app-01",
    node_name: "node-app-01",
    status: "online",
    last_heartbeat_at: "2026-03-03T22:41:00+08:00",
    agent_count: 4,
    node_version: "1.8.2",
    desired_config_version: "cfg-20260303-1",
    relay_enabled: true,
    report_enabled: true,
    last_error: ""
  },
  {
    node_id: "node-app-02",
    node_name: "node-app-02",
    status: "degraded",
    last_heartbeat_at: "2026-03-03T22:39:00+08:00",
    agent_count: 2,
    node_version: "1.8.1",
    desired_config_version: "cfg-20260303-1",
    relay_enabled: true,
    report_enabled: false,
    last_error: "upstream timeout spikes"
  }
];

const initialPolicies: PolicyProfile = {
  default_model: "codex_oauth:gpt-5.4",
  max_turn_per_run: 14,
  max_attachment_size_mb: 15,
  retention_days: 30,
  audit_level: "basic",
  rate_limit_per_min: 45
};

// Placeholder mock identity for offline/demo mode; real account uses Bearer auth.
const initialAccount: AccountProfile = {
  user_id: "mock-user",
  display_name: "CZJ",
  owned_node_ids: ["node-app-01", "node-app-02"],
  default_entry_node_id: "node-app-01",
  created_at: "2025-12-01T08:30:00+08:00"
};

let agents = structuredClone(initialAgents);
let nodes = structuredClone(initialNodes);
let policies = structuredClone(initialPolicies);
let account = structuredClone(initialAccount);

function bumpVersion(version: string) {
  const match = version.match(/v(\d+)/i);
  if (!match) {
    return version;
  }
  return `v${Number(match[1]) + 1}`;
}

export function getInitialAgents() {
  return structuredClone(initialAgents);
}

export function getInitialNodes() {
  return structuredClone(initialNodes);
}

export function getInitialPolicies() {
  return structuredClone(initialPolicies);
}

export function getInitialAccount() {
  return structuredClone(initialAccount);
}

export async function listAgents() {
  await wait();
  return structuredClone(agents);
}

export async function getAgent(agentId: string) {
  await wait();
  const found = agents.find((item) => item.agent_id === agentId);
  return found ? structuredClone(found) : null;
}

export async function updateAgent(agentId: string, patch: Partial<AgentProfile>) {
  await wait();
  agents = agents.map((item) => {
    if (item.agent_id !== agentId) {
      return item;
    }
    return {
      ...item,
      ...patch,
      profile_version: bumpVersion(item.profile_version),
      updated_at: new Date().toISOString()
    };
  });
  return getAgent(agentId);
}

export async function listNodes() {
  await wait();
  return structuredClone(nodes);
}

export async function updateNode(nodeId: string, patch: Partial<NodeProfile>) {
  await wait();
  nodes = nodes.map((item) => (item.node_id === nodeId ? { ...item, ...patch } : item));
  const found = nodes.find((item) => item.node_id === nodeId);
  return found ? structuredClone(found) : null;
}

export async function getPolicies() {
  await wait();
  return structuredClone(policies);
}

export async function updatePolicies(patch: Partial<PolicyProfile>) {
  await wait();
  policies = { ...policies, ...patch };
  return getPolicies();
}

export async function getAccount() {
  await wait();
  return structuredClone(account);
}

export async function updateAccount(patch: Partial<AccountProfile>) {
  await wait();
  account = { ...account, ...patch };
  return getAccount();
}

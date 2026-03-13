import { normalizeItemsEnvelope } from "../../chat/im-chat-api";

export interface AgentSummary {
  agent_id: string;
  owner_id: string;
  display_name: string;
  description: string;
  profile_version: number;
  default_model: string | null;
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
  profile_version: number;
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

export async function updateAgentConfig(agentId: string, next: AgentConfig) {
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

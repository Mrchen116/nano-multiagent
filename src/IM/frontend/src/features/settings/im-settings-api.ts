import { authFetch } from "../auth/auth-fetch";

export interface NodeSettingsProfile {
  node_id: string;
  owner_id: string;
  node_name: string;
  status: "online" | "offline" | "degraded" | string;
  last_heartbeat_at: string;
  agent_count: number;
  version: string;
  relay_enabled: boolean;
  reporting_enabled: boolean;
  alias: string | null;
  last_error: string | null;
}

export interface AccountProfile {
  id: string;
  user_id: string;
  username: string;
  display_name: string;
  owner_id: string;
  owned_node_ids: string[];
  default_entry_node_id: string | null;
  locale: string;
  created_at: string;
}

export interface UpdateAccountInput {
  display_name: string;
  default_entry_node_id: string | null;
  locale?: string;
}

export interface PolicyProfile {
  default_model: string;
  max_turn_per_run: number;
  max_attachment_size_mb: number;
  retention_days: number;
  audit_level: "off" | "basic" | "strict";
  rate_limit_per_min: number;
}

class SettingsRequestError extends Error {
  status: number;
  detail: string;

  constructor(input: { status: number; detail: string; method: string; path: string }) {
    super(`${input.method} ${input.path} failed: ${input.status} (${input.detail})`);
    this.name = "SettingsRequestError";
    this.status = input.status;
    this.detail = input.detail;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authFetch(path, init);
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
    throw new SettingsRequestError({ status: response.status, detail, method, path });
  }
  return (await response.json()) as T;
}

export async function listNodes() {
  return requestJson<NodeSettingsProfile[]>("/im/v1/nodes");
}

export async function updateNode(
  nodeId: string,
  patch: Pick<NodeSettingsProfile, "alias" | "relay_enabled" | "reporting_enabled">
) {
  return requestJson<NodeSettingsProfile>(`/im/v1/nodes/${nodeId}/config`, {
    method: "PATCH",
    body: JSON.stringify(patch)
  });
}

export async function getAccount() {
  // owner_id is derived from the Bearer token server-side; no query parameter needed.
  return requestJson<AccountProfile>(`/im/v1/me`);
}

export async function updateAccount(next: UpdateAccountInput) {
  const body: Record<string, unknown> = {
    display_name: next.display_name,
    default_entry_node_id: next.default_entry_node_id
  };
  if (next.locale !== undefined) body.locale = next.locale;
  return requestJson<AccountProfile>(`/im/v1/me`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
}

export async function getPolicies() {
  return requestJson<PolicyProfile>("/im/v1/policies");
}

export async function updatePolicies(next: PolicyProfile) {
  return requestJson<PolicyProfile>("/im/v1/policies", {
    method: "PATCH",
    body: JSON.stringify(next)
  });
}

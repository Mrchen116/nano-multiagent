import type { PersonalAgentIdentity } from './personal-agent.js';

/** Public configuration fields carried by the existing node configuration protocol.
 *
 * Optional fields preserve older nodes and partial live snapshots. This is a wire
 * projection, not a runtime configuration and not an IM database record.
 */
export interface AgentConfigurationFields {
  agent_id?: string;
  display_name?: string | null;
  skills?: string[] | null;
  skills_selection_mode?: string | null;
  tool_allowlist?: string[];
  group_reply_policy?: string | null;
  default_model?: string | null;
  model_fallbacks?: string[];
  reasoning_effort?: string | null;
  approval_mode?: 'cc' | 'codex' | null;
  work_mode?: string;
  workspace_root?: string | null;
  features?: Record<string, boolean>;
  custom_prompt?: string | null;
  heartbeat_json?: string | null;
  personal_agent?: PersonalAgentIdentity;
  workspace_is_default?: boolean | null;
  confirm_existing_workspace?: boolean;
  create_operation_id?: string;
}

/** Durable intent identity is separate from the transport request identity. */
export interface ConfigurationIntent {
  operation_id: string;
  candidate_fingerprint: string;
  expected_previous_fingerprint: string | null;
  agent: AgentConfigurationFields & { agent_id: string };
}

/** Unconfirmed receipts intentionally allow missing fields for recovery. */
export interface ConfigurationResult {
  operation_id?: string;
  candidate_fingerprint?: string;
  status?: string;
  agent?: AgentConfigurationFields | null;
  error_code?: string;
  message?: string;
  blocks?: unknown[];
}

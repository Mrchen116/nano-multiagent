import type { PersonalAgentIdentity } from './personal-agent.js';

/** Public configuration fields carried by the existing node configuration protocol.
 *
 * Optional fields preserve older nodes and partial live snapshots. This is a wire
 * projection, not a runtime configuration and not an IM database record.
 */
export type AgentConfigurationFields = {
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
};

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

const isRecord = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === 'string';
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(text);
const boolean = (value: unknown): value is boolean => typeof value === 'boolean';
const nullableText = (value: unknown) => value === null || text(value);
function field(value: Record<string, unknown>, key: keyof AgentConfigurationFields, valid: (value: unknown) => boolean): void {
  if (value[key] !== undefined && !valid(value[key])) throw new Error(`Invalid configuration field: ${key}`);
}
function record(value: unknown): Record<string, unknown> {
  if (!isRecord(value)) throw new Error('Configuration must be an object');
  return value;
}

/** Validate consumed configuration fields without normalizing or dropping wire metadata. */
export function parseAgentConfigurationFields(value: unknown): AgentConfigurationFields {
  const p = record(value);
  for (const key of ['agent_id','work_mode','create_operation_id'] as const) field(p, key, text);
  for (const key of ['display_name','skills_selection_mode','group_reply_policy','default_model','reasoning_effort','workspace_root','custom_prompt','heartbeat_json'] as const) field(p, key, nullableText);
  for (const key of ['tool_allowlist','model_fallbacks'] as const) field(p, key, strings);
  field(p, 'skills', value => value === null || strings(value));
  field(p, 'approval_mode', value => value === null || value === 'cc' || value === 'codex');
  field(p, 'features', value => isRecord(value) && Object.values(value).every(boolean));
  field(p, 'workspace_is_default', value => value === null || boolean(value));
  field(p, 'confirm_existing_workspace', boolean);
  field(p, 'personal_agent', value => isRecord(value) && text(value.bindingId) && text(value.ownerId)
    && text(value.conversationId) && Number.isSafeInteger(value.epoch) && Number(value.epoch) > 0);
  // The assertion follows checks for every field in the public projection. Extra
  // node metadata remains on the original object for durable receipt fidelity.
  return p as AgentConfigurationFields;
}

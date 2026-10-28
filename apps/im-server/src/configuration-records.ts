import type {DatabaseSync} from 'node:sqlite';

/** SQLite representation: JSON columns and integer flags never double as HTTP fields. */
export interface AgentProfileRecord {
  agent_id: string;
  owner_id: string;
  space_id: string;
  node_id: string | null;
  display_name: string;
  description: string;
  group_reply_policy: string;
  default_model: string | null;
  reasoning_effort: string | null;
  approval_mode: 'cc' | 'codex' | null;
  work_mode: string;
  workspace_root: string | null;
  workspace_is_default: number | null;
  profile_version: number;
  updated_at: string;
  custom_prompt: string | null;
  heartbeat_json: string | null;
  skills_json: string;
  skills_selection_mode: string | null;
  tool_allowlist_json: string;
  model_fallbacks_json: string;
  features_json: string;
  registration_seed: number;
  pending_create_operation_id: string | null;
  is_stale: number;
}
export interface ConfigOperationRecord {
  operation_id: string;
  root_operation_id: string | null;
  agent_id: string;
  owner_id: string;
  node_id: string;
  operation_kind: 'create' | 'apply' | 'restore' | 'compensation';
  status: 'pending' | 'gateway_applied' | 'committed' | 'rejected' | 'compensating';
  candidate_json: string;
  candidate_fingerprint: string;
  previous_candidate_json: string | null;
  expected_previous_fingerprint: string | null;
  expected_profile_version: number | null;
  gateway_result_json: string | null;
}
interface PersonalBindingRecord {
  binding_id: string;
  owner_id: string;
  conversation_id: string;
  node_epoch: number;
}

// These assertions belong to fixed SQL queries over the center-owned schema.
// Callers cannot choose a result type or claim arbitrary SQL has that shape.
/** Read the durable profile; an owner filter also excludes stale registrations. */
export function readAgentProfile(db: DatabaseSync, agent: string, owner?: string): AgentProfileRecord | undefined {
  return (owner === undefined
    ? db.prepare('SELECT * FROM agent_profiles WHERE agent_id=?').get(agent)
    : db.prepare('SELECT * FROM agent_profiles WHERE agent_id=? AND owner_id=? AND is_stale=0').get(agent, owner)) as AgentProfileRecord | undefined;
}
/** Find the latest recoverable operation, retaining its original intent identity. */
export function activeConfigOperation(db: DatabaseSync, agent: string, owner: string): ConfigOperationRecord | undefined {
  return db.prepare("SELECT * FROM agent_config_operations WHERE agent_id=? AND owner_id=? AND status IN ('pending','gateway_applied') ORDER BY rowid DESC LIMIT 1")
    .get(agent, owner) as ConfigOperationRecord | undefined;
}
/** Read the operation just persisted by this service. */
export function readConfigOperation(db: DatabaseSync, id: string): ConfigOperationRecord | undefined {
  return db.prepare('SELECT * FROM agent_config_operations WHERE operation_id=?').get(id) as ConfigOperationRecord | undefined;
}
/** Resolve only the server-issued personal identity attached to this candidate. */
export function configurationPersonalBinding(db: DatabaseSync, agent: string, owner: string, node: string): PersonalBindingRecord | undefined {
  return db.prepare('SELECT binding_id,owner_id,conversation_id,node_epoch FROM personal_agent_bindings WHERE agent_id=? AND owner_id=? AND node_id=?')
    .get(agent, owner, node) as PersonalBindingRecord | undefined;
}

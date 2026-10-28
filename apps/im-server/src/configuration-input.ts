import {parseAgentConfigurationFields, type AgentConfigurationFields} from '@nano/product-contracts';
import {fail} from './context.js';
import {isRecord} from './node-rpc-values.js';

/** Business candidate: no SQL columns, transport IDs, or arbitrary field indexing. */
export interface ConfigurationCandidate extends AgentConfigurationFields {
  agent_id: string;
  description?: string;
  owner_id?: string;
  space_id?: string;
  node_id?: string | null;
}
interface ConfigurationWriteFields extends Omit<AgentConfigurationFields, 'work_mode' | 'features'> {
  work_mode?: string | null;
  features?: Record<string, boolean> | null;
}
export interface CreateConfigurationInput extends ConfigurationWriteFields {
  agent_id: string;
  display_name: string;
  group_reply_policy: string;
  description?: string;
}
export interface UpdateConfigurationInput extends ConfigurationWriteFields {
  display_name: string;
  group_reply_policy: string;
  profile_version: number;
  description?: string;
  heartbeat?: unknown;
}

/** Parse the existing HTTP contract without normalizing text, omission, or explicit null.
 *
 * Args:
 *   value: Fastify body before a route has asserted any field types.
 *   create: Whether this is the node's Agent creation endpoint.
 * Returns:
 *   Checked public input. Unknown extra keys remain ignored by candidate construction.
 * Raises:
 *   Error: 422 with existing required/list/version errors, or invalid optional fields.
 */
export function parseConfigurationInput(value: unknown, create: true): CreateConfigurationInput;
export function parseConfigurationInput(value: unknown, create?: false): UpdateConfigurationInput;
export function parseConfigurationInput(value: unknown, create = false): CreateConfigurationInput | UpdateConfigurationInput {
  const p = isRecord(value) ? value : {};
  for (const key of create ? ['agent_id','display_name','group_reply_policy'] : ['display_name','group_reply_policy']) {
    if (typeof p[key] !== 'string' || !p[key].trim()) fail(422, `${key} is required`);
  }
  for (const key of ['skills','tool_allowlist','model_fallbacks']) {
    const field = p[key];
    if (key in p && (!Array.isArray(field) || field.some(item => typeof item !== 'string'))) fail(422, `${key} must be a string list`);
  }
  if (p.approval_mode != null && p.approval_mode !== 'cc' && p.approval_mode !== 'codex') fail(422, 'invalid approval_mode');
  if (p.work_mode != null && p.work_mode !== 'single_thread' && p.work_mode !== 'global') fail(422, 'invalid work_mode');
  if (p.skills_selection_mode != null && !['default_discovery','explicit_allowlist','explicit_denylist'].includes(String(p.skills_selection_mode))) fail(422, 'invalid skills_selection_mode');
  if (!create && (typeof p.profile_version !== 'number' || !Number.isInteger(p.profile_version) || p.profile_version < 1)) fail(422, 'invalid profile_version');
  if (p.description != null && typeof p.description !== 'string') fail(422, 'description must be text');
  let fields: AgentConfigurationFields;
  try { fields = parseAgentConfigurationFields({...p,work_mode:p.work_mode ?? undefined,features:p.features ?? undefined}); }
  catch { fail(422, 'invalid configuration fields'); }
  const displayName = p.display_name, policy = p.group_reply_policy;
  // Explicitly narrow the required fields rather than asserting an HTTP object
  // to a business type. The earlier checks retain their existing error details.
  if (typeof displayName !== 'string' || typeof policy !== 'string') fail(422, 'invalid configuration fields');
  const input = {...fields, display_name:displayName, group_reply_policy:policy,
    work_mode:p.work_mode === null ? null : fields.work_mode,
    features:p.features === null ? null : fields.features,
    ...(typeof p.description === 'string' ? {description:p.description} : {})};
  if (create) {
    if (typeof p.agent_id !== 'string') fail(422, 'agent_id is required');
    return {...input,agent_id:p.agent_id};
  }
  if (typeof p.profile_version !== 'number') fail(422, 'invalid profile_version');
  return {...input,profile_version:p.profile_version,...('heartbeat' in p ? {heartbeat:p.heartbeat} : {})};
}

/** Decode our persisted candidate at its JSON storage boundary, not in each caller. */
export function storedConfigurationCandidate(json: string): ConfigurationCandidate {
  const value: unknown = JSON.parse(json);
  const fields = parseAgentConfigurationFields(value);
  if (!fields.agent_id || !isRecord(value)) throw new Error('Invalid stored configuration candidate');
  for (const key of ['description','owner_id','space_id']) if (value[key] !== undefined && typeof value[key] !== 'string') throw new Error(`Invalid stored configuration ${key}`);
  if (value.node_id != null && typeof value.node_id !== 'string') throw new Error('Invalid stored configuration node');
  return {...fields,agent_id:fields.agent_id};
}

/** Read the configured resource identity from the HTTP router, never a Row cast. */
export function controlRouteId(request: {params: unknown}, name: string): string {
  const value = isRecord(request.params) ? request.params[name] : undefined;
  if (typeof value !== 'string') fail(422, `${name} is required`);
  return value;
}

/** Preserve the existing live/mirror default; authorization still distinguishes humans and devices. */
export function configurationSource(request: {query: unknown}): unknown {
  return isRecord(request.query) ? request.query.source ?? 'live' : 'live';
}

/** Skill migration has a deliberately smaller write contract than profile editing. */
export function parseSkillsMigration(value: unknown): {profile_version: number} {
  if (!isRecord(value) || Object.keys(value).some(key => key !== 'profile_version') || typeof value.profile_version !== 'number' || !Number.isInteger(value.profile_version)) fail(422, 'Invalid skills');
  return {profile_version:value.profile_version};
}

import { sortedJsonAscii } from './serialization.js';
import { createHash } from 'node:crypto';
import type { PersonalAgentIdentity } from './index.js';

const text = (value: unknown): string | null => typeof value === 'string' && value.trim() ? value.trim() : null;
const strings = (value: unknown): string[] => Array.isArray(value) ? value.flatMap(item => text(item) ? [text(item)!] : []) : [];
/** One non-secret configuration representation shared by node and IM. */
export function canonicalAgentConfiguration(payload: Record<string, unknown>) {
  const agentId = text(payload.agent_id) ?? '';
  const approvalMode = payload.approval_mode ?? null;
  if (approvalMode !== null && approvalMode !== 'cc' && approvalMode !== 'codex') throw new Error('Invalid approval_mode');
  const skills = Array.isArray(payload.skills) ? strings(payload.skills) : null;
  let mode = text(payload.skills_selection_mode);
  if (mode && !['default_discovery', 'explicit_allowlist', 'explicit_denylist'].includes(mode)) throw new Error('Invalid skills_selection_mode');
  if (skills !== null) mode ??= skills.length ? 'explicit_allowlist' : 'default_discovery';
  let personal: PersonalAgentIdentity | undefined;
  if (payload.personal_agent != null) {
    const value = payload.personal_agent as Partial<PersonalAgentIdentity>;
    if (!value || typeof value !== 'object' || !text(value.bindingId) || !text(value.ownerId)
      || !text(value.conversationId) || !Number.isSafeInteger(value.epoch) || value.epoch! < 1) {
      throw new Error('Invalid server-issued personal_agent binding');
    }
    personal = { bindingId: value.bindingId!, ownerId: value.ownerId!, conversationId: value.conversationId!, epoch: value.epoch! };
  }
  const heartbeat = text(payload.heartbeat_json);
  let heartbeatJson: string | null = null;
  if (heartbeat) {
    const decoded: unknown = JSON.parse(heartbeat);
    if (!decoded || typeof decoded !== 'object' || Array.isArray(decoded)) throw new Error('heartbeat_json must encode an object');
    heartbeatJson = sortedJsonAscii(decoded);
  }
  return {
    ...(personal ? { personal_agent: personal } : {}),
    agent_id: agentId, approval_mode: approvalMode as 'cc' | 'codex' | null, work_mode: text(payload.work_mode) ?? 'single_thread',
    display_name: text(payload.display_name) ?? agentId, skills, skills_selection_mode: mode,
    tool_allowlist: strings(payload.tool_allowlist), group_reply_policy: text(payload.group_reply_policy) ?? 'manual',
    default_model: text(payload.default_model), model_fallbacks: strings(payload.model_fallbacks), reasoning_effort: text(payload.reasoning_effort),
    workspace_root: text(payload.workspace_root), custom_prompt: text(payload.custom_prompt), heartbeat_json: heartbeatJson,
    features: payload.features && typeof payload.features === 'object' && !Array.isArray(payload.features)
      ? Object.fromEntries(Object.entries(payload.features).filter((pair): pair is [string, boolean] => typeof pair[1] === 'boolean')) : {} as Record<string, boolean>,
  };
}
export type CanonicalAgentConfiguration = ReturnType<typeof canonicalAgentConfiguration>;
/** Empty heartbeat settings and absent settings have the same effective fingerprint. */
export function agentConfigurationFingerprint(payload: Record<string, unknown>): string {
  const canonical = canonicalAgentConfiguration(payload);
  if (canonical.heartbeat_json === '{}') canonical.heartbeat_json = null;
  // Inherited mode preserves fingerprints stored in pre-strategy operation receipts.
  const { approval_mode, ...legacy } = canonical;
  return createHash('sha256').update(sortedJsonAscii(approval_mode === null ? legacy : canonical)).digest('hex');
}

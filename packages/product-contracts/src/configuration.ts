import { createHash } from 'node:crypto';

const text = (value: unknown): string | null => typeof value === 'string' && value.trim() ? value.trim() : null;
const strings = (value: unknown): string[] => Array.isArray(value) ? value.flatMap(item => text(item) ? [text(item)!] : []) : [];
/** Matches the existing Python protocol's sorted, ASCII-escaped JSON fingerprint. */
export function canonicalJson(value: unknown): string {
  const sort = (value: unknown): unknown => Array.isArray(value) ? value.map(sort)
    : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, entry]) => [key, sort(entry)])) : value;
  return JSON.stringify(sort(value)).replace(/[\u0080-\uffff]/g, char => `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`);
}
/** One non-secret configuration representation shared by node and IM. */
export function canonicalAgentConfiguration(payload: Record<string, unknown>) {
  const agentId = text(payload.agent_id) ?? '';
  const skills = Array.isArray(payload.skills) ? strings(payload.skills) : null;
  let mode = text(payload.skills_selection_mode);
  if (mode && !['default_discovery', 'explicit_allowlist'].includes(mode)) throw new Error('Invalid skills_selection_mode');
  if (skills !== null) mode ??= skills.length ? 'explicit_allowlist' : 'default_discovery';
  const heartbeat = text(payload.heartbeat_json);
  let heartbeatJson: string | null = null;
  if (heartbeat) {
    const decoded: unknown = JSON.parse(heartbeat);
    if (!decoded || typeof decoded !== 'object' || Array.isArray(decoded)) throw new Error('heartbeat_json must encode an object');
    heartbeatJson = canonicalJson(decoded);
  }
  return {
    agent_id: agentId, work_mode: text(payload.work_mode) ?? 'single_thread',
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
  return createHash('sha256').update(canonicalJson(canonical)).digest('hex');
}

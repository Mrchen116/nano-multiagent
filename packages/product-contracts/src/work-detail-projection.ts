import { decodeWorkEvent, workObject } from './work-event-codec.js';
import type { WorkJournalEvent } from './work-events.js';
import { workDetailLimits } from './work-sync.js';

// Prioritize identifiers consumed by projection before adding optional display content.
export const workDetailFields = [
  'run_id', 'scope', 'parent_session_id', 'child_session_id', 'child_agent_id', 'workflow_run_id',
  'parent_tool_call_id', 'retired', 'historical_only', 'origin', 'model', 'model_id', 'started_at',
  'finished_at', 'lifecycle_revision', 'status', 'stop_reason', 'completed', 'elapsed_ms', 'duration_ms',
  'context_window', 'call_id', 'tool_call_id', 'tool_name', 'name', 'reason_code', 'is_error',
  'request_id', 'message_id', 'role', 'source_kind', 'source_session_id', 'native_turn',
  'target', 'submission_id', 'review_id', 'job_id', 'command', 'delivery_state', 'user_message_count',
  'trigger', 'usage', 'error', 'presentation', 'permission_request', 'options', 'source_refs',
  'background_returns', 'updated_targets', 'title', 'description', 'text', 'delta', 'reasoning_content',
  'content', 'summary', 'arguments',
] as const;

const identityFields = new Set<string>(workDetailFields.slice(0, workDetailFields.indexOf('trigger')));
const displayFields = ['kind', 'job_id', 'label', 'summary', 'detail', 'emoji', 'id', 'name', 'message',
  'code', 'status', 'title', 'description', 'text', 'content', 'path', 'conversation_id', 'message_id', 'child_session_id', 'agent_id', 'task_id', 'task_type',
  'lifecycle_revision', 'options', 'context_used', 'output', 'context_window', 'prompt_tokens',
  'completion_tokens', 'total_tokens', 'total', 'cache_read_tokens', 'cache_total_input_tokens'];
const clip = (value: string, size: number) => value.length <= size ? value : value.slice(0, size) + '…';

function bounded(value: unknown, depth: number): unknown {
  if (typeof value === 'string') return clip(value, 768);
  if (value === null || typeof value === 'boolean' || typeof value === 'number') return value;
  if (depth === 0) return undefined;
  if (Array.isArray(value)) return value.slice(0, 8).map(item => bounded(item, depth - 1)).filter(item => item !== undefined);
  if (workObject(value)) return Object.fromEntries(displayFields.flatMap(key => {
    if (!Object.hasOwn(value, key)) return [];
    const child = bounded(value[key], depth - 1);
    return child === undefined ? [] : [[key, child]];
  }));
  return undefined;
}

/** Derive the same bounded Work projection on the node and on the center. */
export function projectWorkDetail(event: WorkJournalEvent): WorkJournalEvent {
  const { seq, event_id, root_agent_id, session_id, turn_id, observed_at, type } = event;
  const payload: Record<string, unknown> = {large_detail_preview: true};
  const result: WorkJournalEvent = {seq, event_id, root_agent_id, session_id, turn_id, observed_at, type, payload};
  let bytes = Buffer.byteLength(JSON.stringify(result));
  if (bytes > 4096 || event_id.length > 300) throw new Error('invalid_detail_identity');
  for (const key of workDetailFields) {
    if (!Object.hasOwn(event.payload, key)) continue;
    const input = event.payload[key];
    // Preserve the truthiness used to derive tool/turn failure, even for opaque errors.
    const value = key === 'error' && input ? bounded(input, 2) || true
      : identityFields.has(key) && typeof input === 'string' && input.length <= 1024 ? input : bounded(input, 3);
    if (value === undefined) continue;
    const size = Buffer.byteLength(JSON.stringify([key, value])) + 1;
    if (bytes + size > workDetailLimits.projectionBytes) continue;
    payload[key] = value;
    bytes += size;
  }
  return decodeWorkEvent(result).event;
}

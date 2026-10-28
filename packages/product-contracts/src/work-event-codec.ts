import type {DecodedWorkEvent, ReceivedWorkFact, WorkAppendBatch, WorkJournalEvent, WorkEventType} from './work-events.js';

/** A domain error mapped by each HTTP/WS adapter, without coupling contracts to HTTP. */
export class WorkEventError extends Error {}
export const workObject = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown) => typeof value === 'string';
const number = (value: unknown) => typeof value === 'number' && Number.isFinite(value);
const permissionOptions = (value: unknown) => Array.isArray(value) && value.every(option => workObject(option) && text(option.id));
const boolean = (value: unknown) => typeof value === 'boolean';
const nullable = (check: (value: unknown) => boolean) => (value: unknown) => value === null || check(value);
function fields(value: Record<string, unknown>, names: readonly string[], valid: (value: unknown) => boolean): void {
  for (const name of names) if (value[name] !== undefined && !valid(value[name])) throw new WorkEventError('invalid_event');
}
const types = {
  session_registered: 1, session_linked: 1, turn_started: 1, turn_start: 1, turn_end: 1,
  run_completed: 1, run_failed: 1, run_cancelled: 1, model_selected: 1, tool_start: 1, tool_end: 1,
  permission_request: 1, permission_resolved: 1, message: 1, message_delta: 1, text_delta: 1,
  draft_withheld: 1, message_sent: 1, dispatch_confirmed: 1, inbox_read_committed: 1,
  inbox_wake_admitted: 1, tool_result_committed: 1, turn_input_committed: 1, run_heartbeat: 1,
  injection_consumed: 1, self_evolution_review: 1, control_result: 1, recording_degraded: 1,
  model_fallback: 1, cron_trigger: 1, cron_delivery: 1,
} satisfies Record<WorkEventType, number>;

/** Decode consumed product fields while preserving the original object and JSON byte order.
 *
 * Args:
 *   value: Untrusted journal event from wire or durable local JSON.
 * Returns:
 *   Original envelope plus a typed known fact, or an explicitly opaque extension.
 */
export function decodeWorkEvent(value: unknown): DecodedWorkEvent {
  if (!workObject(value) || !Number.isSafeInteger(value.seq) || Number(value.seq) < 1 ||
      !['event_id', 'root_agent_id', 'session_id', 'type'].every(key => typeof value[key] === 'string' && !!value[key]) || !workObject(value.payload))
    throw new WorkEventError('invalid_sequence');
  fields(value, ['turn_id', 'observed_at'], nullable(text));
  const p = value.payload;
  fields(p, ['run_id'], nullable(text));
  fields(p, ['source_refs'], nullable(Array.isArray));
  const known = Object.hasOwn(types, String(value.type));
  if (known) {
    // Only fields consumed by the matching event are fixed; extra wire metadata is retained.
    switch (value.type) {
      case 'session_registered':
        if (!['global_main', 'subagent', 'workflow', 'cron'].includes(String(p.scope))) throw new WorkEventError('invalid_scope');
        fields(p, ['scope', 'child_agent_id', 'workflow_run_id', 'title', 'description'], text);
        fields(p, ['parent_session_id'], nullable(text)); fields(p, ['retired', 'historical_only'], boolean); break;
      case 'session_linked':
        if (!['parent_session_id', 'child_session_id'].every(key => typeof p[key] === 'string' && !!p[key])) throw new WorkEventError('invalid_event');
        fields(p, ['parent_session_id', 'child_session_id', 'workflow_run_id', 'title', 'description'], text); break;
      case 'turn_started': case 'turn_start':
        fields(p, ['origin'], text); fields(p, ['model', 'model_id', 'started_at'], nullable(text));
        fields(p, ['lifecycle_revision'], number); fields(p, ['trigger'], nullable(workObject));
        if (workObject(p.trigger)) fields(p.trigger, ['kind', 'job_id'], text); break;
      case 'turn_end': case 'run_completed': case 'run_failed': case 'run_cancelled':
        fields(p, ['status', 'model', 'finished_at'], nullable(text)); fields(p, ['stop_reason'], text); fields(p, ['completed'], boolean);
        fields(p, ['elapsed_ms', 'duration_ms', 'context_window'], nullable(number)); fields(p, ['usage'], nullable(workObject));
        if (workObject(p.usage)) fields(p.usage, ['context_used', 'output', 'context_window', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'total', 'cache_read_tokens', 'cache_total_input_tokens'], number); break;
      case 'model_selected': fields(p, ['model'], text); break;
      case 'tool_start': case 'tool_end':
        fields(p, ['call_id', 'tool_call_id', 'tool_name', 'name', 'reason_code'], text); fields(p, ['is_error'], boolean); fields(p, ['duration_ms'], number);
        fields(p, ['presentation'], nullable(workObject));
        if (workObject(p.presentation)) fields(p.presentation, ['summary', 'label', 'emoji'], text); break;
      case 'permission_request': case 'permission_resolved':
        fields(p, ['request_id'], text); fields(p, ['lifecycle_revision'], number); fields(p, ['options'], nullable(permissionOptions));
        fields(p, ['permission_request'], nullable(workObject));
        if (workObject(p.permission_request)) {
          fields(p.permission_request, ['lifecycle_revision'], number);
          fields(p.permission_request, ['options'], nullable(permissionOptions));
        } break;
      case 'message': case 'message_delta': case 'text_delta':
        fields(p, ['message_id', 'role', 'text', 'delta', 'reasoning_content', 'source_kind', 'source_session_id'], text); fields(p, ['native_turn'], number); break;
      case 'draft_withheld': case 'message_sent': case 'dispatch_confirmed': case 'inbox_read_committed':
        fields(p, ['call_id', 'tool_call_id', 'target', 'text'], text); break;
      case 'inbox_wake_admitted': fields(p, ['submission_id'], text); break;
      case 'injection_consumed': fields(p, ['background_returns'], Array.isArray); break;
      case 'self_evolution_review': fields(p, ['review_id'], text); fields(p, ['updated_targets'], value => Array.isArray(value) && value.every(text)); break;
    }
  }
  // The assertions are limited to this decoder after every consumed field is checked.
  return {event: value as unknown as WorkJournalEvent, fact: known ? value as unknown as ReceivedWorkFact : undefined};
}

/** Validate a complete batch before any of its events can advance the journal.
 * Args:
 *   value: Untrusted append envelope.
 * Returns:
 *   The original batch without field normalization or reordering.
 */
export function decodeWorkBatch(value: unknown): WorkAppendBatch {
  if (!workObject(value) || typeof value.journal_id !== 'string' || !value.journal_id ||
      !Number.isSafeInteger(value.from_seq) || Number(value.from_seq) < 1 || !Array.isArray(value.events) || !value.events.length || value.events.length > 100)
    throw new WorkEventError('invalid_arguments');
  for (const event of value.events) decodeWorkEvent(event);
  return value as unknown as WorkAppendBatch;
}

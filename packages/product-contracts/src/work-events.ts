/** Stable product Work facts; native runtime records and tool content remain opaque. */
export interface WorkCommonFields {
  run_id?: string | null;
  source_refs?: unknown[] | null;
}
export type WorkScope = 'global_main' | 'subagent' | 'workflow' | 'cron';
export interface WorkSessionFields extends WorkCommonFields {
  scope: WorkScope;
  parent_session_id?: string | null;
  child_agent_id?: string;
  workflow_run_id?: string;
  title?: string;
  description?: string;
  retired?: boolean;
  historical_only?: boolean;
}
export interface WorkLinkFields extends WorkCommonFields {
  parent_session_id: string;
  child_session_id: string;
  workflow_run_id?: string;
  title?: string;
  description?: string;
}
export interface WorkUsage {
  context_used?: number;
  output?: number;
  context_window?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  total?: number;
  cache_read_tokens?: number;
  cache_total_input_tokens?: number;
  [metric: string]: unknown;
}
export interface WorkStartFields extends WorkCommonFields {
  origin?: string;
  trigger?: {kind?: string; job_id?: string; [key: string]: unknown} | null;
  model?: string | null;
  model_id?: string | null;
  started_at?: string | null;
  lifecycle_revision?: number;
}
export interface WorkEndFields extends WorkCommonFields {
  status?: string | null;
  stop_reason?: string;
  completed?: boolean;
  error?: unknown;
  model?: string | null;
  finished_at?: string | null;
  elapsed_ms?: number | null;
  duration_ms?: number | null;
  usage?: WorkUsage | null;
  context_window?: number | null;
}
export interface WorkToolFields extends WorkCommonFields {
  call_id?: string;
  tool_call_id?: string;
  tool_name?: string;
  name?: string;
  arguments?: unknown;
  error?: unknown;
  is_error?: boolean;
  reason_code?: string;
  duration_ms?: number;
  presentation?: {summary?: string; label?: string; detail?: unknown; emoji?: string; [key: string]: unknown} | null;
}
export interface WorkPermissionOption {id: string; [field: string]: unknown}
export interface WorkPermissionRequest {
  lifecycle_revision?: number;
  options?: WorkPermissionOption[] | null;
  [field: string]: unknown;
}
export interface WorkPermissionFields extends WorkCommonFields {
  request_id?: string;
  lifecycle_revision?: number;
  permission_request?: WorkPermissionRequest | null;
  options?: WorkPermissionOption[] | null;
}
export interface WorkMessageFields extends WorkCommonFields {
  message_id?: string;
  role?: string;
  text?: string;
  delta?: string;
  reasoning_content?: string;
  source_kind?: string;
  source_session_id?: string;
  native_turn?: number;
}
export interface WorkCallFactFields extends WorkCommonFields {
  call_id?: string;
  tool_call_id?: string;
  target?: string;
  text?: string;
}
export interface WorkPayloads {
  session_registered: WorkSessionFields;
  session_linked: WorkLinkFields;
  turn_started: WorkStartFields;
  turn_start: WorkStartFields;
  turn_end: WorkEndFields;
  run_completed: WorkEndFields;
  run_failed: WorkEndFields;
  run_cancelled: WorkEndFields;
  model_selected: WorkCommonFields & {model: string};
  tool_start: WorkToolFields;
  tool_end: WorkToolFields;
  permission_request: WorkPermissionFields;
  permission_resolved: WorkPermissionFields;
  message: WorkMessageFields;
  message_delta: WorkMessageFields;
  text_delta: WorkMessageFields;
  draft_withheld: WorkCallFactFields;
  message_sent: WorkCallFactFields;
  dispatch_confirmed: WorkCallFactFields;
  inbox_read_committed: WorkCallFactFields;
  inbox_wake_admitted: WorkCommonFields & {submission_id?: string};
  tool_result_committed: WorkCommonFields;
  turn_input_committed: WorkCommonFields;
  run_heartbeat: WorkCommonFields;
  injection_consumed: WorkCommonFields & {background_returns: unknown[]};
  self_evolution_review: WorkCommonFields & {review_id: string; updated_targets: string[]};
  control_result: WorkCommonFields & Record<string, unknown>;
  recording_degraded: WorkCommonFields & Record<string, unknown>;
  model_fallback: WorkCommonFields & Record<string, unknown>;
  cron_trigger: WorkCommonFields & Record<string, unknown>;
  cron_delivery: WorkCommonFields & Record<string, unknown>;
}
export type WorkEventType = keyof WorkPayloads;
/** Passing the fact as one value keeps type and payload correlated. */
export type WorkFact = {[K in WorkEventType]: {type: K; payload: WorkPayloads[K]}}[WorkEventType];
export interface WorkIdentity {
  event_id: string;
  root_agent_id: string;
  session_id: string;
  turn_id?: string | null;
  observed_at?: string | null;
}
export type WorkDraft = WorkIdentity & WorkFact;
/** Transport also retains old/unknown event names; producers only accept WorkDraft. */
export interface WorkJournalEvent extends WorkIdentity {
  seq: number;
  type: string;
  payload: WorkCommonFields & Record<string, unknown>;
}
/** Older senders may omit optional display data; the decoder validates present fields. */
type ReceivedWorkPayload<K extends WorkEventType> = K extends 'session_registered' ? WorkSessionFields
  : K extends 'session_linked' ? WorkLinkFields : Partial<WorkPayloads[K]>;
export type ReceivedWorkFact = {[K in WorkEventType]: {type: K; payload: ReceivedWorkPayload<K>}}[WorkEventType];
export interface DecodedWorkEvent {
  event: WorkJournalEvent;
  fact: ReceivedWorkFact | undefined;
}
export interface WorkAppendBatch {journal_id: string; from_seq: number; events: WorkJournalEvent[]}
export interface WorkAppendAck {journal_id: string; through_seq: number; expected_seq?: number}

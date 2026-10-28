import type { WorkSessionFields, WorkUsage } from '@nano/product-contracts';

/** Fixed SQLite rows keep JSON columns separate from decoded public values. */
export interface WorkSessionRecord {
  session_id: string; root_agent_id: string; node_id: string; scope: string;
  parent_session_id: string | null; payload: string;
}
export interface WorkEventRecord {
  revision: number; node_id: string; journal_id: string; seq: number; event_id: string;
  root_agent_id: string; session_id: string; turn_id: string | null; type: string;
  observed_at: string; payload: string;
}
export interface WorkTurnRecord {session_id: string; turn_id: string; seq: number; payload: string}
export interface WorkItemRecord {
  session_id: string; turn_id: string; item_id: string; seq: number; kind: string;
  observed_at: string | null; payload: string; revision: number;
}
export type WorkSessionView = Omit<WorkSessionRecord, 'payload'> & Omit<Partial<WorkSessionFields>, 'scope'>;
export interface WorkTurnData {
  session_id: string; turn_id: string; status: string; usage: WorkUsage | null;
  source_refs: unknown[]; model_id?: string | null; run_id?: string | null;
  origin?: string; trigger?: Record<string, unknown> | null; job_id?: string;
  started_at?: string | null; finished_at?: string | null; elapsed_ms?: number | null; error?: unknown;
}
/** Item payloads retain arbitrary original extension fields and tool content. */
export interface WorkItemData {
  seq?: number; text?: string; input?: unknown; output?: unknown; name?: string;
  work_facts?: Array<Record<string, unknown>>;
  [field: string]: unknown;
}
export interface WorkItemView {item_id: string; seq: number; kind: string; observed_at: string | null; revision: number; payload: WorkItemData}
export interface WorkItemsPage {items: WorkItemView[]; next_cursor: string | null}
export interface WorkTurnView extends WorkTurnData {scope: string; items: WorkItemView[]; next_items_cursor: string | null}
export interface WorkTurnsPage {turns: WorkTurnView[]; control_items: WorkItemView[]; next_cursor: string | null}
export interface WorkRecordView {
  root_agent_id: string; main_session_id: string | null; revision: number;
  latest_main_usage: (WorkUsage & {session_id: string; turn_id: string; model_id?: string | null}) | null;
  main_execution: string; node_id: string; control_items: WorkItemView[];
  other_executions: WorkSessionView[]; turns: WorkTurnView[]; next_cursor: string | null;
}

export interface WorkView extends Omit<WorkRecordView, 'node_id'> {
  node_connection_state: 'online' | 'offline';
  record_sync_state: 'current' | 'catching_up' | 'unknown';
}

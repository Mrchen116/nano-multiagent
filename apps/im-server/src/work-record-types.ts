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
  tool_count?: number; model_request_state?: 'none' | 'requested';
  maintenance_stage?: string; maintenance_title?: string;
}
/** Item payloads retain arbitrary original extension fields and tool content. */
export interface WorkItemData {
  seq?: number; text?: string; input?: unknown; output?: unknown; name?: string;
  work_facts?: Array<Record<string, unknown>>;
  [field: string]: unknown;
}
export interface WorkItemView {item_id: string; seq: number; kind: string; observed_at: string | null; revision: number; has_exact_child?: boolean; detail_deferred?: true; payload: WorkItemData}
export interface WorkItemsPage {items: WorkItemView[]; next_cursor: string | null; revision?: number}
export interface WorkCatalogFilter {parent?: string; call?: string; agent?: string; historical?: boolean}
export interface WorkCatalogPage {sessions: WorkSessionView[]; next_cursor: string | null; match_mode?: "exact" | "weak"}
export interface WorkTurnView extends WorkTurnData {seq: number; scope: string; items: WorkItemView[]; next_items_cursor: string | null; items_deferred?: boolean; tool_count?: number; has_background_returns?: boolean; background_task_type?: string | null}
export interface WorkFocus {turn: WorkTurnView; newer_turn_id: string | null; older_turn_id: string | null}
export interface WorkTurnsPage {turns: WorkTurnView[]; control_items: WorkItemView[]; next_cursor: string | null; next_turn_id: string | null}
export interface WorkRecordView {
  catalog?: 'separate'; timeline?: 'combined'; root_agent_id: string; main_session_id: string | null; revision: number;
  focus?: {session_id: string; turn_id: string} | null;
  latest_main_usage: (WorkUsage & {session_id: string; turn_id: string; model_id?: string | null}) | null;
  main_execution: string; node_id: string; control_items: WorkItemView[];
  other_executions: WorkSessionView[]; turns: WorkTurnView[]; next_cursor: string | null; next_turn_id: string | null; next_turn_seq?: number | null;
}

export interface WorkView extends Omit<WorkRecordView, 'node_id'> {
  node_connection_state: 'online' | 'offline';
  record_sync_state: 'current' | 'catching_up' | 'unknown';
}

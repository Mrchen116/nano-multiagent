import type { TaskDoingWake, TaskMode, TaskWait } from './task-graphs.js';
export type { TaskDoingWake, TaskWait } from './task-graphs.js';

/** Runtime-independent check of a native schedule belonging to one task owner. */
export interface TaskWaitInspection {
  valid: boolean;
  owner_agent_id?: string;
  session_id?: string;
  next_check_at?: string;
  checked_at: string;
  reason_code?: 'missing'|'inactive'|'expired'|'owner_or_session_mismatch'|'unavailable';
  pending_occurrence_id?: string;
}
/** Minimum task context needed to keep a product Agent responsible for its work. */
export interface TaskResponsibility {
  graph_id: string;
  node_id: string;
  title: string;
  status: 'doing' | 'waiting';
  revision: number;
  updated_at: string;
  conversation: {id: string};
  relative_url: string;
  root_node_id?: string;
  root_title?: string;
  root_goal_summary?: string;
  parent_path?: { id: string; title: string; mode?: TaskMode }[];
  doing_wake?: TaskDoingWake | null;
  wait?: TaskWait;
  resume_request?: { actor_id: string; at: string; revision: number };
}
/** Current responsibility projection, never a second persisted Task state. */
export interface TaskExecutionSnapshot {
  kind: 'continue' | 'quiescent' | 'unavailable';
  tasks: TaskResponsibility[];
  reason?: string;
}
/** Private invalidation hint; no task body crosses this notification. */
export interface TaskExecutionChange { agent_ids: string[]; conversation_ids: string[] }

/** Current native execution observation, with no private session or task content. */
export interface TaskExecutionState { state: 'running' | 'idle' | 'offline' | 'unknown' }

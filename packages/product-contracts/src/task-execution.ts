/** A native execution reference stored in the canonical Task, never another Task status. */
export interface TaskExecutionBinding {
  child_id:string; root_session_id:string; owner_agent_id:string;
  request_revision:number; bound_revision:number; needs_coordination?:boolean;
  correction_source_ref?:string; input_receipt?:string; delivery_receipt?:string;
}
/** Persisted Task waiting facts; Schedule remains the timer authority. */
export interface TaskWait {
  reason: string;
  schedule_id: string;
  owner_agent_id: string;
  session_id: string;
  next_check_at: string;
}
/** Runtime-independent check of a native schedule belonging to one task owner. */
export interface TaskWaitInspection {
  valid: boolean;
  owner_agent_id?: string;
  session_id?: string;
  next_check_at?: string;
  checked_at: string;
  reason_code?: string;
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
  wait?: TaskWait;
  execution?: TaskExecutionBinding;
  resume_request?: { actor_id: string; at: string; revision: number };
}
/** Current responsibility projection, never a second persisted Task state. */
export interface TaskExecutionSnapshot {
  kind: 'continue' | 'quiescent' | 'unavailable';
  tasks: TaskResponsibility[];
  repair_task_ids: string[];
  reason?: string;
}
/** Private invalidation hint; no task body crosses this notification. */
export interface TaskExecutionChange { agent_ids: string[]; conversation_ids: string[] }

/** Current native execution observation, with no private session or task content. */
export interface TaskExecutionState { state: 'running' | 'idle' | 'offline' | 'unknown' }

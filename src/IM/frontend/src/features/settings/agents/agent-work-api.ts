import { tr } from "./agent-work-text";
import { authFetch } from "../../auth/auth-fetch";
import { readHttpError } from "../../auth/http-error";
import type { TokenUsage } from "../../chat/chat-types";

export interface WorkItem { item_id: string; seq: number; revision?: number; has_exact_child?: boolean; detail_deferred?: true; kind: string; observed_at?: string; payload: Record<string, unknown> }
export interface WorkTurn { seq: number; description?: string; session_id: string; turn_id: string; scope?: string; job_id?: string; run_id?: string; status: string; origin?: string | Record<string, unknown>; trigger?: Record<string, unknown>; model_id?: string; started_at?: string; finished_at?: string; elapsed_ms?: number; error?: {code?: string; message?: string}; usage: (Partial<TokenUsage> & {total_tokens?: number}) | null; items: WorkItem[]; next_items_cursor: string | null; items_deferred?: boolean; tool_count?: number; maintenance_stage?: string; maintenance_title?: string; model_request_state?: string; has_background_returns?: boolean; background_task_type?: string | null }
export interface WorkSession { session_id: string; scope: string; job_id?: string; trigger?: string; parent_session_id?: string; parent_tool_call_id?: string; child_agent_id?: string; description?: string; title?: string; status?: string }
export interface WorkItemsPage { items: WorkItem[]; next_cursor: string | null; revision?: number }
export interface WorkCatalogPage { sessions: WorkSession[]; next_cursor: string | null; match_mode?: "exact" | "weak" }
export interface WorkTurnPage { control_items?: WorkItem[]; turns: WorkTurn[]; next_cursor: string | null; next_turn_id?: string | null; next_turn_seq?: number | null }
export interface WorkFocus { turn: WorkTurn; newer_turn_id: string | null; older_turn_id?: string | null }
export interface WorkView extends WorkTurnPage { catalog?: 'separate'; timeline?: 'combined'; root_agent_id: string; main_session_id: string | null; revision: number; node_connection_state: string; record_sync_state?: "current" | "catching_up" | "unknown"; main_execution: string; latest_main_usage: (Partial<TokenUsage> & { turn_id: string; model_id?: string }) | null; other_executions: WorkSession[] }
export class WorkRequestError extends Error {
  constructor(readonly status: number, message = `${tr("工作记录读取失败")} (${status})`) {
    super(message);
  }
}

export class AgentExecutionDeletedError extends WorkRequestError {
  constructor() { super(410, tr("执行记录已删除")); }
}

export const workAccessLost = (error: unknown) =>
  error instanceof WorkRequestError && [401, 403, 404, 409, 410].includes(error.status);

export async function workRequest<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await authFetch(path, {signal});
  if (response.status === 410) {
    const error = await readHttpError(response);
    if (error.code === "agent_execution_deleted" || error.detail === "agent_execution_deleted") throw new AgentExecutionDeletedError();
  }
  if (!response.ok) throw new WorkRequestError(response.status);
  return response.json() as Promise<T>;
}
export const workBase = (agentId: string) => `/im/v1/agents/${encodeURIComponent(agentId)}/work`;

export const workSessionPath = (agentId: string, sessionId: string) => `${workBase(agentId)}/sessions/${encodeURIComponent(sessionId)}`;
export const workCatalogPath = (agentId: string, params: Record<string, string>) =>
  `${workBase(agentId)}/sessions?${new URLSearchParams(params)}`;

export interface WorkActivitySession {
  session_id: string;
  parent_session_id?: string | null;
  title?: string;
  status: string;
  turn_id?: string;
  last_active_at?: string;
}

export interface WorkActivity {
  revision: number;
  node_connection_state: string;
  record_sync_state: "current" | "catching_up" | "unknown";
  main_execution: string;
  main_session_id: string | null;
  latest_tool: {name: string; label?: string; status?: string; turn_id: string; item_id: string; session_id: string} | null;
  running_count: number | null;
  waiting_permission_count: number | null;
  sessions: WorkActivitySession[];
  next_cursor: string | null;
}

export interface WorkDelegationNode extends WorkActivitySession {
  scope?: string;
  ancestor_only?: boolean;
  usage: {total_tokens: number | null; reported_turns: number; missing_turns: number};
}

export interface WorkDelegationPage {
  window: "3d" | "2h";
  from: string;
  until: string;
  revision: number;
  node_connection_state: string;
  record_sync_state: WorkActivity["record_sync_state"];
  main_session_id: string | null;
  nodes: WorkDelegationNode[];
  next_cursor: string | null;
}

import { authFetch } from "../../auth/auth-fetch";
import type { TokenUsage } from "../../chat/chat-types";

export interface WorkItem { item_id: string; seq: number; kind: string; observed_at?: string; payload: Record<string, unknown> }
export interface WorkTurn { session_id: string; turn_id: string; scope?: string; job_id?: string; run_id?: string; status: string; origin?: string | Record<string, unknown>; trigger?: Record<string, unknown>; model_id?: string; started_at?: string; finished_at?: string; elapsed_ms?: number; usage: Partial<TokenUsage> | null; items: WorkItem[]; next_items_cursor: string | null }
export interface WorkSession { session_id: string; scope: string; job_id?: string; trigger?: string; parent_session_id?: string; parent_tool_call_id?: string; child_agent_id?: string; description?: string; title?: string; status?: string }
export interface WorkTurnPage { control_items?: WorkItem[]; turns: WorkTurn[]; next_cursor: string | null }
export interface WorkView extends WorkTurnPage { root_agent_id: string; main_session_id: string | null; revision: number; node_connection_state: string; main_execution: string; latest_main_usage: (Partial<TokenUsage> & { turn_id: string; model_id?: string }) | null; other_executions: WorkSession[] }
export async function workRequest<T>(path: string): Promise<T> {
  const response = await authFetch(path);
  if (!response.ok) throw new Error(`工作记录读取失败 (${response.status})`);
  return response.json() as Promise<T>;
}
export const workBase = (agentId: string) => `/im/v1/agents/${encodeURIComponent(agentId)}/work`;

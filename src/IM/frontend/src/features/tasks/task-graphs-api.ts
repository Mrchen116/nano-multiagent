import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";

import { authFetch } from "../auth/auth-fetch";
import { useAuthStore } from "../auth/auth-store";

export type TaskMode = "none" | "dag" | "explore";
export type TaskStatus = "todo" | "doing" | "in_review" | "done" | "paused" | "closed";
export type TaskActor = { type: "user" | "agent"; id: string; display_name?: string | null; user_id?: string | null };
export type DirectCounts = Record<TaskStatus | "total", number>;
export type TaskConversation = { id: string; title: string; visibility: "public" | "private"; dissolved_at: string | null; is_member: boolean; can_write: boolean };
export type TaskNode = {
  created_by?: TaskActor;
  assignee?: TaskActor | null;
  updated_by_actor?: TaskActor;
  can_edit?: boolean;
  can_delete?: boolean;
  can_claim?: boolean;
  direct_counts?: DirectCounts;
  id: string;
  container_id: string | null;
  title: string;
  description: string;
  mode: TaskMode;
  status: TaskStatus;
  result: string;
  change_note?: string;
  derived_from_id: string | null;
  selected_candidate_id: string | null;
  selection_reason: string;
  links: string[];
  order: number;
  created_at: string;
  updated_at: string;
  updated_by: string;
  last_chat_id: string | null;
  last_chat_title: string | null;
};
export type TaskDependency = { from: string; to: string };
export type TaskGraph = {
  schema_version: 2;
  conversation?: TaskConversation;
  graph_id: string;
  root_node_id: string;
  revision: number;
  nodes: TaskNode[];
  dependencies: TaskDependency[];
  created_at: string;
  updated_at: string;
  updated_by: string;
  relative_url: string;
};
export type TaskGraphSummary = Pick<TaskGraph,
  "graph_id" | "root_node_id" |
  "revision" | "updated_at" | "updated_by" | "relative_url"
> & { title: string; mode: TaskMode; status: TaskStatus; created_by?: TaskActor; assignee?: TaskActor | null; direct_counts?: DirectCounts; conversation?: TaskConversation; node_id?: string; scope_id?: string | null; parent_path?: {id: string; title: string}[] };
export type TaskGraphList = { items: TaskGraphSummary[]; next_cursor: string | null; total: number };

export class TaskGraphReadError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function read<T>(path: string, signal?: AbortSignal): Promise<T | null> {
  const response = await authFetch(path, { signal });
  // A revoked resource must replace previously cached content, unlike transient errors.
  if (response.status === 403 || response.status === 404) return null;
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new TaskGraphReadError(response.status, body?.detail?.code ?? "read_failed", body?.detail?.message ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

export type TaskListOptions = { query?: string; cursor?: string; limit?: number; assignee_type?: string; assignee_id?: string; statuses?: TaskStatus[] };

export function listTaskGraphs(options: TaskListOptions, signal?: AbortSignal) {
  const params = new URLSearchParams();
  if (options.assignee_type && options.assignee_id) { params.set("assignee_type", options.assignee_type); params.set("assignee_id", options.assignee_id); }
  if (options.statuses) params.set("statuses", options.statuses.join(","));
  if (options.query) params.set("query", options.query);
  if (options.cursor) params.set("cursor", options.cursor);
  params.set("limit", String(options.limit ?? 20));
  return read<TaskGraphList>(`/im/v1/task-graphs?${params}`, signal);
}

export async function getTaskGraph(graphId: string, signal?: AbortSignal) {
  const graph = await read<TaskGraph>(`/im/v1/task-graphs/${encodeURIComponent(graphId)}?view=all`, signal);
  if (graph && graph.schema_version !== 2) {
    throw new TaskGraphReadError(400, "unsupported_schema", "Unsupported task graph schema");
  }
  return graph;
}

const refreshOptions = {
  refetchInterval: () => document.visibilityState === "visible" ? 3_000 : false as const,
  refetchIntervalInBackground: false,
  refetchOnWindowFocus: "always" as const,
  retry: false
};

export function useTaskGraphList(options: { query?: string; cursor?: string; limit?: number; assignee_type?: string; assignee_id?: string }) {
  const userId = useAuthStore(state => state.user?.id);
  const client = useQueryClient();
  return useQuery({
    queryKey: ["task-graphs", userId, "list", options],
    queryFn: async ({ signal }) => {
      const list = await listTaskGraphs(options, signal);
      if (list === null) client.setQueriesData({ queryKey: ["task-graphs", userId] }, null);
      return list;
    },
    ...refreshOptions
  });
}

/** Keeps active columns' pages while polling; filters restart after leaving a column. */
export function useTaskGraphColumn(options: TaskListOptions) {
  const userId = useAuthStore(state => state.user?.id);
  const client = useQueryClient();
  return useInfiniteQuery({
    queryKey: ["task-graphs", userId, "column", options],
    gcTime: 0,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ signal, pageParam }) => {
      const list = await listTaskGraphs({ ...options, cursor: pageParam }, signal);
      if (list === null) client.setQueriesData({ queryKey: ["task-graphs", userId] }, null);
      return list;
    },
    getNextPageParam: page => page?.next_cursor ?? undefined,
    ...refreshOptions
  });
}

export function useTaskGraph(graphId: string | undefined) {
  const userId = useAuthStore(state => state.user?.id);
  const client = useQueryClient();
  return useQuery({
    queryKey: ["task-graphs", userId, "detail", graphId],
    queryFn: async ({ signal }) => {
      const graph = await getTaskGraph(graphId!, signal);
      if (graph === null) client.setQueriesData({ queryKey: ["task-graphs", userId] }, null);
      return graph;
    },
    enabled: Boolean(graphId),
    ...refreshOptions
  });
}

export function taskGraphUrl(graphId: string, scope?: string | null, node?: string | null) {
  const params = new URLSearchParams();
  if (scope) params.set("scope", scope);
  if (node) params.set("node", node);
  return `/tasks/${encodeURIComponent(graphId)}${params.size ? `?${params}` : ""}`;
}

export type TaskActivity = { graph_id: string; node_id: string; scope_id: string | null; title: string; root_title: string; status: TaskStatus; updated_at: string };
export function useTaskActivity(conversationId: string) {
  const userId = useAuthStore(state => state.user?.id);
  return useQuery({ queryKey: ["task-graphs", userId, "activity", conversationId],
    queryFn: ({ signal }) => read<{ items: TaskActivity[] }>(`/im/v1/conversations/${encodeURIComponent(conversationId)}/task-activity`, signal),
    ...refreshOptions });
}

export async function writeTaskGraph(path: string, body: Record<string, unknown>, method = "POST"): Promise<{ graph_id: string }> {
  const response = await authFetch(`/im/v1/task-graphs${path}`, { method, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new TaskGraphReadError(response.status, data?.detail?.code ?? "write_failed", data?.detail?.message ?? response.statusText);
  return data;
}

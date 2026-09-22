import { useQuery, useQueryClient } from "@tanstack/react-query";

import { authFetch } from "../auth/auth-fetch";
import { useAuthStore } from "../auth/auth-store";

export type TaskMode = "none" | "dag" | "explore";
export type TaskStatus = "todo" | "doing" | "done" | "paused" | "dropped";
export type TaskNode = {
  id: string;
  container_id: string | null;
  title: string;
  description: string;
  mode: TaskMode;
  status: TaskStatus;
  result: string;
  derived_from_id: string | null;
  selected_candidate_id: string | null;
  selection_reason: string;
  links: string[];
  order: number;
  created_at: string;
  updated_at: string;
  updated_by: string;
};
export type TaskDependency = { from: string; to: string };
export type TaskGraph = {
  schema_version: 1;
  graph_id: string;
  home_conversation_id: string;
  home_conversation_title: string;
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
  "graph_id" | "root_node_id" | "home_conversation_id" | "home_conversation_title" |
  "revision" | "updated_at" | "updated_by" | "relative_url"
> & { title: string; mode: TaskMode; status: TaskStatus };
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

export function listTaskGraphs(options: { conversationId?: string; query?: string; cursor?: string; limit?: number }, signal?: AbortSignal) {
  const params = new URLSearchParams();
  if (options.conversationId) params.set("conversation_id", options.conversationId);
  if (options.query) params.set("query", options.query);
  if (options.cursor) params.set("cursor", options.cursor);
  params.set("limit", String(options.limit ?? 20));
  return read<TaskGraphList>(`/im/v1/task-graphs?${params}`, signal);
}

export async function getTaskGraph(graphId: string, signal?: AbortSignal) {
  const graph = await read<TaskGraph>(`/im/v1/task-graphs/${encodeURIComponent(graphId)}?view=all`, signal);
  if (graph && graph.schema_version !== 1) {
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

export function useTaskGraphList(options: { conversationId?: string; query?: string; cursor?: string; limit?: number }) {
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

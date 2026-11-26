import { useEffect } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";

import { authFetch } from "../auth/auth-fetch";
import { useAuthStore } from "../auth/auth-store";

export const TASK_MODES = ["none", "dag", "explore"] as const;
export type TaskMode = (typeof TASK_MODES)[number];

export const TASK_STATUSES = [
  "proposed",
  "todo",
  "doing",
  "waiting",
  "in_review",
  "done",
  "paused",
  "backlog",
  "closed",
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export function isKnownTaskStatus(value: string): value is TaskStatus {
  return (TASK_STATUSES as readonly string[]).includes(value);
}

export type TaskActor = {
  type: "user" | "agent";
  id: string;
  display_name?: string | null;
  user_id?: string | null;
};

export type DirectCounts = Partial<Record<TaskStatus, number>> & { total?: number; done?: number };

export type TaskConversation = {
  id: string;
  title: string;
  visibility: "public" | "private";
  dissolved_at: string | null;
  is_member: boolean;
  can_write: boolean;
};

export type TaskWait = {
  reason: string;
  schedule_id?: string | null;
  owner_agent_id?: string | null;
  session_id?: string | null;
  next_check_at?: string | null;
  asked_user_id?: string | null;
};

export type TaskWaitHealth = {
  state: "valid" | "invalid" | "unknown";
  checked_at: string;
  reason_code?: string;
};

export type TaskCardRef = {
  graph_id: string;
  node_id: string;
};

export type TaskNode = {
  proposed_for_user_id?: string | null;
  wait?: TaskWait;
  wait_health?: TaskWaitHealth;
  prereq_blocked?: boolean;
  blocked_by_dag?: boolean;
  root_title?: string;
  root_goal_summary?: string;
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

export type TaskGraphSummary = Pick<
  TaskGraph,
  "graph_id" | "root_node_id" | "revision" | "updated_at" | "updated_by" | "relative_url"
> &
  Pick<TaskNode, "wait" | "wait_health" | "proposed_for_user_id"> & {
    title: string;
    description?: string;
    result?: string;
    mode: TaskMode;
    status: TaskStatus;
    prereq_blocked?: boolean;
    blocked_by_dag?: boolean;
    root_title?: string;
    root_goal_summary?: string;
    created_by?: TaskActor;
    assignee?: TaskActor | null;
    direct_counts?: DirectCounts;
    conversation?: TaskConversation;
    node_id?: string;
    scope_id?: string | null;
    parent_path?: { id: string; title: string; mode?: TaskMode }[];
    can_edit?: boolean;
    can_delete?: boolean;
    can_claim?: boolean;
  };

export type TaskGoalStageSummary = {
  id: string;
  title: string;
  status: TaskStatus;
  mode: TaskMode;
  child_count: number;
};

export type TaskFocusGoalItem = TaskGraphSummary & {
  progress?: { done: number; total: number };
  stage_nodes?: TaskGoalStageSummary[];
};

export type TaskFocusSection = "needs_you" | "stashed" | "active" | "goals" | "completed";
export type TaskFocusScope = "mine" | "assignee" | "all";

export type TaskFocusResponse = {
  needs_you: TaskGraphSummary[];
  stashed: TaskGraphSummary[];
  active: TaskGraphSummary[];
  goals: TaskFocusGoalItem[];
  completed?: TaskGraphSummary[];
  completed_count: number;
  counts: {
    needs_you: number;
    stashed: number;
    active: number;
    goals: number;
    completed: number;
  };
  next_cursors: Record<TaskFocusSection, string | null>;
};

export type TaskGraphList = { items: TaskGraphSummary[]; next_cursor: string | null; total: number };

export class TaskGraphReadError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

/** Check whether a proposed/queued node is blocked by unfinished sibling DAG dependencies. */
export function isTaskPrereqBlocked(
  cardOrNode: { prereq_blocked?: boolean; blocked_by_dag?: boolean },
  graph?: TaskGraph | null,
  nodeId?: string,
): boolean {
  if (cardOrNode.prereq_blocked !== undefined) return Boolean(cardOrNode.prereq_blocked);
  if (cardOrNode.blocked_by_dag !== undefined) return Boolean(cardOrNode.blocked_by_dag);
  if (graph && nodeId) {
    const node = graph.nodes.find(candidate => candidate.id === nodeId);
    const parent = node?.container_id ? graph.nodes.find(candidate => candidate.id === node.container_id) : null;
    if (parent?.mode === "dag") {
      return graph.dependencies.some(
        edge => edge.to === nodeId && graph.nodes.find(candidate => candidate.id === edge.from)?.status !== "done",
      );
    }
  }
  return false;
}

function normalizeCard<T extends TaskGraphSummary>(item: T): T {
  return {
    ...item,
    prereq_blocked: item.prereq_blocked ?? item.blocked_by_dag ?? false,
  };
}

async function read<T>(path: string, signal?: AbortSignal): Promise<T | null> {
  const response = await authFetch(path, { signal });
  // A revoked resource must replace previously cached content, unlike transient errors.
  if (response.status === 403 || response.status === 404) return null;
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new TaskGraphReadError(
      response.status,
      body?.detail?.code ?? "read_failed",
      body?.detail?.message ?? response.statusText,
    );
  }
  return response.json() as Promise<T>;
}

export type TaskListOptions = {
  query?: string;
  cursor?: string;
  limit?: number;
  assignee_type?: string;
  assignee_id?: string;
  statuses?: TaskStatus[];
  conversation_id?: string;
};

export async function listTaskGraphs(options: TaskListOptions, signal?: AbortSignal) {
  const params = new URLSearchParams();
  if (options.assignee_type && options.assignee_id) {
    params.set("assignee_type", options.assignee_type);
    params.set("assignee_id", options.assignee_id);
  }
  if (options.statuses?.length) params.set("statuses", options.statuses.join(","));
  if (options.conversation_id) params.set("conversation_id", options.conversation_id);
  if (options.query) params.set("query", options.query);
  if (options.cursor) params.set("cursor", options.cursor);
  params.set("limit", String(options.limit ?? 20));
  const data = await read<TaskGraphList>(`/im/v1/task-graphs?${params}`, signal);
  if (!data) return null;
  return {
    ...data,
    items: (data.items ?? []).map(normalizeCard),
  };
}

export type TaskFocusOptions = {
  scope?: TaskFocusScope;
  assignee_type?: string;
  assignee_id?: string;
  conversation_id?: string;
  query?: string;
  limit?: number;
  section?: TaskFocusSection;
  cursor?: string;
};

export async function getTaskFocus(options: TaskFocusOptions, signal?: AbortSignal): Promise<TaskFocusResponse | null> {
  const params = new URLSearchParams();
  const scope = options.scope ?? "mine";
  params.set("scope", scope);
  if (scope === "assignee" && options.assignee_type && options.assignee_id) {
    params.set("assignee_type", options.assignee_type);
    params.set("assignee_id", options.assignee_id);
  }
  if (options.conversation_id) params.set("conversation_id", options.conversation_id);
  if (options.query) params.set("query", options.query);
  if (options.section) params.set("section", options.section);
  if (options.cursor) params.set("cursor", options.cursor);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  const raw = await read<Partial<TaskFocusResponse>>(`/im/v1/task-graphs/focus?${params}`, signal);
  if (!raw) return null;
  const needsYou = (raw.needs_you ?? []).map(normalizeCard);
  const stashed = (raw.stashed ?? []).map(normalizeCard);
  const active = (raw.active ?? []).map(normalizeCard);
  const goals = (raw.goals ?? []).map(normalizeCard);
  const completed = (raw.completed ?? []).map(normalizeCard);
  const completedCount = raw.completed_count ?? raw.counts?.completed ?? 0;
  return {
    needs_you: needsYou,
    stashed,
    active,
    goals,
    completed,
    completed_count: completedCount,
    counts: {
      needs_you: raw.counts?.needs_you ?? needsYou.length,
      stashed: raw.counts?.stashed ?? stashed.length,
      active: raw.counts?.active ?? active.length,
      goals: raw.counts?.goals ?? goals.length,
      completed: completedCount,
    },
    next_cursors: {
      needs_you: raw.next_cursors?.needs_you ?? null,
      stashed: raw.next_cursors?.stashed ?? null,
      active: raw.next_cursors?.active ?? null,
      goals: raw.next_cursors?.goals ?? null,
      completed: raw.next_cursors?.completed ?? null,
    },
  };
}

export async function getTaskCardNodes(refs: TaskCardRef[], signal?: AbortSignal): Promise<{ items: TaskGraphSummary[] } | null> {
  const unique = [...new Set(refs.filter(r => r.graph_id && r.node_id).map(r => `${r.graph_id}:${r.node_id}`))].slice(0, 50);
  if (!unique.length) return { items: [] };
  const params = new URLSearchParams({ refs: unique.join(",") });
  const raw = await read<{ items?: TaskGraphSummary[] }>(`/im/v1/task-graphs/nodes?${params}`, signal);
  if (!raw) return null;
  return { items: (raw.items ?? []).map(normalizeCard) };
}

export async function getTaskGraph(graphId: string, signal?: AbortSignal) {
  const graph = await read<TaskGraph>(`/im/v1/task-graphs/${encodeURIComponent(graphId)}?view=all`, signal);
  if (graph && graph.schema_version !== 2) {
    throw new TaskGraphReadError(400, "unsupported_schema", "Unsupported task graph schema");
  }
  return graph;
}

const refreshOptions = {
  refetchInterval: () => (document.visibilityState === "visible" ? 3_000 : (false as const)),
  refetchIntervalInBackground: false,
  refetchOnWindowFocus: "always" as const,
  retry: false,
};

function useTaskGraphStreamInvalidation() {
  const client = useQueryClient();
  useEffect(() => {
    const onTaskChanged = () => {
      void client.invalidateQueries({ queryKey: ["task-graphs"] });
    };
    window.addEventListener("im:task-graph-changed", onTaskChanged);
    return () => window.removeEventListener("im:task-graph-changed", onTaskChanged);
  }, [client]);
}

export function useTaskFocus(options: TaskFocusOptions, extraEnabled = true) {
  const userId = useAuthStore(state => state.user?.id);
  const client = useQueryClient();
  useTaskGraphStreamInvalidation();
  const scope = options.scope ?? "mine";
  const enabled = extraEnabled && (scope !== "assignee" || Boolean(options.assignee_type && options.assignee_id));
  return useQuery({
    queryKey: ["task-graphs", userId, "focus", options],
    enabled,
    queryFn: async ({ signal }) => {
      const focus = await getTaskFocus(options, signal);
      if (focus === null) client.setQueriesData({ queryKey: ["task-graphs", userId] }, null);
      return focus;
    },
    ...refreshOptions,
  });
}

export function useTaskCardNodes(refs: TaskCardRef[] | undefined) {
  const userId = useAuthStore(state => state.user?.id);
  useTaskGraphStreamInvalidation();
  const uniqueKeys = [...new Set((refs ?? []).filter(r => r.graph_id && r.node_id).map(r => `${r.graph_id}:${r.node_id}`))].slice(0, 50);
  return useQuery({
    queryKey: ["task-graphs", userId, "nodes", uniqueKeys],
    enabled: uniqueKeys.length > 0,
    queryFn: ({ signal }) =>
      getTaskCardNodes(
        uniqueKeys.map(entry => {
          const sep = entry.indexOf(":");
          return { graph_id: entry.slice(0, sep), node_id: entry.slice(sep + 1) };
        }),
        signal,
      ),
    ...refreshOptions,
  });
}

export function useTaskGraphList(options: { query?: string; cursor?: string; limit?: number; assignee_type?: string; assignee_id?: string }) {
  const userId = useAuthStore(state => state.user?.id);
  const client = useQueryClient();
  useTaskGraphStreamInvalidation();
  return useQuery({
    queryKey: ["task-graphs", userId, "list", options],
    queryFn: async ({ signal }) => {
      const list = await listTaskGraphs(options, signal);
      if (list === null) client.setQueriesData({ queryKey: ["task-graphs", userId] }, null);
      return list;
    },
    ...refreshOptions,
  });
}

/** Keeps active columns' pages while polling; filters restart after leaving a column. */
export function useTaskGraphColumn(options: TaskListOptions, enabled = true) {
  const userId = useAuthStore(state => state.user?.id);
  const client = useQueryClient();
  useTaskGraphStreamInvalidation();
  return useInfiniteQuery({
    queryKey: ["task-graphs", userId, "column", options],
    enabled,
    gcTime: 0,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ signal, pageParam }) => {
      const list = await listTaskGraphs({ ...options, cursor: pageParam }, signal);
      if (list === null) client.setQueriesData({ queryKey: ["task-graphs", userId] }, null);
      return list;
    },
    getNextPageParam: page => page?.next_cursor ?? undefined,
    ...refreshOptions,
  });
}

export function useTaskGraph(graphId: string | undefined) {
  const userId = useAuthStore(state => state.user?.id);
  const client = useQueryClient();
  useTaskGraphStreamInvalidation();
  return useQuery({
    queryKey: ["task-graphs", userId, "detail", graphId],
    queryFn: async ({ signal }) => {
      const graph = await getTaskGraph(graphId!, signal);
      if (graph === null) client.setQueriesData({ queryKey: ["task-graphs", userId] }, null);
      return graph;
    },
    enabled: Boolean(graphId),
    ...refreshOptions,
  });
}

export function taskGraphUrl(
  graphId: string,
  scope?: string | null,
  node?: string | null,
  returnChat?: string | null,
  returnMessage?: string | null,
) {
  const params = new URLSearchParams();
  if (scope) params.set("scope", scope);
  if (node) params.set("node", node);
  if (returnChat) params.set("return_chat", returnChat);
  if (returnMessage) params.set("return_message", returnMessage);
  return `/tasks/${encodeURIComponent(graphId)}${params.size ? `?${params}` : ""}`;
}

export type TaskActivity = {
  graph_id: string;
  node_id: string;
  scope_id: string | null;
  title: string;
  root_title: string;
  status: TaskStatus;
  updated_at: string;
};

export function useTaskActivity(conversationId: string) {
  const userId = useAuthStore(state => state.user?.id);
  useTaskGraphStreamInvalidation();
  return useQuery({
    queryKey: ["task-graphs", userId, "activity", conversationId],
    queryFn: ({ signal }) =>
      read<{ items: TaskActivity[] }>(`/im/v1/conversations/${encodeURIComponent(conversationId)}/task-activity`, signal),
    ...refreshOptions,
  });
}

export async function writeTaskGraph(path: string, body: Record<string, unknown>, method = "POST"): Promise<{ graph_id: string; status?: TaskStatus }> {
  const response = await authFetch(`/im/v1/task-graphs${path}`, { method, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) {
    throw new TaskGraphReadError(
      response.status,
      data?.detail?.code ?? "write_failed",
      data?.detail?.message ?? response.statusText,
    );
  }
  return data;
}

export const getTaskRuntime = (graphId: string, nodeId: string) =>
  read<{ state: "running" | "idle" | "offline" | "unknown" }>(
    `/im/v1/task-graphs/${encodeURIComponent(graphId)}/runtime?node_id=${encodeURIComponent(nodeId)}`,
  );

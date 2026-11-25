/** Shared progressive task-graph contracts across IM, Gateway, Web, and iOS. */

export const TASK_MODES = ['none', 'dag', 'explore'] as const;
export type TaskMode = (typeof TASK_MODES)[number];

export const TASK_STATUSES = [
  'proposed',
  'todo',
  'doing',
  'waiting',
  'in_review',
  'done',
  'paused',
  'backlog',
  'closed',
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

/** Canonical nine-word UI badge labels (never mixed with wait reasons or assignees). */
export const TASK_STATUS_BADGE_LABELS: Record<TaskStatus, string> = {
  proposed: '待拍板',
  todo: '待办',
  doing: '推进中',
  waiting: '等待中',
  in_review: '待确认',
  done: '已完成',
  paused: '已暂缓',
  backlog: '先存着',
  closed: '已关闭',
};

/** System collaboration notice labels for status transitions in conversations. */
export const TASK_NOTICE_STATUS_LABELS: Record<TaskStatus, string> = {
  proposed: '待拍板',
  todo: '待办',
  doing: '推进中',
  waiting: '等待中',
  in_review: '提交待确认',
  done: '已完成',
  paused: '已暂缓',
  backlog: '先存着',
  closed: '已关闭',
};

export const MAX_PROPOSED_TASKS_PER_CONVERSATION = 15;
export const MAX_TASK_WAIT_MS = 180 * 86_400_000;
export const MAX_TASK_CARDS_PER_MESSAGE = 5;

/** Check whether an untrusted value is a supported task container mode. */
export function isTaskMode(value: unknown): value is TaskMode {
  return typeof value === 'string' && (TASK_MODES as readonly string[]).includes(value);
}

/** Check whether an untrusted value is one of the nine canonical task statuses. */
export function isTaskStatus(value: unknown): value is TaskStatus {
  return typeof value === 'string' && (TASK_STATUSES as readonly string[]).includes(value);
}

export interface TaskProposalMeta {
  rationale: string;
  on_approve: string;
  proposed_for_user_id?: string | null;
}

/** Persisted Task waiting facts; Schedule is optional and remains timer authority when bound. */
export interface TaskWait {
  reason: string;
  schedule_id?: string | null;
  owner_agent_id?: string | null;
  session_id?: string | null;
  next_check_at?: string | null;
  question?: string | null;
  asked_user_id?: string | null;
}

/** Monotonic edge-triggered wake stamp recorded when a node enters or re-enters doing. */
export interface TaskDoingWake {
  revision: number;
  assignee_id: string | null;
  actor: { type: 'user' | 'agent'; id: string };
  at: string;
}

/** Lightweight message-level live reference to an authoritative task-graph node. */
export interface TaskCardRef {
  graph_id: string;
  node_id: string;
}

/** Validate top-level message task_cards references at transport boundaries.
 *
 * Args:
 *   value: Untrusted wire array of task card references.
 * Returns:
 *   Validated references preserving wire order.
 */
export function validateTaskCards(value: unknown): TaskCardRef[] {
  if (!Array.isArray(value) || value.length > MAX_TASK_CARDS_PER_MESSAGE) {
    throw new Error(`task_cards must be an array of at most ${MAX_TASK_CARDS_PER_MESSAGE} items`);
  }
  return value.map(entry => {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
      throw new Error('task_cards entry must be an object');
    }
    const row = entry as Record<string, unknown>;
    if (Object.keys(row).some(key => key !== 'graph_id' && key !== 'node_id')) {
      throw new Error('task_cards entry allows only graph_id and node_id');
    }
    if (typeof row.graph_id !== 'string' || !row.graph_id.trim() || row.graph_id.length > 128) {
      throw new Error('task_cards.graph_id required');
    }
    if (typeof row.node_id !== 'string' || !row.node_id.trim() || row.node_id.length > 128) {
      throw new Error('task_cards.node_id required');
    }
    return { graph_id: row.graph_id, node_id: row.node_id };
  });
}

export interface ProactiveSyncObservationsInput {
  sessionId: string;
  agentId: string;
  ownerId: string;
}

export interface ProactiveSyncObservationsResult {
  synced_count: number;
  unread_conversations: { conversation_id: string; title: string; count: number }[];
}

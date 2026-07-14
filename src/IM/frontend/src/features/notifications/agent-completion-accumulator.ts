import type { UserStreamEvent } from "../../realtime/user-stream";

const STORAGE_PREFIX = "im.agent-completion.pending.v1";
const PREVIEW_MAX = 140;

export interface PendingAgentCompletion {
  conversationId: string;
  senderUserId: string;
  senderName: string;
  createdAt?: string;
}

export interface AgentCompletionState {
  pendingByMessageId: Record<string, PendingAgentCompletion>;
}

export interface AgentCompletionCandidate extends PendingAgentCompletion {
  messageKey: string;
  messageId: string;
  preview: string;
}

export interface AgentCompletionReduction {
  state: AgentCompletionState;
  candidate: AgentCompletionCandidate | null;
}

export interface NotificationStateStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): unknown;
  removeItem(key: string): unknown;
}

export const emptyAgentCompletionState: AgentCompletionState = { pendingByMessageId: {} };

function text(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

function senderName(payload: Record<string, unknown>, senderUserId: string): string {
  return text(payload.sender_display_name)
    ?? text(payload.sender_name)
    ?? text(payload.display_name)
    ?? text(payload.agent_display_name)
    ?? text(payload.agent_id)
    ?? senderUserId;
}

function truncatePreview(value: string): string {
  return value.length <= PREVIEW_MAX ? value : `${value.slice(0, PREVIEW_MAX - 1)}…`;
}

function withoutPending(state: AgentCompletionState, messageId: string): AgentCompletionState {
  if (!(messageId in state.pendingByMessageId)) return state;
  const pendingByMessageId = { ...state.pendingByMessageId };
  delete pendingByMessageId[messageId];
  return { pendingByMessageId };
}

/** Reduce the canonical agent-message lifecycle into one notification candidate. */
export function reduceAgentCompletionEvent(
  state: AgentCompletionState,
  event: UserStreamEvent
): AgentCompletionReduction {
  const payload = event.payload;
  const messageId = text(payload.message_id);
  if (!messageId) return { state, candidate: null };

  if (event.eventType === "message.created") {
    const conversationId = text(payload.conversation_id);
    const senderUserId = text(payload.sender_user_id);
    if (payload.sender_type !== "agent" || !conversationId || !senderUserId) {
      return { state, candidate: null };
    }
    return {
      state: {
        pendingByMessageId: {
          ...state.pendingByMessageId,
          [messageId]: {
            conversationId,
            senderUserId,
            senderName: senderName(payload, senderUserId),
            ...(text(payload.created_at) ? { createdAt: text(payload.created_at)! } : {})
          }
        }
      },
      candidate: null
    };
  }

  if (event.eventType === "message.discarded") {
    return { state: withoutPending(state, messageId), candidate: null };
  }

  // relay.completed is a transport receipt. Canonical message.completed owns
  // the user-facing Agent reply reminder identity.
  if (event.eventType !== "message.completed") return { state, candidate: null };
  const pending = state.pendingByMessageId[messageId];
  const preview = text(payload.content);
  const nextState = withoutPending(state, messageId);
  if (!pending || !preview) return { state: nextState, candidate: null };
  return {
    state: nextState,
    candidate: {
      ...pending,
      messageKey: `message:${messageId}`,
      messageId,
      preview: truncatePreview(preview)
    }
  };
}

function storageKey(userId: string): string {
  return `${STORAGE_PREFIX}:${userId}`;
}

function defaultStorage(): NotificationStateStorage | null {
  try {
    return typeof sessionStorage === "undefined" ? null : sessionStorage;
  } catch {
    return null;
  }
}

function isPending(value: unknown): value is PendingAgentCompletion {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return Boolean(text(record.conversationId) && text(record.senderUserId) && text(record.senderName))
    && (record.createdAt === undefined || text(record.createdAt) !== null);
}

/** Hydrate only pending sender identity; completed/history events are never persisted. */
export function hydrateAgentCompletionState(
  userId: string | null,
  storage: NotificationStateStorage | null = defaultStorage()
): AgentCompletionState {
  if (!userId || !storage) return emptyAgentCompletionState;
  try {
    const raw = storage.getItem(storageKey(userId));
    if (!raw) return emptyAgentCompletionState;
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return emptyAgentCompletionState;
    const pendingByMessageId: Record<string, PendingAgentCompletion> = {};
    for (const [messageId, pending] of Object.entries(parsed as Record<string, unknown>)) {
      if (text(messageId) && isPending(pending)) pendingByMessageId[messageId] = pending;
    }
    return { pendingByMessageId };
  } catch {
    return emptyAgentCompletionState;
  }
}

export function persistAgentCompletionState(
  userId: string | null,
  state: AgentCompletionState,
  storage: NotificationStateStorage | null = defaultStorage()
): void {
  if (!userId || !storage) return;
  try {
    if (Object.keys(state.pendingByMessageId).length === 0) {
      storage.removeItem(storageKey(userId));
    } else {
      storage.setItem(storageKey(userId), JSON.stringify(state.pendingByMessageId));
    }
  } catch {
    // Notifications are best effort; blocked storage must not interrupt user stream dispatch.
  }
}

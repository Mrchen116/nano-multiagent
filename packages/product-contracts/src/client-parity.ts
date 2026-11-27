/** Cross-platform client parity contracts, notification hints, and deterministic view reducers. */

import {
  AGENT_LIFECYCLE_DESIRED_STATES,
  AGENT_LIFECYCLE_OBSERVED_STATES,
} from './agent-lifecycle.js';
import { MESSAGE_RECEIPT_STATUSES } from './chat.js';
import { COLLABORATION_SCOPES } from './collaboration.js';
import { TASK_MODES, TASK_STATUSES } from './task-graphs.js';
import { workerRuntimes } from './worker-runtimes.js';

export const USER_NOTIFICATION_KINDS = [
  'human_message',
  'mention',
  'message_completed',
  'chat_permission',
  'work_permission',
] as const;
export type UserNotificationKind = (typeof USER_NOTIFICATION_KINDS)[number];

export interface ClientContractEnumSpec {
  readonly name: string;
  readonly doc: string;
  readonly values: readonly string[];
}

/** Canonical registry driving Swift and Rust client enum generation. */
export const CLIENT_CONTRACT_ENUM_SPECS: readonly ClientContractEnumSpec[] = [
  {
    name: 'TaskModeContract',
    doc: 'Supported task container execution modes.',
    values: TASK_MODES,
  },
  {
    name: 'TaskStatusContract',
    doc: 'Nine canonical progressive task-graph node statuses.',
    values: TASK_STATUSES,
  },
  {
    name: 'AgentLifecycleDesiredContract',
    doc: 'Persistent human lifecycle intent for an Agent.',
    values: AGENT_LIFECYCLE_DESIRED_STATES,
  },
  {
    name: 'AgentLifecycleObservedContract',
    doc: 'Node-confirmed execution lifecycle state for an Agent.',
    values: AGENT_LIFECYCLE_OBSERVED_STATES,
  },
  {
    name: 'CollaborationScopeContract',
    doc: 'Visibility and communication boundary for an Agent or PA.',
    values: COLLABORATION_SCOPES,
  },
  {
    name: 'WorkerRuntimeContract',
    doc: 'Supported first-level delegated worker runtimes.',
    values: workerRuntimes,
  },
  {
    name: 'MessageReceiptStatusContract',
    doc: 'Confirmed per-recipient message delivery/read progress.',
    values: MESSAGE_RECEIPT_STATUSES,
  },
  {
    name: 'UserNotificationKindContract',
    doc: 'Unified cross-client notification categories on /im/ws/user.',
    values: USER_NOTIFICATION_KINDS,
  },
] as const;

/** Server-projected per-recipient notification directive attached to terminal/actionable user-stream frames. */
export interface UserStreamNotificationHint {
  eligible: boolean;
  replayed?: true;
  kind?: UserNotificationKind;
  dedupe_key: string;
  is_muted: boolean;
  mentions_viewer: boolean;
  conversation_id?: string;
  conversation_type?: 'direct' | 'group';
  conversation_title?: string;
  conversation_unread?: number;
  thread_root_message_id?: string;
  agent_id?: string;
  sender_name?: string;
  preview_text?: string;
  has_interactive_card?: boolean;
  attachment_name?: string;
  tool_name?: string;
  target_route: string;
}

export interface UnreadBadgeConversationInput {
  id: string;
  unread_count?: number | null;
  is_muted?: boolean | null;
  local_unseen?: boolean | null;
}

/** Compute the unread count shown on an individual conversation row (retains muted conversation counts).
 *
 * Args:
 *   conversation: Conversation summary with optional local unseen flag.
 * Returns:
 *   Non-negative integer unread count for that single row.
 */
export function computeConversationRowUnread(conversation: UnreadBadgeConversationInput): number {
  const raw = typeof conversation.unread_count === 'number' && Number.isFinite(conversation.unread_count)
    ? Math.max(0, Math.trunc(conversation.unread_count))
    : 0;
  return conversation.local_unseen ? Math.max(1, raw) : raw;
}

/** Compute the global app/navigation unread badge total (excludes muted conversations).
 *
 * Args:
 *   conversations: Visible conversation summaries for the current account.
 * Returns:
 *   Sum of unread counts across non-muted conversations only.
 */
export function computeUnreadBadgeTotal(conversations: readonly UnreadBadgeConversationInput[]): number {
  let total = 0;
  for (const item of conversations) {
    if (item.is_muted) continue;
    total += computeConversationRowUnread(item);
  }
  return total;
}

export interface TimelineDividerCandidate {
  type: string;
  id: string;
  created_at?: string | null;
  has_system_notice?: boolean;
}

const FIVE_MINUTES_MS = 300_000;
const dayFormatterCache = new Map<string, Intl.DateTimeFormat>();

function getDayFormatter(timeZone?: string): Intl.DateTimeFormat {
  const key = timeZone ?? '__local__';
  let formatter = dayFormatterCache.get(key);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat('en-CA', {
      ...(timeZone ? { timeZone } : {}),
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
    dayFormatterCache.set(key, formatter);
  }
  return formatter;
}

/** Compute message IDs that require a centered date/time divider across Web, Desktop, and iOS.
 *
 * System notices and configuration boundary items are skipped without resetting the elapsed-time
 * anchor between surrounding ordinary messages.
 *
 * Args:
 *   items: Ordered timeline entries.
 *   timeZone: Optional IANA timezone identifier; defaults to the host runtime local timezone.
 * Returns:
 *   Ordered list of message IDs that start a new time/date group.
 */
export function timelineDividerMessageIds(
  items: readonly TimelineDividerCandidate[],
  timeZone?: string,
): string[] {
  const formatter = getDayFormatter(timeZone);
  const result: string[] = [];
  let prevMs: number | undefined;
  let prevDayKey: string | undefined;

  for (const item of items) {
    if (item.type !== 'message' || item.has_system_notice || !item.created_at) continue;
    const ms = Date.parse(item.created_at);
    if (Number.isNaN(ms)) continue;
    const dayKey = formatter.format(new Date(ms));
    if (prevMs === undefined || dayKey !== prevDayKey || ms - prevMs >= FIVE_MINUTES_MS) {
      result.push(item.id);
    }
    prevMs = ms;
    prevDayKey = dayKey;
  }
  return result;
}

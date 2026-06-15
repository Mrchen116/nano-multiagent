// New chat data contracts (M4 rewrite).
//
// These types model the wire shape returned by the IM HTTP API + the WS event
// payloads emitted by `IM.api.ws.event_types`. They are intentionally narrow:
// only fields the chat UI actually consumes are declared, so the compiler
// catches drift if the backend renames a field we depend on.

export type ConversationKind =
  | "direct-agent"
  | "direct-user"
  | "group"
  | "agent-network";

export type DeliveryStatus = "sent" | "running" | "completed" | "failed";

export type ToolCallStatus = "running" | "completed" | "failed";

export interface Actor {
  type: "user" | "agent" | "system";
  id: string;
  display_name?: string | null;
  is_stale?: boolean | null;
}

export interface Attachment {
  url: string;
  content_type?: string | null;
  file_name?: string | null;
}

// bugfix-410-M2 (#97): sidecar badge classification of a non-success terminal,
// kept separate from `status`. denied→已拒绝 / timed_out→执行超时 / interrupted→已中断.
export type ToolCallReason = "denied" | "timed_out" | "interrupted";

export interface ToolCall {
  id: string;
  name: string;
  status: ToolCallStatus;
  input: unknown;
  duration_ms?: number;
  output?: string;
  reason?: ToolCallReason | string;
}

export interface TokenUsage {
  output: number;
  context_used: number;
  context_window: number;
  /** Per-turn prompt+completion sum (M17/R8-3); optional for back-compat with rows persisted before M17. */
  total?: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender: Actor;
  sender_user_id: string;
  sender_type: string;
  content: string;
  attachments: Attachment[];
  delivery_status: DeliveryStatus;
  created_at: string;
  tool_calls?: ToolCall[];
  token_usage?: TokenUsage | null;
  /**
   * bugfix-367: 同一 message 上所有 ask 按时间顺序保留 (允许 / 拒绝 / 当前 pending)。
   * 渲染时按 `request_id` 做 React key,新请求自然 mount 成新卡,旧 resolved 卡
   * 保留在原位 —— 用户能回看"按了多少次同意"。
   */
  permission_requests: PermissionRequest[];
}

export interface Conversation {
  id: string;
  title: string;
  participants: Actor[];
  participant_ids: string[];
  type: string;
  direct_kind: string | null;
  owner_id: string;
  creator_id: string;
  is_pinned: boolean;
  is_muted: boolean;
  unread_count: number;
  last_message_preview: string | null;
  last_message_at: string | null;
  created_at: string;
}

/**
 * Derived "kind" used purely for UI categorisation + badges. The backend stores
 * `type` ("direct"/"group") + `direct_kind` ("agent"/"user"); we collapse those
 * two fields into one tag because the chat list filter tabs and KindBadge work
 * off a single classification.
 */
export function classifyConversationKind(c: Pick<Conversation, "type" | "direct_kind" | "participants">): ConversationKind {
  if (c.type === "direct") {
    if (c.direct_kind === "user-user" || c.direct_kind === "user") return "direct-user";
    return "direct-agent";
  }
  if (c.type === "group") {
    // Agent-network = group of only agents (no human user). Used for visualizing
    // agent ↔ agent collaborations (spec scenario A's "Deploy: agent network").
    const onlyAgents = c.participants.length > 0 && c.participants.every((p) => p.type === "agent");
    return onlyAgents ? "agent-network" : "group";
  }
  return "group";
}

// ─── WebSocket event envelopes ───────────────────────────────────────────────
//
// Mirror the wire-level constants from `IM/api/ws/event_types.py`. The producer
// already serializes `seq` (per design §4) at the dispatch layer, so we accept
// it as optional here — useful when reducing but never required to parse.

export type WsEvent =
  | { type: "message.created"; seq?: number; conversation_id: string; message_id: string; sender_user_id: string; sender_type: string; content: string; tool_calls: ToolCall[]; token_usage: TokenUsage | null; delivery_status: DeliveryStatus; created_at: string }
  | { type: "message.delta"; seq?: number; conversation_id: string; message_id: string; delta_text: string }
  | { type: "message.completed"; seq?: number; conversation_id: string; message_id: string; content: string; token_usage: TokenUsage | null }
  | { type: "tool_call.upserted"; seq?: number; conversation_id: string; message_id: string; tool_call: ToolCall }
  | { type: "tool_call.completed"; seq?: number; conversation_id: string; message_id: string; tool_call: ToolCall }
  // bugfix-367 (updated from feat-333-M3/R1): permission ask flow. Backend emits
  // these when auto_mode_gate triggers an `ask` decision; the frontend reducer
  // appends `permission_request` to `message.permission_requests`(按 request_id
  // dedup);`permission.resolved` 按 request_id 在 list 中定位、就地改 status。
  // 每次 WS event 仍只承载一条,载荷形状不变。
  | { type: "permission.request"; seq?: number; conversation_id: string; message_id: string; permission_request: PermissionRequest }
  | { type: "permission.resolved"; seq?: number; conversation_id: string; message_id: string; request_id: string; decision: string };

export interface MentionCandidate {
  agent_id: string;
  display_name: string;
  initials: string;
  status: "online" | "offline";
}

// ─── Permission request types (auto_mode_gate ask flow) ──────────────────────
//
// Mirrors the PermissionRequest / PermissionOption structures from
// `agent/platform/permissions/broker.py`. The frontend only needs the subset
// that drives the inline permission card UI.

export interface PermissionOption {
  id: string;
  label: string;
  description: string;
}

export interface PermissionRequest {
  request_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  question: string;
  options: PermissionOption[];
  /** "pending" until the user has responded; "resolved" once a decision is recorded. */
  status: "pending" | "resolved";
  /** Populated when status === "resolved" (from permission_resolved WS event). */
  decision?: string;
}

/** The Message type extended with the list of embedded permission requests. */
export interface MessagePermissionData {
  permission_requests: PermissionRequest[];
}

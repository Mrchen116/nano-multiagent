// Pure reducer mapping IM WS events to a conversation's in-memory message list.
//
// Why a pure reducer (vs. patching React Query cache directly): the chat
// workspace needs to compose live deltas with the historical paginated load,
// and exposing a side-effect-free function makes it trivial to unit-test each
// of the five WS event types in isolation. The workspace then applies the
// reducer to the active conversation cache slice. A reducer-shaped contract
// also makes it cheap to add `sync` replay later (decision §3) by treating the
// /im/v1/sync response as a sequence of synthetic events.

import type { Message, ToolCall, WsEvent } from "./chat-types";

export interface ConversationState {
  conversation_id: string | null;
  messages: Message[];
}

export const emptyConversationState: ConversationState = {
  conversation_id: null,
  messages: []
};

/**
 * Compare two messages by created_at ascending, with message id as a tie-break
 * for deterministic ordering when timestamps are equal (e.g. optimistic insert
 * races a WS echo with the same second). Mirrors the compareMessageRecency
 * semantics used in im-chat-api.ts for conversation previews.
 *
 * Exported so streamReducer (chat-workspace-page.tsx) can apply the same
 * ordering to reset and append_optimistic paths — all three insertion paths
 * share one ordering invariant (bugfix-419).
 */
export function compareMessages(a: Message, b: Message): number {
  // Messages lacking created_at sort to the end rather than crashing.
  const ta = Date.parse(a.created_at ?? "");
  const tb = Date.parse(b.created_at ?? "");
  const aHas = Number.isFinite(ta);
  const bHas = Number.isFinite(tb);
  if (aHas && bHas && ta !== tb) return ta - tb;
  if (aHas !== bHas) return aHas ? -1 : 1;
  return a.id.localeCompare(b.id);
}

function patchMessage(
  state: ConversationState,
  messageId: string,
  patch: (m: Message) => Message
): ConversationState {
  let changed = false;
  const messages = state.messages.map((m) => {
    if (m.id !== messageId) return m;
    changed = true;
    return patch(m);
  });
  if (!changed) return state;
  return { ...state, messages };
}

function isEmptyValue(v: unknown): boolean {
  // Only called on ToolCall.input (a record) and .output (a string), so an empty
  // object is the meaningful "empty" case beyond undefined/null/"".
  if (v === undefined || v === null || v === "") return true;
  if (typeof v === "object") return Object.keys(v as object).length === 0;
  return false;
}

function mergeToolCall(prev: ToolCall, next: ToolCall): ToolCall {
  // bugfix-416 #111: a later event (e.g. a timed-out tool's reconcile) may carry
  // fewer fields than the upsert. A naive {...prev, ...next} lets an empty
  // input/output clobber the real command/description shown at tool_start. Keep the
  // existing non-empty value whenever the incoming field is empty.
  const merged = { ...prev, ...next };
  if (isEmptyValue(next.input) && !isEmptyValue(prev.input)) merged.input = prev.input;
  if (isEmptyValue(next.output) && !isEmptyValue(prev.output)) merged.output = prev.output;
  return merged;
}

function upsertToolCall(message: Message, next: ToolCall): Message {
  const current = message.tool_calls ?? [];
  const idx = current.findIndex((t) => t.id === next.id);
  const merged = idx >= 0 ? current.map((t, i) => (i === idx ? mergeToolCall(t, next) : t)) : [...current, next];
  return { ...message, tool_calls: merged };
}

export function applyWsEvent(
  state: ConversationState,
  ev: WsEvent,
  opts?: { sendersById?: Record<string, string | undefined> }
): ConversationState {
  // Reducer is scoped to one conversation at a time; events for a different
  // conversation_id bypass entirely so the active view never gets contaminated.
  if (state.conversation_id !== null && ev.conversation_id !== state.conversation_id) {
    return state;
  }

  switch (ev.type) {
    case "message.created": {
      // M17/R8-1 defensive: synthetic relay-mirror ids must never enter the
      // workspace cache as standalone bubbles (backend dedup is the primary
      // defence, this is the belt-and-braces frontend filter).
      if (ev.message_id.includes(":relay:")) return state;
      // Backend echoes the user's own POST through the WS feed; dedupe so the
      // optimistic insert (from createMessage) doesn't get doubled.
      if (state.messages.some((m) => m.id === ev.message_id)) return state;
      // M17/R8-2: WS payload only carries sender_user_id (UUID). The workspace
      // passes the agents-by-user-id map so the bubble can show the right
      // display_name immediately, instead of rendering the raw UUID until the
      // next history refetch.
      const resolvedDisplayName =
        ev.sender?.display_name ??
        ev.sender_display_name ??
        opts?.sendersById?.[ev.sender_user_id] ??
        null;
      const senderId = ev.sender?.id ?? ev.sender_user_id.replace(/^(agent|user):/, "");
      const created: Message = {
        id: ev.message_id,
        conversation_id: ev.conversation_id,
        sender: {
          type: ev.sender_type === "agent" ? "agent" : ev.sender_type === "system" ? "system" : "user",
          id: senderId,
          display_name: resolvedDisplayName
        },
        sender_user_id: ev.sender_user_id,
        sender_type: ev.sender_type,
        content: ev.content,
        attachments: ev.attachments ?? [],
        delivery_status: ev.delivery_status,
        created_at: ev.created_at,
        tool_calls: ev.tool_calls,
        // feat-439-M2: 历史回放 / 建泡时还原已持久化的思考过程项。
        thinking: ev.thinking,
        token_usage: ev.token_usage,
        permission_requests: []
      };
      // bugfix-419: sort by created_at so WS arrival order does not dictate
      // render order. The tie-break on id makes ordering deterministic when two
      // messages share the same timestamp (e.g. optimistic insert + WS echo).
      return { ...state, messages: [...state.messages, created].sort(compareMessages) };
    }
    case "message.delta": {
      return patchMessage(state, ev.message_id, (m) => ({ ...m, content: m.content + ev.delta_text }));
    }
    case "message.completed": {
      return patchMessage(state, ev.message_id, (m) => ({
        ...m,
        content: ev.content,
        delivery_status: "completed",
        token_usage: ev.token_usage,
        // feat-414: 权威耗时来自后端，覆盖前端本地 tick。
        elapsed_ms: ev.elapsed_ms,
        // feat-445-M1: a live-completed agent bubble becomes forkable immediately
        // (no refetch) once its kernel message id arrives on the completed event.
        kernel_message_id: ev.kernel_message_id ?? m.kernel_message_id,
      }));
    }
    case "tool_call.upserted":
    case "tool_call.completed": {
      return patchMessage(state, ev.message_id, (m) => upsertToolCall(m, ev.tool_call));
    }
    // feat-439-M2: 追加一段思考过程项。seq 是后端赋予的 per-message 单调唯一序号；
    // 按 seq 去重(幂等)——reducer 契约会重放/双投递事件，正如 tool_calls 按 id 幂等。
    // 渲染端按 seq 把思考与工具 merge 成一条过程时间线。
    case "thinking.segment": {
      return patchMessage(state, ev.message_id, (m) => {
        const current = m.thinking ?? [];
        if (current.some((s) => s.seq === ev.thinking_segment.seq)) return m;
        return { ...m, thinking: [...current, ev.thinking_segment] };
      });
    }
    // bugfix-367: 同一 message 上多次 ask 现按 list 累积。同 request_id 二次
    // 写入视为 idempotent 替换;新 request_id 追加。resolved 按 request_id 在
    // list 中定位、就地改 status/decision —— 不再覆盖整列(覆盖会丢失同泡其他
    // 历史 ask)。
    case "permission.request": {
      return patchMessage(state, ev.message_id, (m) => {
        const current = m.permission_requests ?? [];
        const idx = current.findIndex((r) => r.request_id === ev.permission_request.request_id);
        const next = idx >= 0
          ? current.map((r, i) => (i === idx ? ev.permission_request : r))
          : [...current, ev.permission_request];
        return { ...m, permission_requests: next };
      });
    }
    case "permission.resolved": {
      return patchMessage(state, ev.message_id, (m) => {
        const current = m.permission_requests ?? [];
        const idx = current.findIndex((r) => r.request_id === ev.request_id);
        if (idx < 0) return m;
        const updated = {
          ...current[idx]!,
          status: "resolved" as const,
          decision: ev.decision
        };
        const next = current.map((r, i) => (i === idx ? updated : r));
        return { ...m, permission_requests: next };
      });
    }
    default:
      return state;
  }
}

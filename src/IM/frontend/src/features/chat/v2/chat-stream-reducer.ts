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

function upsertToolCall(message: Message, next: ToolCall): Message {
  const current = message.tool_calls ?? [];
  const idx = current.findIndex((t) => t.id === next.id);
  const merged = idx >= 0 ? current.map((t, i) => (i === idx ? { ...t, ...next } : t)) : [...current, next];
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
      const resolvedDisplayName = opts?.sendersById?.[ev.sender_user_id] ?? null;
      const created: Message = {
        id: ev.message_id,
        conversation_id: ev.conversation_id,
        sender: {
          type: ev.sender_type === "agent" ? "agent" : ev.sender_type === "system" ? "system" : "user",
          id: ev.sender_user_id.replace(/^(agent|user):/, ""),
          display_name: resolvedDisplayName
        },
        sender_user_id: ev.sender_user_id,
        sender_type: ev.sender_type,
        content: ev.content,
        attachments: [],
        delivery_status: ev.delivery_status,
        created_at: ev.created_at,
        tool_calls: ev.tool_calls,
        token_usage: ev.token_usage
      };
      return { ...state, messages: [...state.messages, created] };
    }
    case "message.delta": {
      return patchMessage(state, ev.message_id, (m) => ({ ...m, content: m.content + ev.delta_text }));
    }
    case "message.completed": {
      return patchMessage(state, ev.message_id, (m) => ({
        ...m,
        content: ev.content,
        delivery_status: "completed",
        token_usage: ev.token_usage
      }));
    }
    case "tool_call.upserted":
    case "tool_call.completed": {
      return patchMessage(state, ev.message_id, (m) => upsertToolCall(m, ev.tool_call));
    }
    default:
      return state;
  }
}

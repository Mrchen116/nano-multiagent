// Minimal REST client for the chat surface.
//
// Why a fresh client rather than reusing `im-chat-api.ts`:
// - The legacy file (~2k lines) bundles auth-less fetch helpers, mock fall-backs,
//   binding tokens, and bootstrap snapshots — concepts we have outgrown after
//   M1/M2 (Bearer auth + WS schema). Keeping the v2 surface narrow lets the
//   chat-workspace consume exactly the contract M1/M2 declared and nothing else.
// - All calls go through `authFetch` so 401 → refresh → retry happens once
//   transparently per request (M3 guarantee).

import { authFetch } from "../../auth/auth-fetch";
import { useAuthStore } from "../../auth/auth-store";
import type {
  Actor,
  Attachment,
  Conversation,
  MentionCandidate,
  Message
} from "./chat-types";

async function jsonOrThrow<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${label} failed: ${res.status} ${body}`);
  }
  return (await res.json()) as T;
}

export async function listConversations(): Promise<Conversation[]> {
  const res = await authFetch("/im/v1/conversations");
  const payload = await jsonOrThrow<{ items: Conversation[] }>(res, "listConversations");
  return payload.items;
}

export interface ListMessagesOptions {
  limit?: number;
  beforeMessageId?: string;
  markAsRead?: boolean;
}

export interface ListMessagesResult {
  items: Message[];
  next_before_message_id: string | null;
}

export async function listMessages(
  conversationId: string,
  opts: ListMessagesOptions = {}
): Promise<ListMessagesResult> {
  const params = new URLSearchParams();
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.beforeMessageId) params.set("before_message_id", opts.beforeMessageId);
  if (opts.markAsRead) params.set("mark_as_read", "true");
  const qs = params.toString();
  const url = `/im/v1/conversations/${encodeURIComponent(conversationId)}/messages${qs ? `?${qs}` : ""}`;
  const res = await authFetch(url);
  return jsonOrThrow<ListMessagesResult>(res, "listMessages");
}

export interface CreateMessageRequest {
  conversationId: string;
  content: string;
  attachments?: Attachment[];
}

function requireSelfUser(): { id: string } {
  const user = useAuthStore.getState().user;
  if (!user) throw new Error("createMessage: not authenticated");
  return { id: user.id };
}

export async function createMessage(req: CreateMessageRequest): Promise<Message> {
  const self = requireSelfUser();
  const body = {
    sender: { type: "user", id: self.id } as Actor,
    content: req.content,
    attachments: req.attachments ?? []
  };
  const res = await authFetch(`/im/v1/conversations/${encodeURIComponent(req.conversationId)}/messages`, {
    method: "POST",
    body: JSON.stringify(body)
  });
  return jsonOrThrow<Message>(res, "createMessage");
}

export interface CreateConversationRequest {
  title: string;
  /** Agent IDs to include alongside the current user. */
  agentIds: string[];
}

export async function createConversation(req: CreateConversationRequest): Promise<Conversation> {
  const self = requireSelfUser();
  const participants: Actor[] = [
    { type: "user", id: self.id },
    ...req.agentIds.map((id): Actor => ({ type: "agent", id }))
  ];
  const res = await authFetch("/im/v1/conversations", {
    method: "POST",
    body: JSON.stringify({ title: req.title, participants })
  });
  return jsonOrThrow<Conversation>(res, "createConversation");
}

/**
 * Mention candidates = the agents that participate in this conversation (per
 * spec Q8: candidates only come from the current user's own agents and the
 * conversation already restricts to those). The agent list endpoint returns
 * every agent the user owns; we intersect with the conversation participants
 * so the picker shows exactly the agents the message can actually mention.
 */
export interface AgentRow {
  agent_id: string;
  display_name: string;
  node_id?: string;
  description?: string;
  /** IM user UUID for ``agent:<agent_id>`` — used to map WS sender_user_id → display_name. */
  user_id?: string | null;
}

function initialsFrom(name: string): string {
  const cleaned = name.trim();
  if (!cleaned) return "?";
  const parts = cleaned.split(/\s+/);
  if (parts.length >= 2) return (parts[0]!.charAt(0) + parts[1]!.charAt(0)).toUpperCase();
  return cleaned.slice(0, 2).toUpperCase();
}

export async function listMentionCandidates(opts: {
  conversation: { participants: { type: string; id: string; is_stale?: boolean | null }[] };
}): Promise<MentionCandidate[]> {
  const res = await authFetch("/im/v1/agents");
  const rows = await jsonOrThrow<AgentRow[]>(res, "listMentionCandidates");
  const allowed = new Set(
    opts.conversation.participants
      .filter((p) => p.type === "agent" && !p.is_stale)
      .map((p) => p.id.replace(/^agent:/, ""))
  );
  return rows
    .filter((r) => allowed.has(r.agent_id.replace(/^agent:/, "")))
    .map((r) => ({
      agent_id: r.agent_id,
      display_name: r.display_name,
      initials: initialsFrom(r.display_name),
      // Backend agent list does not yet carry online/offline; surface "offline"
      // by default and let WS `agent.status_changed` patch it in once live.
      status: "offline" as const
    }));
}

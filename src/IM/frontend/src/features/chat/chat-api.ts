// Canonical REST client for the Chat surface. All calls share authFetch so
// token refresh and retry semantics stay owned by the auth transport.

import { authFetch, authFetchJson } from "../auth/auth-fetch";
import { useAuthStore } from "../auth/auth-store";
import type {
  Actor,
  Attachment,
  Conversation,
  Message,
  TimelineItem
} from "./chat-types";

export async function listConversations(): Promise<Conversation[]> {
  const payload = await authFetchJson<{ items: Conversation[] }>(
    "/im/v1/conversations",
    undefined,
    "listConversations"
  );
  return payload.items;
}

export interface ListMessagesOptions {
  limit?: number;
  beforeMessageId?: string;
  markAsRead?: boolean;
}

export interface ListMessagesResult {
  items: TimelineItem[];
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
  const response = await authFetchJson<{ items: Array<TimelineItem | Message>; next_before_message_id: string | null }>(
    url,
    undefined,
    "listMessages"
  );
  // During rolling deploys a stale IM can still return the former bare-message
  // page. Normalize at the API seam so the workspace remains a typed consumer.
  return {
    ...response,
    items: response.items.map((item) => "type" in item ? item : { type: "message", message: item })
  };
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
  return authFetchJson<Message>(
    `/im/v1/conversations/${encodeURIComponent(req.conversationId)}/messages`,
    { method: "POST", body: JSON.stringify(body) },
    "createMessage"
  );
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
  return authFetchJson<Conversation>(
    "/im/v1/conversations",
    { method: "POST", body: JSON.stringify({ title: req.title, participants }) },
    "createConversation"
  );
}

export interface CreateDistillPromptRequest {
  sources: Array<{ conversationId: string; sourceAgentId: string }>;
  executionAgentId: string;
  targetScope: "agent" | "global";
}

export interface CreateDistillPromptResult {
  conversation: Conversation;
  prompt: string;
}

/** Request a Gateway-produced draft and its same-Gateway execution chat. */
export async function createDistillPrompt(
  req: CreateDistillPromptRequest,
): Promise<CreateDistillPromptResult> {
  return authFetchJson<CreateDistillPromptResult>(
    "/im/v1/conversations/distill-prompt",
    {
      method: "POST",
      body: JSON.stringify({
        sources: req.sources.map((source) => ({
          conversation_id: source.conversationId,
          source_agent_id: source.sourceAgentId,
        })),
        execution_agent_id: req.executionAgentId,
        target_scope: req.targetScope,
      }),
    },
    "createDistillPrompt",
  );
}

/**
 * feat-445-M1: fork a direct agent chat at one completed agent reply. Returns the new
 * branch conversation (same agent, history copied through the fork point). Throws on
 * non-ok (e.g. 409 agent offline, 502 fork delegation failure) so callers surface it.
 */
export async function forkConversation(
  conversationId: string,
  forkMessageId: string
): Promise<Conversation> {
  return authFetchJson<Conversation>(
    `/im/v1/conversations/${encodeURIComponent(conversationId)}/fork`,
    { method: "POST", body: JSON.stringify({ fork_message_id: forkMessageId }) },
    "forkConversation"
  );
}

// ─── Group settings (feat-438): rename / add / remove / dissolve ─────────────

/** Update mutable conversation metadata (currently just the group title). */
export async function updateConversation(
  conversationId: string,
  patch: { title: string }
): Promise<Conversation> {
  return authFetchJson<Conversation>(
    `/im/v1/conversations/${encodeURIComponent(conversationId)}`,
    { method: "PATCH", body: JSON.stringify(patch) },
    "updateConversation"
  );
}

/** Add agent participants to an existing group; returns the refreshed snapshot. */
export async function addParticipants(
  conversationId: string,
  agentIds: string[]
): Promise<Conversation> {
  const participants: Actor[] = agentIds.map((id): Actor => ({ type: "agent", id }));
  return authFetchJson<Conversation>(
    `/im/v1/conversations/${encodeURIComponent(conversationId)}/participants`,
    { method: "POST", body: JSON.stringify({ participants }) },
    "addParticipants"
  );
}

/**
 * Remove one participant from a group. ``userId`` MUST be the participant's
 * ``user_id`` (UUID) — for agents that is distinct from ``id`` (agent_id); the
 * backend keys the delete on conversation_participants.user_id (决策 5).
 */
export async function removeParticipant(
  conversationId: string,
  userId: string
): Promise<void> {
  const res = await authFetch(
    `/im/v1/conversations/${encodeURIComponent(conversationId)}/participants/${encodeURIComponent(userId)}`,
    { method: "DELETE" }
  );
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`removeParticipant failed: ${res.status} ${body}`);
  }
}

/** Dissolve a group conversation (creator only; backend enforces 403 otherwise). */
export async function deleteConversation(conversationId: string): Promise<void> {
  const res = await authFetch(`/im/v1/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE"
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`deleteConversation failed: ${res.status} ${body}`);
  }
}

/** Agent list row shared by the Chat workspace's authoritative agent snapshot. */
export interface AgentRow {
  agent_id: string;
  display_name: string;
  node_id?: string;
  description?: string;
  /** IM user UUID for ``agent:<agent_id>`` — used to map WS sender_user_id → display_name. */
  user_id?: string | null;
}

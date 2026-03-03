import { ChatMessage, ConversationDetail, ConversationSummary } from "./types";

interface ImUser {
  id: string;
  username: string;
  display_name: string;
}

interface ImConversation {
  id: string;
  title: string;
  participant_ids: string[];
}

interface ImMessage {
  id: string;
  conversation_id: string;
  sender_user_id: string;
  content: string;
  created_at: string;
}

interface ParsedPayload {
  [key: string]: unknown;
}

export interface ParsedImStreamEvent {
  eventType: string;
  payload: ParsedPayload;
  eventId?: number;
}

const SELF_USERNAME = "you";
const PEER_USERNAME = "peer";
const DEFAULT_CONVERSATION_TITLE = "You & Teammate";

let bootstrapPromise: Promise<{ selfUserId: string }> | null = null;

function getApiBaseUrl() {
  return (import.meta.env.VITE_IM_API_BASE_URL ?? "").replace(/\/$/, "");
}

function withBase(path: string) {
  return `${getApiBaseUrl()}${path}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(withBase(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function listUsersRaw() {
  return requestJson<ImUser[]>("/im/v1/users");
}

async function createUserRaw(payload: { username: string; display_name: string }) {
  return requestJson<ImUser>("/im/v1/users", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

async function listConversationsRaw() {
  return requestJson<ImConversation[]>("/im/v1/conversations");
}

async function createConversationRaw(payload: { title: string; participant_ids: string[] }) {
  return requestJson<ImConversation>("/im/v1/conversations", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

async function listMessagesRaw(conversationId: string) {
  return requestJson<ImMessage[]>(`/im/v1/conversations/${conversationId}/messages`);
}

async function ensureUser(username: string, displayName: string): Promise<ImUser> {
  const users = await listUsersRaw();
  const found = users.find((item) => item.username === username);
  if (found) {
    return found;
  }
  try {
    return await createUserRaw({ username, display_name: displayName });
  } catch {
    const refreshed = await listUsersRaw();
    const fallback = refreshed.find((item) => item.username === username);
    if (fallback) {
      return fallback;
    }
    throw new Error(`cannot ensure user ${username}`);
  }
}

async function ensureBootstrap() {
  if (!bootstrapPromise) {
    bootstrapPromise = (async () => {
      const self = await ensureUser(SELF_USERNAME, "You");
      const peer = await ensureUser(PEER_USERNAME, "Teammate");
      const conversations = await listConversationsRaw();
      if (conversations.length === 0) {
        await createConversationRaw({
          title: DEFAULT_CONVERSATION_TITLE,
          participant_ids: [self.id, peer.id]
        });
      }
      return { selfUserId: self.id };
    })();
  }
  return bootstrapPromise;
}

function toChatMessage(input: {
  message: ImMessage;
  userById: Map<string, ImUser>;
  selfUserId: string;
  defaultStatus: "sent" | "completed";
}): ChatMessage {
  const sender = input.userById.get(input.message.sender_user_id);
  const isMine = input.message.sender_user_id === input.selfUserId;
  return {
    message_id: input.message.id,
    sender_type: "user",
    sender_name: sender?.display_name ?? input.message.sender_user_id,
    is_mine: isMine,
    content: input.message.content,
    created_at: input.message.created_at,
    delivery_status: input.defaultStatus
  };
}

function toConversationSummary(input: {
  conversation: ImConversation;
  messages: ImMessage[];
  userById: Map<string, ImUser>;
  selfUserId: string;
}): ConversationSummary {
  const latest = input.messages.at(-1);
  const unreadCount = input.messages.filter((item) => item.sender_user_id !== input.selfUserId).length;
  return {
    conversation_id: input.conversation.id,
    title: input.conversation.title,
    last_message_preview: latest?.content ?? "",
    last_message_at: latest?.created_at,
    unread_count: unreadCount,
    participants: input.conversation.participant_ids.map(
      (participantId) => input.userById.get(participantId)?.display_name ?? participantId
    )
  };
}

async function loadUserMap() {
  const users = await listUsersRaw();
  return new Map(users.map((item) => [item.id, item]));
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const { selfUserId } = await ensureBootstrap();
  const [conversations, userById] = await Promise.all([listConversationsRaw(), loadUserMap()]);
  const messagesByConversation = await Promise.all(
    conversations.map(async (item) => ({
      conversation: item,
      messages: await listMessagesRaw(item.id)
    }))
  );
  return messagesByConversation
    .map((item) =>
      toConversationSummary({
        conversation: item.conversation,
        messages: item.messages,
        userById,
        selfUserId
      })
    )
    .sort((left, right) => (right.last_message_at ?? "").localeCompare(left.last_message_at ?? ""));
}

export async function getConversation(conversationId: string): Promise<ConversationDetail | null> {
  const { selfUserId } = await ensureBootstrap();
  const [conversations, userById, messages] = await Promise.all([
    listConversationsRaw(),
    loadUserMap(),
    listMessagesRaw(conversationId)
  ]);
  const conversation = conversations.find((item) => item.id === conversationId);
  if (!conversation) {
    return null;
  }
  return {
    conversation_id: conversation.id,
    title: conversation.title,
    messages: messages.map((message) =>
      toChatMessage({
        message,
        userById,
        selfUserId,
        defaultStatus: "completed"
      })
    )
  };
}

export async function sendMessage(input: { conversationId: string; content: string }): Promise<ChatMessage> {
  const { selfUserId } = await ensureBootstrap();
  const [created, userById] = await Promise.all([
    requestJson<ImMessage>(`/im/v1/conversations/${input.conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ sender_user_id: selfUserId, content: input.content })
    }),
    loadUserMap()
  ]);
  return toChatMessage({
    message: created,
    userById,
    selfUserId,
    defaultStatus: "sent"
  });
}

export function parseImStreamEvent(input: {
  eventType: string;
  data: string;
}): { eventType: string; payload: ParsedPayload } | null {
  try {
    const payload = JSON.parse(input.data) as ParsedPayload;
    return {
      eventType: input.eventType,
      payload
    };
  } catch {
    return null;
  }
}

export function streamConversationEvents(input: {
  conversationId: string;
  onEvent: (event: ParsedImStreamEvent) => void;
  onError?: (error: Error) => void;
}) {
  if (typeof window === "undefined" || typeof window.EventSource === "undefined") {
    return () => undefined;
  }

  const source = new window.EventSource(withBase(`/im/v1/conversations/${input.conversationId}/events`));
  const eventTypes = ["message_created", "text_delta", "turn_end", "message_status"];
  const listeners = eventTypes.map((eventType) => {
    const handler = (event: Event) => {
      const messageEvent = event as MessageEvent<string>;
      const parsed = parseImStreamEvent({ eventType, data: messageEvent.data });
      if (!parsed) {
        return;
      }
      const parsedEventId = Number(messageEvent.lastEventId);
      input.onEvent({
        ...parsed,
        eventId: Number.isFinite(parsedEventId) && parsedEventId > 0 ? parsedEventId : undefined
      });
    };
    source.addEventListener(eventType, handler);
    return { eventType, handler };
  });

  source.onerror = () => {
    input.onError?.(new Error("SSE connection failed"));
  };

  return () => {
    for (const item of listeners) {
      source.removeEventListener(item.eventType, item.handler);
    }
    source.close();
  };
}

import { ChatMessage, ChatStarter, ConversationDetail, ConversationSummary } from "./types";

interface ImUser {
  id: string;
  username: string;
  display_name: string;
  owned_node_ids?: string[];
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
  delivery_status?: string;
  created_at: string;
}

interface ImAgent {
  agent_id: string;
  display_name: string;
  description: string;
}

interface ImNode {
  node_id: string;
  node_name: string;
  status: string;
  relay_enabled: boolean;
}

interface BootstrapState {
  selfUserId: string;
  targetNodeId: string | null;
  starter: ChatStarter;
  starterConversationId: string | null;
}

interface ItemsEnvelope<T> {
  items: T[];
}

interface CreateMessagePayload {
  sender_user_id: string;
  content: string;
  target_node_id?: string;
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
const AGENT_USERNAME_PREFIX = "agent:";
const DEFAULT_AGENT_NAME = "OpsBot";
const DEFAULT_AGENT_DESCRIPTION = "OpsBot handles the default IM replies for this workspace.";

let bootstrapPromise: Promise<BootstrapState> | null = null;

function getApiBaseUrl() {
  return (import.meta.env.VITE_IM_API_BASE_URL ?? "").replace(/\/$/, "");
}

function withBase(path: string) {
  return `${getApiBaseUrl()}${path}`;
}

class ChatRequestError extends Error {
  status: number;
  detail: string;

  constructor(input: { status: number; detail: string; method: string; path: string }) {
    super(`${input.method} ${input.path} failed: ${input.status} (${input.detail})`);
    this.name = "ChatRequestError";
    this.status = input.status;
    this.detail = input.detail;
  }
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
    const method = init?.method ?? "GET";
    let detail = response.statusText || "request failed";
    const rawBody = await response.text();
    if (rawBody) {
      try {
        const parsed = JSON.parse(rawBody) as { detail?: string };
        detail = typeof parsed.detail === "string" && parsed.detail.length > 0 ? parsed.detail : rawBody;
      } catch {
        detail = rawBody;
      }
    }
    throw new ChatRequestError({ status: response.status, detail, method, path });
  }
  return (await response.json()) as T;
}

export function normalizeItemsEnvelope<T>(payload: ItemsEnvelope<T> | T[]): T[] {
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.items) ? payload.items : [];
}

export function pickPrimaryOwnedNodeId(user: { owned_node_ids?: string[] | null }): string | null {
  if (!Array.isArray(user.owned_node_ids) || user.owned_node_ids.length === 0) {
    return null;
  }
  return typeof user.owned_node_ids[0] === "string" && user.owned_node_ids[0].length > 0 ? user.owned_node_ids[0] : null;
}

export function pickDefaultNodeForSend(nodes: Array<Pick<ImNode, "node_id" | "status" | "relay_enabled" | "node_name">>) {
  return nodes.find((item) => item.relay_enabled && item.status === "online") ?? nodes.find((item) => item.relay_enabled) ?? null;
}

export function buildStarterConversationTitle(agentName: string): string {
  return `Agent · ${agentName}`;
}

export function buildCreateMessageRequest(input: {
  selfUserId: string;
  content: string;
  targetNodeId: string | null;
}): CreateMessagePayload {
  const payload: CreateMessagePayload = {
    sender_user_id: input.selfUserId,
    content: input.content
  };
  if (input.targetNodeId) {
    payload.target_node_id = input.targetNodeId;
  }
  return payload;
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
  const payload = await requestJson<ItemsEnvelope<ImConversation> | ImConversation[]>("/im/v1/conversations");
  return normalizeItemsEnvelope(payload);
}

async function listAgentsRaw() {
  return requestJson<ImAgent[]>("/im/v1/agents");
}

async function listNodesRaw() {
  return requestJson<ImNode[]>("/im/v1/nodes");
}

async function createConversationRaw(payload: { title: string; participant_ids: string[] }) {
  return requestJson<ImConversation>("/im/v1/conversations", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

async function listMessagesRaw(conversationId: string) {
  const payload = await requestJson<ItemsEnvelope<ImMessage> | ImMessage[]>(`/im/v1/conversations/${conversationId}/messages`);
  return normalizeItemsEnvelope(payload);
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

function pickStarterAgent(agents: ImAgent[]): ImAgent {
  return (
    agents.find((item) => item.display_name.trim().length > 0) ?? {
      agent_id: PEER_USERNAME,
      display_name: DEFAULT_AGENT_NAME,
      description: DEFAULT_AGENT_DESCRIPTION
    }
  );
}

function buildStarterDescription(agent: ImAgent): string {
  return agent.description.trim() || `${agent.display_name} handles the default IM replies for this workspace.`;
}

function resolveConversationTitle(input: { conversation: ImConversation; starterTitle: string }): string {
  const normalized = input.conversation.title.trim();
  if (!normalized || normalized === DEFAULT_CONVERSATION_TITLE) {
    return input.starterTitle;
  }
  return normalized;
}

function findStarterConversation(input: {
  conversations: ImConversation[];
  selfUserId: string;
  peerUserId: string;
  starterTitle: string;
}): ImConversation | null {
  return (
    input.conversations.find(
      (item) =>
        item.participant_ids.length === 2 &&
        item.participant_ids.includes(input.selfUserId) &&
        item.participant_ids.includes(input.peerUserId)
    ) ??
    input.conversations.find((item) => item.title === input.starterTitle) ??
    input.conversations[0] ??
    null
  );
}

async function ensureBootstrap() {
  if (!bootstrapPromise) {
    bootstrapPromise = (async () => {
      const [self, agents, nodes] = await Promise.all([ensureUser(SELF_USERNAME, "You"), listAgentsRaw(), listNodesRaw()]);
      const starterAgent = pickStarterAgent(agents);
      const starterPeer = await ensureUser(
        `${AGENT_USERNAME_PREFIX}${starterAgent.agent_id}`,
        starterAgent.display_name || DEFAULT_AGENT_NAME
      );
      const starterTitle = buildStarterConversationTitle(starterAgent.display_name || DEFAULT_AGENT_NAME);
      const existingConversations = await listConversationsRaw();
      const starterConversation =
        findStarterConversation({
          conversations: existingConversations,
          selfUserId: self.id,
          peerUserId: starterPeer.id,
          starterTitle
        }) ??
        (await createConversationRaw({
          title: starterTitle,
          participant_ids: [self.id, starterPeer.id]
        }));
      const targetNode = pickDefaultNodeForSend(nodes) ??
        (pickPrimaryOwnedNodeId(self)
          ? {
              node_id: pickPrimaryOwnedNodeId(self)!,
              node_name: pickPrimaryOwnedNodeId(self)!,
              status: "unknown",
              relay_enabled: true
            }
          : null);
      return {
        selfUserId: self.id,
        targetNodeId: targetNode?.node_id ?? null,
        starterConversationId: starterConversation.id,
        starter: {
          title: starterTitle,
          actionLabel: `Open ${starterTitle}`,
          actionHref: `/chat/${starterConversation.id}`,
          agentName: starterAgent.display_name || DEFAULT_AGENT_NAME,
          description: buildStarterDescription(starterAgent),
          nodeLabel: targetNode?.node_name ?? targetNode?.node_id,
          statusLabel: targetNode?.status
        }
      };
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
    delivery_status:
      input.message.delivery_status === "sent" ||
      input.message.delivery_status === "running" ||
      input.message.delivery_status === "completed" ||
      input.message.delivery_status === "failed"
        ? input.message.delivery_status
        : input.defaultStatus
  };
}

function toConversationSummary(input: {
  conversation: ImConversation;
  messages: ImMessage[];
  userById: Map<string, ImUser>;
  selfUserId: string;
  starterTitle: string;
}): ConversationSummary {
  const latest = input.messages.at(-1);
  const unreadCount = input.messages.filter((item) => item.sender_user_id !== input.selfUserId).length;
  return {
    conversation_id: input.conversation.id,
    title: resolveConversationTitle({ conversation: input.conversation, starterTitle: input.starterTitle }),
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

export async function getChatStarter(): Promise<ChatStarter> {
  const { starter } = await ensureBootstrap();
  return starter;
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const { selfUserId, starter } = await ensureBootstrap();
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
        selfUserId,
        starterTitle: starter.title
      })
    )
    .sort((left, right) => (right.last_message_at ?? "").localeCompare(left.last_message_at ?? ""));
}

export async function getConversation(conversationId: string): Promise<ConversationDetail | null> {
  const { selfUserId, starter } = await ensureBootstrap();
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
    title: resolveConversationTitle({ conversation, starterTitle: starter.title }),
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
  const { selfUserId, targetNodeId } = await ensureBootstrap();
  if (!targetNodeId) {
    throw new Error("No relay node is available. Connect an online node and retry.");
  }
  const [created, userById] = await Promise.all([
    requestJson<ImMessage>(`/im/v1/conversations/${input.conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify(
        buildCreateMessageRequest({
          selfUserId,
          content: input.content,
          targetNodeId
        })
      )
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
  const eventTypes = [
    "message.sent",
    "message.delivered",
    "relay.accepted",
    "relay.processing",
    "relay.completed",
    "relay.failed",
    "conversation.notice",
    "message_created",
    "text_delta",
    "turn_end",
    "message_status"
  ];
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

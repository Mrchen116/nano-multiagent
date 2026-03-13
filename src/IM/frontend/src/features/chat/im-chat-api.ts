import { ChatMessage, ChatOwnershipSummary, ChatStarter, ConversationDetail, ConversationSummary } from "./types";

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
  targetNodeStatus: string | null;
  ownership: ChatOwnershipSummary;
  starter: ChatStarter;
  starterConversationId: string | null;
}

export interface SendAvailability {
  canSend: boolean;
  state: "unbound" | "offline" | "available";
  helperText: string | null;
  placeholder: string;
}

const FAILURE_PANEL_TITLE = "Chat unavailable";
const SEND_DISABLED_UNBOUND_HELPER = "Bind this Gateway to continue. Web IM disables the composer until one of your Gateway nodes is connected.";
const SEND_DISABLED_UNBOUND_PLACEHOLDER = "Bind this Gateway to continue";
const SEND_DISABLED_OFFLINE_HELPER = "Your bound Gateway is offline. Bring that node online or bind another online node to re-enable chat.";
const SEND_DISABLED_OFFLINE_PLACEHOLDER = "Gateway offline — chat disabled";
const SEND_ENABLED_PLACEHOLDER = "Type message";
const SEND_FAILURE_RETRY_ACTION = "Connect an online node and retry.";
const SEND_FAILURE_UNAVAILABLE_HELPER = `${FAILURE_PANEL_TITLE}. No online relay node is available for this chat. ${SEND_FAILURE_RETRY_ACTION}`;
const SEND_FAILURE_UNAVAILABLE_PLACEHOLDER = "No online relay node available";

export function resolveSendAvailability(input: {
  targetNodeId: string | null;
  nodeStatus: string | null;
}): SendAvailability {
  if (!input.targetNodeId) {
    return {
      canSend: false,
      state: "unbound",
      helperText: SEND_DISABLED_UNBOUND_HELPER,
      placeholder: SEND_DISABLED_UNBOUND_PLACEHOLDER
    };
  }
  if (input.nodeStatus !== "online") {
    return {
      canSend: false,
      state: "offline",
      helperText: SEND_DISABLED_OFFLINE_HELPER,
      placeholder: SEND_DISABLED_OFFLINE_PLACEHOLDER
    };
  }
  return {
    canSend: true,
    state: "available",
    helperText: null,
    placeholder: SEND_ENABLED_PLACEHOLDER
  };
}

export function isNodeReadyForSend(input: { targetNodeId: string | null; nodeStatus: string | null }) {
  return resolveSendAvailability(input).canSend;
}

export function getSendAvailabilityMessages() {
  return {
    failureTitle: FAILURE_PANEL_TITLE,
    retryAction: SEND_FAILURE_RETRY_ACTION,
    unavailableHelperText: SEND_FAILURE_UNAVAILABLE_HELPER,
    unavailablePlaceholder: SEND_FAILURE_UNAVAILABLE_PLACEHOLDER,
    unboundHelperText: SEND_DISABLED_UNBOUND_HELPER,
    unboundPlaceholder: SEND_DISABLED_UNBOUND_PLACEHOLDER,
    offlineHelperText: SEND_DISABLED_OFFLINE_HELPER,
    offlinePlaceholder: SEND_DISABLED_OFFLINE_PLACEHOLDER,
    enabledPlaceholder: SEND_ENABLED_PLACEHOLDER
  };
}

function toNodeStatus(node: Pick<ImNode, "status"> | null) {
  return node?.status ?? null;
}

function selectTargetNode(input: {
  nodes: ImNode[];
  ownedNodeId: string | null;
}) {
  const preferred = pickDefaultNodeForSend(input.nodes);
  if (preferred) {
    return preferred;
  }
  if (!input.ownedNodeId) {
    return null;
  }
  return input.nodes.find((item) => item.node_id === input.ownedNodeId) ?? null;
}

function resolveTargetNode(input: {
  nodes: ImNode[];
  ownedNodeId: string | null;
}) {
  const selected = selectTargetNode(input);
  if (selected) {
    return selected;
  }
  if (!input.ownedNodeId) {
    return null;
  }
  return {
    node_id: input.ownedNodeId,
    node_name: input.ownedNodeId,
    status: "offline",
    relay_enabled: false
  };
}

function toBootstrapNodeState(input: {
  targetNode: ImNode | null;
  starterAgentName: string;
}) {
  const agentName = sanitizeMainAgentName(input.starterAgentName);
  const nodeId = input.targetNode?.node_id ?? null;
  const nodeLabel = input.targetNode?.node_name ?? nodeId;
  const nodeStatus = toNodeStatus(input.targetNode);
  return {
    targetNodeId: nodeId,
    targetNodeStatus: nodeStatus,
    ownership: {
      nodeId,
      nodeLabel,
      nodeStatus,
      agentLabel: agentName,
      ownershipLabel: buildMainAgentOwnershipLabel(agentName, nodeLabel, nodeStatus)
    }
  };
}

export interface ChatBootstrapState {
  selfUserId: string;
  targetNodeId: string | null;
  targetNodeStatus: string | null;
  initialConversationId: string | null;
  ownership: ChatOwnershipSummary;
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
const DEFAULT_AGENT_DESCRIPTION = "OpsBot is your main agent and default IM entry for this workspace.";
const MAIN_AGENT_PREFIX = "主 Agent · ";
const MAIN_AGENT_SESSION_LABEL = "主 Agent 会话";
const MAIN_AGENT_ENTRY_HINT = "这是你与主 Agent 的默认产品入口。";
const DIRECT_AGENT_SESSION_LABEL = "Direct agent chat";
const DIRECT_AGENT_DISCOVERABILITY_HINT = "This is a one-to-one conversation with an available target.";
const MAIN_AGENT_DISCOVERABILITY_HINT = "Use this thread when you want to talk to your main agent acting as your delegate.";
const MAIN_AGENT_TARGET_LABEL = "你的主 Agent";
const MAIN_AGENT_LIST_HINT = "This is the user-visible product entry where your main agent receives intent and routes follow-up work.";
const MAIN_AGENT_OWNERSHIP_PREFIX = "Using your main agent";
const MAIN_AGENT_STATUS_SUFFIX = " and ready to chat";
const MAIN_AGENT_DEFAULT_DESCRIPTION_SUFFIX = "is your main agent and default starter chat, but you can also open direct agent chats, group chats, and agent-to-agent threads from the conversation list.";
const MAIN_AGENT_IDENTITY_ALIASES = ["main agent", "主 agent", "主agent", "your delegate", "替身"];

function sanitizeMainAgentName(agentName: string): string {
  const trimmed = agentName.trim();
  if (!trimmed) {
    return DEFAULT_AGENT_NAME;
  }
  return trimmed
    .replace(/^主\s*Agent\s*/i, "")
    .replace(/^main\s+agent\s*/i, "")
    .trim() || DEFAULT_AGENT_NAME;
}

function isMainAgentStarterTitle(title: string): boolean {
  return title.startsWith(MAIN_AGENT_PREFIX);
}

function buildMainAgentOwnershipLabel(agentName: string, nodeLabel: string | null, nodeStatus: string | null): string {
  if (!nodeLabel) {
    return `No bound node is selected for ${agentName}`;
  }
  const status = nodeStatus ? ` (${nodeStatus}${nodeStatus === "online" ? MAIN_AGENT_STATUS_SUFFIX : ""})` : "";
  return `${MAIN_AGENT_OWNERSHIP_PREFIX} ${agentName} on ${nodeLabel}${status}`;
}

function toConversationSemantics(input: {
  title: string;
  ownershipLabel?: string | null;
}): Pick<ConversationSummary, "kind_label" | "target_label" | "discoverability_hint" | "ownership_label"> &
  Pick<ConversationDetail, "kind_label" | "target_label" | "discoverability_hint" | "ownership_label"> {
  if (isMainAgentStarterTitle(input.title)) {
    return {
      kind_label: MAIN_AGENT_SESSION_LABEL,
      target_label: MAIN_AGENT_TARGET_LABEL,
      discoverability_hint: MAIN_AGENT_DISCOVERABILITY_HINT,
      ownership_label: input.ownershipLabel ?? MAIN_AGENT_ENTRY_HINT
    };
  }
  return {
    kind_label: DIRECT_AGENT_SESSION_LABEL,
    target_label: undefined,
    discoverability_hint: DIRECT_AGENT_DISCOVERABILITY_HINT,
    ownership_label: input.ownershipLabel ?? undefined
  };
}

function buildListDiscoverabilityHint(title: string, fallback: string): string {
  return isMainAgentStarterTitle(title) ? MAIN_AGENT_LIST_HINT : fallback;
}

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
  return `${MAIN_AGENT_PREFIX}${sanitizeMainAgentName(agentName)}`;
}

export function buildStarterPeerUsername(agentId: string): string {
  return agentId === PEER_USERNAME ? PEER_USERNAME : `${AGENT_USERNAME_PREFIX}${agentId}`;
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

async function ensureSelfUser() {
  return ensureUser(SELF_USERNAME, "You");
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
  const normalizedName = sanitizeMainAgentName(agent.display_name);
  return agent.description.trim() || `${normalizedName} ${MAIN_AGENT_DEFAULT_DESCRIPTION_SUFFIX}`;
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

async function ensureBootstrap(): Promise<BootstrapState> {
  if (!bootstrapPromise) {
    bootstrapPromise = (async () => {
      const [self, agents, nodes] = await Promise.all([ensureUser(SELF_USERNAME, "You"), listAgentsRaw(), listNodesRaw()]);
      const starterAgent = pickStarterAgent(agents);
      const starterPeer = await ensureUser(
        buildStarterPeerUsername(starterAgent.agent_id),
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
      const agentName = starterAgent.display_name || DEFAULT_AGENT_NAME;
      const ownedNodeId = pickPrimaryOwnedNodeId(self);
      const targetNode = resolveTargetNode({ nodes, ownedNodeId });
      const bootstrapNodeState = toBootstrapNodeState({ targetNode, starterAgentName: agentName });
      return {
        selfUserId: self.id,
        targetNodeId: bootstrapNodeState.targetNodeId,
        targetNodeStatus: bootstrapNodeState.targetNodeStatus,
        ownership: bootstrapNodeState.ownership,
        starterConversationId: starterConversation.id,
        starter: {
          title: starterTitle,
          actionLabel: `Open ${starterTitle}`,
          actionHref: `/chat/${starterConversation.id}`,
          agentName,
          description: buildStarterDescription(starterAgent),
          nodeLabel: bootstrapNodeState.ownership.nodeLabel ?? undefined,
          statusLabel: bootstrapNodeState.ownership.ownershipLabel ?? undefined
        }
      };
    })();
  }
  return bootstrapPromise;
}

export function resetChatBootstrapState() {
  bootstrapPromise = null;
}

export async function getChatBootstrapState(): Promise<ChatBootstrapState> {
  const bootstrap = await ensureBootstrap();
  return {
    selfUserId: bootstrap.selfUserId,
    targetNodeId: bootstrap.targetNodeId,
    targetNodeStatus: bootstrap.targetNodeStatus,
    initialConversationId: bootstrap.starterConversationId,
    ownership: bootstrap.ownership
  };
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
  ownership: ChatOwnershipSummary;
}): ConversationSummary {
  const latest = input.messages.at(-1);
  const unreadCount = input.messages.filter((item) => item.sender_user_id !== input.selfUserId).length;
  const resolvedTitle = resolveConversationTitle({ conversation: input.conversation, starterTitle: input.starterTitle });
  const semantics = toConversationSemantics({ title: resolvedTitle, ownershipLabel: input.ownership.ownershipLabel });
  return {
    conversation_id: input.conversation.id,
    title: resolvedTitle,
    last_message_preview: latest?.content ?? "",
    last_message_at: latest?.created_at,
    unread_count: unreadCount,
    participants: input.conversation.participant_ids.map(
      (participantId) => input.userById.get(participantId)?.display_name ?? participantId
    ),
    node_label: input.ownership.nodeLabel ?? undefined,
    node_status: input.ownership.nodeStatus ?? undefined,
    agent_label: input.ownership.agentLabel ?? undefined,
    ownership_label: semantics.ownership_label,
    kind_label: semantics.kind_label,
    target_label: semantics.target_label,
    discoverability_hint: buildListDiscoverabilityHint(resolvedTitle, semantics.discoverability_hint ?? "")
  };
}

async function loadUserMap() {
  const users = await listUsersRaw();
  return new Map(users.map((item) => [item.id, item]));
}

export async function confirmBindToken(bindToken: string) {
  const self = await ensureSelfUser();
  const response = await requestJson<{ node_id: string }>("/im/v1/bind", {
    method: "POST",
    body: JSON.stringify({
      action: "confirm",
      bind_token: bindToken,
      user_id: self.id
    })
  });
  resetChatBootstrapState();
  return response;
}

export async function getChatStarter(): Promise<ChatStarter> {
  const { starter } = await ensureBootstrap();
  return starter;
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const { selfUserId, starter, ownership } = await ensureBootstrap();
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
        starterTitle: starter.title,
        ownership
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
  const resolvedTitle = resolveConversationTitle({ conversation, starterTitle: starter.title });
  const semantics = toConversationSemantics({ title: resolvedTitle, ownershipLabel: starter.statusLabel });
  return {
    conversation_id: conversation.id,
    title: resolvedTitle,
    kind_label: semantics.kind_label,
    target_label: semantics.target_label,
    discoverability_hint: semantics.discoverability_hint,
    ownership_label: semantics.ownership_label,
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
  const { selfUserId, targetNodeId, targetNodeStatus } = await ensureBootstrap();
  if (!isNodeReadyForSend({ targetNodeId, nodeStatus: targetNodeStatus })) {
    throw new Error(SEND_FAILURE_UNAVAILABLE_HELPER);
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

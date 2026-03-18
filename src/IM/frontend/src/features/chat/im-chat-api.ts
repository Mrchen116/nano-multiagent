import {
  ChatAttachment,
  ChatMessage,
  ChatOwnershipSummary,
  ChatStarter,
  ConversationDetail,
  ConversationSummary,
  GroupChatParticipantOption,
  MentionCandidate,
  UsageMetricRow
} from "./types";

interface ImUser {
  id: string;
  username: string;
  display_name: string;
  owner_id: string;
  owned_node_ids?: string[];
}

interface ImConversation {
  id: string;
  title: string;
  participant_ids: string[];
  type: string;
  owner_id: string;
  creator_id?: string;
  created_at?: string;
}

function isAgentUsername(username: string) {
  return username.startsWith(AGENT_USERNAME_PREFIX);
}

function toMentionLabel(user: ImUser) {
  return user.display_name.trim() || user.username;
}

function toMentionCandidates(input: {
  conversation: ImConversation;
  userById: Map<string, ImUser>;
  selfUserId: string;
}): MentionCandidate[] {
  if (input.conversation.type !== "group") {
    return [];
  }
  const seenAgentIds = new Set<string>();
  return input.conversation.participant_ids
    .filter((participantId) => participantId !== input.selfUserId)
    .map((participantId) => input.userById.get(participantId))
    .filter((participant): participant is ImUser => Boolean(participant && isAgentUsername(participant.username)))
    .map((participant) => ({
      agentId: participant.username.slice(AGENT_USERNAME_PREFIX.length),
      label: toMentionLabel(participant)
    }))
    .filter((participant) => participant.agentId.length > 0)
    .filter((participant) => {
      if (seenAgentIds.has(participant.agentId)) {
        return false;
      }
      seenAgentIds.add(participant.agentId);
      return true;
    });
}

interface ImMessage {
  id: string;
  conversation_id: string;
  sender_user_id: string;
  sender_type?: string;
  content: string;
  attachments?: ChatAttachment[];
  delivery_status?: string;
  created_at: string;
}

interface ImAgent {
  agent_id: string;
  display_name: string;
  description: string;
}

export interface DiscoverableAgent {
  agent_id: string;
  display_name: string;
  description: string;
  existing_conversation_id: string | null;
}

function compareParticipantOptions(left: GroupChatParticipantOption, right: GroupChatParticipantOption) {
  if (left.kind !== right.kind) {
    return left.kind === "agent" ? -1 : 1;
  }
  return left.label.localeCompare(right.label);
}

function toGroupParticipantOption(input: {
  user: ImUser;
  selfUserId: string;
  agentById: Map<string, ImAgent>;
}): GroupChatParticipantOption | null {
  if (input.user.id === input.selfUserId) {
    return null;
  }
  const label = input.user.display_name.trim() || input.user.username;
  if (isAgentUsername(input.user.username)) {
    const agentId = input.user.username.slice(AGENT_USERNAME_PREFIX.length);
    const agent = input.agentById.get(agentId);
    return {
      user_id: input.user.id,
      label,
      kind: "agent",
      description: agent?.description?.trim() || "Configured agent available for shared group chat."
    };
  }
  return {
    user_id: input.user.id,
    label,
    kind: "teammate",
    description: "Workspace teammate available for shared chat."
  };
}

interface ImNode {
  node_id: string;
  node_name: string;
  status: string;
  relay_enabled: boolean;
}

interface BootstrapState {
  selfUserId: string;
  ownerId: string;
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
  ownerId: string;
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
  attachments?: ChatAttachment[];
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
const GROUP_CHAT_SESSION_LABEL = "Group chat";
const DIRECT_AGENT_DISCOVERABILITY_HINT = "Reuse this stable direct chat for the same agent, or start a fresh session here when you need a new prompt snapshot.";
const GROUP_CHAT_DISCOVERABILITY_HINT = "Group thread";
const GROUP_CHAT_TARGET_LABEL = "Shared thread";
const GROUP_CHAT_LIST_HINT = "Keep people and agents in one shared conversation timeline.";
const GROUP_CHAT_ENTRY_HINT = "Group chat";
const ENGINEERING_GROUP_OWNERSHIP_PATTERNS = [/^Using your main agent .+ready to chat\)$/i];
const AGENT_NETWORK_SESSION_LABEL = "Agent-to-agent chat";
const AGENT_NETWORK_DISCOVERABILITY_HINT = "This is a read-only coordination thread between agents.";
const AGENT_NETWORK_TARGET_LABEL = "Agents only";
const AGENT_NETWORK_LIST_HINT = "Use this thread to inspect coordination between agents.";
const AGENT_NETWORK_ENTRY_HINT = "Read-only coordination thread between agents.";
const MAIN_AGENT_DISCOVERABILITY_HINT = "Use this thread when you want to talk to your main agent acting as your delegate.";
const MAIN_AGENT_TARGET_LABEL = "你的主 Agent";
const MAIN_AGENT_LIST_HINT = "This is the user-visible product entry where your main agent receives intent and routes follow-up work.";
const MAIN_AGENT_OWNERSHIP_PREFIX = "Using your main agent";
const MAIN_AGENT_STATUS_SUFFIX = " and ready to chat";
const MAIN_AGENT_DEFAULT_DESCRIPTION_SUFFIX = "is your main agent and default starter chat. Reuse each agent's dedicated direct chat from Settings, or open group chats and agent-to-agent threads from the conversation list.";
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

function sanitizeGroupOwnershipLabel(ownershipLabel: string | null | undefined) {
  const trimmed = ownershipLabel?.trim();
  if (!trimmed) {
    return GROUP_CHAT_ENTRY_HINT;
  }
  if (ENGINEERING_GROUP_OWNERSHIP_PATTERNS.some((pattern) => pattern.test(trimmed))) {
    return GROUP_CHAT_ENTRY_HINT;
  }
  return trimmed;
}

function toConversationSemantics(input: {
  title: string;
  conversationType?: string;
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
  if (input.conversationType === "group") {
    return {
      kind_label: GROUP_CHAT_SESSION_LABEL,
      target_label: GROUP_CHAT_TARGET_LABEL,
      discoverability_hint: GROUP_CHAT_DISCOVERABILITY_HINT,
      ownership_label: sanitizeGroupOwnershipLabel(input.ownershipLabel)
    };
  }
  if (input.conversationType === "agent-network") {
    return {
      kind_label: AGENT_NETWORK_SESSION_LABEL,
      target_label: AGENT_NETWORK_TARGET_LABEL,
      discoverability_hint: AGENT_NETWORK_DISCOVERABILITY_HINT,
      ownership_label: input.ownershipLabel ?? AGENT_NETWORK_ENTRY_HINT
    };
  }
  return {
    kind_label: DIRECT_AGENT_SESSION_LABEL,
    target_label: undefined,
    discoverability_hint: DIRECT_AGENT_DISCOVERABILITY_HINT,
    ownership_label: input.ownershipLabel ?? undefined
  };
}

function buildListDiscoverabilityHint(input: { title: string; conversationType?: string; fallback: string }): string {
  if (isMainAgentStarterTitle(input.title)) {
    return MAIN_AGENT_LIST_HINT;
  }
  if (input.conversationType === "group") {
    return GROUP_CHAT_LIST_HINT;
  }
  if (input.conversationType === "agent-network") {
    return AGENT_NETWORK_LIST_HINT;
  }
  return input.fallback;
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

async function requestUpload(path: string, input: {
  body: Blob;
  contentType: string;
}): Promise<ChatAttachment> {
  const response = await fetch(withBase(path), {
    method: "POST",
    body: input.body,
    headers: {
      "Content-Type": input.contentType || "application/octet-stream"
    }
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new ChatRequestError({
      status: response.status,
      detail: detail || response.statusText || "request failed",
      method: "POST",
      path
    });
  }
  return (await response.json()) as ChatAttachment;
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

export function buildGroupConversationTitle(labels: string[]): string {
  const normalizedLabels = Array.from(new Set(labels.map((item) => item.trim()).filter((item) => item.length > 0)));
  if (normalizedLabels.length === 0) {
    return "New group chat";
  }
  if (normalizedLabels.length === 1) {
    return `${normalizedLabels[0]} group`;
  }
  if (normalizedLabels.length === 2) {
    return `${normalizedLabels[0]} + ${normalizedLabels[1]}`;
  }
  return `${normalizedLabels[0]} + ${normalizedLabels[1]} +${normalizedLabels.length - 2}`;
}

export function resolveGroupConversationTitle(input: {
  groupName: string | undefined;
  participantLabels: string[];
}): string {
  // Use custom name when provided; fall back to auto-generated title from participant labels.
  const trimmed = input.groupName?.trim() ?? "";
  if (trimmed.length > 0) {
    return trimmed;
  }
  return buildGroupConversationTitle(input.participantLabels);
}

export function buildStarterPeerUsername(agentId: string): string {
  return agentId === PEER_USERNAME ? PEER_USERNAME : `${AGENT_USERNAME_PREFIX}${agentId}`;
}

export function buildCreateMessageRequest(input: {
  selfUserId: string;
  content: string;
  attachments?: ChatAttachment[];
  targetNodeId: string | null;
}): CreateMessagePayload {
  const payload: CreateMessagePayload = {
    sender_user_id: input.selfUserId,
    content: input.content
  };
  if (input.attachments && input.attachments.length > 0) {
    payload.attachments = input.attachments;
  }
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

export async function uploadAttachment(file: File): Promise<ChatAttachment> {
  const fileName = file.name.trim() || "upload.bin";
  return requestUpload(`/im/v1/uploads?file_name=${encodeURIComponent(fileName)}`, {
    body: file,
    contentType: file.type || "application/octet-stream"
  });
}

export async function getUsageMetrics(input: { ownerId?: string; conversationId?: string; agentId?: string } = {}) {
  const params = new URLSearchParams();
  if (input.ownerId) {
    params.set("owner_id", input.ownerId);
  }
  if (input.conversationId) {
    params.set("conversation_id", input.conversationId);
  }
  if (input.agentId) {
    params.set("agent_id", input.agentId);
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return requestJson<UsageMetricRow[]>(`/im/v1/metrics/usage${suffix}`);
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

function compareConversationCreation(left: ImConversation, right: ImConversation) {
  const leftCreatedAt = Date.parse(left.created_at ?? "");
  const rightCreatedAt = Date.parse(right.created_at ?? "");
  const leftHasTimestamp = Number.isFinite(leftCreatedAt);
  const rightHasTimestamp = Number.isFinite(rightCreatedAt);
  if (leftHasTimestamp && rightHasTimestamp && leftCreatedAt !== rightCreatedAt) {
    return leftCreatedAt - rightCreatedAt;
  }
  if (leftHasTimestamp !== rightHasTimestamp) {
    return leftHasTimestamp ? -1 : 1;
  }
  return left.id.localeCompare(right.id);
}

export function pickCanonicalDirectConversation(input: {
  conversations: ImConversation[];
  selfUserId: string;
  peerUserId: string;
}): ImConversation | null {
  const matches = input.conversations.filter(
    (item) =>
      item.type !== "group" &&
      item.participant_ids.length === 2 &&
      item.participant_ids.includes(input.selfUserId) &&
      item.participant_ids.includes(input.peerUserId)
  );
  if (matches.length === 0) {
    return null;
  }
  return [...matches].sort(compareConversationCreation)[0] ?? null;
}

function findStarterConversation(input: {
  conversations: ImConversation[];
  selfUserId: string;
  peerUserId: string;
  starterTitle: string;
}): ImConversation | null {
  return (
    pickCanonicalDirectConversation({
      conversations: input.conversations,
      selfUserId: input.selfUserId,
      peerUserId: input.peerUserId
    }) ??
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
        ownerId: self.owner_id,
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
    ownerId: bootstrap.ownerId,
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
    sender_type:
      input.message.sender_type === "agent" || input.message.sender_type === "system" ? input.message.sender_type : "user",
    sender_name: sender?.display_name ?? input.message.sender_user_id,
    is_mine: isMine,
    content: input.message.content,
    attachments: input.message.attachments ?? [],
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
  const semantics = toConversationSemantics({
    title: resolvedTitle,
    conversationType: input.conversation.type,
    ownershipLabel: input.ownership.ownershipLabel
  });
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
    discoverability_hint: buildListDiscoverabilityHint({
      title: resolvedTitle,
      conversationType: input.conversation.type,
      fallback: semantics.discoverability_hint ?? ""
    })
  };
}

async function loadUserMap() {
  const users = await listUsersRaw();
  return new Map(users.map((item) => [item.id, item]));
}

function resolveDirectAgentId(input: {
  conversation: ImConversation;
  userById: Map<string, ImUser>;
  selfUserId: string;
}): string | undefined {
  if (input.conversation.type === "group") {
    return undefined;
  }
  const agentParticipant = input.conversation.participant_ids
    .filter((participantId) => participantId !== input.selfUserId)
    .map((participantId) => input.userById.get(participantId))
    .find((participant): participant is ImUser => Boolean(participant && isAgentUsername(participant.username)));
  if (!agentParticipant) {
    return undefined;
  }
  return agentParticipant.username.slice(AGENT_USERNAME_PREFIX.length) || undefined;
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
  return {
    ...response,
    self_user_id: self.id
  };
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

export async function listDiscoverableAgents(): Promise<DiscoverableAgent[]> {
  const { selfUserId } = await ensureBootstrap();
  const [agents, users, conversations] = await Promise.all([listAgentsRaw(), listUsersRaw(), listConversationsRaw()]);
  const usersByUsername = new Map(users.map((item) => [item.username, item]));
  return agents.map((agent) => {
    const peer = usersByUsername.get(buildStarterPeerUsername(agent.agent_id));
    const existingConversation = peer
      ? pickCanonicalDirectConversation({
          conversations,
          selfUserId,
          peerUserId: peer.id
        })
      : null;
    return {
      agent_id: agent.agent_id,
      display_name: agent.display_name,
      description: agent.description,
      existing_conversation_id: existingConversation?.id ?? null
    };
  });
}

export async function listDiscoverableGroupParticipants(): Promise<GroupChatParticipantOption[]> {
  const { selfUserId } = await ensureBootstrap();
  const agents = await listAgentsRaw();
  await Promise.all(
    agents.map((agent) => ensureUser(buildStarterPeerUsername(agent.agent_id), agent.display_name || agent.agent_id))
  );
  const users = await listUsersRaw();
  const agentById = new Map(agents.map((agent) => [agent.agent_id, agent]));
  return users
    .map((user) =>
      toGroupParticipantOption({
        user,
        selfUserId,
        agentById
      })
    )
    .filter((item): item is GroupChatParticipantOption => Boolean(item))
    .sort(compareParticipantOptions);
}

export async function createDirectConversation(input: { agentId: string }): Promise<{ conversation_id: string }> {
  const { selfUserId } = await ensureBootstrap();
  const agents = await listAgentsRaw();
  const agent = agents.find((item) => item.agent_id === input.agentId);
  if (!agent) {
    throw new Error(`agent not found: ${input.agentId}`);
  }
  const peer = await ensureUser(buildStarterPeerUsername(agent.agent_id), agent.display_name || agent.agent_id);
  const conversations = await listConversationsRaw();
  const existing = pickCanonicalDirectConversation({
    conversations,
    selfUserId,
    peerUserId: peer.id
  });
  if (existing) {
    return { conversation_id: existing.id };
  }
  const created = await createConversationRaw({
    title: agent.display_name || agent.agent_id,
    participant_ids: [selfUserId, peer.id]
  });
  return { conversation_id: created.id };
}

export async function createFreshDirectConversation(input: { agentId: string }): Promise<{ conversation_id: string }> {
  const { selfUserId } = await ensureBootstrap();
  const agents = await listAgentsRaw();
  const agent = agents.find((item) => item.agent_id === input.agentId);
  if (!agent) {
    throw new Error(`agent not found: ${input.agentId}`);
  }
  const peer = await ensureUser(buildStarterPeerUsername(agent.agent_id), agent.display_name || agent.agent_id);
  const created = await createConversationRaw({
    title: `${agent.display_name || agent.agent_id} · Fresh session`,
    participant_ids: [selfUserId, peer.id]
  });
  return { conversation_id: created.id };
}

export async function createGroupConversation(input: {
  participantIds: string[];
  /** Optional custom group name; leave blank to auto-generate from participant names. */
  groupName?: string;
}): Promise<{ conversation_id: string }> {
  const { selfUserId } = await ensureBootstrap();
  const participantIds = Array.from(
    new Set(input.participantIds.filter((participantId) => participantId && participantId !== selfUserId))
  );
  if (participantIds.length < 2) {
    throw new Error("select at least two participants to create a group chat");
  }
  const userById = await loadUserMap();
  const participantLabels = participantIds.map((participantId) => userById.get(participantId)?.display_name ?? participantId);
  const title = resolveGroupConversationTitle({ groupName: input.groupName, participantLabels });
  const created = await createConversationRaw({
    title,
    participant_ids: [selfUserId, ...participantIds]
  });
  return { conversation_id: created.id };
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
  const semantics = toConversationSemantics({
    title: resolvedTitle,
    conversationType: conversation.type,
    ownershipLabel: starter.statusLabel
  });
  return {
    conversation_id: conversation.id,
    title: resolvedTitle,
    kind_label: semantics.kind_label,
    target_label: semantics.target_label,
    discoverability_hint: semantics.discoverability_hint,
    ownership_label: semantics.ownership_label,
    // creator_id is forwarded so the UI can show the dissolve button only to the creator (M234).
    creator_id: conversation.creator_id ?? undefined,
    mention_candidates: toMentionCandidates({
      conversation,
      userById,
      selfUserId
    }),
    direct_agent_id: resolveDirectAgentId({
      conversation,
      userById,
      selfUserId
    }),
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

export async function sendMessage(input: {
  conversationId: string;
  content: string;
  attachments?: ChatAttachment[];
}): Promise<ChatMessage> {
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
          attachments: input.attachments,
          targetNodeId: null
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

/**
 * Dissolve a group conversation (creator only).
 *
 * Sends DELETE /im/v1/conversations/{conversationId} with a JSON body
 * carrying the requester_id for server-side permission enforcement.
 */
export async function deleteConversation(input: {
  conversationId: string;
  requesterId: string;
}): Promise<void> {
  const response = await fetch(withBase(`/im/v1/conversations/${input.conversationId}`), {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requester_id: input.requesterId })
  });
  if (!response.ok) {
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
    throw new ChatRequestError({ status: response.status, detail, method: "DELETE", path: `/im/v1/conversations/${input.conversationId}` });
  }
}

/**
 * Leave a group conversation (any participant).
 *
 * Sends DELETE /im/v1/conversations/{conversationId}/participants/{userId}.
 */
export async function leaveConversation(input: {
  conversationId: string;
  userId: string;
}): Promise<void> {
  const response = await fetch(withBase(`/im/v1/conversations/${input.conversationId}/participants/${input.userId}`), {
    method: "DELETE"
  });
  if (!response.ok) {
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
    throw new ChatRequestError({ status: response.status, detail, method: "DELETE", path: `/im/v1/conversations/${input.conversationId}/participants/${input.userId}` });
  }
}

/**
 * Rename a group conversation (M235).
 *
 * Sends PATCH /im/v1/conversations/{conversationId} with { title }.
 * Returns the updated title on success.
 */
export async function renameConversation(input: {
  conversationId: string;
  title: string;
}): Promise<{ title: string }> {
  const response = await requestJson<{ id: string; title: string }>(
    `/im/v1/conversations/${input.conversationId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ title: input.title })
    }
  );
  return { title: response.title };
}

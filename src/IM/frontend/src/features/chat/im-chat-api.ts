import {
  ChatAttachment,
  ChatMessage,
  ChatOwnershipSummary,
  ChatStarter,
  ConversationKind,
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
  participants?: ImActorRef[];
  participant_ids?: string[];
  type: string;
  owner_id: string;
  creator_id?: string;
  unread_count?: number;
  last_message_at?: string | null;
  created_at?: string;
}

type ImActorType = "user" | "agent" | "system";

interface ImActorRef {
  type: ImActorType;
  id: string;
  display_name?: string;
}

function isAgentUsername(username: string) {
  return username.startsWith(AGENT_USERNAME_PREFIX);
}

function normalizeActorType(value: unknown): ImActorType | null {
  if (value === "user" || value === "agent" || value === "system") {
    return value;
  }
  return null;
}

function normalizeActorId(type: ImActorType, rawId: unknown): string | null {
  if (typeof rawId !== "string") {
    return null;
  }
  const trimmed = rawId.trim();
  if (!trimmed) {
    return null;
  }
  if (type === "agent" && trimmed.startsWith(AGENT_USERNAME_PREFIX)) {
    return trimmed.slice(AGENT_USERNAME_PREFIX.length) || null;
  }
  return trimmed;
}

function parseActorRef(value: unknown): ImActorRef | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const payload = value as Record<string, unknown>;
  const type = normalizeActorType(payload.type);
  if (!type) {
    return null;
  }
  const directId = normalizeActorId(type, payload.id);
  const aliasId = normalizeActorId(type, type === "agent" ? payload.agent_id : payload.user_id);
  const id = directId ?? aliasId;
  if (!id) {
    return null;
  }
  const displayName = typeof payload.display_name === "string" ? payload.display_name.trim() : "";
  return {
    type,
    id,
    display_name: displayName || undefined
  };
}

function toActorFromUser(user: ImUser): ImActorRef {
  if (isAgentUsername(user.username)) {
    return {
      type: "agent",
      id: user.username.slice(AGENT_USERNAME_PREFIX.length),
      display_name: user.display_name
    };
  }
  return {
    type: "user",
    id: user.id,
    display_name: user.display_name
  };
}

function resolveConversationParticipants(input: {
  conversation: ImConversation;
  userById: Map<string, ImUser>;
}): ImActorRef[] {
  const parsedParticipants = (input.conversation.participants ?? [])
    .map((item) => parseActorRef(item))
    .filter((item): item is ImActorRef => Boolean(item));
  if (parsedParticipants.length > 0) {
    return parsedParticipants;
  }
  return (input.conversation.participant_ids ?? []).map((participantId) => {
    const user = input.userById.get(participantId);
    if (!user) {
      return { type: "user", id: participantId };
    }
    return toActorFromUser(user);
  });
}

function toParticipantDisplayName(participant: ImActorRef): string {
  const displayName = participant.display_name?.trim();
  if (displayName) {
    return displayName;
  }
  if (participant.type === "agent") {
    return `agent:${participant.id}`;
  }
  if (participant.type === "system") {
    return `system:${participant.id}`;
  }
  return participant.id;
}

function toParticipantIdentityTag(participant: ImActorRef): string {
  if (participant.type === "agent") {
    return `agent_id:${participant.id}`;
  }
  if (participant.type === "user") {
    return `user_id:${participant.id}`;
  }
  return `id:${participant.id}`;
}

function toParticipantIdentityLabel(participant: ImActorRef): string {
  return `${toParticipantDisplayName(participant)} (${toParticipantIdentityTag(participant)})`;
}

function toMentionCandidateLabel(participant: ImActorRef): string {
  return toParticipantIdentityLabel(participant);
}

function toMentionCandidates(input: {
  conversation: ImConversation;
  userById: Map<string, ImUser>;
  selfUserId: string;
}): MentionCandidate[] {
  if (input.conversation.type !== "group") {
    return [];
  }
  const seenTargets = new Set<string>();
  return resolveConversationParticipants({
    conversation: input.conversation,
    userById: input.userById
  })
    .filter((participant) => participant.type === "agent" || participant.type === "user")
    .filter((participant) => !(participant.type === "user" && participant.id === input.selfUserId))
    .map((participant) => ({
      agentId: participant.id,
      label: toMentionCandidateLabel(participant)
    }))
    .filter((participant) => participant.agentId.length > 0)
    .filter((participant) => {
      if (seenTargets.has(participant.agentId)) {
        return false;
      }
      seenTargets.add(participant.agentId);
      return true;
    })
    .sort((left, right) => left.label.localeCompare(right.label));
}

interface ImMessage {
  id: string;
  conversation_id: string;
  sender?: ImActorRef;
  sender_user_id?: string;
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
  bound_nodes?: string[];
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
  sender: ImActorRef;
  sender_user_id?: string;
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

interface ConversationPreviewSnapshot {
  preview: string;
  lastMessageAt?: string;
}

const conversationPreviewSnapshotById = new Map<string, ConversationPreviewSnapshot>();

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
const DIRECT_USER_SESSION_LABEL = "Direct teammate chat";
const GROUP_CHAT_SESSION_LABEL = "Group chat";
const DIRECT_AGENT_DISCOVERABILITY_HINT = "Reuse this stable direct chat for the same agent, or start a fresh session here when you need a new prompt snapshot.";
const DIRECT_USER_DISCOVERABILITY_HINT = "Direct conversation with one teammate.";
const DIRECT_USER_TARGET_LABEL = "Teammate";
const GROUP_CHAT_DISCOVERABILITY_HINT = "Group thread";
const GROUP_CHAT_TARGET_LABEL = "Shared thread";
const GROUP_CHAT_LIST_HINT = "Keep people and agents in one shared conversation timeline.";
const GROUP_CHAT_ENTRY_HINT = "Group chat";
const ENGINEERING_GROUP_OWNERSHIP_PATTERNS = [/^Using your main agent .+ready to chat\)$/i];
const AGENT_NETWORK_SESSION_LABEL = "Agent-to-agent direct chat";
const AGENT_NETWORK_DISCOVERABILITY_HINT = "Direct conversation between two agents in your workspace.";
const AGENT_NETWORK_TARGET_LABEL = "Agent pair";
const AGENT_NETWORK_LIST_HINT = "Review direct coordination between agents.";
const AGENT_NETWORK_ENTRY_HINT = "Agent-to-agent direct conversation.";
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

function resolveConversationKind(input: {
  title: string;
  conversation: ImConversation;
  participants: ImActorRef[];
  selfUserId: string;
}): ConversationKind {
  if (isMainAgentStarterTitle(input.title)) {
    return "direct-agent";
  }
  if (input.conversation.type === "group") {
    return "group";
  }
  const participants = input.participants;
  const hasAgent = participants.some((item) => item.type === "agent");
  const hasSelfUser = participants.some((item) => item.type === "user" && item.id === input.selfUserId);
  const allAgents = participants.length > 0 && participants.every((item) => item.type === "agent");
  if (allAgents) {
    return "agent-network";
  }
  if (hasAgent && hasSelfUser) {
    return "direct-agent";
  }
  if (participants.some((item) => item.type === "system")) {
    return "system";
  }
  return "direct-user";
}

function toConversationSemantics(input: {
  title: string;
  conversationKind: ConversationKind;
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
  if (input.conversationKind === "group") {
    return {
      kind_label: GROUP_CHAT_SESSION_LABEL,
      target_label: GROUP_CHAT_TARGET_LABEL,
      discoverability_hint: GROUP_CHAT_DISCOVERABILITY_HINT,
      ownership_label: sanitizeGroupOwnershipLabel(input.ownershipLabel)
    };
  }
  if (input.conversationKind === "agent-network") {
    return {
      kind_label: AGENT_NETWORK_SESSION_LABEL,
      target_label: AGENT_NETWORK_TARGET_LABEL,
      discoverability_hint: AGENT_NETWORK_DISCOVERABILITY_HINT,
      ownership_label: input.ownershipLabel ?? AGENT_NETWORK_ENTRY_HINT
    };
  }
  if (input.conversationKind === "direct-user") {
    return {
      kind_label: DIRECT_USER_SESSION_LABEL,
      target_label: DIRECT_USER_TARGET_LABEL,
      discoverability_hint: DIRECT_USER_DISCOVERABILITY_HINT,
      ownership_label: input.ownershipLabel ?? undefined
    };
  }
  return {
    kind_label: DIRECT_AGENT_SESSION_LABEL,
    target_label: undefined,
    discoverability_hint: DIRECT_AGENT_DISCOVERABILITY_HINT,
    ownership_label: input.ownershipLabel ?? undefined
  };
}

function buildListDiscoverabilityHint(input: { title: string; conversationKind: ConversationKind; fallback: string }): string {
  if (isMainAgentStarterTitle(input.title)) {
    return MAIN_AGENT_LIST_HINT;
  }
  if (input.conversationKind === "group") {
    return GROUP_CHAT_LIST_HINT;
  }
  if (input.conversationKind === "agent-network") {
    return AGENT_NETWORK_LIST_HINT;
  }
  return input.fallback;
}

function formatIdentityList(items: string[]): string {
  if (items.length === 0) {
    return "";
  }
  if (items.length <= 3) {
    return items.join(", ");
  }
  return `${items.slice(0, 3).join(", ")} +${items.length - 3}`;
}

function toConversationParticipantLabels(input: {
  participants: ImActorRef[];
  conversationKind: ConversationKind;
}): string[] {
  if (input.conversationKind === "group" || input.conversationKind === "agent-network") {
    return input.participants.map((participant) => toParticipantIdentityLabel(participant));
  }
  return input.participants.map((participant) => toParticipantDisplayName(participant));
}

function buildParticipantDiscoverabilityHint(input: {
  conversationKind: ConversationKind;
  participants: ImActorRef[];
  baseHint?: string;
}): string | undefined {
  const agentIdentities = input.participants
    .filter((item) => item.type === "agent")
    .map((item) => toParticipantIdentityLabel(item));
  const userIdentities = input.participants
    .filter((item) => item.type === "user")
    .map((item) => toParticipantIdentityLabel(item));
  if (input.conversationKind === "group") {
    const summary = [
      userIdentities.length > 0 ? `users: ${formatIdentityList(userIdentities)}` : "",
      agentIdentities.length > 0 ? `agents: ${formatIdentityList(agentIdentities)}` : ""
    ]
      .filter(Boolean)
      .join(" · ");
    if (!summary) {
      return input.baseHint;
    }
    const base = input.baseHint ? `${input.baseHint} ` : "";
    return `${base}Participants — ${summary}. Mentions support participant IDs (user_id / agent_id).`;
  }
  if (input.conversationKind === "agent-network" && agentIdentities.length > 0) {
    const base = input.baseHint ? `${input.baseHint} ` : "";
    return `${base}Agents — ${formatIdentityList(agentIdentities)}.`;
  }
  return input.baseHint;
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

function normalizeNodeIdList(nodeIds: string[] | null | undefined): string[] {
  if (!Array.isArray(nodeIds)) {
    return [];
  }
  return nodeIds
    .map((nodeId) => (typeof nodeId === "string" ? nodeId.trim() : ""))
    .filter((nodeId) => nodeId.length > 0);
}

export function pickDefaultNodeForSend(nodes: Array<Pick<ImNode, "node_id" | "status" | "relay_enabled" | "node_name">>) {
  return nodes.find((item) => item.relay_enabled && item.status === "online") ?? nodes.find((item) => item.relay_enabled) ?? null;
}

function resolveBoundNodeForAgent(input: { agent: ImAgent | undefined; nodes: ImNode[] }) {
  const boundNodeIds = normalizeNodeIdList(input.agent?.bound_nodes);
  if (boundNodeIds.length === 0) {
    return null;
  }
  const boundNodes = boundNodeIds.map(
    (nodeId) =>
      input.nodes.find((item) => item.node_id === nodeId) ?? {
        node_id: nodeId,
        node_name: nodeId,
        status: "offline",
        relay_enabled: false
      }
  );
  return pickDefaultNodeForSend(boundNodes) ?? boundNodes[0] ?? null;
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

function buildLegacyParticipantIds(input: { participants: ImActorRef[]; selfUserId: string; peerUserId?: string }): string[] {
  const ids: string[] = [];
  for (const participant of input.participants) {
    if (participant.type === "user") {
      ids.push(participant.id);
    }
  }
  if (!ids.includes(input.selfUserId)) {
    ids.unshift(input.selfUserId);
  }
  if (input.peerUserId && !ids.includes(input.peerUserId)) {
    ids.push(input.peerUserId);
  }
  return ids;
}

export function buildCreateMessageRequest(input: {
  selfUserId: string;
  content: string;
  attachments?: ChatAttachment[];
  targetNodeId: string | null;
}): CreateMessagePayload {
  const payload: CreateMessagePayload = {
    sender: {
      type: "user",
      id: input.selfUserId
    },
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

async function createConversationRaw(payload: {
  title: string;
  participants: ImActorRef[];
  participant_ids?: string[];
}) {
  return requestJson<ImConversation>("/im/v1/conversations", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

async function listMessagesRaw(conversationId: string, options?: { markAsRead?: boolean }) {
  const params = new URLSearchParams();
  if (options?.markAsRead) {
    params.set("mark_as_read", "true");
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  const payload = await requestJson<ItemsEnvelope<ImMessage> | ImMessage[]>(`/im/v1/conversations/${conversationId}/messages${suffix}`);
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
  peerUserId?: string;
  peerAgentId?: string;
  userById?: Map<string, ImUser>;
}): ImConversation | null {
  const userById = input.userById ?? new Map<string, ImUser>();
  const matches = input.conversations.filter((item) => {
    if (item.type === "group") {
      return false;
    }
    const participants = resolveConversationParticipants({
      conversation: item,
      userById
    });
    if (participants.length !== 2) {
      return false;
    }
    if (input.peerAgentId) {
      return (
        participants.some((participant) => participant.type === "user" && participant.id === input.selfUserId) &&
        participants.some((participant) => participant.type === "agent" && participant.id === input.peerAgentId)
      );
    }
    if (input.peerUserId) {
      return (
        participants.some((participant) => participant.type === "user" && participant.id === input.selfUserId) &&
        participants.some((participant) => participant.type === "user" && participant.id === input.peerUserId)
      );
    }
    return false;
  });
  if (matches.length === 0) {
    return null;
  }
  return [...matches].sort(compareConversationCreation)[0] ?? null;
}

function findStarterConversation(input: {
  conversations: ImConversation[];
  selfUserId: string;
  peerUserId: string;
  starterAgentId: string;
  userById: Map<string, ImUser>;
  starterTitle: string;
}): ImConversation | null {
  return (
    pickCanonicalDirectConversation({
      conversations: input.conversations,
      selfUserId: input.selfUserId,
      peerAgentId: input.starterAgentId,
      userById: input.userById
    }) ??
    pickCanonicalDirectConversation({
      conversations: input.conversations,
      selfUserId: input.selfUserId,
      peerUserId: input.peerUserId,
      userById: input.userById
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
      const [existingConversations, userById] = await Promise.all([listConversationsRaw(), loadUserMap()]);
      const starterConversation =
        findStarterConversation({
          conversations: existingConversations,
          selfUserId: self.id,
          peerUserId: starterPeer.id,
          starterAgentId: starterAgent.agent_id,
          userById,
          starterTitle
        }) ??
        (await createConversationRaw({
          title: starterTitle,
          participants: [
            { type: "user", id: self.id },
            { type: "agent", id: starterAgent.agent_id, display_name: starterAgent.display_name }
          ],
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
  conversationPreviewSnapshotById.clear();
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
  const resolvedSender =
    parseActorRef(input.message.sender) ??
    (input.message.sender_user_id
      ? {
          type: normalizeActorType(input.message.sender_type) ?? "user",
          id: input.message.sender_user_id
        }
      : null);
  const senderName =
    resolvedSender?.display_name ??
    (resolvedSender?.type === "user" ? input.userById.get(resolvedSender.id)?.display_name : undefined) ??
    resolvedSender?.id ??
    "Unknown";
  const isMine = resolvedSender?.type === "user" ? resolvedSender.id === input.selfUserId : false;
  return {
    message_id: input.message.id,
    sender_type:
      resolvedSender?.type === "agent" || resolvedSender?.type === "system"
        ? resolvedSender.type
        : input.message.sender_type === "agent" || input.message.sender_type === "system"
          ? input.message.sender_type
          : "user",
    sender_name: senderName,
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

function toMessagePreview(message: Pick<ImMessage, "content" | "attachments"> | null | undefined) {
  const content = message?.content?.trim();
  if (content) {
    return content;
  }
  const firstAttachmentName = message?.attachments?.[0]?.file_name?.trim();
  if (firstAttachmentName) {
    return firstAttachmentName;
  }
  return "";
}

function compareMessageRecency(left: ImMessage, right: ImMessage) {
  const leftTimestamp = Date.parse(left.created_at);
  const rightTimestamp = Date.parse(right.created_at);
  const leftHasTimestamp = Number.isFinite(leftTimestamp);
  const rightHasTimestamp = Number.isFinite(rightTimestamp);
  if (leftHasTimestamp && rightHasTimestamp && leftTimestamp !== rightTimestamp) {
    return leftTimestamp - rightTimestamp;
  }
  if (leftHasTimestamp !== rightHasTimestamp) {
    return leftHasTimestamp ? 1 : -1;
  }
  return left.id.localeCompare(right.id);
}

function pickLatestConversationMessage(messages: ImMessage[]) {
  if (messages.length === 0) {
    return null;
  }
  return [...messages].sort(compareMessageRecency).at(-1) ?? null;
}

function shouldApplyPreviewSnapshot(input: {
  current: ConversationPreviewSnapshot | undefined;
  next: ConversationPreviewSnapshot;
}) {
  if (!input.current) {
    return true;
  }
  const currentAt = input.current.lastMessageAt ?? "";
  const nextAt = input.next.lastMessageAt ?? "";
  if (nextAt && currentAt) {
    if (nextAt > currentAt) {
      return true;
    }
    if (nextAt < currentAt) {
      return false;
    }
  } else if (nextAt && !currentAt) {
    return true;
  } else if (!nextAt && currentAt) {
    return false;
  }
  const currentPreview = input.current.preview.trim();
  const nextPreview = input.next.preview.trim();
  if (!currentPreview && nextPreview) {
    return true;
  }
  if (currentPreview && !nextPreview) {
    return false;
  }
  return nextPreview.length >= currentPreview.length;
}

function updateConversationPreviewSnapshot(input: {
  conversationId: string;
  preview: string;
  lastMessageAt?: string;
}) {
  const next: ConversationPreviewSnapshot = {
    preview: input.preview,
    lastMessageAt: input.lastMessageAt
  };
  const current = conversationPreviewSnapshotById.get(input.conversationId);
  if (!shouldApplyPreviewSnapshot({ current, next })) {
    return;
  }
  conversationPreviewSnapshotById.set(input.conversationId, next);
}

function updateConversationPreviewFromMessages(input: {
  conversationId: string;
  messages: ImMessage[];
}) {
  const latest = pickLatestConversationMessage(input.messages);
  if (!latest) {
    return;
  }
  updateConversationPreviewSnapshot({
    conversationId: input.conversationId,
    preview: toMessagePreview(latest),
    lastMessageAt: latest.created_at
  });
}

export function getConversationPreviewSnapshot(conversationId: string): ConversationPreviewSnapshot | null {
  return conversationPreviewSnapshotById.get(conversationId) ?? null;
}

export function setConversationPreviewSnapshot(input: {
  conversationId: string;
  preview: string;
  lastMessageAt?: string;
}) {
  updateConversationPreviewSnapshot({
    conversationId: input.conversationId,
    preview: input.preview,
    lastMessageAt: input.lastMessageAt
  });
}

function toConversationSummary(input: {
  conversation: ImConversation;
  messages: ImMessage[];
  userById: Map<string, ImUser>;
  selfUserId: string;
  starterTitle: string;
  ownership: ChatOwnershipSummary;
}): ConversationSummary {
  const resolvedTitle = resolveConversationTitle({ conversation: input.conversation, starterTitle: input.starterTitle });
  const participants = resolveConversationParticipants({
    conversation: input.conversation,
    userById: input.userById
  });
  const conversationKind = resolveConversationKind({
    title: resolvedTitle,
    conversation: input.conversation,
    participants,
    selfUserId: input.selfUserId
  });
  const latest = pickLatestConversationMessage(input.messages);
  const unreadCount =
    typeof input.conversation.unread_count === "number" && Number.isFinite(input.conversation.unread_count)
      ? Math.max(0, Math.trunc(input.conversation.unread_count))
      : 0;
  const semantics = toConversationSemantics({
    title: resolvedTitle,
    conversationKind,
    ownershipLabel: input.ownership.ownershipLabel
  });
  const baseDiscoverabilityHint = buildListDiscoverabilityHint({
    title: resolvedTitle,
    conversationKind,
    fallback: semantics.discoverability_hint ?? ""
  });
  updateConversationPreviewSnapshot({
    conversationId: input.conversation.id,
    preview: toMessagePreview(latest),
    lastMessageAt: latest?.created_at
  });
  const previewSnapshot = getConversationPreviewSnapshot(input.conversation.id);
  return {
    conversation_id: input.conversation.id,
    title: resolvedTitle,
    last_message_preview: previewSnapshot?.preview ?? "",
    last_message_at: previewSnapshot?.lastMessageAt ?? latest?.created_at,
    unread_count: unreadCount,
    kind: conversationKind,
    participants: toConversationParticipantLabels({
      participants,
      conversationKind
    }),
    node_id: input.ownership.nodeId ?? undefined,
    node_label: input.ownership.nodeLabel ?? undefined,
    node_status: input.ownership.nodeStatus ?? undefined,
    agent_label: input.ownership.agentLabel ?? undefined,
    ownership_label: semantics.ownership_label,
    kind_label: semantics.kind_label,
    target_label: semantics.target_label,
    discoverability_hint: buildParticipantDiscoverabilityHint({
      conversationKind,
      participants,
      baseHint: baseDiscoverabilityHint
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
  const participants = resolveConversationParticipants({
    conversation: input.conversation,
    userById: input.userById
  });
  const conversationKind = resolveConversationKind({
    title: input.conversation.title,
    conversation: input.conversation,
    participants,
    selfUserId: input.selfUserId
  });
  if (conversationKind !== "direct-agent") {
    return undefined;
  }
  const agentParticipant = participants.find((participant) => participant.type === "agent");
  if (!agentParticipant) {
    return undefined;
  }
  return agentParticipant.id || undefined;
}

function resolveDirectConversationNodeState(input: {
  conversation: ImConversation;
  userById: Map<string, ImUser>;
  selfUserId: string;
  agentsById: Map<string, ImAgent>;
  nodes: ImNode[];
}) {
  const directAgentId = resolveDirectAgentId({
    conversation: input.conversation,
    userById: input.userById,
    selfUserId: input.selfUserId
  });
  if (!directAgentId) {
    return null;
  }
  const targetNode = resolveBoundNodeForAgent({
    agent: input.agentsById.get(directAgentId),
    nodes: input.nodes
  });
  if (!targetNode) {
    return {
      targetNodeId: null,
      targetNodeLabel: null,
      targetNodeStatus: null
    };
  }
  return {
    targetNodeId: targetNode.node_id,
    targetNodeLabel: targetNode.node_name ?? targetNode.node_id,
    targetNodeStatus: toNodeStatus(targetNode)
  };
}

function resolveConversationOwnershipForSummary(input: {
  conversation: ImConversation;
  userById: Map<string, ImUser>;
  selfUserId: string;
  defaultOwnership: ChatOwnershipSummary;
  agentsById: Map<string, ImAgent>;
  nodes: ImNode[];
}): ChatOwnershipSummary {
  const directNodeState = resolveDirectConversationNodeState({
    conversation: input.conversation,
    userById: input.userById,
    selfUserId: input.selfUserId,
    agentsById: input.agentsById,
    nodes: input.nodes
  });
  if (!directNodeState) {
    return input.defaultOwnership;
  }
  return {
    ...input.defaultOwnership,
    nodeId: directNodeState.targetNodeId,
    nodeLabel: directNodeState.targetNodeLabel,
    nodeStatus: directNodeState.targetNodeStatus
  };
}

async function resolveConversationSendNodeState(input: {
  conversationId: string;
  selfUserId: string;
  fallback: {
    targetNodeId: string | null;
    targetNodeStatus: string | null;
  };
}) {
  const [conversations, userById, agents, nodes] = await Promise.all([
    listConversationsRaw(),
    loadUserMap(),
    listAgentsRaw(),
    listNodesRaw()
  ]);
  const conversation = conversations.find((item) => item.id === input.conversationId);
  if (!conversation) {
    return input.fallback;
  }
  const directNodeState = resolveDirectConversationNodeState({
    conversation,
    userById,
    selfUserId: input.selfUserId,
    agentsById: new Map(agents.map((agent) => [agent.agent_id, agent])),
    nodes
  });
  if (!directNodeState) {
    return input.fallback;
  }
  return {
    targetNodeId: directNodeState.targetNodeId,
    targetNodeStatus: directNodeState.targetNodeStatus
  };
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
  const [conversations, userById, agents, nodes] = await Promise.all([
    listConversationsRaw(),
    loadUserMap(),
    listAgentsRaw(),
    listNodesRaw()
  ]);
  const agentsById = new Map(agents.map((agent) => [agent.agent_id, agent]));
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
        ownership: resolveConversationOwnershipForSummary({
          conversation: item.conversation,
          userById,
          selfUserId,
          defaultOwnership: ownership,
          agentsById,
          nodes
        })
      })
    )
    .sort((left, right) => (right.last_message_at ?? "").localeCompare(left.last_message_at ?? ""));
}

export async function listDiscoverableAgents(): Promise<DiscoverableAgent[]> {
  const { selfUserId } = await ensureBootstrap();
  const [agents, users, conversations] = await Promise.all([listAgentsRaw(), listUsersRaw(), listConversationsRaw()]);
  const userById = new Map(users.map((item) => [item.id, item]));
  const usersByUsername = new Map(users.map((item) => [item.username, item]));
  return agents.map((agent) => {
    const peer = usersByUsername.get(buildStarterPeerUsername(agent.agent_id));
    const existingConversation =
      pickCanonicalDirectConversation({
        conversations,
        selfUserId,
        peerAgentId: agent.agent_id,
        userById
      }) ??
      (peer
        ? pickCanonicalDirectConversation({
            conversations,
            selfUserId,
            peerUserId: peer.id,
            userById
          })
        : null);
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
  const [peer, conversations, userById] = await Promise.all([
    ensureUser(buildStarterPeerUsername(agent.agent_id), agent.display_name || agent.agent_id),
    listConversationsRaw(),
    loadUserMap()
  ]);
  const existing = pickCanonicalDirectConversation({
    conversations,
    selfUserId,
    peerAgentId: agent.agent_id,
    userById
  }) ?? pickCanonicalDirectConversation({
    conversations,
    selfUserId,
    peerUserId: peer.id,
    userById
  });
  if (existing) {
    return { conversation_id: existing.id };
  }
  const participants: ImActorRef[] = [
    { type: "user", id: selfUserId },
    { type: "agent", id: agent.agent_id, display_name: agent.display_name || agent.agent_id }
  ];
  const created = await createConversationRaw({
    title: agent.display_name || agent.agent_id,
    participants,
    participant_ids: buildLegacyParticipantIds({
      participants,
      selfUserId,
      peerUserId: peer.id
    })
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
  const participants: ImActorRef[] = [
    { type: "user", id: selfUserId },
    { type: "agent", id: agent.agent_id, display_name: agent.display_name || agent.agent_id }
  ];
  const created = await createConversationRaw({
    title: `${agent.display_name || agent.agent_id} · Fresh session`,
    participants,
    participant_ids: buildLegacyParticipantIds({
      participants,
      selfUserId,
      peerUserId: peer.id
    })
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
  const participants: ImActorRef[] = [
    { type: "user", id: selfUserId },
    ...participantIds.map<ImActorRef>((participantId) => {
      const user = userById.get(participantId);
      if (!user) {
        return { type: "user", id: participantId };
      }
      return toActorFromUser(user);
    })
  ];
  const created = await createConversationRaw({
    title,
    participants,
    participant_ids: buildLegacyParticipantIds({
      participants,
      selfUserId
    })
  });
  return { conversation_id: created.id };
}

export async function getConversation(conversationId: string): Promise<ConversationDetail | null> {
  const { selfUserId, starter } = await ensureBootstrap();
  const [conversations, userById, messages] = await Promise.all([
    listConversationsRaw(),
    loadUserMap(),
    listMessagesRaw(conversationId, { markAsRead: true })
  ]);
  const conversation = conversations.find((item) => item.id === conversationId);
  if (!conversation) {
    return null;
  }
  updateConversationPreviewFromMessages({ conversationId, messages });
  const resolvedTitle = resolveConversationTitle({ conversation, starterTitle: starter.title });
  const participants = resolveConversationParticipants({
    conversation,
    userById
  });
  const conversationKind = resolveConversationKind({
    title: resolvedTitle,
    conversation,
    participants,
    selfUserId
  });
  const semantics = toConversationSemantics({
    title: resolvedTitle,
    conversationKind,
    ownershipLabel: starter.statusLabel
  });
  const detailDiscoverabilityHint = buildParticipantDiscoverabilityHint({
    conversationKind,
    participants,
    baseHint: semantics.discoverability_hint
  });
  return {
    conversation_id: conversation.id,
    title: resolvedTitle,
    kind_label: semantics.kind_label,
    target_label: semantics.target_label,
    discoverability_hint: detailDiscoverabilityHint,
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
  const bootstrap = await ensureBootstrap();
  const sendNodeState = await resolveConversationSendNodeState({
    conversationId: input.conversationId,
    selfUserId: bootstrap.selfUserId,
    fallback: {
      targetNodeId: bootstrap.targetNodeId,
      targetNodeStatus: bootstrap.targetNodeStatus
    }
  });
  if (!isNodeReadyForSend({ targetNodeId: sendNodeState.targetNodeId, nodeStatus: sendNodeState.targetNodeStatus })) {
    throw new Error(SEND_FAILURE_UNAVAILABLE_HELPER);
  }
  const [created, userById] = await Promise.all([
    requestJson<ImMessage>(`/im/v1/conversations/${input.conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify(
        buildCreateMessageRequest({
          selfUserId: bootstrap.selfUserId,
          content: input.content,
          attachments: input.attachments,
          targetNodeId: null
        })
      )
    }),
    loadUserMap()
  ]);
  updateConversationPreviewSnapshot({
    conversationId: input.conversationId,
    preview: toMessagePreview(created),
    lastMessageAt: created.created_at
  });
  return toChatMessage({
    message: created,
    userById,
    selfUserId: bootstrap.selfUserId,
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

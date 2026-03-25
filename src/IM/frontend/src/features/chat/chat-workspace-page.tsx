import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { useIsMobile } from "../../hooks/use-is-mobile";
import { ConversationList } from "./components/conversation-list";
import { MessagePane } from "./components/message-pane";
import {
  createFreshDirectConversation,
  createGroupConversation,
  deleteConversation,
  getChatBootstrapState,
  getChatStarter,
  getConversation,
  getUsageMetrics,
  leaveConversation,
  listConversations,
  listDiscoverableGroupParticipants,
  renameConversation,
  resolveSendAvailability,
  sendMessage,
  streamConversationEvents,
  uploadAttachment
} from "./chat-api";
import {
  ChatAttachment,
  ChatBootstrapState,
  ChatMessage,
  ChatUsageView,
  ConversationDetail,
  ConversationSummary,
  UsageAgentView,
  UsageMetricRow,
  UsageTotals
} from "./types";

function toStatus(value: unknown): ChatMessage["delivery_status"] | undefined {
  if (value === "sent" || value === "running" || value === "completed" || value === "failed") {
    return value;
  }
  return undefined;
}

function toRecoveryActionLabel(status: ChatMessage["delivery_status"], senderType: ChatMessage["sender_type"]) {
  if (status !== "failed") {
    return undefined;
  }
  return senderType === "agent" ? "Retry request" : "Retry send";
}

function toRecoveryHint(input: { status: ChatMessage["delivery_status"]; senderType: ChatMessage["sender_type"] }) {
  if (input.status !== "failed") {
    return undefined;
  }
  return input.senderType === "agent"
    ? "The agent stopped before finishing this turn. Retry the request to ask the agent again."
    : "The message did not reach the relay. Retry after the connection is back.";
}

function toSenderType(value: unknown): ChatMessage["sender_type"] | undefined {
  if (value === "user" || value === "agent" || value === "system") {
    return value;
  }
  return undefined;
}

function toSenderName(input: {
  senderUserId: string | null;
  senderType: ChatMessage["sender_type"];
  selfUserId: string | undefined;
  fallback: string;
}) {
  if (input.senderUserId && input.selfUserId && input.senderUserId === input.selfUserId) {
    return "You";
  }
  if (input.senderUserId) {
    return input.senderUserId;
  }
  if (input.senderType === "agent") {
    return "Agent";
  }
  if (input.senderType === "system") {
    return "System";
  }
  return input.fallback;
}

function buildStreamMessage(input: {
  payload: Record<string, unknown>;
  selfUserId: string | undefined;
  fallbackSenderType: ChatMessage["sender_type"];
  fallbackStatus: ChatMessage["delivery_status"];
  fallbackSenderName: string;
  createdAt?: string;
  content: string;
}): ChatMessage | null {
  const messageId = toStringValue(input.payload.message_id);
  if (!messageId) {
    return null;
  }
  const senderUserId = toStringValue(input.payload.sender_user_id);
  const senderType = toSenderType(input.payload.sender_type) ?? input.fallbackSenderType;
  const deliveryStatus = toStatus(input.payload.delivery_status) ?? input.fallbackStatus;
  return {
    message_id: messageId,
    sender_type: senderType,
    sender_name: toSenderName({
      senderUserId,
      senderType,
      selfUserId: input.selfUserId,
      fallback: input.fallbackSenderName
    }),
    content: input.content,
    attachments: toAttachments(input.payload.attachments),
    created_at: input.createdAt ?? toStringValue(input.payload.created_at) ?? new Date().toISOString(),
    is_mine: senderUserId !== null && input.selfUserId !== undefined ? senderUserId === input.selfUserId : undefined,
    delivery_status: deliveryStatus,
    recovery_action_label: toRecoveryActionLabel(deliveryStatus, senderType),
    recovery_hint: toRecoveryHint({ status: deliveryStatus, senderType })
  };
}

function toStringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function isChatAttachment(value: ChatAttachment | null): value is ChatAttachment {
  return value !== null;
}

function toAttachments(value: unknown): ChatAttachment[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item): ChatAttachment | null => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const attachment = item as Record<string, unknown>;
      const url = toStringValue(attachment.url);
      if (!url) {
        return null;
      }
      return {
        url,
        file_name: toStringValue(attachment.file_name) ?? undefined,
        content_type: toStringValue(attachment.content_type) ?? undefined
      };
    })
    .filter(isChatAttachment);
}

export function sortMessagesChronologically(messages: ChatMessage[] | undefined) {
  return [...(messages ?? [])]
    .map((message, index) => ({ message, index }))
    .sort((left, right) => {
      const createdAtOrder = left.message.created_at.localeCompare(right.message.created_at);
      if (createdAtOrder !== 0) {
        return createdAtOrder;
      }
      return left.index - right.index;
    })
    .map(({ message }) => message);
}

function upsertMessage(messages: ChatMessage[], message: ChatMessage) {
  const existingIndex = messages.findIndex((item) => item.message_id === message.message_id);
  if (existingIndex === -1) {
    return sortMessagesChronologically([...messages, message]);
  }
  const existing = messages[existingIndex];
  const next = [...messages];
  next[existingIndex] = {
    ...existing,
    ...message,
    content:
      message.content.length >= existing.content.length || existing.content.length === 0 ? message.content : existing.content,
    attachments: message.attachments && message.attachments.length > 0 ? message.attachments : existing.attachments
  };
  return sortMessagesChronologically(next);
}

export function mergeMessages(baseMessages: ChatMessage[] | undefined, incomingMessages: ChatMessage[] | undefined) {
  return sortMessagesChronologically(
    (incomingMessages ?? []).reduce<ChatMessage[]>((messages, message) => upsertMessage(messages, message), [...(baseMessages ?? [])])
  );
}

export function normalizeConversationDetail(detail: ConversationDetail | null | undefined): ConversationDetail | null {
  if (!detail) {
    return null;
  }
  return {
    ...detail,
    messages: sortMessagesChronologically(detail.messages)
  };
}

function createConversationPlaceholder(conversationId: string, messages: ChatMessage[] = []): ConversationDetail {
  return {
    conversation_id: conversationId,
    title: "Conversation",
    mention_candidates: [],
    messages: sortMessagesChronologically(messages)
  };
}

export function mergeConversationDetail(
  detail: ConversationDetail | null | undefined,
  cachedDetail: ConversationDetail | null | undefined
): ConversationDetail | null {
  if (!detail && !cachedDetail) {
    return null;
  }
  if (!detail) {
    return normalizeConversationDetail(cachedDetail);
  }
  if (!cachedDetail) {
    return normalizeConversationDetail(detail);
  }
  return normalizeConversationDetail({
    ...cachedDetail,
    ...detail,
    mention_candidates: detail.mention_candidates ?? cachedDetail.mention_candidates,
    messages: mergeMessages(detail.messages, cachedDetail.messages)
  });
}

function isDirectAgentConversation(summary: ConversationSummary | null | undefined) {
  return summary?.kind === "direct-agent" || summary?.kind_label === "Direct agent chat";
}

function resolveConversationSendNodeState(input: {
  conversationId?: string;
  conversations: ConversationSummary[];
  bootstrap: ChatBootstrapState | null;
}) {
  const fallback = {
    targetNodeId: input.bootstrap?.targetNodeId ?? null,
    nodeStatus: input.bootstrap?.targetNodeStatus ?? null
  };
  if (!input.conversationId) {
    return fallback;
  }
  const activeConversation = input.conversations.find((item) => item.conversation_id === input.conversationId);
  if (!isDirectAgentConversation(activeConversation)) {
    return fallback;
  }
  const hasExplicitNodeState =
    (activeConversation && Object.prototype.hasOwnProperty.call(activeConversation, "node_id")) ||
    (activeConversation && Object.prototype.hasOwnProperty.call(activeConversation, "node_label")) ||
    (activeConversation && Object.prototype.hasOwnProperty.call(activeConversation, "node_status"));
  if (!hasExplicitNodeState) {
    return fallback;
  }
  return {
    targetNodeId: activeConversation?.node_id ?? activeConversation?.node_label ?? null,
    nodeStatus: activeConversation?.node_status ?? null
  };
}

function upsertConversationMessage(
  detail: ConversationDetail | null | undefined,
  conversationId: string,
  message: ChatMessage
): ConversationDetail {
  const base = detail ?? createConversationPlaceholder(conversationId);
  return {
    ...base,
    messages: upsertMessage(base.messages, message)
  };
}

function updateConversationList(
  items: ConversationSummary[] | undefined,
  conversationId: string,
  patch: Partial<ConversationSummary>
) {
  if (!items) {
    return items;
  }
  return items.map((item) => (item.conversation_id === conversationId ? { ...item, ...patch } : item));
}

export function toUsageTotals(rows: UsageMetricRow[] | undefined): UsageTotals {
  return (rows ?? []).reduce<UsageTotals>(
    (totals, row) => ({
      turns: totals.turns + row.turns,
      promptTokens: totals.promptTokens + row.prompt_tokens,
      completionTokens: totals.completionTokens + row.completion_tokens,
      totalTokens: totals.totalTokens + row.total_tokens
    }),
    {
      turns: 0,
      promptTokens: 0,
      completionTokens: 0,
      totalTokens: 0
    }
  );
}

function rowsForScope(rows: UsageMetricRow[] | undefined, scope: string) {
  return (rows ?? []).filter((row) => row.scope === scope);
}

export function buildUsageView(input: {
  conversationRows: UsageMetricRow[] | undefined;
  workspaceRows: UsageMetricRow[] | undefined;
}): ChatUsageView {
  const conversationRows = rowsForScope(input.conversationRows, "conversation");
  const workspaceRows = rowsForScope(input.workspaceRows, "owner");
  const agents = rowsForScope(input.conversationRows, "agent").map<UsageAgentView>((row) => ({
    agentId: row.agent_id ?? "unknown-agent",
    label: row.agent_id ?? "Unknown agent",
    totals: toUsageTotals([row])
  }));
  return {
    conversation: toUsageTotals(conversationRows),
    workspace: toUsageTotals(workspaceRows),
    agents
  };
}

export function shouldRefreshUsageForEvent(eventType: string) {
  return ["message.sent", "relay.report", "relay.completed", "message.delivered", "turn_end", "message_status"].includes(eventType);
}

function refreshUsageQueries(input: {
  conversationId: string | undefined;
  ownerId: string | undefined;
  queryClient: ReturnType<typeof useQueryClient>;
}) {
  if (input.conversationId) {
    input.queryClient.invalidateQueries({ queryKey: ["chat", "usage", "conversation", input.conversationId] });
  }
  if (input.ownerId) {
    input.queryClient.invalidateQueries({ queryKey: ["chat", "usage", "workspace", input.ownerId] });
  }
}

function isSuppressedNoReplyReceipt(eventType: string, detail: string | null) {
  return (
    (eventType === "relay.completed" || eventType === "message.delivered") &&
    detail?.includes("suppressed_by=no_reply_token")
  );
}

function isNoReplyProtocolToken(value: string | null) {
  return value?.trim() === "NO_REPLY";
}

function toRelaySenderIdentity(payload: Record<string, unknown>, fallback?: { sender_name?: string; sender_display_name?: string }) {
  const senderDisplayName =
    toStringValue(payload.sender_display_name) ??
    toStringValue(payload.display_name) ??
    toStringValue(payload.agent_display_name) ??
    fallback?.sender_display_name ??
    undefined;
  const agentId = toStringValue(payload.agent_id);
  const nodeId = toStringValue(payload.node_id);
  return {
    sender_display_name: senderDisplayName,
    sender_name: agentId ?? fallback?.sender_name ?? nodeId ?? "Agent"
  };
}

function toRelayIdentityToken(payload: Record<string, unknown>, fallbackIdentity?: string) {
  const agentId = toStringValue(payload.agent_id);
  if (agentId) {
    return agentId;
  }
  const relayTaskId = toStringValue(payload.relay_task_id);
  if (relayTaskId) {
    return relayTaskId;
  }
  return fallbackIdentity ?? null;
}

function toRelaySyntheticMessageId(payload: Record<string, unknown>, fallbackIdentity?: string) {
  const messageId = toStringValue(payload.message_id);
  if (!messageId) {
    return null;
  }
  // Prefer relay_task_id (unique per turn) over agent_id (shared across all turns by the same agent).
  // relay.report and relay.processing events are server-enriched with relay_task_id from relay.accepted;
  // relay.completed and message.delivered carry relay_task_id natively.
  const relayTaskId = toStringValue(payload.relay_task_id);
  if (relayTaskId) {
    return `${messageId}:relay:${relayTaskId}`;
  }
  const identityToken = toRelayIdentityToken(payload, fallbackIdentity);
  return identityToken ? `${messageId}:agent:${identityToken}` : `${messageId}:agent`;
}

function parseRelayRunId(payload: Record<string, unknown>) {
  const directRunId = toStringValue(payload.run_id);
  if (directRunId) {
    return directRunId;
  }
  const detail = toStringValue(payload.detail);
  if (!detail) {
    return null;
  }
  const match = /^run_id=(.+)$/.exec(detail.trim());
  return match?.[1]?.trim() || null;
}

export function toRelayAgentMessage(event: {
  eventType: string;
  payload: Record<string, unknown>;
  identityHint?: string;
  senderHint?: { sender_name?: string; sender_display_name?: string };
}): ChatMessage | null {
  if (toSenderType(event.payload.sender_type)) {
    return null;
  }
  const syntheticMessageId = toRelaySyntheticMessageId(event.payload, event.identityHint);
  if (!syntheticMessageId) {
    return null;
  }
  const detail = toStringValue(event.payload.detail);
  if (isSuppressedNoReplyReceipt(event.eventType, detail)) {
    return null;
  }
  const content =
    toStringValue(event.payload.summary) ??
    detail ??
    toStringValue(event.payload.content);
  if (!content || isNoReplyProtocolToken(content)) {
    return null;
  }
  const status =
    event.eventType === "relay.processing"
      ? "running"
      : event.eventType === "relay.failed"
        ? "failed"
        : "completed";
  const senderIdentity = toRelaySenderIdentity(event.payload, event.senderHint);
  return {
    message_id: syntheticMessageId,
    sender_type: "agent",
    sender_name: senderIdentity.sender_name,
    sender_display_name: senderIdentity.sender_display_name,
    is_mine: false,
    content,
    created_at: toStringValue(event.payload.created_at) ?? new Date().toISOString(),
    delivery_status: status,
    recovery_action_label: toRecoveryActionLabel(status, "agent"),
    recovery_hint: toRecoveryHint({ status, senderType: "agent" })
  };
}

export function ChatWorkspacePage() {
  const { conversationId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const queryClient = useQueryClient();
  const [isCreatingGroupChat, setIsCreatingGroupChat] = useState(false);
  const [selectedGroupParticipantIds, setSelectedGroupParticipantIds] = useState<string[]>([]);
  // M235: optional custom group name input; blank = auto-generate from participant labels.
  const [groupNameDraft, setGroupNameDraft] = useState("");
  const relayRunIdentityRef = useRef<Map<string, { identity: string; sender_name?: string; sender_display_name?: string }>>(new Map());

  const bootstrapQuery = useQuery<ChatBootstrapState>({
    queryKey: ["chat", "bootstrap"],
    queryFn: async () => (await getChatBootstrapState()) as ChatBootstrapState
  });

  const conversationsQuery = useQuery({
    queryKey: ["chat", "conversations"],
    queryFn: listConversations
  });

  const starterQuery = useQuery({
    queryKey: ["chat", "starter"],
    queryFn: getChatStarter
  });

  const discoverableGroupParticipantsQuery = useQuery({
    enabled: isCreatingGroupChat,
    queryKey: ["chat", "discoverable-group-participants"],
    queryFn: listDiscoverableGroupParticipants
  });

  const detailQuery = useQuery({
    enabled: Boolean(conversationId),
    queryKey: ["chat", "conversation", conversationId],
    queryFn: async () => {
      const detail = await getConversation(conversationId!);
      return mergeConversationDetail(
        detail,
        queryClient.getQueryData<ConversationDetail | null>(["chat", "conversation", conversationId])
      );
    }
  });

  const conversationUsageQuery = useQuery({
    enabled: Boolean(conversationId),
    queryKey: ["chat", "usage", "conversation", conversationId],
    queryFn: () => getUsageMetrics({ conversationId: conversationId! }),
    refetchOnMount: "always"
  });

  const workspaceUsageQuery = useQuery({
    enabled: Boolean(bootstrapQuery.data?.ownerId),
    queryKey: ["chat", "usage", "workspace", bootstrapQuery.data?.ownerId, conversationId ?? "workspace-home"],
    queryFn: () => getUsageMetrics({ ownerId: bootstrapQuery.data!.ownerId }),
    refetchOnMount: "always"
  });
  const ownerId = bootstrapQuery.data?.ownerId;
  const selfUserId = bootstrapQuery.data?.selfUserId;
  const boundSelfUserId =
    location.state && typeof location.state === "object" && "boundSelfUserId" in location.state
      ? toStringValue((location.state as { boundSelfUserId?: unknown }).boundSelfUserId)
      : null;

  useEffect(() => {
    relayRunIdentityRef.current.clear();
  }, [conversationId]);

  useEffect(() => {
    if (!conversationId) {
      return;
    }
    queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) =>
      updateConversationList(previous, conversationId, { unread_count: 0 })
    );
  }, [conversationId, conversationsQuery.data, queryClient]);

  useEffect(() => {
    if (!conversationId) {
      return;
    }
    return streamConversationEvents({
      conversationId,
      onEvent: (event) => {
        const messageId = toStringValue(event.payload.message_id);
        if (!messageId) {
          return;
        }

        if (event.eventType === "message.sent") {
          const createdAt = toStringValue(event.payload.created_at) ?? new Date().toISOString();
          const content = toStringValue(event.payload.content) ?? "";
          const nextMessage = buildStreamMessage({
            payload: event.payload as Record<string, unknown>,
            selfUserId,
            fallbackSenderType: "user",
            fallbackStatus: "sent",
            fallbackSenderName: "Participant",
            createdAt,
            content
          });
          if (!nextMessage) {
            return;
          }
          queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) =>
            upsertConversationMessage(previous, conversationId, nextMessage)
          );
          refreshUsageQueries({ conversationId, ownerId, queryClient });
          return;
        }

        if (event.eventType === "message.delivered" && toSenderType(event.payload.sender_type)) {
          queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) => {
            const base = previous ?? createConversationPlaceholder(conversationId);
            const existing = base.messages.find((item) => item.message_id === messageId);
            const deliveredMessage = buildStreamMessage({
              payload: event.payload as Record<string, unknown>,
              selfUserId,
              fallbackSenderType: existing?.sender_type ?? "user",
              fallbackStatus: "completed",
              fallbackSenderName: existing?.sender_name ?? "Participant",
              createdAt: existing?.created_at,
              content: toStringValue(event.payload.content) ?? existing?.content ?? ""
            });
            if (!deliveredMessage) {
              return previous ?? base;
            }
            return {
              ...base,
              messages: upsertMessage(base.messages, {
                ...existing,
                ...deliveredMessage,
                delivery_status: "completed"
              })
            };
          });
          refreshUsageQueries({ conversationId, ownerId, queryClient });
          return;
        }

        if (event.eventType === "relay.accepted") {
          const relayPayload = event.payload as Record<string, unknown>;
          const runId = parseRelayRunId(relayPayload);
          const identity = toRelayIdentityToken(relayPayload);
          if (runId && identity) {
            const senderIdentity = toRelaySenderIdentity(relayPayload);
            relayRunIdentityRef.current.set(runId, {
              identity,
              sender_name: senderIdentity.sender_name,
              sender_display_name: senderIdentity.sender_display_name
            });
          }
          return;
        }

        if (
          event.eventType === "relay.processing" ||
          event.eventType === "relay.report" ||
          event.eventType === "relay.completed" ||
          event.eventType === "relay.failed" ||
          event.eventType === "message.delivered"
        ) {
          const relayPayload = event.payload as Record<string, unknown>;
          const relayRunId = parseRelayRunId(relayPayload);
          const relayIdentity = relayRunId ? relayRunIdentityRef.current.get(relayRunId) : undefined;
          const nextMessage = toRelayAgentMessage({
            eventType: event.eventType,
            payload: relayPayload,
            identityHint: relayIdentity?.identity,
            senderHint: relayIdentity
          });
          if (!nextMessage) {
            return;
          }
          queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) =>
            upsertConversationMessage(previous, conversationId, nextMessage)
          );
          queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) =>
            updateConversationList(previous, conversationId, {
              last_message_preview: nextMessage.content,
              last_message_at: nextMessage.created_at
            })
          );
          if (shouldRefreshUsageForEvent(event.eventType)) {
            refreshUsageQueries({ conversationId, ownerId, queryClient });
          }
          return;
        }

        if (event.eventType === "message_created") {
          const createdAt = toStringValue(event.payload.created_at) ?? new Date().toISOString();
          const content = toStringValue(event.payload.content) ?? "";
          const nextMessage = buildStreamMessage({
            payload: event.payload as Record<string, unknown>,
            selfUserId,
            fallbackSenderType: "user",
            fallbackStatus: "running",
            fallbackSenderName: "Participant",
            createdAt,
            content
          });
          if (!nextMessage) {
            return;
          }
          queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) =>
            upsertConversationMessage(previous, conversationId, nextMessage)
          );
          if (content) {
            queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) =>
              updateConversationList(previous, conversationId, {
                last_message_preview: content,
                last_message_at: createdAt
              })
            );
          }
          return;
        }

        if (event.eventType === "text_delta") {
          const delta = toStringValue(event.payload.delta) ?? "";
          if (!delta) {
            return;
          }
          queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) => {
            const base = previous ?? createConversationPlaceholder(conversationId);
            const existing = base.messages.find((item) => item.message_id === messageId);
            const seededMessage = buildStreamMessage({
              payload: event.payload as Record<string, unknown>,
              selfUserId,
              fallbackSenderType: existing?.sender_type ?? "user",
              fallbackStatus: "running",
              fallbackSenderName: existing?.sender_name ?? "Participant",
              content: `${existing?.content ?? ""}${delta}`
            });
            if (!seededMessage) {
              return previous ?? base;
            }
            const nextMessage: ChatMessage = existing
              ? {
                  ...existing,
                  ...seededMessage,
                  attachments: existing.attachments,
                  content: `${existing.content}${delta}`,
                  delivery_status: "running"
                }
              : seededMessage;
            return {
              ...base,
              messages: upsertMessage(base.messages, nextMessage)
            };
          });
          queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) => {
            const active = previous?.find((item) => item.conversation_id === conversationId);
            if (!active) {
              return previous;
            }
            return updateConversationList(previous, conversationId, {
              last_message_preview: `${active.last_message_preview ?? ""}${delta}`,
              last_message_at: new Date().toISOString()
            });
          });
          return;
        }

        if (event.eventType === "turn_end" || event.eventType === "message_status" || event.eventType === "conversation.notice") {
          const status = toStatus(event.payload.status) ?? "completed";
          const content = toStringValue(event.payload.content);
          queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) => {
            if (!previous) {
              return null;
            }
            const existing = previous.messages.find((item) => item.message_id === messageId);
            if (!existing) {
              return previous;
            }
            const nextMessage: ChatMessage = {
              ...existing,
              content: content ?? existing.content,
              delivery_status: status,
              recovery_action_label: toRecoveryActionLabel(status, existing.sender_type),
              recovery_hint: toRecoveryHint({ status, senderType: existing.sender_type })
            };
            return {
              ...previous,
              messages: upsertMessage(previous.messages, nextMessage)
            };
          });
          if (content) {
            queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) =>
              updateConversationList(previous, conversationId, {
                last_message_preview: content,
                last_message_at: new Date().toISOString()
              })
            );
          }
          if (shouldRefreshUsageForEvent(event.eventType)) {
            refreshUsageQueries({ conversationId, ownerId, queryClient });
          }
        }
      }
    });
  }, [conversationId, ownerId, queryClient, selfUserId]);

  const createGroupConversationMutation = useMutation({
    mutationFn: (payload: { participantIds: string[]; participantLabels: string[]; groupName?: string }) =>
      createGroupConversation({ participantIds: payload.participantIds, groupName: payload.groupName }),
    onSuccess: async ({ conversation_id }, variables) => {
      const detail = await getConversation(conversation_id);
      queryClient.setQueryData(["chat", "conversation", conversation_id], detail);
      if (detail) {
        queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) => {
          const existing = previous ?? [];
          if (existing.some((item) => item.conversation_id === conversation_id)) {
            return existing;
          }
          return [
            {
              conversation_id,
              title: detail.title,
              last_message_preview: detail.messages.at(-1)?.content ?? "",
              last_message_at: detail.messages.at(-1)?.created_at,
              unread_count: 0,
              participants: ["You", ...variables.participantLabels],
              kind_label: detail.kind_label,
              target_label: detail.target_label,
              discoverability_hint: detail.discoverability_hint
            },
            ...existing
          ];
        });
      }
      setSelectedGroupParticipantIds([]);
      setGroupNameDraft("");
      setIsCreatingGroupChat(false);
      navigate(`/chat/${conversation_id}`);
      void queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
    }
  });

  const createFreshDirectConversationMutation = useMutation({
    mutationFn: (agentId: string) => createFreshDirectConversation({ agentId }),
    onSuccess: async ({ conversation_id }) => {
      const detail = await getConversation(conversation_id);
      queryClient.setQueryData(["chat", "conversation", conversation_id], detail);
      navigate(`/chat/${conversation_id}`);
      void queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
    }
  });

  // M234: remove conversation from cache then navigate home.
  function removeConversationFromCache(targetConversationId: string) {
    queryClient.setQueryData<ConversationSummary[] | undefined>(
      ["chat", "conversations"],
      (previous) => previous?.filter((item) => item.conversation_id !== targetConversationId)
    );
    queryClient.removeQueries({ queryKey: ["chat", "conversation", targetConversationId], exact: true });
    if (conversationId === targetConversationId) {
      navigate("/chat");
    }
  }

  const leaveConversationMutation = useMutation({
    mutationFn: (payload: { conversationId: string; userId: string }) =>
      leaveConversation({ conversationId: payload.conversationId, userId: payload.userId }),
    onSuccess: (_data, variables) => {
      removeConversationFromCache(variables.conversationId);
      void queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
    }
  });

  const deleteConversationMutation = useMutation({
    mutationFn: (payload: { conversationId: string; requesterId: string }) =>
      deleteConversation({ conversationId: payload.conversationId, requesterId: payload.requesterId }),
    onSuccess: (_data, variables) => {
      removeConversationFromCache(variables.conversationId);
      void queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
    }
  });

  const sendMutation = useMutation({
    mutationFn: (payload: { content: string; attachments: ChatAttachment[] }) =>
      sendMessage({ conversationId: conversationId!, content: payload.content, attachments: payload.attachments }),
    onSuccess: (message) => {
      if (!conversationId) {
        return;
      }
      queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) => {
        if (!previous) {
          return {
            conversation_id: conversationId,
            title: "Conversation",
            messages: [message]
          };
        }
        return {
          ...previous,
          messages: upsertMessage(previous.messages, message)
        };
      });
      queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) =>
        updateConversationList(previous, conversationId, {
          last_message_preview: message.content || message.attachments?.[0]?.file_name || "Attachment",
          last_message_at: message.created_at
        })
      );
      refreshUsageQueries({ conversationId, ownerId, queryClient });
    }
  });

  useEffect(() => {
    if (!boundSelfUserId || !selfUserId || boundSelfUserId === selfUserId || bootstrapQuery.isLoading) {
      return;
    }
    void queryClient.invalidateQueries({ queryKey: ["chat", "bootstrap"] });
    void queryClient.invalidateQueries({ queryKey: ["chat", "starter"] });
    void queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
    if (conversationId) {
      queryClient.removeQueries({ queryKey: ["chat", "conversation", conversationId], exact: true });
    }
    navigate(location.pathname, { replace: true, state: null });
  }, [boundSelfUserId, bootstrapQuery.isLoading, conversationId, location.pathname, navigate, queryClient, selfUserId]);

  if (
    bootstrapQuery.isLoading ||
    conversationsQuery.isLoading ||
    starterQuery.isLoading ||
    (Boolean(conversationId) && detailQuery.isLoading)
  ) {
    return <section className="im-card flex w-full items-center justify-center">Loading chat...</section>;
  }

  const conversations = conversationsQuery.data ?? [];
  const starter = starterQuery.data ?? null;
  const detail = (detailQuery.data ?? null) as ConversationDetail | null;
  const bootstrap = bootstrapQuery.data ?? null;
  const sendNodeState = resolveConversationSendNodeState({
    conversationId,
    conversations,
    bootstrap
  });
  const usage = buildUsageView({
    conversationRows: conversationUsageQuery.data,
    workspaceRows: workspaceUsageQuery.data
  });
  const sendAvailability = resolveSendAvailability({
    targetNodeId: sendNodeState.targetNodeId,
    nodeStatus: sendNodeState.nodeStatus
  });
  const groupParticipantOptions = discoverableGroupParticipantsQuery.data ?? [];
  const selectedGroupParticipants = groupParticipantOptions.filter((item) => selectedGroupParticipantIds.includes(item.user_id));
  const remainingParticipantsNeeded = Math.max(0, 2 - selectedGroupParticipants.length);
  const canCreateGroupChat = remainingParticipantsNeeded === 0 && !createGroupConversationMutation.isPending;
  // M234: determine group creator so the dissolve button appears only for them.
  const isGroupCreator = Boolean(detail?.creator_id && selfUserId && detail.creator_id === selfUserId);

  // M234: handlers wired to leave/delete mutations; only shown for group conversations.
  const isGroupConversation = detail?.kind_label === "Group chat";
  const handleLeaveConversation = isGroupConversation && selfUserId
    ? (targetConversationId: string) =>
        leaveConversationMutation.mutateAsync({ conversationId: targetConversationId, userId: selfUserId })
    : undefined;
  const handleDeleteConversation = isGroupConversation && selfUserId
    ? (targetConversationId: string) =>
        deleteConversationMutation.mutateAsync({ conversationId: targetConversationId, requesterId: selfUserId })
    : undefined;

  // M235: inline group rename handler; optimistically updates sidebar list and conversation cache.
  const handleRenameConversation = isGroupConversation
    ? async (targetConversationId: string, newTitle: string) => {
        const { title: confirmedTitle } = await renameConversation({ conversationId: targetConversationId, title: newTitle });
        // Optimistically update conversation detail cache.
        queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", targetConversationId], (previous) =>
          previous ? { ...previous, title: confirmedTitle } : previous
        );
        // Update sidebar list.
        queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) =>
          updateConversationList(previous, targetConversationId, { title: confirmedTitle })
        );
      }
    : undefined;

  if (isMobile && conversationId) {
    return (
      <div className="w-full">
        <MessagePane
          detail={detail}
          starter={null}
          isMobile={isMobile}
          isSending={sendMutation.isPending}
          isStartingFreshSession={createFreshDirectConversationMutation.isPending}
          sendAvailability={sendAvailability}
          usage={usage}
          onSend={(payload) => sendMutation.mutateAsync(payload)}
          onStartFreshSession={
            detail?.direct_agent_id
              ? (agentId) => createFreshDirectConversationMutation.mutateAsync(agentId)
              : undefined
          }
          onUploadAttachment={uploadAttachment}
          onLeaveConversation={handleLeaveConversation}
          onDeleteConversation={handleDeleteConversation}
          isGroupCreator={isGroupCreator}
          onRenameConversation={handleRenameConversation}
        />
      </div>
    );
  }

  const groupChatPanel = isCreatingGroupChat ? (
    <section className="im-card rounded-2xl border border-[var(--im-border)] bg-slate-50 px-4 py-4 text-sm text-slate-700">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Group chat</p>
          <h2 className="im-title mt-1 text-lg font-bold">Select participants</h2>
          <p className="mt-1 text-xs text-slate-500">
            Create a shared thread with multiple agents or teammates, then enter the conversation from the list.
          </p>
        </div>
        <button
          type="button"
          className="im-btn im-btn-muted"
          onClick={() => {
            setSelectedGroupParticipantIds([]);
            setGroupNameDraft("");
            setIsCreatingGroupChat(false);
          }}
        >
          Cancel
        </button>
      </div>
      {/* M235: optional custom group name input */}
      <div className="mt-4">
        <label className="block text-xs font-semibold text-slate-700" htmlFor="group-name-input">
          群聊名称（可选）
        </label>
        <input
          id="group-name-input"
          type="text"
          className="im-input mt-1 w-full"
          placeholder="留空则自动生成"
          value={groupNameDraft}
          onChange={(e) => setGroupNameDraft(e.target.value)}
          maxLength={100}
        />
      </div>
      <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-xs text-slate-600">
        <p className="font-semibold text-slate-900">Selected participants</p>
        <p className="mt-1">
          {selectedGroupParticipants.length === 0
            ? "No participants selected yet. Pick at least two people or agents to create a real group chat."
            : `${selectedGroupParticipants.length} participant${selectedGroupParticipants.length === 1 ? "" : "s"} selected.`}
        </p>
        {selectedGroupParticipants.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedGroupParticipants.map((participant) => (
              <span key={participant.user_id} className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-700">
                {participant.label}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="mt-4">
        {discoverableGroupParticipantsQuery.isLoading ? (
          <div className="rounded-2xl border border-[var(--im-border)] bg-white px-4 py-6 text-center text-sm text-slate-500">
            Loading available participants...
          </div>
        ) : groupParticipantOptions.length === 0 ? (
          <div className="rounded-2xl border border-[var(--im-border)] bg-white px-4 py-6 text-center text-sm text-slate-500">
            No available participants yet. Add a teammate or configure another agent to start a shared thread.
          </div>
        ) : (
          // 候选列表固定最大高度并启用内部滚动，防止候选项过多时将左栏 ConversationList 推出视口。
          <div className="max-h-60 overflow-y-auto">
            <div className="grid gap-3">
              {groupParticipantOptions.map((participant) => {
                const checked = selectedGroupParticipantIds.includes(participant.user_id);
                return (
                  <label
                    key={participant.user_id}
                    className={`flex cursor-pointer items-start gap-3 rounded-2xl border px-4 py-3 transition ${
                      checked ? "border-[#9bd2d6] bg-[#eef8f8]" : "border-[var(--im-border)] bg-white hover:border-slate-300"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 rounded border-slate-300 text-emerald-700"
                      checked={checked}
                      onChange={() => {
                        setSelectedGroupParticipantIds((previous) =>
                          previous.includes(participant.user_id)
                            ? previous.filter((item) => item !== participant.user_id)
                            : [...previous, participant.user_id]
                        );
                      }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-slate-900">{participant.label}</span>
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                          {participant.kind === "agent" ? "Agent" : "Teammate"}
                        </span>
                        {checked && (
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">Selected</span>
                        )}
                      </div>
                      {participant.description && <p className="mt-1 text-xs text-slate-500">{participant.description}</p>}
                    </div>
                  </label>
                );
              })}
            </div>
          </div>
        )}
      </div>
      <div className="mt-4 flex flex-col gap-3 border-t border-[var(--im-border)] pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-slate-500">
          {remainingParticipantsNeeded > 0
            ? `Select ${remainingParticipantsNeeded} more participant${remainingParticipantsNeeded === 1 ? "" : "s"} to create a group chat.`
            : `Ready to create a group chat with ${selectedGroupParticipants.length} selected participants plus you.`}
        </p>
        <button
          type="button"
          className="im-btn im-btn-primary"
          disabled={!canCreateGroupChat}
          onClick={() =>
            createGroupConversationMutation.mutate({
              participantIds: selectedGroupParticipants.map((item) => item.user_id),
              participantLabels: selectedGroupParticipants.map((item) => item.label),
              // M235: pass custom group name; empty string means auto-generate.
              groupName: groupNameDraft
            })
          }
        >
          {createGroupConversationMutation.isPending ? "Creating group chat..." : "Create selected group chat"}
        </button>
      </div>
    </section>
  ) : null;

  return (
    <section className="grid h-full w-full min-h-0 gap-4 lg:grid-cols-[360px_1fr]">
      <div className="flex min-h-0 flex-col gap-4">
        {isMobile && !conversationId && starter && (
          <MessagePane
            detail={null}
            starter={starter}
            isMobile={isMobile}
            isSending={false}
            isStartingFreshSession={false}
            sendAvailability={sendAvailability}
            usage={usage}
            onSend={async () => undefined}
            onUploadAttachment={uploadAttachment}
          />
        )}
        {groupChatPanel}
        <ConversationList
          items={conversations}
          activeId={conversationId}
          compact={isMobile}
          onCreateGroupChat={() => {
            setSelectedGroupParticipantIds([]);
            setGroupNameDraft("");
            setIsCreatingGroupChat(true);
          }}
        />
      </div>
      {!isMobile && (
        <MessagePane
          detail={detail}
          starter={conversationId ? null : starter}
          isMobile={isMobile}
          isSending={sendMutation.isPending}
          isStartingFreshSession={createFreshDirectConversationMutation.isPending}
          sendAvailability={sendAvailability}
          usage={usage}
          onSend={(payload) => sendMutation.mutateAsync(payload)}
          onStartFreshSession={
            detail?.direct_agent_id
              ? (agentId) => createFreshDirectConversationMutation.mutateAsync(agentId)
              : undefined
          }
          onUploadAttachment={uploadAttachment}
          onLeaveConversation={handleLeaveConversation}
          onDeleteConversation={handleDeleteConversation}
          isGroupCreator={isGroupCreator}
          onRenameConversation={handleRenameConversation}
        />
      )}
    </section>
  );
}

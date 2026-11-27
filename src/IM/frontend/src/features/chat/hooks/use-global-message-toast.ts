import { mentionNameMap, mentionPlainText } from "../components/mention-parser";
import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import type { Conversation } from "../chat-types";
import { getConversation, listConversations } from "../chat-api";
import { i18n } from "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import { subscribeUserStream, type UserStreamEvent } from "../../../realtime/user-stream";
import {
  type AgentCompletionCandidate,
  type AgentCompletionState,
  emptyAgentCompletionState,
  hasInteractiveCard,
  hydrateAgentCompletionState,
  persistAgentCompletionState,
  reduceAgentCompletionEvent
} from "../../notifications/agent-completion-accumulator";
import {
  clearLocalUnreadFeedback,
  markLocalUnreadFeedback,
  resetLocalUnreadFeedback
} from "../../notifications/local-unread-feedback";

/** 应用内 toast 通知的载荷。 */
export interface ToastPayload {
  id: string;
  conversationId: string;
  threadRootId?: string;
  targetRoute?: string;
  senderName: string;
  preview: string;
  titleOverride?: string;
  isGroupOverride?: boolean;
}

interface NotificationCandidate {
  messageKey: string;
  senderName: string;
  preview: string;
  cardOnly?: true;
  createdAt?: string;
}

interface ConversationNotificationState {
  lastSeenEventId: number;
  notifiedMessageKeys: Set<string>;
}

interface PendingExternalClassification {
  inFlight: boolean;
  retry(): void;
}

function mergeAuthorityConversation(
  previous: Conversation[] | undefined,
  authoritative: Conversation[],
  candidate: Conversation
): Conversation[] {
  if (!previous) return authoritative;
  if (previous.some((conversation) => conversation.id === candidate.id)) return previous;
  return [candidate, ...previous];
}

function normalizeText(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function normalizeUserId(value: unknown): string | null {
  const raw = normalizeText(value);
  if (!raw) {
    return null;
  }
  if (raw.startsWith("user:")) {
    return raw.slice("user:".length) || null;
  }
  return raw;
}

function mentionsUserInContent(payload: Record<string, unknown>, userId: string | null): boolean {
  if (!userId || typeof payload.content !== "string") return false;
  return (
    payload.content.includes(`target_id="${userId}"`) ||
    payload.content.includes(`target_id='${userId}'`)
  );
}

function extractPreview(payload: Record<string, unknown>): string | null {
  const content = normalizeText(payload.content);
  if (content) {
    return content;
  }
  const attachments = Array.isArray(payload.attachments) ? payload.attachments : [];
  const fileName = normalizeText(payload.file_name) ?? normalizeText(attachments[0]?.file_name);
  if (fileName) {
    return fileName;
  }
  if (attachments.length > 0) {
    return "Attachment";
  }
  return null;
}

function extractSenderName(payload: Record<string, unknown>): string {
  const sender = payload.sender as { display_name?: unknown } | undefined;
  return (
    normalizeText(payload.sender_display_name) ??
    normalizeText(sender?.display_name) ??
    normalizeText(payload.sender_name) ??
    normalizeText(payload.display_name) ??
    normalizeText(payload.agent_display_name) ??
    i18n.t(payload.sender_type === "agent" ? "chat.toast.agent" : "chat.toast.member")
  );
}

function patchConversationPreview(
  items: Conversation[] | undefined,
  conversationId: string,
  { preview, createdAt, cardOnly, senderName }: NotificationCandidate,
  markUnread = false,
  explicitUnread?: number
) {
  if (!items) {
    return items;
  }
  const patched = items.map((item) => {
    if (item.id !== conversationId) return item;
    const nextUnread =
      typeof explicitUnread === "number"
        ? explicitUnread
        : markUnread
          ? Math.max(1, item.unread_count)
          : item.unread_count;
    const currentTime = Date.parse(item.last_message_at ?? "");
    const candidateTime = Date.parse(createdAt ?? "");
    if (Number.isFinite(currentTime) && Number.isFinite(candidateTime) && currentTime > candidateTime) {
      return nextUnread !== item.unread_count ? { ...item, unread_count: nextUnread } : item;
    }
    return {
      ...item,
      last_message_preview: cardOnly ? "" : preview,
      ...(item.type === "group" ? { last_message_sender_name: senderName } : {}),
      last_message_card: cardOnly
        ? (createdAt === item.last_message_at ? item.last_message_card : null) ?? { title: null }
        : null,
      last_message_system_notice: null,
      last_message_at: createdAt ?? item.last_message_at,
      unread_count: nextUnread
    };
  });
  return patched.sort((left, right) => {
    const leftTime = Date.parse(left.last_message_at ?? "");
    const rightTime = Date.parse(right.last_message_at ?? "");
    if (!Number.isFinite(leftTime) || !Number.isFinite(rightTime)) return 0;
    return rightTime - leftTime;
  });
}

function isViewingConversation(pathname: string, conversationId: string): boolean {
  return pathname === `/chat/${conversationId}`;
}

function buildConversationRoute(conversationId: string, threadRootId?: string | null): string {
  return `/chat/${conversationId}${threadRootId ? `?thread=${encodeURIComponent(threadRootId)}` : ""}`;
}

function isSelfAuthoredUserMessage(payload: Record<string, unknown>, selfUserId: string | null): boolean {
  if (!selfUserId) {
    return false;
  }
  if (payload.sender_type !== "user") {
    return false;
  }
  const sender = payload.sender;
  if (sender && typeof sender === "object") {
    const senderId = normalizeUserId((sender as Record<string, unknown>).id);
    if (senderId === selfUserId) {
      return true;
    }
  }
  return normalizeUserId(payload.sender_user_id) === selfUserId;
}

export function buildNotificationCandidate(event: UserStreamEvent): NotificationCandidate | null {
  const payload = event.payload as Record<string, unknown>;
  if (event.eventType === "permission.request") {
    const nested = (payload.permission_request ?? payload) as Record<string, unknown>;
    const status = normalizeText(nested.status) ?? normalizeText(payload.status) ?? "pending";
    if (status !== "pending") return null;
    const reqId = normalizeText(nested.request_id) ?? normalizeText(payload.request_id) ?? normalizeText(payload.message_id);
    if (!reqId) return null;
    const toolName = normalizeText(nested.tool_name) ?? normalizeText(payload.tool_name);
    const question = normalizeText(nested.question) ?? normalizeText(payload.question);
    const fallback = i18n.language.startsWith("en")
      ? (toolName ? `Approval requested for ${toolName}` : "Tool approval requested")
      : (toolName ? `请求授权执行 ${toolName}` : "工具权限待确认");
    return {
      messageKey: `perm:${reqId}`,
      senderName: extractSenderName(payload),
      preview: question ?? fallback,
      createdAt: normalizeText(payload.created_at) ?? undefined
    };
  }

  const preview = extractPreview(payload);
  if (!preview && !hasInteractiveCard(payload)) {
    return null;
  }

  if (
    event.eventType === "message.sent"
    || (event.eventType === "message.created" && payload.sender_type === "user")
  ) {
    const messageId = normalizeText(payload.message_id);
    if (!messageId) {
      return null;
    }
    return {
      messageKey: `message:${messageId}`,
      senderName: extractSenderName(payload),
      preview: preview ?? i18n.t("chat.toast.card"),
      ...(!preview ? { cardOnly: true } : {}),
      createdAt: normalizeText(payload.created_at) ?? undefined
    };
  }

  return null;
}

/**
 * 通过用户维 WebSocket 订阅全局事件；在未打开对应会话时弹出应用内 toast。
 */
export function useGlobalMessageToast(_input?: { maxConversations?: number }) {
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const [agentCompletionCandidate, setAgentCompletionCandidate] = useState<AgentCompletionCandidate | null>(null);
  const queryClient = useQueryClient();
  const location = useLocation();
  const pathnameRef = useRef(location.pathname);
  const searchRef = useRef(location.search);
  const selfUserId = useAuthStore((s) => s.user?.id ?? null);
  const selfUserIdRef = useRef<string | null>(selfUserId);
  /** 按会话记录已处理 event_id，避免重复 toast。 */
  const conversationStateRef = useRef(new Map<string, ConversationNotificationState>());
  const globalNotifiedKeysRef = useRef(new Set<string>());
  const pendingExternalClassificationsRef = useRef(new Map<string, PendingExternalClassification>());
  const agentCompletionRef = useRef<AgentCompletionState>(emptyAgentCompletionState);

  useEffect(() => {
    pathnameRef.current = location.pathname;
    searchRef.current = location.search;
    const viewedConversationId = location.pathname.startsWith("/chat/")
      ? location.pathname.slice("/chat/".length)
      : null;
    if (viewedConversationId) clearLocalUnreadFeedback(viewedConversationId);
  }, [location.pathname, location.search]);

  useEffect(() => {
    selfUserIdRef.current = selfUserId;
    conversationStateRef.current.clear();
    globalNotifiedKeysRef.current.clear();
    pendingExternalClassificationsRef.current.clear();
    agentCompletionRef.current = hydrateAgentCompletionState(selfUserId);
    resetLocalUnreadFeedback();
    setToast(null);
    setAgentCompletionCandidate(null);
  }, [selfUserId]);

  useEffect(() => {
    return subscribeUserStream({
      onRecovery: async () => {
        await queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
        for (const pending of pendingExternalClassificationsRef.current.values()) {
          pending.retry();
        }
      },
      onEvent: (event) => {
        const payload = event.payload as Record<string, unknown>;

        if (event.eventType === "conversation.read" || event.eventType === "conversation.preference_updated") {
          const cid = normalizeText(payload.conversation_id);
          if (!cid) return;
          if (event.eventType === "conversation.read") {
            clearLocalUnreadFeedback(cid);
          }
          queryClient.setQueryData<Conversation[] | undefined>(["chat", "conversations"], (previous) =>
            previous?.map((item) =>
              item.id === cid
                ? {
                    ...item,
                    ...(typeof payload.unread_count === "number" ? { unread_count: payload.unread_count } : {}),
                    ...(typeof payload.is_muted === "boolean" ? { is_muted: payload.is_muted } : {}),
                    ...(typeof payload.is_pinned === "boolean" ? { is_pinned: payload.is_pinned } : {})
                  }
                : item
            )
          );
          return;
        }

        if (event.eventType === "agent.work.updated") {
          const hint = event.notificationHint;
          if (!hint || !hint.eligible || hint.replayed || hint.kind !== "work_permission") return;
          if (
            hint.agent_id &&
            pathnameRef.current === `/settings/agents/${hint.agent_id}` &&
            searchRef.current.includes("view=work")
          ) {
            return;
          }
          if (globalNotifiedKeysRef.current.has(hint.dedupe_key)) return;
          globalNotifiedKeysRef.current.add(hint.dedupe_key);
          const agentTitle = hint.sender_name || hint.agent_id || i18n.t("chat.toast.agent");
          const preview = i18n.language.startsWith("en")
            ? "Tool approval needed — click to open Agent Work"
            : "等待工具授权，点击打开助手 Work 处理";
          setToast({
            id: hint.dedupe_key,
            conversationId: "",
            targetRoute: hint.target_route,
            senderName: agentTitle,
            preview,
            titleOverride: agentTitle,
            isGroupOverride: false
          });
          setAgentCompletionCandidate({
            conversationId: "",
            senderUserId: hint.agent_id ? `agent:${hint.agent_id}` : "agent",
            senderName: agentTitle,
            messageKey: hint.dedupe_key,
            messageId: hint.dedupe_key,
            preview,
            targetRoute: hint.target_route
          });
          return;
        }

        if (typeof event.eventId !== "number") return;
        const conversationIdRaw = payload.conversation_id;
        if (typeof conversationIdRaw !== "string" || !conversationIdRaw) return;
        const conversationId = conversationIdRaw;
        const hint = event.notificationHint;
        const threadRootId = hint?.thread_root_message_id ?? normalizeText(payload.thread_root_message_id);
        if (
          !hint &&
          threadRootId &&
          Array.isArray(payload.thread_notify_user_ids) &&
          !payload.thread_notify_user_ids.includes(selfUserIdRef.current)
        ) {
          return;
        }
        let state = conversationStateRef.current.get(conversationId);
        if (!state) {
          state = { lastSeenEventId: 0, notifiedMessageKeys: new Set<string>() };
          conversationStateRef.current.set(conversationId, state);
        }
        if (event.eventId <= state.lastSeenEventId) return;
        state.lastSeenEventId = event.eventId;

        const previousCompletionState = agentCompletionRef.current;
        const completion = reduceAgentCompletionEvent(previousCompletionState, event);
        agentCompletionRef.current = completion.state;
        if (completion.state !== previousCompletionState) {
          persistAgentCompletionState(selfUserIdRef.current, completion.state);
        }

        if (hint) {
          if (event.eventType === "message.completed" || hint.has_interactive_card) {
            void queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] }).catch(() => undefined);
          }
          if (!hint.eligible || hint.replayed) return;

          const viewingConversation = isViewingConversation(pathnameRef.current, conversationId);
          const rawPreview =
            hint.kind === "chat_permission"
              ? hint.preview_text ??
                (hint.tool_name
                  ? i18n.language.startsWith("en")
                    ? `Approval requested for ${hint.tool_name}`
                    : `请求授权执行 ${hint.tool_name}`
                  : i18n.language.startsWith("en")
                    ? "Tool approval requested"
                    : "工具权限待确认")
              : hint.preview_text ??
                (hint.has_interactive_card
                  ? i18n.t("chat.toast.card")
                  : hint.attachment_name ?? extractPreview(payload) ?? i18n.t("chat.toast.newMessage"));
          const senderName =
            hint.sender_name ?? completion.candidate?.senderName ?? extractSenderName(payload);
          const candidateForSidebar: NotificationCandidate = {
            messageKey: hint.dedupe_key,
            senderName,
            preview: rawPreview,
            ...(hint.has_interactive_card && !hint.preview_text ? { cardOnly: true as const } : {}),
            createdAt: normalizeText(payload.created_at) ?? undefined
          };

          if (!viewingConversation) {
            markLocalUnreadFeedback(conversationId);
          }
          if (threadRootId) {
            void queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
          } else {
            queryClient.setQueryData<Conversation[] | undefined>(["chat", "conversations"], (previous) =>
              patchConversationPreview(
                previous,
                conversationId,
                candidateForSidebar,
                !viewingConversation,
                !viewingConversation ? hint.conversation_unread : undefined
              )
            );
          }

          const cachedConv = queryClient
            .getQueryData<Conversation[]>(["chat", "conversations"])
            ?.find((c) => c.id === conversationId);
          const effectiveMuted = cachedConv?.is_muted ?? hint.is_muted;
          if (effectiveMuted && !hint.mentions_viewer) return;

          if (
            state.notifiedMessageKeys.has(hint.dedupe_key) ||
            globalNotifiedKeysRef.current.has(hint.dedupe_key)
          ) {
            return;
          }

          if (hint.kind === "message_completed" || hint.kind === "chat_permission") {
            const bgCandidate: AgentCompletionCandidate = completion.candidate
              ? {
                  ...completion.candidate,
                  messageKey: hint.dedupe_key,
                  preview: rawPreview,
                  targetRoute: hint.target_route
                }
              : {
                  conversationId,
                  senderUserId:
                    normalizeText(payload.sender_user_id) ??
                    (hint.agent_id ? `agent:${hint.agent_id}` : "agent"),
                  senderName,
                  messageKey: hint.dedupe_key,
                  messageId: normalizeText(payload.message_id) ?? hint.dedupe_key,
                  preview: rawPreview,
                  targetRoute: hint.target_route
                };
            setAgentCompletionCandidate(bgCandidate);
          }

          if (viewingConversation) return;
          state.notifiedMessageKeys.add(hint.dedupe_key);
          globalNotifiedKeysRef.current.add(hint.dedupe_key);
          setToast({
            id: hint.dedupe_key,
            conversationId,
            ...(threadRootId ? { threadRootId } : {}),
            targetRoute: hint.target_route,
            senderName,
            preview: mentionPlainText(rawPreview, mentionNameMap(cachedConv?.participants)).slice(0, 80),
            ...(hint.conversation_title ? { titleOverride: hint.conversation_title } : {}),
            ...(hint.conversation_type ? { isGroupOverride: hint.conversation_type === "group" } : {})
          });
          return;
        }

        // Fallback branch for synthetic test events without server `notification_hint`
        const conversations = queryClient.getQueryData<Conversation[]>(["chat", "conversations"]);
        const cachedConversation = conversations?.find((conversation) => conversation.id === conversationId);
        const mentionsSelf = mentionsUserInContent(payload, selfUserIdRef.current);
        const targetRoute = buildConversationRoute(conversationId, threadRootId);

        if (completion.candidate && (!cachedConversation?.is_muted || mentionsSelf)) {
          setAgentCompletionCandidate({
            ...completion.candidate,
            targetRoute
          });
        }
        let candidate = buildNotificationCandidate(event);
        if (completion.candidate) {
          candidate = {
            messageKey: completion.candidate.messageKey,
            senderName: completion.candidate.senderName,
            preview: completion.candidate.preview,
            cardOnly: completion.candidate.cardOnly,
            createdAt: completion.candidate.createdAt
          };
        }
        if (event.eventType === "message.completed" || (candidate && hasInteractiveCard(payload))) {
          void queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] }).catch(() => undefined);
        }
        if (!candidate) return;
        const viewingConversation = isViewingConversation(pathnameRef.current, conversationId);
        const authoredByAccountUser = isSelfAuthoredUserMessage(payload, selfUserIdRef.current);
        const surfaceCandidate = (resolvedSelfAuthored: boolean): void => {
          if (!candidate) return;
          const shouldMarkUnread = !viewingConversation && !resolvedSelfAuthored;
          if (shouldMarkUnread) markLocalUnreadFeedback(conversationId);
          if (threadRootId) {
            void queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
          } else {
            queryClient.setQueryData<Conversation[] | undefined>(["chat", "conversations"], (previous) =>
              patchConversationPreview(previous, conversationId, candidate, shouldMarkUnread)
            );
          }
          const latestConv = queryClient
            .getQueryData<Conversation[]>(["chat", "conversations"])
            ?.find((item) => item.id === conversationId);
          if (
            viewingConversation ||
            resolvedSelfAuthored ||
            (Boolean(latestConv?.is_muted) && !mentionsSelf) ||
            state.notifiedMessageKeys.has(candidate.messageKey)
          ) {
            return;
          }
          state.notifiedMessageKeys.add(candidate.messageKey);
          setToast({
            id: candidate.messageKey,
            conversationId,
            ...(threadRootId ? { threadRootId } : {}),
            targetRoute,
            senderName: candidate.senderName,
            preview: mentionPlainText(candidate.preview, mentionNameMap(latestConv?.participants)).slice(0, 80)
          });
        };

        const externalConversation = Boolean(cachedConversation?.external_source);
        if (
          externalConversation &&
          candidate &&
          event.eventType === "message.created" &&
          payload.sender_type === "user"
        ) {
          pendingExternalClassificationsRef.current.delete(conversationId);
        }
        const unresolvedExternalOwnerMirror = Boolean(
          candidate &&
            event.eventType === "message.created" &&
            payload.sender_type === "user" &&
            authoredByAccountUser &&
            cachedConversation === undefined
        );
        if (unresolvedExternalOwnerMirror && candidate) {
          const eventUserId = selfUserIdRef.current;
          const pending: PendingExternalClassification = {
            inFlight: false,
            retry: () => undefined
          };
          pending.retry = () => {
            if (pending.inFlight) return;
            pending.inFlight = true;
            void queryClient
              .cancelQueries({
                queryKey: ["chat", "conversations"],
                exact: true
              })
              .then(() =>
                pendingExternalClassificationsRef.current.get(conversationId) === pending
                  ? listConversations()
                  : undefined
              )
              .then((freshConversations) => {
                if (
                  !freshConversations ||
                  pendingExternalClassificationsRef.current.get(conversationId) !== pending ||
                  selfUserIdRef.current !== eventUserId ||
                  conversationStateRef.current.get(conversationId) !== state
                ) {
                  return;
                }
                pendingExternalClassificationsRef.current.delete(conversationId);
                const freshConversation = freshConversations.find((item) => item.id === conversationId);
                if (freshConversation) {
                  queryClient.setQueryData<Conversation[] | undefined>(
                    ["chat", "conversations"],
                    (previous) => mergeAuthorityConversation(previous, freshConversations, freshConversation)
                  );
                }
                surfaceCandidate(!freshConversation?.external_source);
              })
              .catch(() => undefined)
              .finally(() => {
                pending.inFlight = false;
              });
          };
          pendingExternalClassificationsRef.current.set(conversationId, pending);
          pending.retry();
          return;
        }
        surfaceCandidate(authoredByAccountUser && !externalConversation);
      }
    });
  }, [queryClient]);

  const dismiss = useCallback(() => setToast(null), []);

  const cachedConversation = queryClient
    .getQueryData<Conversation[]>(["chat", "conversations"])
    ?.find((item) => item.id === toast?.conversationId);
  const { data: fetchedConversation } = useQuery({
    queryKey: ["chat", "conversation-detail", toast?.conversationId],
    queryFn: () => getConversation(toast!.conversationId),
    enabled: Boolean(toast && toast.conversationId && !cachedConversation && !toast.titleOverride),
    retry: false
  });
  const toastConversation = cachedConversation ?? fetchedConversation;

  return {
    toast: toast
      ? {
          ...toast,
          conversationTitle:
            toast.titleOverride || toastConversation?.title || i18n.t("chat.toast.newMessage"),
          isGroup: toast.isGroupOverride ?? toastConversation?.type === "group"
        }
      : null,
    dismiss,
    agentCompletionCandidate
  };
}

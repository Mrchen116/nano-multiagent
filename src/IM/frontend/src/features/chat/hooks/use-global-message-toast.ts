import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import type { Conversation } from "../chat-types";
import { listConversations } from "../chat-api";
import { useAuthStore } from "../../auth/auth-store";
import { subscribeUserStream, type UserStreamEvent } from "../../../realtime/user-stream";
import {
  type AgentCompletionCandidate,
  type AgentCompletionState,
  emptyAgentCompletionState,
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
  senderName: string;
  preview: string;
}

interface NotificationCandidate {
  messageKey: string;
  senderName: string;
  preview: string;
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

function truncatePreview(preview: string): string {
  return preview.slice(0, 80);
}

function extractPreview(payload: Record<string, unknown>): string | null {
  const content = normalizeText(payload.content);
  if (content) {
    return truncatePreview(content);
  }
  const fileName = normalizeText(payload.file_name);
  if (fileName) {
    return truncatePreview(fileName);
  }
  const attachments = Array.isArray(payload.attachments) ? payload.attachments : [];
  if (attachments.length > 0) {
    return "Attachment";
  }
  return null;
}

function extractSenderName(payload: Record<string, unknown>): string {
  return (
    normalizeText(payload.sender_display_name) ??
    normalizeText(payload.sender_name) ??
    normalizeText(payload.display_name) ??
    normalizeText(payload.agent_display_name) ??
    normalizeText(payload.agent_id) ??
    (payload.sender_type === "agent" ? "Agent" : "New message")
  );
}

function patchConversationPreview(
  items: Conversation[] | undefined,
  conversationId: string,
  preview: string,
  createdAt?: string,
  markUnread = false
) {
  if (!items) {
    return items;
  }
  const patched = items.map((item) =>
    item.id === conversationId
      ? {
          ...item,
          last_message_preview: preview,
          last_message_at: createdAt ?? item.last_message_at,
          unread_count: markUnread ? Math.max(1, item.unread_count) : item.unread_count
        }
      : item
  );
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
  const preview = extractPreview(payload);
  if (!preview) {
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
      preview,
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
  const selfUserId = useAuthStore((s) => s.user?.id ?? null);
  const selfUserIdRef = useRef<string | null>(selfUserId);
  /** 按会话记录已处理 event_id，避免重复 toast。 */
  const conversationStateRef = useRef(new Map<string, ConversationNotificationState>());
  const pendingExternalClassificationsRef = useRef(new Map<string, PendingExternalClassification>());
  const agentCompletionRef = useRef<AgentCompletionState>(emptyAgentCompletionState);

  useEffect(() => {
    pathnameRef.current = location.pathname;
    const viewedConversationId = location.pathname.startsWith("/chat/")
      ? location.pathname.slice("/chat/".length)
      : null;
    if (viewedConversationId) clearLocalUnreadFeedback(viewedConversationId);
  }, [location.pathname]);

  useEffect(() => {
    selfUserIdRef.current = selfUserId;
    conversationStateRef.current.clear();
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
        if (typeof event.eventId !== "number") return;
        const payload = event.payload as Record<string, unknown>;
        const conversationIdRaw = payload.conversation_id;
        if (typeof conversationIdRaw !== "string" || !conversationIdRaw) return;
        const conversationId = conversationIdRaw;
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
        if (completion.candidate) setAgentCompletionCandidate(completion.candidate);
        let candidate = buildNotificationCandidate(event);
        if (completion.candidate) {
          candidate = {
            messageKey: completion.candidate.messageKey,
            senderName: completion.candidate.senderName,
            preview: truncatePreview(completion.candidate.preview),
            createdAt: completion.candidate.createdAt
          };
        }
        const viewingConversation = isViewingConversation(pathnameRef.current, conversationId);
        const conversations = queryClient.getQueryData<Conversation[]>(["chat", "conversations"]);
        const cachedConversation = conversations?.find((conversation) => conversation.id === conversationId);
        const authoredByAccountUser = isSelfAuthoredUserMessage(payload, selfUserIdRef.current);
        const surfaceCandidate = (resolvedSelfAuthored: boolean): void => {
          if (!candidate) return;
          const shouldMarkUnread = !viewingConversation && !resolvedSelfAuthored;
          if (shouldMarkUnread) markLocalUnreadFeedback(conversationId);
          queryClient.setQueryData<Conversation[] | undefined>(["chat", "conversations"], (previous) =>
            patchConversationPreview(previous, conversationId, candidate.preview, candidate.createdAt, shouldMarkUnread)
          );
          if (
            viewingConversation
            || resolvedSelfAuthored
            || state.notifiedMessageKeys.has(candidate.messageKey)
          ) return;
          state.notifiedMessageKeys.add(candidate.messageKey);
          setToast({
            id: candidate.messageKey,
            conversationId,
            senderName: candidate.senderName,
            preview: candidate.preview
          });
        };

        const externalConversation = Boolean(cachedConversation?.external_source);
        // External shadow writes intentionally persist under the account owner so
        // they stay inside the owner's conversation scope. The conversation's
        // existing external identity, not that storage identity, decides whether
        // this tab should surface the inbound peer message.
        if (event.eventType === "message.completed") {
          void queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] }).catch(() => undefined);
        }

        const unresolvedExternalOwnerMirror = Boolean(
          candidate
          && event.eventType === "message.created"
          && payload.sender_type === "user"
          && authoredByAccountUser
          && cachedConversation === undefined
        );
        if (unresolvedExternalOwnerMirror && candidate) {
          const eventUserId = selfUserIdRef.current;
          const candidateKey = candidate.messageKey;
          const pending: PendingExternalClassification = {
            inFlight: false,
            retry: () => undefined
          };
          pending.retry = () => {
            if (pending.inFlight) return;
            pending.inFlight = true;
            void queryClient.fetchQuery({
              queryKey: ["chat", "conversations"],
              queryFn: listConversations,
              // The cached list can still be fresh when the server creates an
              // external conversation and immediately emits its first message.
              // Force this classification read through to the authoritative API.
              staleTime: 0
            }).then((freshConversations) => {
              if (
                pendingExternalClassificationsRef.current.get(candidateKey) !== pending
                || selfUserIdRef.current !== eventUserId
                || conversationStateRef.current.get(conversationId) !== state
              ) return;
              pendingExternalClassificationsRef.current.delete(candidateKey);
              const freshConversation = freshConversations.find((item) => item.id === conversationId);
              surfaceCandidate(!freshConversation?.external_source);
            }).catch(() => undefined).finally(() => {
              pending.inFlight = false;
            });
          };
          pendingExternalClassificationsRef.current.set(candidateKey, pending);
          pending.retry();
          return;
        }
        surfaceCandidate(authoredByAccountUser && !externalConversation);
      }
    });
  }, [queryClient]);

  const dismiss = useCallback(() => setToast(null), []);

  return { toast, dismiss, agentCompletionCandidate };
}

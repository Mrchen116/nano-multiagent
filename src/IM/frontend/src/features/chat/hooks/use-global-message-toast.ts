import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import {
  getChatBootstrapState,
  getConversationLatestEventId,
  listConversations,
  streamConversationEvents
} from "../chat-api";
import { ParsedImStreamEvent, setConversationPreviewSnapshot } from "../im-chat-api";
import { ConversationSummary } from "../types";

/** Payload for a single in-app toast notification. */
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
  baselineEventId: number;
  lastSeenEventId: number;
  notifiedMessageKeys: Set<string>;
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

function extractPreview(eventType: string, payload: Record<string, unknown>): string | null {
  const content = normalizeText(payload.content);
  if (content) {
    return truncatePreview(content);
  }
  const detail = normalizeText(payload.detail);
  if (eventType === "relay.completed" && detail && !detail.includes("suppressed_by=no_reply_token") && detail !== "NO_REPLY") {
    return truncatePreview(detail);
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
  items: ConversationSummary[] | undefined,
  conversationId: string,
  preview: string,
  createdAt?: string
) {
  if (!items) {
    return items;
  }
  return items.map((item) =>
    item.conversation_id === conversationId
      ? {
          ...item,
          last_message_preview: preview,
          last_message_at: createdAt ?? item.last_message_at
        }
      : item
  );
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

function toRelayMessageKey(payload: Record<string, unknown>): string | null {
  const messageId = normalizeText(payload.message_id);
  if (!messageId) {
    return null;
  }
  const relayIdentity =
    normalizeText(payload.relay_task_id) ??
    normalizeText(payload.agent_id) ??
    normalizeText(payload.run_id) ??
    "agent";
  return `relay:${messageId}:${relayIdentity}`;
}

export function buildNotificationCandidate(event: ParsedImStreamEvent): NotificationCandidate | null {
  const payload = event.payload as Record<string, unknown>;
  const preview = extractPreview(event.eventType, payload);
  if (!preview) {
    return null;
  }

  if (event.eventType === "message.sent" || event.eventType === "message_created") {
    const messageId = normalizeText(payload.message_id);
    if (!messageId) {
      return null;
    }
    return {
      messageKey: `message:${messageId}`,
      senderName: extractSenderName(payload),
      preview,
      createdAt: normalizeText(payload.created_at)
    };
  }

  if (event.eventType === "relay.completed") {
    const messageKey = toRelayMessageKey(payload);
    if (!messageKey) {
      return null;
    }
    return {
      messageKey,
      senderName: extractSenderName(payload),
      preview,
      createdAt: normalizeText(payload.created_at)
    };
  }

  return null;
}

/**
 * Subscribes to SSE streams for all known conversations and emits an in-app
 * toast when a true new message arrives while the user is not on that conversation's page.
 */
export function useGlobalMessageToast(input?: { maxConversations?: number }) {
  const maxConversations = input?.maxConversations ?? 10;
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const queryClient = useQueryClient();
  const location = useLocation();
  const pathnameRef = useRef(location.pathname);
  const selfUserIdRef = useRef<string | null>(null);
  const conversationStateRef = useRef(new Map<string, ConversationNotificationState>());
  const hasInitializedRef = useRef(false);
  const [subscriptions, setSubscriptions] = useState<Array<{ conversationId: string; afterEventId: number }>>([]);

  useEffect(() => {
    pathnameRef.current = location.pathname;
  }, [location.pathname]);

  useEffect(() => {
    let cancelled = false;

    async function refreshNotificationSubscriptions() {
      try {
        const [items, bootstrap] = await Promise.all([listConversations(), getChatBootstrapState()]);
        if (cancelled) {
          return;
        }
        selfUserIdRef.current = bootstrap.selfUserId;
        const trackedConversations = items.slice(0, maxConversations);
        const trackedIds = new Set(trackedConversations.map((item: ConversationSummary) => item.conversation_id));
        const previousState = conversationStateRef.current;
        const nextState = new Map<string, ConversationNotificationState>();
        const subscriptionsToLoad: Array<{ conversationId: string; unreadCount: number }> = [];

        for (const item of trackedConversations) {
          const existing = previousState.get(item.conversation_id);
          if (existing) {
            nextState.set(item.conversation_id, existing);
            continue;
          }
          subscriptionsToLoad.push({
            conversationId: item.conversation_id,
            unreadCount: typeof item.unread_count === "number" ? Math.max(0, Math.trunc(item.unread_count)) : 0
          });
        }

        const latestEventIds = await Promise.all(
          subscriptionsToLoad.map(async ({ conversationId, unreadCount }) => ({
            conversationId,
            unreadCount,
            latestEventId: await getConversationLatestEventId(conversationId)
          }))
        );
        if (cancelled) {
          return;
        }

        for (const { conversationId, unreadCount, latestEventId } of latestEventIds) {
          const shouldReplayLatestEvent = hasInitializedRef.current && unreadCount > 0 && latestEventId > 0;
          const baselineEventId = shouldReplayLatestEvent ? latestEventId - 1 : latestEventId;
          nextState.set(conversationId, {
            baselineEventId,
            lastSeenEventId: baselineEventId,
            notifiedMessageKeys: new Set<string>()
          });
        }

        conversationStateRef.current = new Map(
          [...nextState.entries()].filter(([conversationId]) => trackedIds.has(conversationId))
        );
        setSubscriptions(
          [...conversationStateRef.current.entries()].map(([conversationId, state]) => ({
            conversationId,
            afterEventId: state.lastSeenEventId
          }))
        );
        hasInitializedRef.current = true;
      } catch {
        if (!cancelled) {
          conversationStateRef.current = new Map();
          setSubscriptions([]);
        }
      }
    }

    void refreshNotificationSubscriptions();
    const intervalId = window.setInterval(() => {
      void refreshNotificationSubscriptions();
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [maxConversations]);

  useEffect(() => {
    if (subscriptions.length === 0) {
      return;
    }

    const teardowns = subscriptions.map(({ conversationId, afterEventId }) =>
      streamConversationEvents({
        conversationId,
        afterEventId,
        onEvent: (event) => {
          const conversationState = conversationStateRef.current.get(conversationId);
          if (!conversationState || typeof event.eventId !== "number") {
            return;
          }
          if (event.eventId <= conversationState.baselineEventId || event.eventId <= conversationState.lastSeenEventId) {
            return;
          }
          conversationState.lastSeenEventId = event.eventId;
          const payload = event.payload as Record<string, unknown>;
          const candidate = buildNotificationCandidate(event);
          if (candidate) {
            queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) =>
              patchConversationPreview(previous, conversationId, candidate.preview, candidate.createdAt)
            );
            setConversationPreviewSnapshot({
              conversationId,
              preview: candidate.preview,
              lastMessageAt: candidate.createdAt
            });
          }
          if (isViewingConversation(pathnameRef.current, conversationId)) {
            return;
          }
          if (isSelfAuthoredUserMessage(payload, selfUserIdRef.current)) {
            return;
          }
          if (!candidate || conversationState.notifiedMessageKeys.has(candidate.messageKey)) {
            return;
          }
          conversationState.notifiedMessageKeys.add(candidate.messageKey);
          setToast({
            id: candidate.messageKey,
            conversationId,
            senderName: candidate.senderName,
            preview: candidate.preview
          });
        }
      })
    );

    return () => {
      for (const teardown of teardowns) {
        teardown();
      }
    };
  }, [queryClient, subscriptions]);

  const dismiss = useCallback(() => setToast(null), []);

  return { toast, dismiss };
}

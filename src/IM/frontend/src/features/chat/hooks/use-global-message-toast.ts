import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import { attachUserConversationStream, getChatBootstrapState, listConversations } from "../chat-api";
import { ParsedImStreamEvent, setConversationPreviewSnapshot } from "../im-chat-api";
import { ConversationSummary } from "../types";
import { useAuthStore } from "../../auth/auth-store";

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
      createdAt: normalizeText(payload.created_at) ?? undefined
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
  const queryClient = useQueryClient();
  const location = useLocation();
  const pathnameRef = useRef(location.pathname);
  const selfUserIdRef = useRef<string | null>(null);
  const accessToken = useAuthStore((s) => s.accessToken ?? "");
  /** 按会话记录已处理 event_id，避免重复 toast。 */
  const conversationStateRef = useRef(new Map<string, ConversationNotificationState>());

  useEffect(() => {
    pathnameRef.current = location.pathname;
  }, [location.pathname]);

  useEffect(() => {
    let cancelled = false;
    let detach: (() => void) | undefined;

    void (async () => {
      try {
        const [bootstrap] = await Promise.all([getChatBootstrapState(), listConversations()]);
        if (cancelled || !bootstrap.selfUserId) {
          return;
        }
        selfUserIdRef.current = bootstrap.selfUserId;
        // 预热侧边栏缓存（与用户流解耦）
        void queryClient.ensureQueryData({ queryKey: ["chat", "conversations"], queryFn: listConversations });

        detach = attachUserConversationStream({
          selfUserId: bootstrap.selfUserId,
          token: accessToken,
          onResyncRequired: async () => {
            await queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
          },
          onEvent: (event) => {
            if (typeof event.eventId !== "number") {
              return;
            }
            const payload = event.payload as Record<string, unknown>;
            const conversationIdRaw = payload.conversation_id;
            if (typeof conversationIdRaw !== "string" || !conversationIdRaw) {
              return;
            }
            const conversationId = conversationIdRaw;
            let state = conversationStateRef.current.get(conversationId);
            if (!state) {
              state = { lastSeenEventId: 0, notifiedMessageKeys: new Set<string>() };
              conversationStateRef.current.set(conversationId, state);
            }
            if (event.eventId <= state.lastSeenEventId) {
              return;
            }
            state.lastSeenEventId = event.eventId;

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
            if (!candidate || state.notifiedMessageKeys.has(candidate.messageKey)) {
              return;
            }
            state.notifiedMessageKeys.add(candidate.messageKey);
            setToast({
              id: candidate.messageKey,
              conversationId,
              senderName: candidate.senderName,
              preview: candidate.preview
            });
          }
        });
      } catch {
        /* bootstrap 失败时静默跳过 toast 流 */
      }
    })();

    return () => {
      cancelled = true;
      detach?.();
    };
  }, [queryClient]);

  const dismiss = useCallback(() => setToast(null), []);

  return { toast, dismiss };
}

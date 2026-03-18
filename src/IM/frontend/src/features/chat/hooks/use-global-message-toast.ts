import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

import { listConversations, streamConversationEvents } from "../chat-api";
import { ConversationSummary } from "../types";

/** Payload for a single in-app toast notification. */
export interface ToastPayload {
  id: string;
  conversationId: string;
  senderName: string;
  preview: string;
}

function extractSenderName(payload: Record<string, unknown>): string {
  const senderName = payload.sender_name;
  if (typeof senderName === "string" && senderName.trim()) {
    return senderName;
  }
  const senderType = payload.sender_type;
  if (senderType === "agent") {
    return "Agent";
  }
  return "New message";
}

function extractPreview(payload: Record<string, unknown>): string | null {
  const content = payload.content ?? payload.summary ?? payload.detail ?? payload.delta;
  if (typeof content === "string" && content.trim()) {
    return content.slice(0, 80);
  }
  return null;
}

function isNotifiableEventType(eventType: string): boolean {
  return (
    eventType === "message.sent" ||
    eventType === "message_created" ||
    eventType === "relay.report" ||
    eventType === "relay.completed"
  );
}

/** Determines whether the user is currently viewing a specific conversation. */
function isViewingConversation(pathname: string, conversationId: string): boolean {
  return pathname === `/chat/${conversationId}`;
}

/**
 * Subscribes to SSE streams for all known conversations and emits an in-app
 * toast when a new message arrives while the user is not on that conversation's page.
 *
 * Returns the current toast to display (at most one at a time) and a dismiss callback.
 * Only opens streams for a reasonable maximum of conversations to avoid connection overload.
 */
export function useGlobalMessageToast(input?: { maxConversations?: number }) {
  const maxConversations = input?.maxConversations ?? 10;
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const location = useLocation();
  const pathnameRef = useRef(location.pathname);
  const [conversationIds, setConversationIds] = useState<string[]>([]);

  // Keep pathname ref current without re-triggering effects
  useEffect(() => {
    pathnameRef.current = location.pathname;
  }, [location.pathname]);

  // Load the conversation list once on mount so we know which streams to open
  useEffect(() => {
    let cancelled = false;
    listConversations()
      .then((items: ConversationSummary[]) => {
        if (!cancelled) {
          setConversationIds(items.slice(0, maxConversations).map((item) => item.conversation_id));
        }
      })
      .catch(() => {
        // Non-critical: toast feature degrades gracefully if list fails
      });
    return () => {
      cancelled = true;
    };
  }, [maxConversations]);

  // Open one SSE stream per conversation; emit toast when away from that conversation
  useEffect(() => {
    if (conversationIds.length === 0) {
      return;
    }

    const teardowns = conversationIds.map((conversationId) =>
      streamConversationEvents({
        conversationId,
        onEvent: (event) => {
          if (!isNotifiableEventType(event.eventType)) {
            return;
          }
          if (isViewingConversation(pathnameRef.current, conversationId)) {
            return;
          }
          const preview = extractPreview(event.payload as Record<string, unknown>);
          if (!preview) {
            return;
          }
          const senderName = extractSenderName(event.payload as Record<string, unknown>);
          setToast({
            id: `${conversationId}:${Date.now()}`,
            conversationId,
            senderName,
            preview
          });
        }
      })
    );

    return () => {
      for (const teardown of teardowns) {
        teardown();
      }
    };
  }, [conversationIds]);

  const dismiss = useCallback(() => setToast(null), []);

  return { toast, dismiss };
}

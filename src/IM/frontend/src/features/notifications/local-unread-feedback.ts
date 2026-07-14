import { useSyncExternalStore } from "react";

import type { Conversation } from "../chat/chat-types";

const locallyUnreadConversationIds = new Set<string>();
const listeners = new Set<() => void>();
let revision = 0;

function emitChange(): void {
  revision += 1;
  for (const listener of [...listeners]) listener();
}

export function markLocalUnreadFeedback(conversationId: string): void {
  if (locallyUnreadConversationIds.has(conversationId)) return;
  locallyUnreadConversationIds.add(conversationId);
  emitChange();
}

export function clearLocalUnreadFeedback(conversationId: string): void {
  if (!locallyUnreadConversationIds.delete(conversationId)) return;
  emitChange();
}

export function resetLocalUnreadFeedback(): void {
  if (locallyUnreadConversationIds.size === 0) return;
  locallyUnreadConversationIds.clear();
  emitChange();
}

export function hasLocalUnreadFeedback(conversationId: string): boolean {
  return locallyUnreadConversationIds.has(conversationId);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): number {
  return revision;
}

/** Merge this tab's live unseen feedback without mutating authoritative query data. */
export function useLocalUnreadFeedback(conversations: Conversation[]): Conversation[] {
  useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  if (locallyUnreadConversationIds.size === 0) return conversations;
  return conversations.map((conversation) =>
    locallyUnreadConversationIds.has(conversation.id) && conversation.unread_count === 0
      ? { ...conversation, unread_count: 1 }
      : conversation
  );
}

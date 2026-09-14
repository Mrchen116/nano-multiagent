import type { Attachment } from "../chat-types";

export type ComposerDraftMention = {
  label: string;
  type: "agent" | "user";
  target_id: string;
};

export type ComposerSnapshot = {
  draft: string;
  draftMentions: ComposerDraftMention[];
  pending: Attachment[];
  slashDismissed: boolean;
};

export const EMPTY_COMPOSER_SNAPSHOT: ComposerSnapshot = {
  draft: "",
  draftMentions: [],
  pending: [],
  slashDismissed: false
};

export function cloneComposerSnapshot(live: ComposerSnapshot): ComposerSnapshot {
  return {
    draft: live.draft,
    draftMentions: [...live.draftMentions],
    pending: [...live.pending],
    slashDismissed: live.slashDismissed
  };
}

const stores = new Map<string, Map<string, ComposerSnapshot>>();
const sendingIds = new Set<string>();
const revokedConversations = new WeakMap<Map<string, ComposerSnapshot>, Set<string>>();
const listeners = new WeakMap<Map<string, ComposerSnapshot>, Set<(conversationId: string) => void>>();

export function composerStoreFor(userId: string | null): Map<string, ComposerSnapshot> {
  const key = userId ?? "anon";
  let store = stores.get(key);
  if (!store) {
    store = new Map();
    stores.set(key, store);
  }
  return store;
}

export function writeComposerSnapshot(
  store: Map<string, ComposerSnapshot>,
  conversationId: string,
  snapshot: ComposerSnapshot
): void {
  if (revokedConversations.get(store)?.has(conversationId)) return;
  store.set(conversationId, cloneComposerSnapshot(snapshot));
  listeners.get(store)?.forEach((listener) => listener(conversationId));
}

export function subscribeComposerStore(
  store: Map<string, ComposerSnapshot>,
  listener: (conversationId: string) => void
): () => void {
  let set = listeners.get(store);
  if (!set) {
    set = new Set();
    listeners.set(store, set);
  }
  set.add(listener);
  return () => {
    set?.delete(listener);
  };
}

export function markComposerSending(conversationId: string): void {
  sendingIds.add(conversationId);
}

export function clearComposerSending(conversationId: string): void {
  sendingIds.delete(conversationId);
}

export function isComposerSending(conversationId: string): boolean {
  return sendingIds.has(conversationId);
}

/** 测试之间清掉会话草稿，避免固定 conversation id 把上一例的输入框带过来。 */
export function resetComposerStores(): void {
  stores.clear();
  sendingIds.clear();
}

/** Reject late upload/unmount writes after this person loses the conversation. */
export function forgetComposerConversation(store: Map<string, ComposerSnapshot>, conversationId: string): void {
  const revoked = revokedConversations.get(store) ?? new Set<string>();
  revoked.add(conversationId);
  revokedConversations.set(store, revoked);
  store.delete(conversationId);
  listeners.get(store)?.forEach(listener => listener(conversationId));
}

export function restoreComposerMembership(store: Map<string, ComposerSnapshot>, conversationIds: Iterable<string>): void {
  for (const id of conversationIds) revokedConversations.get(store)?.delete(id);
}

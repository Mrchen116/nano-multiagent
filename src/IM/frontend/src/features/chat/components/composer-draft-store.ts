import { desktopScopedKey, getDesktopBootContext } from "../../../desktop/desktop-context";
import type { Attachment } from "../chat-types";
import { forgetSendAttempts } from "./send-attempt-store";

export type ComposerDraftMention = {
  label: string;
  type: "agent" | "user";
  target_id: string;
};

export type ComposerUpload = {
  id: string;
  file: File;
  status: "queued" | "uploading" | "ready" | "failed";
  attachment?: Attachment;
  code?: string;
  retryAt?: number;
};

export type ComposerSnapshot = {
  revision?: string;
  replyTo?: import("../chat-types").ReplyReference;
  draft: string;
  draftMentions: ComposerDraftMention[];
  pending: Attachment[];
  uploads?: ComposerUpload[];
  slashDismissed: boolean;
};

export const EMPTY_COMPOSER_SNAPSHOT: ComposerSnapshot = {
  draft: "",
  draftMentions: [],
  pending: [],
  uploads: [],
  slashDismissed: false
};

export function cloneComposerSnapshot(live: ComposerSnapshot): ComposerSnapshot {
  return {
    revision: live.revision,
    replyTo: live.replyTo,
    draft: live.draft,
    draftMentions: [...live.draftMentions],
    pending: [...live.pending],
    uploads: [...(live.uploads ?? [])],
    slashDismissed: live.slashDismissed
  };
}

const DESKTOP_DRAFT_STORAGE_PREFIX = "crewden:composer-drafts::";

const stores = new Map<string, Map<string, ComposerSnapshot>>();
const readingStores = new Map<string, Map<string, { anchorId: string; offset: number; latestId: string; latestAt: number }>>();
const sendingIds = new Set<string>();
const revokedConversations = new WeakMap<Map<string, ComposerSnapshot>, Set<string>>();
const listeners = new WeakMap<Map<string, ComposerSnapshot>, Set<(conversationId: string) => void>>();
const owners = new WeakMap<Map<string, ComposerSnapshot>, string>();
const sessionStorageKeys = new WeakMap<Map<string, ComposerSnapshot>, string>();

type PersistedComposerEntry = {
  revision?: string;
  replyTo?: import("../chat-types").ReplyReference;
  draft: string;
  draftMentions: ComposerDraftMention[];
  pending: Attachment[];
  slashDismissed: boolean;
};

function desktopSessionStorageKeyFor(rawOwner: string): string | null {
  const boot = getDesktopBootContext();
  if (!boot || typeof window === "undefined") return null;
  return `${DESKTOP_DRAFT_STORAGE_PREFIX}${boot.imOrigin}::${boot.contextEpoch}::${rawOwner}`;
}

function pruneStaleDesktopDraftKeys(activeOrigin: string, activeEpoch: number): void {
  if (typeof window === "undefined") return;
  try {
    const validPrefix = `${DESKTOP_DRAFT_STORAGE_PREFIX}${activeOrigin}::${activeEpoch}::`;
    const toRemove: string[] = [];
    for (let i = 0; i < window.sessionStorage.length; i += 1) {
      const k = window.sessionStorage.key(i);
      if (k && k.startsWith(DESKTOP_DRAFT_STORAGE_PREFIX) && !k.startsWith(validPrefix)) {
        toRemove.push(k);
      }
    }
    toRemove.forEach((k) => window.sessionStorage.removeItem(k));
  } catch {
    // Ignore storage access errors in restricted sandboxes.
  }
}

/** Clear all persisted Desktop composer drafts from `sessionStorage` on sign-out or session revocation. */
export function clearDesktopComposerDraftStorage(userId?: string): void {
  if (typeof window === "undefined") return;
  try {
    const toRemove: string[] = [];
    for (let i = 0; i < window.sessionStorage.length; i += 1) {
      const k = window.sessionStorage.key(i);
      if (!k || !k.startsWith(DESKTOP_DRAFT_STORAGE_PREFIX)) continue;
      if (!userId || k.endsWith(`::${userId}`)) {
        toRemove.push(k);
      }
    }
    toRemove.forEach((k) => window.sessionStorage.removeItem(k));
  } catch {
    // Ignore storage access errors.
  }
}

function hydrateStoreFromSessionStorage(
  storageKey: string,
  store: Map<string, ComposerSnapshot>,
): void {
  if (typeof window === "undefined") return;
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Record<string, PersistedComposerEntry>;
    if (!parsed || typeof parsed !== "object") return;
    for (const [cid, entry] of Object.entries(parsed)) {
      if (!entry || typeof entry.draft !== "string") continue;
      store.set(cid, {
        revision: entry.revision,
        replyTo: entry.replyTo,
        draft: entry.draft,
        draftMentions: Array.isArray(entry.draftMentions) ? entry.draftMentions : [],
        pending: Array.isArray(entry.pending) ? entry.pending : [],
        uploads: [],
        slashDismissed: Boolean(entry.slashDismissed),
      });
    }
  } catch {
    // Ignore malformed storage entries.
  }
}

function persistStoreToSessionStorage(store: Map<string, ComposerSnapshot>): void {
  const storageKey = sessionStorageKeys.get(store);
  if (!storageKey || typeof window === "undefined") return;
  try {
    const serialized: Record<string, PersistedComposerEntry> = {};
    let count = 0;
    for (const [cid, snap] of store.entries()) {
      const hasContent =
        snap.draft.length > 0 ||
        snap.draftMentions.length > 0 ||
        Boolean(snap.replyTo) ||
        snap.pending.length > 0;
      if (!hasContent) continue;
      serialized[cid] = {
        revision: snap.revision,
        replyTo: snap.replyTo,
        draft: snap.draft,
        draftMentions: snap.draftMentions,
        pending: snap.pending,
        slashDismissed: snap.slashDismissed,
      };
      count += 1;
    }
    if (count === 0) {
      window.sessionStorage.removeItem(storageKey);
    } else {
      window.sessionStorage.setItem(storageKey, JSON.stringify(serialized));
    }
  } catch {
    // Ignore quota errors.
  }
}

export function readingPositionStoreFor(
  userId: string | null,
): Map<string, { anchorId: string; offset: number; latestId: string; latestAt: number }> {
  const key = userId ?? "anon";
  let store = readingStores.get(key);
  if (!store) {
    store = new Map();
    readingStores.set(key, store);
  }
  return store;
}

export function composerStoreFor(userId: string | null): Map<string, ComposerSnapshot> {
  const rawOwner = userId ?? "anon";
  const boot = getDesktopBootContext();
  const key = boot ? `${desktopScopedKey(rawOwner)}::${boot.contextEpoch}` : desktopScopedKey(rawOwner);
  let store = stores.get(key);
  if (!store) {
    store = new Map();
    stores.set(key, store);
    owners.set(store, rawOwner);
    if (boot) {
      pruneStaleDesktopDraftKeys(boot.imOrigin, boot.contextEpoch);
      const storageKey = desktopSessionStorageKeyFor(rawOwner);
      if (storageKey) {
        sessionStorageKeys.set(store, storageKey);
        hydrateStoreFromSessionStorage(storageKey, store);
      }
    }
  }
  return store;
}

export function writeComposerSnapshot(
  store: Map<string, ComposerSnapshot>,
  conversationId: string,
  snapshot: ComposerSnapshot,
  membershipId = conversationId
): void {
  const revoked = revokedConversations.get(store);
  if (revoked?.has(membershipId) || revoked?.has(conversationId)) return;
  store.set(conversationId, cloneComposerSnapshot(snapshot));
  persistStoreToSessionStorage(store);
  listeners.get(store)?.forEach((listener) => listener(conversationId));
}

/** Persist live in-pane Desktop composer state to the backing store and `sessionStorage` without re-notifying active pane subscribers. */
export function syncLiveComposerSnapshot(
  store: Map<string, ComposerSnapshot>,
  conversationId: string,
  snapshot: ComposerSnapshot,
  membershipId = conversationId
): void {
  const revoked = revokedConversations.get(store);
  if (revoked?.has(membershipId) || revoked?.has(conversationId)) return;
  store.set(conversationId, cloneComposerSnapshot(snapshot));
  persistStoreToSessionStorage(store);
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
  readingStores.clear();
  sendingIds.clear();
  clearDesktopComposerDraftStorage();
}

/** Reject late upload/unmount writes after this person loses the conversation. */
export function forgetComposerConversation(store: Map<string, ComposerSnapshot>, conversationId: string): void {
  const owner = owners.get(store);
  if (owner) {
    readingStores.get(owner)?.delete(conversationId);
    void forgetSendAttempts(owner,conversationId).catch(() => {});
  }
  const revoked = revokedConversations.get(store) ?? new Set<string>();
  revoked.add(conversationId);
  revokedConversations.set(store, revoked);
  store.delete(conversationId);
  const threadPrefix = threadDraftKey(conversationId, "");
  for (const key of store.keys()) if (key.startsWith(threadPrefix)) store.delete(key);
  persistStoreToSessionStorage(store);
  listeners.get(store)?.forEach(listener => listener(conversationId));
}

export function restoreComposerMembership(store: Map<string, ComposerSnapshot>, conversationIds: Iterable<string>): void {
  for (const id of conversationIds) revokedConversations.get(store)?.delete(id);
}

/** Remove server-backed and local drafts on sign-out without allowing late writes to resurrect them. */
export function forgetComposerUser(userId: string): void {
  void forgetSendAttempts(userId).catch(() => {});
  readingStores.delete(userId);
  clearDesktopComposerDraftStorage(userId);
  const prefix = desktopScopedKey(userId);
  for (const [k, store] of [...stores.entries()]) {
    if (k === prefix || k.startsWith(`${prefix}::`)) {
      for (const id of store.keys()) forgetComposerConversation(store, id);
      stores.delete(k);
    }
  }
}

/** Topic drafts share the account store and membership lifetime with the parent chat. */
export function threadDraftKey(conversationId: string, rootId: string): string {
  return `thread/${encodeURIComponent(conversationId)}/${encodeURIComponent(rootId)}`;
}

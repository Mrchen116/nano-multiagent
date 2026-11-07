// Client half of the one-shot private background rule. The centre decides what a message
// carries; this module only keeps the two things a browser must own: the highest draft save
// it has confirmed (so leaving a conversation can name what it clears) and the unsaved-draft
// failures that must block sending instead of silently dropping the edit.
import { useSyncExternalStore } from 'react';
import { discardInteractionBackground, readInteractionDraft } from './chat-api';
import { openChatDatabase } from './chat-local-db';

export type DraftFailureReason = 'transient' | 'conflict';

/** The only seam a card exposes to the composer; its state lives inside the card. */
export interface DraftHandle {
  /** Finish this card's debounce window and return the confirmed save time, or why it failed. */
  flush(): Promise<{ updatedAt?: string; reason?: DraftFailureReason }>;
  /** Read-only comparison of the server draft with the local edit; applies nothing. */
  describeConflict(): Promise<{ columns: { label: string; remote: string; local: string }[] }>;
  /** Adopt the server draft, discarding this device's edit, and clear this card's failure. */
  adoptRemote(): Promise<void>;
}

export interface DraftFailure {
  messageId: string;
  reason: DraftFailureReason;
}

const handles = new Map<string, Map<string, DraftHandle>>();
const failures = new Map<string, Map<string, DraftFailureReason>>();
const listeners = new Set<() => void>();
/** Highest confirmed save per conversation, the only thing leaving may clear. */
const watermarks = new Map<string, string>();
/** Highest watermark this browser already cleared on the server. */
const cleared = new Map<string, string>();
/** Conversations this browser has left; a save that lands after that must also be cleared. */
const leaving = new Set<string>();
/** Tail of the per-conversation discard chain, so clears keep their order. */
const discards = new Map<string, Promise<void>>();
let accountId = '';
let hydrated: Promise<void> | null = null;
let lastWrite: Promise<void> = Promise.resolve();
let generation = 0;
const conversationGenerations = new Map<string, number>();

/** Capture before asynchronous draft work so logout/revocation fences late completions. */
export function draftSession(cid: string): string { return `${generation}:${conversationGenerations.get(cid) ?? 0}`; }
const snapshotCache = new Map<string, DraftFailure[]>();

function notify(): void {
  snapshotCache.clear();
  for (const listener of listeners) listener();
}

function setFailure(cid: string, mid: string, reason: DraftFailureReason | null): void {
  const current = failures.get(cid) ?? new Map<string, DraftFailureReason>();
  const before = current.get(mid);
  if (reason) current.set(mid, reason); else current.delete(mid);
  if (!current.size) failures.delete(cid); else failures.set(cid, current);
  if (before !== (reason ?? undefined)) notify();
}

/** Failures blocking this conversation, newest reason per card. */
export function draftFailures(cid: string): DraftFailure[] {
  const cached = snapshotCache.get(cid);
  if (cached) return cached;
  const value = [...(failures.get(cid) ?? new Map<string, DraftFailureReason>())]
    .map(([messageId, reason]) => ({ messageId, reason }));
  snapshotCache.set(cid, value);
  return value;
}

/** Subscribe the composer alert to the cards' own save outcomes. */
export function useDraftFailures(cid: string): DraftFailure[] {
  return useSyncExternalStore(listen => { listeners.add(listen); return () => listeners.delete(listen); },
    () => draftFailures(cid), () => draftFailures(cid));
}

/** Idempotent: React StrictMode mounts each card twice. */
export function registerDraftHandle(cid: string, mid: string, handle: DraftHandle): () => void {
  const chat = handles.get(cid) ?? new Map<string, DraftHandle>();
  chat.set(mid, handle); handles.set(cid, chat);
  return () => { if (handles.get(cid)?.get(mid) === handle) unregisterDraftHandle(cid, mid); };
}

export function unregisterDraftHandle(cid: string, mid: string): void {
  const chat = handles.get(cid);
  if (!chat) return;
  chat.delete(mid);
  if (!chat.size) handles.delete(cid);
  clearDraftFailure(cid, mid);
}

/** Record a confirmed save as this browser's watermark for the conversation. */
export function noteDraftSaved(cid: string, updatedAt: string | undefined, session = draftSession(cid)): void {
  if (session !== draftSession(cid) || !updatedAt || (cleared.get(cid) ?? '') >= updatedAt) return;
  const previous = watermarks.get(cid);
  if (previous && previous >= updatedAt) return;
  watermarks.delete(cid); watermarks.set(cid, updatedAt);
  if (watermarks.size > LIMIT) watermarks.delete(watermarks.keys().next().value!);
  lastWrite = persistWatermark(accountId, cid, updatedAt, session).catch(() => undefined);
  // This save may have been in flight when the user left; the clear already sent cannot
  // cover it, so send a second one with the time this device itself confirmed.
  if (leaving.has(cid)) void enqueueDiscard(cid, updatedAt);
}

/** Test seam: settles once the IndexedDB write started by the last save has landed. */
export function awaitWatermarkWrite(): Promise<void> { return lastWrite; }

/** Tell the cards that a save failed, so the composer blocks until it succeeds. */
export function noteDraftFailed(cid: string, mid: string, reason: DraftFailureReason, session = draftSession(cid)): void {
  if (session === draftSession(cid)) setFailure(cid, mid, reason);
}

export function clearDraftFailure(cid: string, mid: string, session = draftSession(cid)): void {
  if (session === draftSession(cid)) setFailure(cid, mid, null);
}

export function draftWatermark(cid: string): string | undefined { return watermarks.get(cid); }

export function resetInteractionBackground(nextAccountId = ''): void {
  generation += 1; conversationGenerations.clear();
  handles.clear(); failures.clear(); watermarks.clear(); cleared.clear(); leaving.clear(); discards.clear();
  snapshotCache.clear();
  accountId = nextAccountId; hydrated = null; notify();
}

/** Flush every mounted card in this conversation and collect the outcome per card. */
export async function flushInteractionDrafts(cid: string): Promise<DraftFailure[]> {
  const chat = handles.get(cid), session = draftSession(cid);
  if (!chat?.size) return draftFailures(cid);
  await Promise.all([...chat].map(async ([mid, handle]) => {
    // 404/501 or an offline card must not throw out of the send path.
    const result = await handle.flush().catch((): { reason: DraftFailureReason } => ({ reason: 'transient' }));
    if (session !== draftSession(cid)) return;
    if (result.reason) setFailure(cid, mid, result.reason);
    else { clearDraftFailure(cid, mid); noteDraftSaved(cid, result.updatedAt, session); }
  }));
  return draftFailures(cid);
}

/** True when this conversation may send: no card is holding an unsaved edit. */
export async function beginSend(cid: string): Promise<boolean> {
  await flushInteractionDrafts(cid);
  return draftFailures(cid).length === 0;
}

/** Retry one card's save from the composer alert (transient branch only). */
export async function retryDraft(cid: string, mid: string): Promise<void> {
  const handle = handles.get(cid)?.get(mid), session = draftSession(cid);
  if (!handle) return;
  const result = await handle.flush().catch((): { reason: DraftFailureReason } => ({ reason: 'transient' }));
  if (session !== draftSession(cid)) return;
  if (result.reason) setFailure(cid, mid, result.reason);
  else { clearDraftFailure(cid, mid); noteDraftSaved(cid, result.updatedAt, session); }
}

/** Read-only three-column comparison for the 409 branch. */
export async function describeDraftConflict(cid: string, mid: string): Promise<{ columns: { label: string; remote: string; local: string }[] }> {
  const handle = handles.get(cid)?.get(mid);
  if (handle) return handle.describeConflict();
  const remote = await readInteractionDraft(cid, mid);
  return { columns: (remote.fields ?? []).map(field => ({ label: field.label, remote: readable(field.value, field.display_value), local: '' })) };
}

/** Adopt the server draft for one card after the user accepted the loss. */
export async function adoptRemoteDraft(cid: string, mid: string): Promise<void> {
  const handle = handles.get(cid)?.get(mid);
  if (!handle) { clearDraftFailure(cid, mid); return; }
  await handle.adoptRemote();
  clearDraftFailure(cid, mid);
}

/** Render one value with the labels the server sent, so both columns speak one vocabulary. */
export function readable(value: unknown, display?: string, options?: { label: string; value: string }[]): string {
  if (display) return display;
  const raw = value && typeof value === 'object' && 'value' in (value as Record<string, unknown>)
    ? (value as Record<string, unknown>).value : value;
  const match = options?.find(option => option.value === String(raw));
  if (match) return match.label;
  if (raw === null || raw === undefined) return '';
  return typeof raw === 'string' ? raw : JSON.stringify(raw);
}

/** Leave one conversation: clear only what this browser already saved.
 *
 * A device with no watermark cannot know what it would erase, so it sends nothing;
 * pushing "now" there would wipe another device's unsent edit. The conversation still
 * counts as left, so a save that lands afterwards triggers one more clear (D4 迟到成功).
 */
export function discardOnLeave(cid: string, through = watermarks.get(cid)): Promise<void> {
  leaving.add(cid);
  return enqueueDiscard(cid, through);
}

/** Mark a conversation active again so its earlier leave cannot clear a new edit.
 *
 * Without this, editing after coming back would be cleared by the late-save rule the
 * moment it saves — the edit would silently never be carried.
 */
export function resumeConversation(cid: string): void { leaving.delete(cid); }

/** Wait for an in-flight discard so a message cannot overtake the clear it belongs after. */
export async function awaitPendingDiscard(cid: string): Promise<void> {
  // A late save may enqueue its own clear while we wait, so follow the chain, not one link.
  for (let tail = discards.get(cid); tail;) {
    await tail.catch(() => undefined);
    const next = discards.get(cid);
    tail = next === tail ? undefined : next;
  }
}

/** Queue one clear behind the previous one for this conversation.
 *
 * Order matters: a late save must be cleared after the earlier clear, and a message must
 * never overtake either. Older servers answer 404/501, which we ignore but must not treat
 * as cleared, so the watermark survives for the next leave to retry.
 */
function enqueueDiscard(cid: string, through: string | undefined): Promise<void> {
  if (!through) return Promise.resolve();
  if (cleared.get(cid) && cleared.get(cid)! >= through) return discards.get(cid) ?? Promise.resolve();
  const session = draftSession(cid), userId = accountId;
  const tail = (discards.get(cid) ?? Promise.resolve()).then(async () => {
    if (session !== draftSession(cid)) return;
    try {
      const result = await discardInteractionBackground(cid, through);
      if (!result || session !== draftSession(cid)) return;
      if (!cleared.get(cid) || cleared.get(cid)! < through) cleared.set(cid, through);
      const current = watermarks.get(cid);
      if (!current || current <= through) {
        watermarks.delete(cid);
        await forgetWatermark(userId, cid, through, session);
      }
    } catch { /* Keep the watermark and retry on the next leave. */ }
  });
  discards.set(cid, tail);
  void tail.finally(() => { if (discards.get(cid) === tail) discards.delete(cid); });
  return tail;
}

/** Hydrate this account's watermarks once; a fresh browser starts with none. */
export async function loadWatermarks(nextAccountId: string): Promise<void> {
  if (accountId === nextAccountId && hydrated) return hydrated;
  resetInteractionBackground(nextAccountId);
  hydrated = hydrate(nextAccountId);
  return hydrated;
}

interface WatermarkRow { userId: string; conversationId: string; through: string; at: number }
const STORE = 'watermarks';
const LIMIT = 128;
let storageOrder = 0;

async function storage<T>(mode: IDBTransactionMode, operation: (store: IDBObjectStore, result: (value: T) => void) => void): Promise<T | undefined> {
  if (typeof indexedDB === 'undefined') return;
  const db = await openChatDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    let value: T;
    tx.oncomplete = () => { db.close(); resolve(value); };
    tx.onabort = () => { db.close(); reject(tx.error); };
    tx.onerror = () => { /* Abort owns the failure. */ };
    try { operation(tx.objectStore(STORE), next => { value = next; }); }
    catch (error) { tx.abort(); reject(error); }
  });
}

async function hydrate(userId: string): Promise<void> {
  const session = generation;
  const rows = await storage<WatermarkRow[]>('readonly', (store, result) => {
    const request = store.index('user').getAll(userId);
    request.onsuccess = () => result(request.result as WatermarkRow[]);
  }).catch(() => undefined);
  if (session !== generation) return;
  for (const row of (rows ?? []).sort((a, b) => a.at - b.at).slice(-LIMIT)) {
    storageOrder = Math.max(storageOrder, row.at);
    const previous = watermarks.get(row.conversationId);
    if (!previous || previous < row.through) watermarks.set(row.conversationId, row.through);
  }
}

function persistWatermark(userId: string, cid: string, through: string, session: string): Promise<void> {
  if (!userId) return Promise.resolve();
  return storage<void>('readwrite', store => {
    if (session !== draftSession(cid)) return;
    // The read and max update share one transaction: a delayed write or another tab cannot
    // replace a higher confirmed watermark with an older one.
    const request = store.get([userId, cid]);
    request.onsuccess = () => {
      if (session !== draftSession(cid)) return;
      const previous = request.result as WatermarkRow | undefined;
      storageOrder = Math.max(Date.now(), storageOrder + 1);
      store.put({userId, conversationId: cid, through: previous && previous.through > through ? previous.through : through, at: storageOrder} satisfies WatermarkRow);
      const all = store.index('user').getAll(userId);
      all.onsuccess = () => {
        const rows = (all.result as WatermarkRow[]).sort((a, b) => b.at - a.at);
        for (const row of rows.slice(LIMIT)) store.delete([userId, row.conversationId]);
      };
    };
  });
}

function forgetWatermark(userId: string, cid: string, through: string, session: string): Promise<unknown> {
  return storage('readwrite', store => {
    if (session !== draftSession(cid)) return;
    const request = store.get([userId, cid]);
    request.onsuccess = () => {
      const row = request.result as WatermarkRow | undefined;
      if (session === draftSession(cid) && row && row.through <= through) store.delete([userId, cid]);
    };
  });
}

/** Clear local ownership on logout or revoked access; late saves cannot resurrect it.
 *
 * Args:
 *   userId: Account whose local state lost authorization.
 *   cid: Revoked conversation, or omit for all of that account's conversations.
 */
export async function forgetInteractionBackground(userId: string, cid?: string): Promise<void> {
  if (accountId === userId) {
    if (cid === undefined) resetInteractionBackground();
    else {
      conversationGenerations.set(cid, (conversationGenerations.get(cid) ?? 0) + 1);
      handles.delete(cid); failures.delete(cid); watermarks.delete(cid); cleared.delete(cid);
      leaving.delete(cid); discards.delete(cid); notify();
    }
  }
  await storage('readwrite', store => {
    if (cid !== undefined) { store.delete([userId, cid]); return; }
    const request = store.index('user').getAllKeys(userId);
    request.onsuccess = () => { for (const key of request.result) store.delete(key); };
  });
}

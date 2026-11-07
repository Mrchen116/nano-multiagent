import type { Attachment } from '../chat-types';
import type { ComposerSnapshot } from './composer-draft-store';
import { openChatDatabase } from '../chat-local-db';

/** Frozen wire body. Private background is not part of it: the centre derives and freezes
 * the background with the message, so a retry must resend exactly this payload. */
export interface SendAttemptPayload {
  text: string;
  attachments: Attachment[];
}
export interface SendAttempt extends SendAttemptPayload {
  userId: string;
  conversationId: string;
  key: string;
  draft: ComposerSnapshot;
  retryable: boolean;
}

const generations = new Map<string, number>();
function generation(userId: string, conversationId?: string) {
  return `${generations.get(userId) ?? 0}:${generations.get(JSON.stringify([userId,conversationId])) ?? 0}`;
}

async function transact<T>(mode: IDBTransactionMode, operation: (store: IDBObjectStore, result: (value:T)=>void) => void): Promise<T> {
  const db = await openChatDatabase();
  return new Promise((resolve,reject) => {
    const transaction = db.transaction('attempts',mode);
    let value: T;
    transaction.oncomplete = () => { db.close(); resolve(value); };
    transaction.onabort = () => { db.close(); reject(transaction.error ?? new Error('Send attempt storage aborted')); };
    transaction.onerror = () => { /* onabort reports the transaction failure. */ };
    try { operation(transaction.objectStore('attempts'),next => {value=next;}); }
    catch (error) { transaction.abort(); reject(error); }
  });
}

/** Read submitted snapshots for one account and chat.
 *
 * Args:
 *   userId: Authenticated account owning the snapshots.
 *   conversationId: Chat whose submitted attempts should be recovered.
 * Returns:
 *   Persisted attempts; ordinary unsent drafts are never stored here.
 */
export function listSendAttempts(userId: string, conversationId: string): Promise<SendAttempt[]> {
  return transact('readonly',(store,result) => {
    const request = store.index('conversation').getAll([userId,conversationId]);
    request.onsuccess = () => result(request.result as SendAttempt[]);
  });
}

/** Persist an immutable send before its first POST, reusing only the same draft and payload.
 *
 * Args:
 *   userId: Authenticated account owning the local snapshot.
 *   conversationId: Chat receiving this explicit send.
 *   draft: Submitted composer content and revision.
 *   payload: Frozen wire body: the content and attachment references that decide identity.
 * Returns:
 *   Existing matching attempt or a newly persisted UUID attempt.
 */
export async function prepareSendAttempt(userId: string, conversationId: string, draft: ComposerSnapshot, payload: SendAttemptPayload): Promise<SendAttempt> {
  const epoch = generation(userId,conversationId);
  return transact('readwrite',(store,result) => {
    const request = store.index('conversation').getAll([userId,conversationId]);
    request.onsuccess = () => {
      if (epoch !== generation(userId,conversationId)) { store.transaction.abort(); return; }
      const previous = request.result as SendAttempt[];
      // Compare the fields that decide the message, not the whole stored row: rows written
      // before this unit also carry a `contexts` field the centre now ignores, and treating
      // them as a different payload would POST a second copy instead of retrying the original.
      const existing = previous.find(item => item.retryable && item.draft.revision === draft.revision
        && item.text === payload.text
        && JSON.stringify(item.attachments) === JSON.stringify(payload.attachments));
      if (existing) { result(existing); return; }
      for (const old of previous) if (old.retryable) store.put({...old,retryable:false});
      const attempt: SendAttempt = structuredClone({userId,conversationId,key:crypto.randomUUID(),draft:{...draft,uploads:[]},...payload,retryable:true});
      store.add(attempt);
      result(attempt);
    };
  });
}

/** Remove one confirmed or permanently rejected identity.
 *
 * Args:
 *   attempt: Exact account, conversation and key to remove.
 */
export function removeSendAttempt(attempt: SendAttempt): Promise<void> {
  return transact('readwrite',(store,result) => {
    store.delete([attempt.userId,attempt.conversationId,attempt.key]);
    result(undefined);
  });
}

/** Clear revoked snapshots and invalidate writes already awaiting storage.
 *
 * Args:
 *   userId: Signed-out or revoked account.
 *   conversationId: Revoked chat; omit to clear the entire account.
 */
export function forgetSendAttempts(userId: string, conversationId?: string): Promise<void> {
  const key = conversationId === undefined ? userId : JSON.stringify([userId,conversationId]);
  generations.set(key,(generations.get(key) ?? 0)+1);
  return transact('readwrite',(store,result) => {
    const request = conversationId === undefined ? store.index('user').getAllKeys(userId)
      : store.index('conversation').getAllKeys([userId,conversationId]);
    request.onsuccess = () => { for (const key of request.result) store.delete(key); result(undefined); };
  });
}

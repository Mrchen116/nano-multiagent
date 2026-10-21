import type { Attachment } from '../chat-types';
import type { InteractionContextInput } from '../interactive/types';
import type { ComposerSnapshot } from './composer-draft-store';

export interface SendAttemptPayload {
  text: string;
  attachments: Attachment[];
  contexts: InteractionContextInput[];
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

function openAttempts(): Promise<IDBDatabase> {
  return new Promise((resolve,reject) => {
    const request = indexedDB.open('im-message-attempts',1);
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore('attempts',{keyPath:['userId','conversationId','key']});
      store.createIndex('conversation',['userId','conversationId']);
      store.createIndex('user','userId');
    };
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

async function transact<T>(mode: IDBTransactionMode, operation: (store: IDBObjectStore, result: (value:T)=>void) => void): Promise<T> {
  const db = await openAttempts();
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
 *   payload: Frozen wire body, uploaded attachment references and private context.
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
      const existing = previous.find(item => item.retryable && item.draft.revision === draft.revision
        && JSON.stringify({text:item.text,attachments:item.attachments,contexts:item.contexts}) === JSON.stringify(payload));
      if (existing) { result(existing); return; }
      for (const old of previous) if (old.retryable) store.put({...old,retryable:false});
      const attempt: SendAttempt = structuredClone({userId,conversationId,key:crypto.randomUUID(),draft:{...draft,failed:[]},...payload,retryable:true});
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

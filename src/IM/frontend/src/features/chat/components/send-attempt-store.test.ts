import { describe, expect, it } from 'vitest';
import { forgetSendAttempts, listSendAttempts, prepareSendAttempt } from './send-attempt-store';

const draft = {draft:'hello', draftMentions:[], pending:[{url:'/upload/one'}], slashDismissed:false, revision:'draft-1'};
const payload = {text:'hello',attachments:draft.pending};

/** Write a row in the pre-feat-716 shape, which also froze a client-chosen `contexts`. */
function putLegacyAttempt(row: Record<string, unknown>): Promise<void> {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open('im-message-attempts',1);
    open.onupgradeneeded = () => {
      const store = open.result.createObjectStore('attempts', {keyPath:['userId','conversationId','key']});
      store.createIndex('conversation', ['userId','conversationId']);
      store.createIndex('user', 'userId');
    };
    open.onsuccess = () => {
      const db = open.result;
      const transaction = db.transaction('attempts','readwrite');
      transaction.objectStore('attempts').put(row);
      transaction.oncomplete = () => { db.close(); resolve(); };
      transaction.onerror = () => { db.close(); reject(transaction.error); };
    };
    open.onerror = () => reject(open.error);
  });
}

describe('durable composer send attempts', () => {
  it('retains the same immutable identity after reloading its owner and separates explicit edited sends', async () => {
    const first = await prepareSendAttempt('u1','chat',draft,payload);
    expect(await listSendAttempts('u1','chat')).toEqual([first]);
    const retry = await prepareSendAttempt('u1','chat',structuredClone(draft),structuredClone(payload));
    expect(retry.key).toBe(first.key);

    const edited = {...draft,draft:'changed',revision:'draft-2'};
    const next = await prepareSendAttempt('u1','chat',edited,{...payload,text:'changed'});
    expect(next.key).not.toBe(first.key);
    expect((await listSendAttempts('u1','chat')).find(item=>item.key===first.key)?.retryable).toBe(false);
    expect((await listSendAttempts('u1','chat')).find(item=>item.key===first.key)?.text).toBe('hello');
  });

  it('reuses the identity of a row written before the background became server-derived', async () => {
    // Upgrade window: a row persisted by the previous client also froze `contexts`, which the
    // centre now ignores. Identity is content plus attachments, so the in-flight retry must
    // keep its key instead of POSTing a second copy under a fresh one.
    const first = {userId:'u1', conversationId:'chat', key:'legacy-frozen-key', draft, ...payload, retryable:true};
    await putLegacyAttempt({...structuredClone(first),contexts:[{source_message_id:'card',state:{'$body':'x'}}]});
    const retry = await prepareSendAttempt('u1','chat',structuredClone(draft),structuredClone(payload));
    expect(retry.key).toBe(first.key);
    expect(await listSendAttempts('u1','chat')).toHaveLength(1);
  });

  it('isolates accounts and conversations and removes persisted snapshots on revoke and logout', async () => {
    await prepareSendAttempt('u1','chat',draft,payload);
    await prepareSendAttempt('u1','other',draft,payload);
    await prepareSendAttempt('u2','chat',draft,payload);
    await forgetSendAttempts('u1','chat');
    expect(await listSendAttempts('u1','chat')).toEqual([]);
    expect(await listSendAttempts('u1','other')).toHaveLength(1);
    await forgetSendAttempts('u1');
    expect(await listSendAttempts('u1','other')).toEqual([]);
    expect(await listSendAttempts('u2','chat')).toHaveLength(1);
  });
});

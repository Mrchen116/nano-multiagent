import { describe, expect, it } from 'vitest';
import { forgetSendAttempts, listSendAttempts, prepareSendAttempt } from './send-attempt-store';

const draft = {draft:'hello', draftMentions:[], pending:[{url:'/upload/one'}], slashDismissed:false, revision:'draft-1'};
const payload = {text:'hello',attachments:draft.pending,contexts:[]};

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

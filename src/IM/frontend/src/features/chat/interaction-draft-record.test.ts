import { beforeEach, expect, it, vi } from 'vitest';
import { readInteractionDraft, saveInteractionDraft, discardInteractionBackground } from './chat-api';
import {
  adoptRemoteDraft, attachDraftRecord, awaitPendingDiscard, discardOnLeave, draftFailures, draftWatermark,
  forgetInteractionBackground, interactionDraftRecord, registerDraftHandle, resetInteractionBackground,
  resumeConversation, retryDraft,
} from './interaction-background';
import type { InteractionDraft } from './interactive/types';

vi.mock('./chat-api', () => ({
  readInteractionDraft: vi.fn(), saveInteractionDraft: vi.fn(), discardInteractionBackground: vi.fn(),
}));
const T1 = '2026-05-01T00:00:01.000Z', T2 = '2026-05-01T00:00:02.000Z';
const draft = (revision = 2, value = 'remote', updated_at?: string): InteractionDraft => ({
  draft_revision: revision, state: { '$body': value }, submission_message_id: null, updated_at,
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return {promise, resolve};
}
async function open() {
  const record = interactionDraftRecord('chat', 'card');
  const detach = attachDraftRecord(record);
  await record.load();
  return {record, detach};
}
beforeEach(() => {
  resetInteractionBackground('owner');
  vi.mocked(readInteractionDraft).mockReset().mockResolvedValue(draft());
  vi.mocked(saveInteractionDraft).mockReset().mockResolvedValue(draft(3, 'saved', T1));
  vi.mocked(discardInteractionBackground).mockReset().mockResolvedValue({discarded_through:T1});
});

it.each(['409 conflict', 'offline'])('retains the %s edit and CAS revision after detaching, without rereading it away', async error => {
  const {record, detach} = await open();
  record.update({'$body':'local'}, true);
  vi.mocked(saveInteractionDraft).mockRejectedValueOnce(new Error(error));
  await record.flush();
  detach();
  const replacement = interactionDraftRecord('chat', 'card');
  const release = attachDraftRecord(replacement);
  expect(replacement).toBe(record);
  expect(await replacement.load()).toBe(true);
  expect(replacement.state).toEqual({'$body':'local'});
  expect(replacement.revision).toBe(2);
  expect(replacement.failure).toBe(error.startsWith('409') ? 'conflict' : 'transient');
  expect(draftFailures('chat')).toHaveLength(1);
  expect(readInteractionDraft).toHaveBeenCalledTimes(1);
  release();
});

it('shares the pending PUT across views and saves a newer edit with the acknowledged revision, not its returned state', async () => {
  const pending = deferred<InteractionDraft>();
  vi.mocked(saveInteractionDraft).mockReturnValueOnce(pending.promise).mockResolvedValueOnce(draft(4, 'not a renderer seed', T2));
  const {record, detach} = await open();
  record.update({'$body':'first local'}, true);
  const saving = record.save();
  detach();
  const next = interactionDraftRecord('chat', 'card');
  const release = attachDraftRecord(next);
  await next.load();
  expect(next.request).toBe(saving);
  next.update({'$body':'newer local'}, true);
  expect(next.save()).toBe(saving);
  expect(saveInteractionDraft).toHaveBeenCalledTimes(1);
  pending.resolve(draft(3, 'old response', T1));
  await saving;
  expect(saveInteractionDraft).toHaveBeenNthCalledWith(2, 'chat', 'card', 3, {'$body':'newer local'});
  expect(next.state).toEqual({'$body':'newer local'});
  expect(next.revision).toBe(4);
  expect(next.renderVersion).toBe(1);
  expect(draftWatermark('chat')).toBe(T2);
  expect(draftFailures('chat')).toEqual([]);
  release();
});

it('does not retain clean drafts after detach, so a later mount reads the other device', async () => {
  const {record, detach} = await open();
  detach();
  vi.mocked(readInteractionDraft).mockResolvedValueOnce(draft(8, 'another device'));
  const {record:next, detach:release} = await open();
  expect(next).not.toBe(record);
  expect(next.state).toEqual({'$body':'another device'});
  expect(readInteractionDraft).toHaveBeenCalledTimes(2);
  release();
});

it('evicts a detached record when its PUT settles clean', async () => {
  const pending = deferred<InteractionDraft>();
  vi.mocked(saveInteractionDraft).mockReturnValueOnce(pending.promise);
  const {record, detach} = await open();
  record.update({'$body':'local'}, true);
  const saving = record.save();
  detach();
  pending.resolve(draft(3, 'local', T1));
  await saving;
  expect(interactionDraftRecord('chat', 'card')).not.toBe(record);
});

it('allows a StrictMode detach/reattach lease without duplicating the initial GET', async () => {
  const pending = deferred<InteractionDraft>();
  vi.mocked(readInteractionDraft).mockReturnValueOnce(pending.promise);
  const record = interactionDraftRecord('chat', 'card');
  const detach = attachDraftRecord(record);
  const first = record.load();
  detach();
  const release = attachDraftRecord(record);
  const second = record.load();
  pending.resolve(draft());
  expect(await first).toBe(true);
  expect(await second).toBe(true);
  expect(interactionDraftRecord('chat', 'card')).toBe(record);
  expect(readInteractionDraft).toHaveBeenCalledTimes(1);
  release();
});

it('keeps the conflict when adoption is attempted during a pending submission', async () => {
  const {record} = await open();
  record.update({'$body':'local'}, true);
  vi.mocked(saveInteractionDraft).mockRejectedValueOnce(new Error('409 conflict'));
  await record.save();
  record.beginSubmission(() => ({source_message_id:'card', state:record.state}));

  await expect(adoptRemoteDraft('chat', 'card')).rejects.toThrow();
  expect(draftFailures('chat')).toEqual([{messageId:'card', reason:'conflict'}]);
  expect(record.state).toEqual({'$body':'local'});
  expect(readInteractionDraft).toHaveBeenCalledTimes(1);
});

it('does not apply a stale adoption read over input edited while it was in flight', async () => {
  const {record} = await open();
  record.update({'$body':'local'}, true);
  vi.mocked(saveInteractionDraft).mockRejectedValueOnce(new Error('409 conflict'));
  await record.save();
  const pending = deferred<InteractionDraft>();
  vi.mocked(readInteractionDraft).mockReturnValueOnce(pending.promise);
  const adopting = record.load(true);
  // load waits for any prior PUT before starting the GET.
  await Promise.resolve();
  record.update({'$body':'newer local'}, true);
  pending.resolve(draft(9, 'remote'));
  expect(await adopting).toBe(false);
  expect(record.state).toEqual({'$body':'newer local'});
  expect(record.revision).toBe(2);
  expect(draftFailures('chat')).toEqual([{messageId:'card',reason:'conflict'}]);
});

it('forgets local edits on a real leave but still clears the watermark of an already-started PUT', async () => {
  const pending = deferred<InteractionDraft>();
  vi.mocked(saveInteractionDraft).mockReturnValueOnce(pending.promise);
  const {record, detach} = await open();
  record.update({'$body':'local'}, true);
  const saving = record.save();
  detach();
  await discardOnLeave('chat');
  expect(record.current).toBe(false);
  expect(record.state).toEqual({});
  expect(draftFailures('chat')).toEqual([]);
  pending.resolve(draft(3, 'local', T1));
  await saving;
  await awaitPendingDiscard('chat');
  expect(discardInteractionBackground).toHaveBeenCalledWith('chat', T1);
  expect(draftWatermark('chat')).toBeUndefined();
  resumeConversation('chat');
  const next = await open();
  expect(next.record).not.toBe(record);
  expect(next.record.state).toEqual({'$body':'remote'});
  next.detach();
});

it('keeps an old record leave intent after returning, without clearing the newer post-return edit', async () => {
  const pending = deferred<InteractionDraft>();
  vi.mocked(saveInteractionDraft).mockReturnValueOnce(pending.promise).mockResolvedValueOnce(draft(4, 'new edit', T2));
  const {record, detach} = await open();
  record.update({'$body':'pre-leave'}, true);
  const oldSave = record.save();
  detach();
  await discardOnLeave('chat');
  resumeConversation('chat');
  const next = await open();
  next.record.update({'$body':'post-return'}, true);
  await next.record.save();
  expect(draftWatermark('chat')).toBe(T2);
  pending.resolve(draft(3, 'pre-leave', T1));
  await oldSave;
  await awaitPendingDiscard('chat');
  expect(discardInteractionBackground).toHaveBeenCalledWith('chat', T1);
  expect(discardInteractionBackground).not.toHaveBeenCalledWith('chat', T2);
  expect(draftWatermark('chat')).toBe(T2);
  expect(next.record.state).toEqual({'$body':'post-return'});
  expect(next.record.current).toBe(true);
  next.detach();
});

it.each(['revoked', 'logout', 'other account'])('fences private state and late acknowledgements after %s', async reason => {
  const pending = deferred<InteractionDraft>();
  vi.mocked(saveInteractionDraft).mockReturnValueOnce(pending.promise);
  const {record, detach} = await open();
  record.update({'$body':'secret local'}, true);
  const saving = record.save();
  detach();
  if (reason === 'revoked') await forgetInteractionBackground('owner', 'chat');
  else resetInteractionBackground(reason === 'logout' ? '' : 'other-owner');
  expect(record.current).toBe(false);
  expect(record.state).toEqual({});
  pending.resolve(draft(3, 'secret local', T1));
  await saving;
  expect(draftWatermark('chat')).toBeUndefined();
  expect(draftFailures('chat')).toEqual([]);
  expect(discardInteractionBackground).not.toHaveBeenCalled();
  expect(interactionDraftRecord('chat', 'card')).not.toBe(record);
});

it('does not let a detached old flush resurrect failure after an actual leave', async () => {
  const pending = deferred<InteractionDraft>();
  vi.mocked(saveInteractionDraft).mockReturnValueOnce(pending.promise);
  const {record} = await open();
  record.update({'$body':'local'}, true);
  registerDraftHandle('chat','card',{flush:()=>record.flush(), describeConflict:async()=>({columns:[]}), adoptRemote:async()=>{}});
  const retry = retryDraft('chat','card');
  await discardOnLeave('chat');
  pending.resolve(draft(3, 'local', T1));
  await retry;
  await awaitPendingDiscard('chat');
  expect(draftFailures('chat')).toEqual([]);
});

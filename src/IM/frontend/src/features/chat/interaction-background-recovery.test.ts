import { beforeEach, expect, it, vi } from 'vitest';
import {
  draftFailures, noteDraftFailed, registerDraftHandle, resetInteractionBackground,
  retryPrivateDrafts, type DraftHandle,
} from './interaction-background';

vi.mock('./chat-api', () => ({discardInteractionBackground:vi.fn(), readInteractionDraft:vi.fn()}));
beforeEach(() => resetInteractionBackground());
const card = (flush: DraftHandle['flush']): DraftHandle => ({flush});

it('recovers both save failures and conflict refreshes in only the requested conversation', async () => {
  const transient = vi.fn(async () => ({})), conflict = vi.fn(async () => ({})), other = vi.fn(async () => ({}));
  registerDraftHandle('chat', 'a', card(transient));
  registerDraftHandle('chat', 'b', card(conflict));
  registerDraftHandle('other', 'c', card(other));
  noteDraftFailed('chat', 'a', 'transient'); noteDraftFailed('chat', 'b', 'conflict'); noteDraftFailed('other', 'c', 'transient');
  await retryPrivateDrafts('chat');
  expect(transient).toHaveBeenCalledTimes(1);
  expect(conflict).toHaveBeenCalledOnce();
  expect(other).not.toHaveBeenCalled();
  expect(draftFailures('chat')).toEqual([]);
});

it('coalesces simultaneous online and foreground attempts and leaves another failure for an explicit retry', async () => {
  let finish!: (value:{reason:'transient'}) => void;
  const flush = vi.fn(() => new Promise<{reason:'transient'}>(resolve => { finish = resolve; }));
  registerDraftHandle('chat', 'a', card(flush)); noteDraftFailed('chat', 'a', 'transient');
  const online = retryPrivateDrafts('chat'), foreground = retryPrivateDrafts('chat');
  expect(flush).toHaveBeenCalledTimes(1);
  finish({reason:'transient'});
  await Promise.all([online, foreground]);
  expect(flush).toHaveBeenCalledTimes(1);
  expect(draftFailures('chat')).toEqual([{messageId:'a', reason:'transient'}]);
});

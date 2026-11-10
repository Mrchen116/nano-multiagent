import { beforeEach, expect, it, vi } from 'vitest';
import { discardInteractionBackground } from './chat-api';
import {
  awaitPendingDiscard, awaitWatermarkWrite, discardOnLeave, draftWatermark,
  forgetInteractionBackground, loadWatermarks, noteDraftSaved, resetInteractionBackground,
  resumeConversation, retryPendingDiscards,
} from './interaction-background';

vi.mock('./chat-api', () => ({ discardInteractionBackground: vi.fn(), readInteractionDraft: vi.fn() }));
const T1 = '2026-05-01T00:00:01.000Z', T2 = '2026-05-01T00:00:02.000Z';

beforeEach(() => {
  resetInteractionBackground();
  vi.mocked(discardInteractionBackground).mockReset().mockResolvedValue({discarded_through:T1});
});

async function startReload() {
  await loadWatermarks('u1');
  noteDraftSaved('chat', T1);
  await awaitWatermarkWrite();
  resetInteractionBackground();
  return {restoring:loadWatermarks('u1')};
}

it('clears this device persisted watermark when it leaves before hydration finishes', async () => {
  const {restoring} = await startReload();
  const left = discardOnLeave('chat');
  await Promise.all([restoring, left]);
  await retryPendingDiscards();
  expect(discardInteractionBackground).toHaveBeenCalledExactlyOnceWith('chat', T1);
  expect(draftWatermark('chat')).toBeUndefined();
});

it('does not clear an edit made after returning while the old leave waits for hydration', async () => {
  const {restoring} = await startReload();
  const left = discardOnLeave('chat');
  resumeConversation('chat');
  noteDraftSaved('chat', T2);
  await Promise.all([restoring, left, awaitWatermarkWrite()]);
  expect(discardInteractionBackground).toHaveBeenCalledExactlyOnceWith('chat', T1);
  expect(draftWatermark('chat')).toBe(T2);
});

it('holds a returned conversation send behind the leave started during hydration', async () => {
  const {restoring} = await startReload();
  let resolve!: (value:{discarded_through:string}) => void;
  vi.mocked(discardInteractionBackground).mockReturnValueOnce(new Promise(done => { resolve = done; }));
  const left = discardOnLeave('chat');
  resumeConversation('chat');
  let sent = false;
  const sending = awaitPendingDiscard('chat').then(() => { sent = true; });
  await restoring;
  await vi.waitFor(() => expect(discardInteractionBackground).toHaveBeenCalledTimes(1));
  expect(sent).toBe(false);
  resolve({discarded_through:T1});
  await Promise.all([left, sending]);
  expect(sent).toBe(true);
});

it('does not reuse a completed startup snapshot after its ownership was revoked', async () => {
  const {restoring} = await startReload();
  await restoring;
  await forgetInteractionBackground('u1', 'chat');
  await discardOnLeave('chat');
  expect(discardInteractionBackground).not.toHaveBeenCalled();
});

it('does not submit an old hydrated leave after revocation', async () => {
  const {restoring} = await startReload();
  const left = discardOnLeave('chat');
  const revoked = forgetInteractionBackground('u1', 'chat');
  await Promise.all([restoring, left, revoked]);
  expect(discardInteractionBackground).not.toHaveBeenCalled();
});

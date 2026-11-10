import { beforeEach, describe, expect, it, vi } from 'vitest';

import { discardInteractionBackground } from './chat-api';
import {
  awaitPendingDiscard,
  awaitWatermarkWrite,
  beginSend,
  discardOnLeave,
  draftFailures,
  draftWatermark,
  draftSession,
  forgetInteractionBackground,
  loadWatermarks,
  noteDraftFailed,
  noteDraftSaved,
  registerDraftHandle,
  resetInteractionBackground,
  resumeConversation,
  retryDraft,
  retryPendingDiscards,
  type DraftHandle
} from './interaction-background';

vi.mock('./chat-api', () => ({
  discardInteractionBackground: vi.fn()
}));

const T1 = '2026-05-01T00:00:01.000Z';
const T2 = '2026-05-01T00:00:02.000Z';
const T3 = '2026-05-01T00:00:03.000Z';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(resolvePromise => { resolve = resolvePromise; });
  return { promise, resolve };
}

function handle(overrides: Partial<DraftHandle> = {}): DraftHandle {
  return {
    flush: vi.fn(async () => ({})),
    ...overrides
  };
}

/** Open the watermark store directly, which is the only way to see what a reload would keep. */
function readStoredRows(): Promise<{ userId: string; conversationId: string; through: string }[]> {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open('im-message-attempts');
    open.onsuccess = () => {
      const db = open.result;
      const request = db.transaction('watermarks', 'readonly').objectStore('watermarks').getAll();
      request.onsuccess = () => { resolve(request.result as { userId: string; conversationId: string; through: string }[]); db.close(); };
      request.onerror = () => { reject(request.error); db.close(); };
    };
    open.onerror = () => reject(open.error);
  });
}

beforeEach(() => {
  resetInteractionBackground();
  vi.mocked(discardInteractionBackground).mockReset();
});

describe('drafts block the send until they are saved', () => {
  it('does not let a conversation send while a card reports a 409 conflict', async () => {
    const card = handle({ flush: vi.fn(async () => ({ reason: 'conflict' as const })) });
    registerDraftHandle('chat', 'card', card);

    expect(await beginSend('chat')).toBe(false);
    expect(card.flush).toHaveBeenCalledTimes(1);
    expect(draftFailures('chat')).toEqual([{ messageId: 'card', reason: 'conflict' }]);
  });

  it('lets the conversation send once every card saved, and records the confirmed time', async () => {
    registerDraftHandle('chat', 'card', handle({ flush: vi.fn(async () => ({ updatedAt: T1 })) }));

    expect(await beginSend('chat')).toBe(true);
    expect(draftFailures('chat')).toEqual([]);
    expect(draftWatermark('chat')).toBe(T1);
  });

  it('treats a flush that throws as an unsaved edit instead of letting it escape into the send', async () => {
    registerDraftHandle('chat', 'card', handle({ flush: vi.fn(async () => { throw new Error('offline'); }) }));

    expect(await beginSend('chat')).toBe(false);
    expect(draftFailures('chat')).toEqual([{ messageId: 'card', reason: 'transient' }]);
  });

  it('keeps one entry per card and clears it only when that card saves', async () => {
    noteDraftFailed('chat', 'card', 'transient');
    noteDraftFailed('chat', 'card', 'conflict');
    expect(draftFailures('chat')).toEqual([{ messageId: 'card', reason: 'conflict' }]);

    const card = handle({ flush: vi.fn(async () => ({ updatedAt: T2 })) });
    registerDraftHandle('chat', 'card', card);
    await retryDraft('chat', 'card');
    expect(draftFailures('chat')).toEqual([]);
    expect(draftWatermark('chat')).toBe(T2);
  });
});

describe('leave watermark', () => {
  it('keeps the newest confirmed save when responses arrive out of order', () => {
    noteDraftSaved('chat', T2);
    noteDraftSaved('chat', T1);
    expect(draftWatermark('chat')).toBe(T2);
  });

  it('survives a reload for the same account and stays separate per account', async () => {
    await loadWatermarks('u1');
    noteDraftSaved('chat', T1);
    await awaitWatermarkWrite();

    // A reload keeps IndexedDB but loses the module state, exactly like a page refresh.
    resetInteractionBackground();
    await loadWatermarks('u1');
    expect(draftWatermark('chat')).toBe(T1);

    await loadWatermarks('u2');
    expect(draftWatermark('chat')).toBeUndefined();
    await loadWatermarks('u1');
    expect(draftWatermark('chat')).toBe(T1);
  });

  it('does not persist a save under an account selected while IndexedDB is opening', async () => {
    await loadWatermarks('u1');
    noteDraftSaved('chat', T1);
    await loadWatermarks('u2');
    await awaitWatermarkWrite();
    resetInteractionBackground();
    await loadWatermarks('u2');
    expect(draftWatermark('chat')).toBeUndefined();
  });

  it('ignores a previous account discard completion instead of deleting this account watermark', async () => {
    await loadWatermarks('u1');
    noteDraftSaved('chat', T1);
    await awaitWatermarkWrite();
    const clearing = deferred<{discarded_through: string}>();
    vi.mocked(discardInteractionBackground).mockReturnValueOnce(clearing.promise);
    const left = discardOnLeave('chat');
    await vi.waitFor(() => expect(discardInteractionBackground).toHaveBeenCalledTimes(1));
    await loadWatermarks('u2');
    noteDraftSaved('chat', T1);
    await awaitWatermarkWrite();
    clearing.resolve({discarded_through: T1});
    await left;
    expect(draftWatermark('chat')).toBe(T1);
  });

  it('forgets revoked and signed-out watermarks and rejects a late save from that scope', async () => {
    await loadWatermarks('u1');
    const oldSession = draftSession('chat');
    noteDraftSaved('chat', T1);
    noteDraftSaved('other', T2);
    await awaitWatermarkWrite();
    await forgetInteractionBackground('u1', 'chat');
    noteDraftSaved('chat', T3, oldSession);
    expect(draftWatermark('chat')).toBeUndefined();
    resetInteractionBackground();
    await loadWatermarks('u1');
    expect(draftWatermark('chat')).toBeUndefined();
    expect(draftWatermark('other')).toBe(T2);
    await forgetInteractionBackground('u1');
    await loadWatermarks('u1');
    expect(draftWatermark('other')).toBeUndefined();
  });

  it('does not rehydrate ownership revoked while the database was opening', async () => {
    await loadWatermarks('u1');
    noteDraftSaved('chat', T1);
    await awaitWatermarkWrite();
    resetInteractionBackground();
    const loading = loadWatermarks('u1');
    const revoked = forgetInteractionBackground('u1', 'chat');
    await Promise.all([loading, revoked]);
    expect(draftWatermark('chat')).toBeUndefined();
  });

  it('bounds the stored watermarks so a long-lived browser cannot grow without limit', async () => {
    await loadWatermarks('u1');
    for (let index = 0; index < 132; index += 1) {
      noteDraftSaved(`chat-${index}`, T1);
      await awaitWatermarkWrite();
    }
    const rows = (await readStoredRows()).filter(row => row.userId === 'u1');
    expect(rows.length).toBeLessThanOrEqual(128);
    expect(rows.some(row => row.conversationId === 'chat-131')).toBe(true);
  });

  it('sends nothing when this browser never confirmed a save in that conversation', async () => {
    await loadWatermarks('u1');
    await discardOnLeave('chat');
    expect(discardInteractionBackground).not.toHaveBeenCalled();
  });

  it('clears what it saved and then forgets it, so the same leave is not repeated', async () => {
    await loadWatermarks('u1');
    vi.mocked(discardInteractionBackground).mockResolvedValue({ discarded_through: T1 });
    noteDraftSaved('chat', T1);
    await awaitWatermarkWrite();

    await discardOnLeave('chat');
    expect(discardInteractionBackground).toHaveBeenCalledWith('chat', T1);
    expect(draftWatermark('chat')).toBeUndefined();
    expect(await readStoredRows()).toEqual([]);

    await discardOnLeave('chat');
    expect(discardInteractionBackground).toHaveBeenCalledTimes(1);
  });

  it('keeps the watermark when the server could not apply it, and retries on the next leave', async () => {
    await loadWatermarks('u1');
    // 404/501 (older server) is ignored by the api and must not count as cleared.
    vi.mocked(discardInteractionBackground).mockResolvedValueOnce(null);
    noteDraftSaved('chat', T1);
    await awaitWatermarkWrite();

    await discardOnLeave('chat');
    expect(draftWatermark('chat')).toBe(T1);

    vi.mocked(discardInteractionBackground).mockResolvedValueOnce({ discarded_through: T1 });
    await discardOnLeave('chat');
    expect(discardInteractionBackground).toHaveBeenCalledTimes(2);
    expect(draftWatermark('chat')).toBeUndefined();
  });

  it('does not discard a saved unsent edit on a foreground or a reload', async () => {
    await loadWatermarks('u1');
    noteDraftSaved('chat', T1);
    await awaitWatermarkWrite();
    await retryPendingDiscards();
    resetInteractionBackground();
    await loadWatermarks('u1');
    await retryPendingDiscards();
    expect(discardInteractionBackground).not.toHaveBeenCalled();
    expect(draftWatermark('chat')).toBe(T1);
  });

  it('retries a failed explicit leave after reload without clearing a newer edit', async () => {
    await loadWatermarks('u1');
    noteDraftSaved('chat', T1);
    await awaitWatermarkWrite();
    vi.mocked(discardInteractionBackground).mockResolvedValueOnce(null);
    await discardOnLeave('chat');
    resetInteractionBackground();
    await loadWatermarks('u1');
    resumeConversation('chat');
    noteDraftSaved('chat', T2);
    await awaitWatermarkWrite();
    vi.mocked(discardInteractionBackground).mockResolvedValueOnce({discarded_through: T1});
    await retryPendingDiscards();
    expect(discardInteractionBackground).toHaveBeenNthCalledWith(2, 'chat', T1);
    expect(draftWatermark('chat')).toBe(T2);
    resetInteractionBackground();
    await loadWatermarks('u1');
    await retryPendingDiscards();
    expect(discardInteractionBackground).toHaveBeenCalledTimes(2);
    expect(draftWatermark('chat')).toBe(T2);
  });

  it('serialises clears and sends a second one for a save that lands after the leave', async () => {
    await loadWatermarks('u1');
    const first = deferred<{ discarded_through: string } | null>();
    vi.mocked(discardInteractionBackground)
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce({ discarded_through: T2 });
    noteDraftSaved('chat', T1);
    await awaitWatermarkWrite();

    const leaving = discardOnLeave('chat');
    // The debounced PUT was already in flight when the user switched; its response (and this
    // device's own confirmed time) arrives after the clear was sent.
    noteDraftSaved('chat', T2);
    await vi.waitFor(() => expect(discardInteractionBackground).toHaveBeenCalledTimes(1));

    first.resolve({ discarded_through: T1 });
    await leaving;
    await awaitPendingDiscard('chat');

    // The late save is cleared by a second request that names this device's own time, and it
    // is sent only after the first one finished.
    expect(discardInteractionBackground).toHaveBeenNthCalledWith(2, 'chat', T2);
    expect(draftWatermark('chat')).toBeUndefined();
  });

  it('does not clear an edit made after coming back to the conversation', async () => {
    await loadWatermarks('u1');
    vi.mocked(discardInteractionBackground).mockResolvedValue({ discarded_through: T1 });
    noteDraftSaved('chat', T1);
    await awaitWatermarkWrite();
    await discardOnLeave('chat');
    expect(discardInteractionBackground).toHaveBeenCalledTimes(1);

    resumeConversation('chat');
    noteDraftSaved('chat', T2);
    await awaitWatermarkWrite();
    await Promise.resolve();
    // A new edit must stay carryable: no third clear may name it.
    expect(discardInteractionBackground).toHaveBeenCalledTimes(1);
    expect(draftWatermark('chat')).toBe(T2);
  });

  it('holds a message back until an in-flight clear has been applied', async () => {
    await loadWatermarks('u1');
    const clear = deferred<{ discarded_through: string } | null>();
    vi.mocked(discardInteractionBackground).mockReturnValueOnce(clear.promise);
    noteDraftSaved('chat', T1);
    await awaitWatermarkWrite();
    void discardOnLeave('chat');

    const order: string[] = [];
    const sending = (async () => { await awaitPendingDiscard('chat'); order.push('send'); })();
    await Promise.resolve();
    expect(order).toEqual([]);

    clear.resolve({ discarded_through: T1 });
    await sending;
    expect(order).toEqual(['send']);
  });
});

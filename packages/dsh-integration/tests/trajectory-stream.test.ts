import { expect, it, vi } from 'vitest';
import { TRAJECTORY_MAX_BYTES, TrajectoryValueDecoder } from '@nano/product-contracts';
import { TrajectoryStream } from '../src/trajectory-stream.js';

it('terminates a slow observer at the bounded queue while releasing the native iterator', async () => {
  let disposed = false;
  const stream = new TrajectoryStream(async function* () {
    try { for (let i = 0; i < 5; i++) yield { text: 'x'.repeat(700_000) }; }
    finally { disposed = true; }
  });
  await stream.settled;
  await expect(stream.next()).rejects.toThrow('trajectory_slow_consumer');
  expect(disposed).toBe(true);
});

it('keeps idle readers open but expires an unconsumed batch', async () => {
  vi.useFakeTimers();
  const idle = (signal: AbortSignal) => new Promise<void>(resolve => signal.addEventListener('abort', () => resolve(), { once: true }));
  const empty = new TrajectoryStream(async function* (signal) { await idle(signal); });
  const stale = new TrajectoryStream(async function* (signal) { yield { value: 'retained' }; await idle(signal); });
  try {
    const waiting = empty.next();
    await vi.advanceTimersByTimeAsync(20_000);
    expect(await waiting).toEqual({ frames: [], done: false });
    await expect(stale.next()).rejects.toThrow('trajectory_slow_consumer');
  } finally { empty.close(); stale.close(); await Promise.all([empty.settled, stale.settled]); vi.useRealTimers(); }
});

it('carries a multi-batch native opening without dropping history or overflowing its own queue', async () => {
  const opening = { type: 'snapshot', records: [{ text: '历史😀"\\'.repeat(400_000) }] };
  const source = new TrajectoryStream(async function* () { yield opening; yield { type: 'event', seq: 1 }; });
  const decoder = new TrajectoryValueDecoder(), restored: unknown[] = [];
  let batches = 0;
  try {
    while (true) {
      const batch = await source.next();
      expect(Buffer.byteLength(JSON.stringify(batch))).toBeLessThan(TRAJECTORY_MAX_BYTES);
      batches++;
      for (const frame of batch.frames) {
        const value = decoder.push(frame);
        if (value !== undefined) restored.push(value);
      }
      if (batch.done) break;
    }
    decoder.finish();
    expect(batches).toBeGreaterThan(2);
    expect(restored).toEqual([opening, { type: 'event', seq: 1 }]);
  } finally { source.close(); await source.settled; }
});

it('releases a source waiting for fragment capacity when its observer leaves', async () => {
  let released = false;
  const source = new TrajectoryStream(async function* () {
    try { yield { text: 'x'.repeat(5_000_000) }; }
    finally { released = true; }
  });
  await source.next();
  source.close();
  await source.settled;
  expect(released).toBe(true);
});

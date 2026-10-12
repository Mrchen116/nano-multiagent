import { expect, it, vi } from 'vitest';
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

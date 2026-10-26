import { afterEach, expect, it, vi } from 'vitest';
import { LlmError } from '@deepseek-ai/dsh-llm';
import { ReviewRecovery, interruptible } from '../src/policy/recovery.js';

afterEach(() => vi.useRealTimers());
const service = () => new LlmError('controlled failure', 'SERVER', { status: 503 });
const wait = (signal: AbortSignal) => interruptible(new Promise<never>(() => {}), signal);

it.each([['cc-s1', 30_000], ['cc-s2', 60_000], ['guardian', 90_000]] as const)(
  'exhausts three continuous timeouts with every full %s budget', async (scope, budget) => {
    vi.useFakeTimers();
    const recovery = new ReviewRecovery(new AbortController().signal, scope, () => 0.5);
    let calls = 0;
    const result = recovery.run(scope, budget, attempt => { calls++; return wait(attempt.signal); }).catch(error => error.category);
    await vi.advanceTimersByTimeAsync(budget * 3 + 1500);
    expect(await result).toBe('review_timeout');
    const trace = recovery.finish('review_timeout', 'return_to_agent');
    expect(calls).toBe(3); expect(trace.retriesUsed).toBe(2);
    expect(trace.formatRetriesUsed).toBe(0);
    expect(trace.attempts.map(row => [row.budgetMs, row.category, row.endedAt! - row.startedAt])).toEqual(Array.from({ length: 3 }, () => [budget, 'review_timeout', budget]));
    expect(trace.elapsedMs).toBe(budget * 3 + 1500);
  },
);

it.each([['cc-s1', 30_000], ['cc-s2', 60_000], ['guardian', 90_000]] as const)(
  'shares timeout then 503 then timeout quota in %s without a fourth request', async (scope, budget) => {
    vi.useFakeTimers();
    const recovery = new ReviewRecovery(new AbortController().signal, scope, () => 0.5);
    let calls = 0;
    const result = recovery.run(scope, budget, attempt => { if (++calls === 2) throw service(); return wait(attempt.signal); }).catch(error => error.category);
    await vi.advanceTimersByTimeAsync(budget * 2 + 1500);
    expect(await result).toBe('review_timeout');
    const trace = recovery.finish('review_timeout', 'return_to_agent');
    expect(calls).toBe(3); expect(trace.retriesUsed).toBe(2);
    expect(trace.attempts.map(row => [row.budgetMs, row.retryOrdinal, row.category])).toEqual([
      [budget, 0, 'review_timeout'], [budget, 1, 'transient'], [budget, 2, 'review_timeout'],
    ]);
    await vi.advanceTimersByTimeAsync(90_000); expect(calls).toBe(3);
  },
);

it('shares the action ceiling across normal CC stage progression and failures', async () => {
  vi.useFakeTimers();
  const recovery = new ReviewRecovery(new AbortController().signal, 'two-stage', () => 0.5);
  let first = 0;
  const stage1 = recovery.run('cc-s1', 30_000, async () => { if (++first === 1) throw service(); return 'nonallow'; });
  await vi.advanceTimersByTimeAsync(500); expect(await stage1).toBe('nonallow');
  let second = 0;
  const stage2 = recovery.run('cc-s2', 60_000, attempt => { second++; return wait(attempt.signal); }).catch(error => error.category);
  await vi.advanceTimersByTimeAsync(121_000); expect(await stage2).toBe('review_timeout');
  const trace = recovery.finish('review_timeout', 'interactive_pending');
  expect([first, second, trace.retriesUsed]).toEqual([2, 2, 2]);
  expect(trace.attempts.map(row => [row.scope, row.retryOrdinal, row.budgetMs])).toEqual([
    ['cc-s1', 0, 30_000], ['cc-s1', 1, 30_000], ['cc-s2', 1, 60_000], ['cc-s2', 2, 60_000],
  ]);
});

it('revokes an in-flight generation at the 360 second action deadline, with no successor', async () => {
  vi.useFakeTimers();
  const recovery = new ReviewRecovery(new AbortController().signal, 'deadline', () => 0.5);
  await vi.advanceTimersByTimeAsync(359_999);
  let calls = 0;
  const result = recovery.run('guardian', 90_000, attempt => { calls++; return wait(attempt.signal); }).catch(error => error.category);
  await vi.advanceTimersByTimeAsync(1); expect(await result).toBe('unavailable_unknown');
  const trace = recovery.finish('unavailable_unknown', 'return_to_agent');
  expect(trace.elapsedMs).toBe(360_000); expect(trace.retriesUsed).toBe(0); expect(calls).toBe(1);
  expect(trace.attempts[0]).toMatchObject({ budgetMs: 90_000, category: 'unavailable_unknown' });
  await vi.advanceTimersByTimeAsync(90_000); expect(calls).toBe(1);
});

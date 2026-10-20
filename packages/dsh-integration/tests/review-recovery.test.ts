import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { LlmError } from '@deepseek-ai/dsh-llm';
import { ReviewFailure, ReviewRecovery, reviewFailure } from '../src/policy/recovery.js';

const actions: ReviewRecovery[] = [];
function action(signal = new AbortController().signal) {
  const recovery = new ReviewRecovery(signal, 'call', 'codex', { provider: 'fixture', model: 'review' });
  actions.push(recovery); return recovery;
}
const transient = () => new LlmError('fixture', 'SERVER', { status: 503 });
const failed = (code: string, status?: number) => new LlmError('fixture', code, { status });

beforeEach(() => { vi.useFakeTimers(); vi.spyOn(Math, 'random').mockReturnValue(0.5); });
afterEach(() => { for (const recovery of actions.splice(0)) recovery.finish('test', 'none'); vi.restoreAllMocks(); vi.useRealTimers(); });

it('shares two recoveries across stages without replaying a valid first stage', async () => {
  const recovery = action(); let first = 0; let second = 0;
  const review = (async () => {
    const decision = await recovery.run('cc-s1', 30_000, async () => { if (++first === 1) throw transient(); return 'nonallow'; });
    expect(decision).toBe('nonallow');
    return recovery.run('cc-s2', 60_000, async () => { if (++second <= 2) throw transient(); return 'allow'; });
  })();
  const rejected = expect(review).rejects.toMatchObject({ category: 'transient' });
  await vi.advanceTimersByTimeAsync(1_500); await rejected;
  expect([first, second]).toEqual([2, 2]);
  expect(recovery.trace.attempts.map(row => [row.scope, row.retryOrdinal])).toEqual([['cc-s1', 0], ['cc-s1', 1], ['cc-s2', 1], ['cc-s2', 2]]);
});

it.each([
  { errors: [transient(), new ReviewFailure('malformed')], calls: 3, formats: 1, success: true },
  { errors: [new ReviewFailure('empty_text'), new ReviewFailure('malformed')], calls: 2, formats: 1, success: false },
  { errors: [transient(), transient(), new ReviewFailure('empty_response')], calls: 3, formats: 0, success: false },
  { errors: [failed('EMPTY_RESPONSE'), failed('EMPTY_RESPONSE')], calls: 2, formats: 1, success: false },
])('enforces shared format sublimit ($calls requests)', async ({ errors, calls, formats, success }) => {
  const recovery = action(); let count = 0;
  const pending = recovery.run('guardian', 90_000, async () => { const error = errors[count++]; if (error) throw error; return 'allow'; });
  const check = success ? expect(pending).resolves.toBe('allow') : expect(pending).rejects.toBeInstanceOf(ReviewFailure);
  await vi.advanceTimersByTimeAsync(2_000); await check;
  expect(count).toBe(calls); expect(recovery.trace.formatRetriesUsed).toBe(formats);
});

it.each([30_000, 60_000, 90_000])('gives all three timeout attempts the complete %sms judgment budget', async budget => {
  const recovery = action(); const starts: number[] = [];
  const review = recovery.run('normal', budget, async attempt => {
    starts.push(Date.now());
    await new Promise<void>(resolve => attempt.signal.addEventListener('abort', () => resolve(), { once: true }));
    attempt.assertActive();
  });
  const rejected = expect(review).rejects.toMatchObject({ category: 'review_timeout' });
  await vi.advanceTimersByTimeAsync(budget * 3 + 1500); await rejected;
  expect(starts.map(time => time - starts[0]!)).toEqual([0, budget + 500, budget * 2 + 1500]);
  expect(recovery.trace.attempts.map(row => row.endedAt! - row.startedAt)).toEqual([budget, budget, budget]);
});

it('preparation timeout does not retry or consume judgment allowance', async () => {
  const recovery = action(); let entered = 0;
  const pending = recovery.prepare(async () => { entered++; return new Promise(() => {}); });
  const rejected = expect(pending).rejects.toMatchObject({ category: 'prepare_timeout' });
  await vi.advanceTimersByTimeAsync(15_000); await rejected;
  expect(entered).toBe(1); expect(recovery.trace.retriesUsed).toBe(0);
});

it('cancels backoff and never restarts even when the next verdict would allow', async () => {
  const parent = new AbortController(); const recovery = action(parent.signal); let calls = 0;
  const pending = recovery.run('guardian', 90_000, async () => { if (++calls === 1) throw transient(); return 'allow'; });
  const rejected = expect(pending).rejects.toThrow();
  await vi.advanceTimersByTimeAsync(100); parent.abort();
  await vi.advanceTimersByTimeAsync(10_000); await rejected;
  expect(calls).toBe(1);
});

it('parent cancellation wins a same-tick deadline/late allow', async () => {
  const parent = new AbortController(); const recovery = action(parent.signal);
  const pending = recovery.run('guardian', 90_000, async attempt => {
    await new Promise<void>(resolve => attempt.signal.addEventListener('abort', () => { parent.abort(); resolve(); }, { once: true }));
    return 'allow';
  });
  const rejected = expect(pending).rejects.toThrow();
  await vi.advanceTimersByTimeAsync(90_000); await rejected;
  expect(recovery.trace.retriesUsed).toBe(0);
});

it('quarantines uncooperative work after five seconds and cannot accept its late allow', async () => {
  const recovery = action(); let late!: (value: string) => void; let quarantines = 0; let count = 0;
  const pending = recovery.run('guardian', 90_000, async attempt => {
    count++; attempt.onQuarantine = () => quarantines++;
    return new Promise<string>(resolve => { late = resolve; });
  });
  const rejected = expect(pending).rejects.toMatchObject({ category: 'cleanup_unavailable' });
  await vi.advanceTimersByTimeAsync(95_000); await rejected;
  late('allow'); await vi.advanceTimersByTimeAsync(20_000);
  expect(count).toBe(1); expect(quarantines).toBe(1); expect(recovery.trace.retriesUsed).toBe(0);
});

it('keeps context rebuild allowance across a service recovery', async () => {
  const recovery = action(); let count = 0;
  const pending = recovery.run('guardian', 90_000, async () => {
    if (++count === 1) { expect(recovery.takeContextRebuild()).toBe(true); throw transient(); }
    expect(recovery.takeContextRebuild()).toBe(false); throw new ReviewFailure('context');
  });
  const rejected = expect(pending).rejects.toMatchObject({ category: 'context' });
  await vi.advanceTimersByTimeAsync(500); await rejected;
  expect(recovery.trace.contextRebuilds).toBe(1); expect(count).toBe(2);
});

it.each([
  ['AUTH', 429, 'permanent'], ['QUOTA', 429, 'permanent'], ['SERVER', 500, 'unavailable_unknown'],
  ['SERVER', 503, 'transient'], ['SERVER', undefined, 'transient'], ['TIMEOUT', undefined, 'transient'],
  ['ABORTED', undefined, 'unavailable_unknown'], ['CONTEXT_WINDOW_EXCEEDED', undefined, 'context'],
] as const)('classifies structured %s/%s conservatively', (code, status, category) => {
  expect(reviewFailure(failed(code, status)).category).toBe(category);
  expect(reviewFailure(new Error('503 timeout context overflow connection reset')).category).toBe('unavailable_unknown');
});

it('does not truncate an over-budget Retry-After to send early', async () => {
  const recovery = action(); let calls = 0;
  const pending = recovery.run('guardian', 90_000, async () => { calls++; throw new LlmError('fixture', 'RATE_LIMIT', { status: 429, providerRetryAfterMs: 15_000 }); });
  await expect(pending).rejects.toMatchObject({ category: 'retry_after_exceeds_budget' });
  expect(calls).toBe(1); expect(recovery.trace.retriesUsed).toBe(0);
});

it('caps request summaries and usage details without losing available overflow totals', async () => {
  const recovery = action();
  await recovery.run('guardian', 90_000, async attempt => {
    for (let index = 0; index < 103; index++) {
      for await (const _chunk of attempt.stream(async function* () {
        yield { type: 'usage', usage: { inputTokens: 10, outputTokens: 5 } };
        yield { type: 'finish', reason: { kind: 'stop' } };
      })) { /* consume the actual stream seam */ }
    }
  });
  const trace = recovery.finish('allow', 'allow');
  expect(trace.attempts[0]?.requestCount).toBe(103); expect(trace.attempts[0]?.requests).toHaveLength(100);
  expect(trace.knownUsage).toHaveLength(100); expect(trace.requestsTruncated).toBe(true);
  expect(trace.overflowKnownUsage).toEqual({ inputTokens: 30, outputTokens: 15 });
});

it('action protection revokes the judgment at 360 seconds without another retry', async () => {
  const recovery = action();
  const pending = recovery.run('guardian', 1_000_000, async attempt => {
    await new Promise<void>(resolve => attempt.signal.addEventListener('abort', () => resolve(), { once: true }));
    return 'late allow';
  });
  const rejected = expect(pending).rejects.toMatchObject({ category: 'action_timeout' });
  await vi.advanceTimersByTimeAsync(360_000); await rejected;
  expect(recovery.trace.retriesUsed).toBe(0);
});

it('seals trace without prompts and leaves unknown usage unknown', async () => {
  const recovery = action();
  await recovery.run('guardian', 90_000, async () => ({ outcome: 'deny' }));
  const trace = recovery.finish('deny', 'deny');
  expect(trace).toMatchObject({ complete: true, retriesUsed: 0, knownUsage: [] });
  expect(JSON.stringify(trace)).not.toContain('prompt');
});

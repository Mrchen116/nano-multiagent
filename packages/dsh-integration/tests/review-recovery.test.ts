import { afterEach, expect, it, vi } from 'vitest';
import { LlmError } from '@deepseek-ai/dsh-llm';
import { ReviewRecovery, invalidVerdict, interruptible, type ReviewAttempt } from '../src/policy/recovery.js';
import { recoveryTrace } from '../src/policy/audit.js';

const serviceFailure = () => new LlmError('temporary service failure', 'SERVER', { status: 503 });
function action() { return new ReviewRecovery(new AbortController().signal, 'one-tool-call', () => 0.5); }
afterEach(() => { vi.useRealTimers(); });

it.each([
  ['service-format-success', [serviceFailure(), invalidVerdict('malformed'), 'allow'], 2, 1, 'allow'],
  ['format-format-success', [invalidVerdict('empty_text'), invalidVerdict('malformed'), 'allow'], 1, 1, 'invalid_verdict'],
  ['service-service-format', [serviceFailure(), serviceFailure(), invalidVerdict('malformed')], 2, 0, 'invalid_verdict'],
  ['empty-response-subquota', [new LlmError('empty', 'EMPTY_RESPONSE'), new LlmError('empty', 'EMPTY_RESPONSE'), 'allow'], 1, 1, 'invalid_verdict'],
] as const)('shares two extra recoveries with a single format subquota: %s', async (_name, sequence, retries, formats, terminal) => {
  vi.useFakeTimers();
  const recovery = action(); let calls = 0;
  const result = recovery.run('guardian', 90_000, async () => {
    const item = sequence[calls++]; if (item instanceof Error) throw item; return item;
  }).then(value => value, error => error.category);
  await vi.runAllTimersAsync();
  expect(await result).toBe(terminal);
  const trace = recovery.finish(terminal, 'return_to_agent');
  expect(trace.retriesUsed).toBe(retries); expect(trace.formatRetriesUsed).toBe(formats);
  expect(calls).toBe(retries + 1);
  expect(trace.attempts.map(attempt => attempt.budgetMs)).toEqual(Array(calls).fill(90_000));
  expect(recoveryTrace.parse(trace)).toEqual(trace);
});

it('keeps complete 30/60/90 second budgets and counts normal CC stage progression separately', async () => {
  vi.useFakeTimers(); const recovery = action(); let first = true;
  const stage1 = recovery.run('cc-s1', 30_000, async attempt => {
    if (first) { first = false; await interruptible(new Promise<never>(() => {}), attempt.signal); }
    return 'nonallow';
  });
  await vi.advanceTimersByTimeAsync(30_500); expect(await stage1).toBe('nonallow');
  let second = true;
  const stage2 = recovery.run('cc-s2', 60_000, async attempt => {
    if (second) { second = false; await interruptible(new Promise<never>(() => {}), attempt.signal); }
    return 'allow';
  });
  await vi.advanceTimersByTimeAsync(61_000); expect(await stage2).toBe('allow');
  const trace = recovery.finish('allow', 'allow');
  expect(trace.attempts.map(row => [row.scope, row.budgetMs, row.retryOrdinal])).toEqual([
    ['cc-s1', 30_000, 0], ['cc-s1', 30_000, 1], ['cc-s2', 60_000, 1], ['cc-s2', 60_000, 2],
  ]);
  expect(trace.elapsedMs).toBe(91_500);
});

it.each([
  ['AUTH', 429, 'permanent'], ['QUOTA', 429, 'permanent'], ['INVALID_REQUEST', 503, 'permanent'],
  ['CONTEXT_WINDOW_EXCEEDED', undefined, 'context'], ['ABORTED', undefined, 'unavailable_unknown'],
  ['SERVER', 500, 'unavailable_unknown'], ['SERVER', 502, 'unavailable_unknown'],
])('does not retry permanent, context or unclassified failures: %s/%s', async (code, status, category) => {
  const recovery = action(); let calls = 0;
  await expect(recovery.run('legacy', 30_000, async () => { calls++; throw new LlmError('not recoverable', code, { status }); })).rejects.toMatchObject({ category });
  expect(calls).toBe(1); expect(recovery.finish(category, 'return_to_agent').retriesUsed).toBe(0);
});

it('honors provider Retry-After without truncation or changing the shared ceiling', async () => {
  vi.useFakeTimers(); const recovery = action(); const times: number[] = [];
  const result = recovery.run('guardian', 90_000, async () => {
    times.push(Date.now()); if (times.length < 3) throw new LlmError('limited', 'RATE_LIMIT', { status: 429, providerRetryAfterMs: 2000 }); return 'allow';
  });
  await vi.advanceTimersByTimeAsync(1999); expect(times).toHaveLength(1);
  await vi.advanceTimersByTimeAsync(2001); expect(await result).toBe('allow');
  expect(times.map(time => time - times[0]!)).toEqual([0, 2000, 4000]);
  expect(recovery.finish('allow', 'allow').attempts.slice(0, 2).map(row => row.retryAfterKnown)).toEqual([true, true]);
  const excessive = action();
  await expect(excessive.run('guardian', 90_000, async () => { throw new LlmError('limited', 'RATE_LIMIT', { providerRetryAfterMs: 15000 }); })).rejects.toMatchObject({ category: 'retry_after_exceeds_budget' });
  expect(excessive.finish('unavailable', 'unattended', 'allow').retriesUsed).toBe(0);
});

it.each(['request', 'backoff'] as const)('cancellation in %s revokes old publishing rights and launches no successor', async phase => {
  vi.useFakeTimers(); const parent = new AbortController(); const recovery = new ReviewRecovery(parent.signal, 'cancel-call', () => 0.5);
  let calls = 0; let captured: ReviewAttempt | undefined;
  const result = recovery.run('guardian', 90_000, async attempt => {
    calls++; captured = attempt;
    if (phase === 'backoff') throw serviceFailure();
    return interruptible(new Promise<never>(() => {}), attempt.signal);
  }).catch(error => error.category);
  await vi.advanceTimersByTimeAsync(0); parent.abort(); await vi.advanceTimersByTimeAsync(5000);
  expect(await result).toBe('cancelled'); expect(calls).toBe(1);
  expect(() => captured!.assertActive()).toThrow();
  expect(recovery.finish('cancelled', 'cancel').terminalReason).toBe('cancelled');
});

it('fails closed after five seconds when an aborted provider ignores cleanup, discarding late allow', async () => {
  vi.useFakeTimers(); const parent = new AbortController(); const recovery = new ReviewRecovery(parent.signal);
  let complete!: (value: string) => void; let calls = 0;
  const result = recovery.run('guardian', 90_000, async () => { calls++; return new Promise<string>(resolve => { complete = resolve; }); }).catch(error => error.category);
  await vi.advanceTimersByTimeAsync(90_000); expect(calls).toBe(1);
  await vi.advanceTimersByTimeAsync(5000); expect(await result).toBe('cleanup_unavailable');
  complete('allow'); await vi.advanceTimersByTimeAsync(10_000); expect(calls).toBe(1);
  expect(recovery.finish('cleanup_unavailable', 'return_to_agent').retriesUsed).toBe(0);
});

it('bounds preparation once and does not accept late evidence or pretend unknown usage is zero', async () => {
  vi.useFakeTimers(); const recovery = action(); let finish!: (value: string) => void;
  const result = recovery.prepare(async () => new Promise<string>(resolve => { finish = resolve; })).catch(error => error.category);
  await vi.advanceTimersByTimeAsync(15_000); expect(await result).toBe('prepare_timeout'); finish('late-evidence');
  const trace = recovery.finish('prepare_timeout', 'return_to_agent');
  expect(trace.attempts).toEqual([]); expect(trace.knownUsage).toBeUndefined(); expect(trace.usageComplete).toBe(false);
});

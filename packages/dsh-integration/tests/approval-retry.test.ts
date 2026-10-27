import { afterEach, expect, it, vi } from 'vitest';
import { LlmError } from '@deepseek-ai/dsh-llm';
import { retryReview, ReviewFailure, reviewFailure } from '../src/policy/retry.js';
import { classify } from '../src/policy/classifier.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

const realImmediate = globalThis.setImmediate;
const reviewer = { provider: 'fixture', model: 'fixed-reviewer' };
const allow = { decision: { behavior: 'allow' as const, reason: 'authorized' } };
afterEach(() => vi.useRealTimers());

it.each([
  [['SERVER', 'SERVER', 'allow'], ['service', 'service', 'allow'], 2, 0],
  [['RATE_LIMIT', 'TRANSPORT', 'TIMEOUT', 'allow'], ['service', 'transport', 'timeout'], 2, 0],
  [['invalid', 'SERVER', 'allow'], ['invalid', 'service', 'allow'], 2, 1],
  [['SERVER', 'invalid', 'invalid'], ['service', 'invalid', 'invalid'], 2, 1],
  [['invalid', 'invalid', 'allow'], ['invalid', 'invalid'], 1, 1],
] as const)('shares failure budgets across %j', async (sequence, categories, extras, invalid) => {
  vi.useFakeTimers();
  let calls = 0;
  const pending = retryReview(async () => {
    const item = sequence[calls++];
    if (item === 'allow') return allow;
    if (item === 'invalid') throw new ReviewFailure('invalid');
    throw new LlmError('provider payload is not authorization', item!);
  }, new AbortController().signal, reviewer);
  await vi.runAllTimersAsync();
  const outcome = await pending;
  expect(outcome.retry.attempts.map(a => a.category)).toEqual(categories);
  expect(calls).toBe(categories.length);
  expect(outcome.retry).toMatchObject({ extraUsed: extras, invalidRecoveryUsed: invalid });
  expect(outcome.retry.attempts.every(a => a.reviewer.model === reviewer.model)).toBe(true);
});

it.each(['AUTH', 'MISSING_CREDENTIAL', 'INVALID_CREDENTIAL', 'NO_ADAPTER', 'QUOTA', 'UNKNOWN'])('never retries permanent %s even with 503 status', async code => {
  let calls = 0;
  const result = await retryReview(async () => { calls++; throw new LlmError('secret', code, { status: 503 }); }, new AbortController().signal, reviewer);
  expect(calls).toBe(1);
  expect(JSON.stringify(result.retry)).not.toContain('secret');
  expect(result.retry.extraUsed).toBe(0);
});

it('does not retry final deny or guess transport failures from text', async () => {
  const result = await retryReview(async () => ({ decision: { behavior: 'deny', reason: 'outside scope' } }), new AbortController().signal, reviewer);
  expect(result.retry.attempts).toHaveLength(1);
  expect(result.retry.finalCategory).toBe('deny');
  expect(reviewFailure(new Error('503 fetch timeout'))).toMatchObject({ category: 'unknown' });
});

it('gives every cooperative timeout a full new 90 seconds, caps hints and bounds total elapsed', async () => {
  vi.useFakeTimers();
  const starts: number[] = [];
  const pending = retryReview(signal => new Promise((_, reject) => {
    starts.push(Date.now());
    signal.addEventListener('abort', () => reject(signal.reason), { once: true });
  }), new AbortController().signal, reviewer);
  await vi.runAllTimersAsync();
  const result = await pending;
  expect(starts.map(t => t - starts[0]!)).toEqual([0, 90_500, 181_500]);
  expect(result.retry.attempts.map(a => a.elapsedMs)).toEqual([90_000, 90_000, 90_000]);
  expect(result.retry.totalElapsedMs).toBe(271_500);
  let calls = 0;
  const hinted = retryReview(async () => { if (++calls < 3) throw new LlmError('busy', 'SERVER', { providerRetryAfterMs: 99_000 }); return allow; }, new AbortController().signal, reviewer);
  await vi.runAllTimersAsync();
  expect((await hinted).retry.attempts.map(a => a.delayAfterMs)).toEqual([10_000, 10_000, undefined]);
});

it('bounds an uncooperative attempt and never starts a concurrent replacement or accepts late success', async () => {
  vi.useFakeTimers();
  let finish!: (value: typeof allow) => void; let calls = 0;
  const pending = retryReview(() => { calls++; return new Promise(resolve => { finish = resolve; }); }, new AbortController().signal, reviewer);
  await vi.advanceTimersByTimeAsync(90_050);
  const result = await pending;
  expect(result.error).toMatchObject({ category: 'timeout', cleanupConfirmed: false });
  expect(calls).toBe(1);
  finish(allow); await Promise.resolve();
  expect(result.result).toBeUndefined();
  expect(result.retry.finalCategory).toBe('timeout');
});

it('does not upgrade nested unconfirmed drain when the outer operation settles at its deadline', async () => {
  vi.useFakeTimers(); let calls = 0;
  const pending = retryReview(async signal => {
    calls++;
    // A stage wrapper can settle after abort while its iterator still ignores it.
    signal.addEventListener('abort', () => {}, { once: true });
    await new Promise<void>(resolve => setTimeout(resolve, 90_000));
    throw new ReviewFailure('timeout', undefined, false);
  }, new AbortController().signal, reviewer);
  await vi.runAllTimersAsync();
  const result = await pending;
  expect(result.error).toMatchObject({ category: 'timeout', cleanupConfirmed: false });
  expect(calls).toBe(1);
});

it('retains CC 30/60 stage limits inside fresh complete attempts and snapshots actual inputs', async () => {
  vi.useFakeTimers();
  let started!: () => void; const entered = new Promise<void>(resolve => { started = resolve; });
  let calls = 0; let snapshots = 0; const requests: any[] = [];
  const parent = new AbortController();
  const request: any = { exec: { agent: { session: { header: { cwd: '/workspace' } } }, signal: parent.signal },
    config: { approval: { ...approvalDefaults, globalRoot: '/owner' } }, inherited: [], reviewer, snapshot: {},
    sources: { transcript: async () => { snapshots++; return 'original owner evidence and exact action'; } } };
  const ctx: any = { llm: { resolveModelInfo: async () => ({ context: { contextWindow: 100000 } }), stream: async function* (options: any) {
    const n = calls++; requests.push(options); started();
    yield { type: 'usage', usage: { inputTokens: 7, outputTokens: 2 } };
    if (n === 0 || n === 2) {
      await new Promise<void>(resolve => options.signal.addEventListener('abort', () => resolve(), { once: true }));
      options.signal.throwIfAborted();
    }
    yield { type: 'block-end', index: 0, block: { type: 'text', text: n === 1 ? '<block>yes</block><reason>second stage required</reason>' : '<block>no</block>' } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  } } };
  const pending = retryReview((attemptSignal, children) => classify(ctx, { ...request, attemptSignal, children }), parent.signal, reviewer);
  await entered;
  // Real policy assets may complete between stages; advance only after each request exists.
  await vi.advanceTimersByTimeAsync(30_500);
  while (calls < 3) await new Promise<void>(resolve => realImmediate(resolve));
  await vi.advanceTimersByTimeAsync(61_000);
  while (calls < 4) await new Promise<void>(resolve => realImmediate(resolve));
  const result = await pending;
  expect(result.retry.attempts.map(a => a.category)).toEqual(['timeout', 'timeout', 'allow']);
  expect(result.retry.attempts.map(a => a.elapsedMs)).toEqual([30_000, 60_000, 0]);
  expect(result.retry.attempts.map(a => a.children.map(c => c.stage))).toEqual([[1], [1, 2], [1]]);
  expect(requests.map(r => r.maxTokens)).toEqual([2112, 2112, 10240, 2112]);
  expect(requests[0].messages).toEqual(requests[1].messages);
  expect(requests[1].messages).toEqual(requests[3].messages);
  expect(snapshots).toBe(1);
  expect(result.retry.attempts.every(a => a.children.every(c => c.usage !== undefined))).toBe(true);
});

it.each(['active', 'backoff', 'allow'] as const)('cancellation wins at %s without another attempt', async phase => {
  vi.useFakeTimers();
  const parent = new AbortController(); let calls = 0;
  const pending = retryReview(async signal => {
    calls++;
    if (phase === 'allow') { parent.abort(); return allow; }
    if (phase === 'backoff') throw new LlmError('busy', 'SERVER');
    return new Promise((_, reject) => signal.addEventListener('abort', () => reject(signal.reason), { once: true }));
  }, parent.signal, reviewer);
  await vi.advanceTimersByTimeAsync(1);
  parent.abort();
  await vi.runAllTimersAsync();
  const result = await pending;
  expect(result.error?.category).toBe('cancel');
  expect(result.result).toBeUndefined();
  expect(calls).toBe(1);
  expect(result.retry.extraUsed).toBe(0);
});

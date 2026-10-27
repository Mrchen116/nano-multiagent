import { randomUUID } from 'node:crypto';
import { EMPTY_RESPONSE_CODE, HarnessError, LlmError, resolveRetryPolicy, type LlmFailure } from '@deepseek-ai/dsh-llm';
import type { ApprovalReviewResult, ReviewAttempt, ReviewRetry, ReviewChild } from './types.js';

const policy = resolveRetryPolicy({ mode: 'normal', maxRetries: 2, retryableCodes: ['RATE_LIMIT', 'SERVER', 'TRANSPORT', 'TIMEOUT'],
  backoff: { initialDelayMs: 500, maxDelayMs: 10_000, jitterRatio: 0 } }, 'nano.approval');

/** Carry structured review failure facts without exposing provider text as authorization. */
export class ReviewFailure extends Error {
  constructor(readonly category: string, readonly failure?: LlmFailure, readonly cleanupConfirmed = true) {
    super(`Automatic review ${category}${failure ? ` (${failure.code})` : ''}`);
  }
}

/** Normalize public DSH failures; unknown errors deliberately fail closed.
 * Args:
 *   error: A thrown error or already normalized review failure.
 * Returns:
 *   Stable category and safe machine facts; error text never selects recovery.
 */
export function reviewFailure(error: unknown): ReviewFailure {
  if (error instanceof ReviewFailure) return error;
  const failure = error instanceof LlmError ? error.failure : error instanceof HarnessError ? { code: error.code, message: error.message } : undefined;
  if (!failure) return new ReviewFailure('unknown');
  const code = failure.code;
  const category = code === EMPTY_RESPONSE_CODE ? 'invalid' : ['AUTH', 'MISSING_CREDENTIAL', 'INVALID_CREDENTIAL'].includes(code) ? 'auth'
    : ['NO_ADAPTER', 'CONFIG', 'INVALID_CONFIG'].includes(code) ? 'config'
    : ['RATE_LIMIT', 'SERVER'].includes(code) ? 'service' : code === 'TRANSPORT' ? 'transport' : code === 'TIMEOUT' ? 'timeout'
    : code === 'QUOTA' ? 'quota' : code === 'CONTEXT_WINDOW_EXCEEDED' ? 'context' : 'unknown';
  // Provider messages may contain payloads or credentials. Retain only machine facts.
  return new ReviewFailure(category, { code, message: `Reviewer ${category}`, ...(failure.status !== undefined ? { status: failure.status } : {}),
    ...(failure.requestId ? { requestId: failure.requestId } : {}), ...(failure.providerRetryAfterMs !== undefined ? { providerRetryAfterMs: failure.providerRetryAfterMs } : {}) });
}

/** Bound a signal-aware operation, consuming late settlement without concurrent recovery.
 * Args:
 *   run: Operation observing signal; must not publish after cancellation.
 *   signal: Attempt or stage cancellation boundary.
 * Returns:
 *   Operation result, or a failure marking unconfirmed local drain after 50ms.
 * Notes:
 *   The grace period only permits cooperative cleanup, never authorizes another request.
 */
export async function boundedReview<T>(run: () => Promise<T>, signal: AbortSignal): Promise<T> {
  signal.throwIfAborted();
  let settled = false; let operationFailure: unknown;
  const work = Promise.resolve().then(() => { signal.throwIfAborted(); return run(); }).catch(error => { operationFailure = error; throw error; }).finally(() => { settled = true; });
  let listener: () => void = () => {};
  const aborted = new Promise<never>((_, reject) => {
    listener = () => reject(signal.reason);
    signal.addEventListener('abort', listener, { once: true });
    if (signal.aborted) listener();
  });
  try { return await Promise.race([work, aborted]); }
  catch (error) {
    if (!signal.aborted) throw error;
    let timer: ReturnType<typeof setTimeout> | undefined;
    await Promise.race([work.catch(() => {}), new Promise<void>(resolve => { timer = setTimeout(resolve, 50); })]);
    clearTimeout(timer);
    const failure = reviewFailure(signal.reason);
    // A nested stage may have returned while its iterator is still pending.
    // Settling the wrapper is not evidence that the underlying request drained.
    throw new ReviewFailure(failure.category, failure.failure, settled && reviewFailure(operationFailure).cleanupConfirmed);
  } finally { signal.removeEventListener('abort', listener); }
}

/** Wait without retaining an abort listener or timer after either outcome. */
export function reviewDelay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const finish = (error?: unknown) => { clearTimeout(timer); signal.removeEventListener('abort', abort); error ? reject(error) : resolve(); };
    const abort = () => finish(signal.reason ?? new ReviewFailure('cancel'));
    const timer = setTimeout(() => finish(), ms);
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) abort();
  });
}

/** Execute complete policy attempts under fresh budgets, never replaying a tool.
 * Args:
 *   run: One full strategy including preparation; collects stage/request facts.
 *   parent: Tool cancellation signal; wins over late success.
 *   reviewer: Frozen provider/model identity for the entire review.
 * Returns:
 *   Final result or failure plus one immutable audit aggregate.
 */
export async function retryReview(run: (signal: AbortSignal, children: ReviewChild[]) => Promise<ApprovalReviewResult>, parent: AbortSignal,
  reviewer: { provider: string; model: string }): Promise<{ result?: ApprovalReviewResult; error?: ReviewFailure; retry: ReviewRetry }> {
  const started = Date.now();
  const retry: ReviewRetry = { reviewId: randomUUID(), attempts: [], extraUsed: 0, invalidRecoveryUsed: 0, finalCategory: 'unknown', totalElapsedMs: 0 };
  let result: ApprovalReviewResult | undefined; let error: ReviewFailure | undefined;
  let pendingInvalid = false;
  while (!parent.aborted) {
    if (retry.attempts.length) { retry.extraUsed++; if (pendingInvalid) retry.invalidRecoveryUsed++; }
    const controller = new AbortController();
    const cancel = () => controller.abort(new ReviewFailure('cancel'));
    parent.addEventListener('abort', cancel, { once: true });
    const timer = setTimeout(() => controller.abort(new ReviewFailure('timeout')), 90_000);
    const attempt: ReviewAttempt = { ordinal: retry.attempts.length + 1, start: Date.now(), end: 0, elapsedMs: 0, outcome: 'failure', category: 'unknown', reviewer: { ...reviewer }, children: [] };
    retry.attempts.push(attempt);
    try {
      if (parent.aborted) cancel();
      result = await boundedReview(() => run(controller.signal, attempt.children), controller.signal);
      if (parent.aborted) throw new ReviewFailure('cancel');
      attempt.outcome = result.decision.behavior; attempt.category = result.decision.behavior;
      if (result.usage !== undefined) attempt.usage = result.usage;
      if (result.metadata) attempt.metadata = result.metadata;
      error = undefined;
    } catch (caught) {
      error = parent.aborted ? new ReviewFailure('cancel', undefined, reviewFailure(caught).cleanupConfirmed) : reviewFailure(caught);
      attempt.category = error.category; attempt.cleanupConfirmed = error.cleanupConfirmed;
      if (error.failure) attempt.failure = error.failure;
    } finally {
      clearTimeout(timer); parent.removeEventListener('abort', cancel);
      attempt.end = Date.now(); attempt.elapsedMs = attempt.end - attempt.start;
      // Detach collectors so late, uncooperative completion cannot rewrite final audit.
      attempt.children = structuredClone(attempt.children);
    }
    retry.finalCategory = attempt.category;
    if (!error || !error.cleanupConfirmed || retry.extraUsed >= (policy.mode === 'normal' ? policy.maxRetries : 0)) break;
    pendingInvalid = error.category === 'invalid';
    if (pendingInvalid ? retry.invalidRecoveryUsed >= 1 : !['service', 'transport', 'timeout'].includes(error.category)) break;
    const hint = error.failure?.providerRetryAfterMs;
    const delay = Math.min(policy.maxDelayMs, Math.max(policy.initialDelayMs * 2 ** retry.extraUsed, hint && Number.isFinite(hint) && hint > 0 ? hint : 0));
    attempt.delayAfterMs = delay;
    try { await reviewDelay(delay, parent); } catch { error = new ReviewFailure('cancel'); break; }
  }
  if (parent.aborted) { result = undefined; error = new ReviewFailure('cancel'); }
  retry.finalCategory = error?.category ?? retry.finalCategory;
  retry.totalElapsedMs = Date.now() - started;
  return { result, error, retry };
}

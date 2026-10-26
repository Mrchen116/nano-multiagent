import { randomUUID } from 'node:crypto';
import { LlmError, type LlmFailure, type StreamChunk } from '@deepseek-ai/dsh-llm';
import { withReviewHttpFacts, type HttpFactsSink, type ReviewHttpFacts } from './review-http.js';

export type FailureCategory = 'cancelled' | 'review_timeout' | 'permanent' | 'invalid_verdict' | 'transient' | 'context' | 'unavailable_unknown' | 'prepare_timeout' | 'cleanup_unavailable' | 'retry_after_exceeds_budget';
export class ReviewFailure extends Error {
  constructor(readonly category: FailureCategory, message: string, readonly failure?: LlmFailure) { super(message); }
}
export interface ReviewRequestTrace {
  requestOrdinal: number; provider: string; model: string; resolvedEffort?: string;
  startedAt: number; endedAt?: number; requestId?: string; usage?: unknown; outcome?: string;
  http?: ReviewHttpFacts; failure?: { code: string; status?: number; providerRetryAfterMs?: number };
}
export interface ReviewAttemptTrace {
  scope: string; attemptOrdinal: number; retryOrdinal: number; generation: number; budgetMs: number;
  startedAt: number; endedAt?: number; outcome?: string; category?: FailureCategory; code?: string; status?: number;
  delayMs?: number; retryAfterKnown?: boolean; sessionId?: string; contextMode?: string;
  requests: ReviewRequestTrace[]; requestCount: number;
}
export interface ReviewTrace {
  reviewId: string; callId: string; startedAt: number; endedAt?: number; elapsedMs?: number;
  terminalReason?: string; finalRoute?: string; fallbackOutcome?: string; complete: boolean;
  retriesUsed: number; formatRetriesUsed: number; contextRebuilds: number;
  attempts: ReviewAttemptTrace[]; requestsTruncated: boolean; knownUsage?: Record<string, number>; usageComplete: boolean;
}

/** Validate only facts received at an explicit public failure seam, never arbitrary thrown objects. */
export function publicFailure(failure: LlmFailure): ReviewFailure {
  return new ReviewFailure(failure.code === 'CONTEXT_WINDOW_EXCEEDED' ? 'context' : 'unavailable_unknown', failure.message, failure);
}
export function invalidVerdict(kind: 'empty_text' | 'malformed'): ReviewFailure {
  return new ReviewFailure('invalid_verdict', `Reviewer returned no valid verdict (${kind})`);
}
function category(error: unknown, http?: ReviewHttpFacts): FailureCategory {
  if (error instanceof ReviewFailure && error.category !== 'unavailable_unknown') return error.category;
  const facts = error instanceof LlmError ? error.failure : error instanceof ReviewFailure ? error.failure : undefined;
  const code = facts?.code;
  if (code && ['AUTH', 'INVALID_CREDENTIAL', 'MISSING_CREDENTIAL', 'QUOTA', 'ACCOUNT_QUOTA', 'NO_ADAPTER', 'INVALID_REQUEST', 'MODEL_NOT_FOUND', 'CONFIGURATION'].includes(code) || [401, 403].includes(http?.status ?? facts?.status ?? 0)) return 'permanent';
  if (code === 'EMPTY_RESPONSE') return 'invalid_verdict';
  if (code === 'CONTEXT_WINDOW_EXCEEDED') return 'context';
  const status = http?.status ?? facts?.status;
  if (code === 'RATE_LIMIT' || status === 429 || status === 503 || code === 'SERVER' && status === undefined
    || code && ['TRANSPORT', 'STREAM_CLOSED', 'TIMEOUT'].includes(code)) return 'transient';
  return 'unavailable_unknown';
}

/** One generation owns requests and publishing rights, even if its transport ignores abort. */
export class ReviewAttempt {
  private valid = true;
  private lastHttp?: ReviewHttpFacts;
  private requestCounter = 0;
  private readonly pending = new Map<ReviewRequestTrace, HttpFactsSink>();
  constructor(readonly signal: AbortSignal, readonly trace: ReviewAttemptTrace, private readonly owner: ReviewRecovery) {}
  get generation(): number { return this.trace.generation; }
  assertActive(): void { this.owner.assertActive(); if (!this.valid || this.signal.aborted) throw new ReviewFailure('cancelled', 'Review attempt revoked'); }
  revoke(): void {
    this.valid = false;
    for (const [request, sink] of this.pending) { request.outcome ??= 'aborted'; this.seal(request, sink); }
    this.pending.clear();
  }
  private seal(request: ReviewRequestTrace, sink: HttpFactsSink): void {
    request.endedAt = Date.now();
    if (Object.keys(sink.facts).length) request.http = { ...sink.facts };
    request.requestId = sink.facts.requestId; this.lastHttp = request.http;
    this.owner.requestEnded(request);
  }
  get http(): ReviewHttpFacts | undefined { return this.lastHttp; }
  async *stream(route: { provider: string; model: string; reasoningEffort?: string }, source: () => AsyncIterable<StreamChunk>): AsyncGenerator<StreamChunk> {
    this.assertActive();
    const row: ReviewRequestTrace = { requestOrdinal: ++this.requestCounter, provider: route.provider, model: route.model, resolvedEffort: route.reasoningEffort, startedAt: Date.now() };
    this.trace.requestCount++;
    const sink: HttpFactsSink = { active: () => this.valid && !this.signal.aborted && this.owner.active, facts: {} };
    this.owner.addRequest(this.trace, row); this.pending.set(row, sink);
    try {
      for await (const chunk of withReviewHttpFacts(sink, source)) {
        this.assertActive();
        if (chunk.type === 'usage') row.usage = chunk.usage;
        if (chunk.type === 'finish') {
          row.outcome = chunk.reason.kind;
          if ('failure' in chunk.reason) { const failure = chunk.reason.failure; row.failure = { code: failure.code, status: failure.status, providerRetryAfterMs: failure.providerRetryAfterMs }; }
        }
        yield chunk;
      }
    } catch (error) {
      if (sink.active()) {
        const failure = error instanceof LlmError ? error.failure : error instanceof ReviewFailure ? error.failure : undefined;
        if (failure) row.failure = { code: failure.code, status: failure.status, providerRetryAfterMs: failure.providerRetryAfterMs };
        row.outcome = 'error';
      }
      throw error;
    } finally {
      if (sink.active()) this.seal(row, sink);
      this.pending.delete(row);
    }
  }
}

/** Action-local safety policy shared by CC stages and whole Guardian attempts, not by model steps. */
export class ReviewRecovery {
  readonly trace: ReviewTrace;
  private readonly controller = new AbortController();
  readonly signal: AbortSignal;
  private readonly timer: ReturnType<typeof setTimeout>;
  private readonly prepareDeadline = performance.now() + 15_000;
  private generation = 0;
  private requestCount = 0;
  private completeRequests = 0;
  private readonly knownUsage: Record<string, number> = {};
  private readonly accounted = new WeakSet<ReviewRequestTrace>();
  private readonly pendingCleanup = new Set<Promise<unknown>>();
  private closed = false;
  private readonly parentCancel: () => void;
  constructor(readonly parentSignal: AbortSignal, callId = '', private readonly random = Math.random) {
    this.trace = { reviewId: randomUUID(), callId, startedAt: Date.now(), complete: false, retriesUsed: 0, formatRetriesUsed: 0, contextRebuilds: 0, attempts: [], requestsTruncated: false, usageComplete: false };
    this.signal = this.controller.signal;
    this.parentCancel = () => this.controller.abort(new ReviewFailure('cancelled', 'Review cancelled'));
    parentSignal.addEventListener('abort', this.parentCancel, { once: true });
    if (parentSignal.aborted) this.parentCancel();
    this.timer = setTimeout(() => this.controller.abort(new ReviewFailure('unavailable_unknown', 'Review action safety deadline exceeded')), 360_000);
    this.timer.unref?.();
  }
  get active(): boolean { return !this.closed && !this.signal.aborted; }
  assertActive(): void { if (!this.active) throw this.signal.reason ?? new ReviewFailure('cancelled', 'Review closed'); }
  cancel(): void { this.parentCancel(); }
  takeContextRebuild(): boolean { this.assertActive(); if (this.trace.contextRebuilds) return false; this.trace.contextRebuilds++; return true; }
  addRequest(attempt: ReviewAttemptTrace, request: ReviewRequestTrace): void {
    if (++this.requestCount <= 100) attempt.requests.push(request); else this.trace.requestsTruncated = true;
  }
  requestEnded(request: ReviewRequestTrace): void {
    // Revocation seals partial usage before finish; late iterators cannot change it again.
    if (this.closed || this.accounted.has(request)) return;
    this.accounted.add(request);
    if (request.usage && typeof request.usage === 'object'
      && !['stop', 'tool-calls'].includes(request.outcome ?? '')
      && !Object.values(request.usage).some(value => typeof value === 'number' && Number.isFinite(value) && value > 0)) {
      // pi-ai emits a synthetic all-zero usage chunk even when HTTP never supplied usage.
      delete request.usage;
    }
    if (request.usage && typeof request.usage === 'object') {
      for (const [key, value] of Object.entries(request.usage)) if (typeof value === 'number' && Number.isFinite(value)) this.knownUsage[key] = (this.knownUsage[key] ?? 0) + value;
      if (['stop', 'tool-calls'].includes(request.outcome ?? '')) this.completeRequests++;
    }
  }
  async prepare<T>(work: (signal: AbortSignal) => Promise<T>): Promise<T> {
    this.assertActive();
    const local = new AbortController();
    const signal = AbortSignal.any([this.signal, local.signal]);
    const timer = setTimeout(() => local.abort(new ReviewFailure('prepare_timeout', 'Review preparation timed out')), Math.max(0, this.prepareDeadline - performance.now()));
    try { const value = await interruptible(Promise.resolve().then(() => work(signal)), signal); signal.throwIfAborted(); this.assertActive(); return value; }
    finally { clearTimeout(timer); local.abort(); }
  }
  async run<T>(scope: string, budgetMs: number, work: (attempt: ReviewAttempt) => Promise<T>): Promise<T> {
    while (true) {
      this.assertActive();
      const local = new AbortController();
      const signal = AbortSignal.any([this.signal, local.signal]);
      const row: ReviewAttemptTrace = { scope, budgetMs, startedAt: Date.now(), generation: ++this.generation, attemptOrdinal: this.trace.attempts.length + 1, retryOrdinal: this.trace.retriesUsed, requests: [], requestCount: 0 };
      this.trace.attempts.push(row);
      const attempt = new ReviewAttempt(signal, row, this);
      const timer = setTimeout(() => local.abort(new ReviewFailure('review_timeout', 'Review judgment timed out')), budgetMs);
      const pending = Promise.resolve().then(() => work(attempt));
      try {
        const value = await interruptible(pending, signal);
        attempt.assertActive(); row.outcome = 'verdict'; row.endedAt = Date.now(); return value;
      } catch (error) {
        attempt.revoke(); local.abort(error);
        // No successor may start until this work (including its native/iterator cleanup) drains.
        try { await this.cleanup(pending.then(() => undefined, () => undefined)); }
        catch (cleanup) { row.category = 'cleanup_unavailable'; row.outcome = 'error'; row.endedAt = Date.now(); throw cleanup; }
        if (this.signal.aborted) { row.category = this.parentSignal.aborted ? 'cancelled' : 'unavailable_unknown'; row.outcome = 'error'; row.endedAt = Date.now(); throw this.signal.reason; }
        const failure = signal.aborted && signal.reason instanceof ReviewFailure ? signal.reason : error;
        const kind = category(failure, attempt.http);
        const facts = failure instanceof LlmError ? failure.failure : failure instanceof ReviewFailure ? failure.failure : undefined;
        Object.assign(row, { endedAt: Date.now(), outcome: 'error', category: kind, code: facts?.code, status: attempt.http?.status ?? facts?.status });
        if (!['review_timeout', 'transient', 'invalid_verdict'].includes(kind) || this.trace.retriesUsed >= 2 || kind === 'invalid_verdict' && this.trace.formatRetriesUsed >= 1) throw new ReviewFailure(kind, failure instanceof Error ? failure.message : String(failure), facts);
        const supplied = attempt.http?.retryAfterMs ?? facts?.providerRetryAfterMs;
        const remaining = supplied === undefined ? undefined : Math.max(0, supplied - (attempt.http?.receivedAt === undefined ? 0 : performance.now() - attempt.http.receivedAt));
        row.retryAfterKnown = remaining !== undefined;
        if (remaining !== undefined && remaining > 10_000) throw new ReviewFailure('retry_after_exceeds_budget', 'Retry-After exceeds review waiting budget', facts);
        const delay = Math.max((this.trace.retriesUsed ? 1000 : 500) * (0.9 + this.random() * 0.2), remaining ?? 0);
        row.delayMs = delay;
        this.trace.retriesUsed++; if (kind === 'invalid_verdict') this.trace.formatRetriesUsed++;
        await interruptible(new Promise<void>(resolve => { const wait = setTimeout(resolve, delay); this.signal.addEventListener('abort', () => clearTimeout(wait), { once: true }); }), this.signal);
      } finally { clearTimeout(timer); attempt.revoke(); }
    }
  }
  get hasPendingCleanup(): boolean { return this.pendingCleanup.size > 0; }
  async drain(): Promise<void> { await Promise.allSettled(this.pendingCleanup); }
  async cleanup(work: Promise<unknown>): Promise<void> {
    this.pendingCleanup.add(work);
    void work.then(() => this.pendingCleanup.delete(work), () => this.pendingCleanup.delete(work));
    let timer: ReturnType<typeof setTimeout> | undefined;
    try { await Promise.race([work, new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new ReviewFailure('cleanup_unavailable', 'Review resource did not drain within 5 seconds')), 5000); })]); }
    catch (error) { throw error instanceof ReviewFailure ? error : new ReviewFailure('cleanup_unavailable', 'Review resource cleanup failed'); }
    finally { clearTimeout(timer); }
  }
  finish(terminalReason: string, finalRoute: string, fallbackOutcome?: string): ReviewTrace {
    this.closed = true; clearTimeout(this.timer); this.parentSignal.removeEventListener('abort', this.parentCancel);
    Object.assign(this.trace, { terminalReason, finalRoute, fallbackOutcome, complete: true, endedAt: Date.now(), elapsedMs: Date.now() - this.trace.startedAt });
    if (Object.keys(this.knownUsage).length) this.trace.knownUsage = { ...this.knownUsage };
    this.trace.usageComplete = this.requestCount > 0 && this.completeRequests === this.requestCount;
    return this.trace;
  }
}

/** Abort the wait, retaining rejection handlers on uncancellable read-only/native work. */
export function interruptible<T>(pending: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const cancel = () => reject(signal.reason);
    signal.addEventListener('abort', cancel, { once: true });
    pending.then(resolve, reject).finally(() => signal.removeEventListener('abort', cancel));
    if (signal.aborted) cancel();
  });
}

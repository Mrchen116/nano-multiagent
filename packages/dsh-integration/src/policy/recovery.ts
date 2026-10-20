import { randomUUID } from 'node:crypto';
import { BlockAssembler, LlmError, type LlmFailure, type StreamChunk } from '@deepseek-ai/dsh-llm';
import { withReviewHttpFacts, type HttpFactsSink } from '../llm-attribution.js';

/** Policy-owned failures; never infer transient failures from arbitrary error text. */
export class ReviewFailure extends Error {
  constructor(readonly category: string, readonly failure?: LlmFailure, readonly http?: HttpFactsSink) {
    super(`Automatic review ${category}${failure ? ` (${failure.code})` : ''}`);
  }
}
export interface RequestTrace {
  requestOrdinal: number; provider: string; model: string; startedAt: number; endedAt?: number;
  code?: string; status?: number; requestId?: string; usage?: unknown; usageComplete: boolean;
  retryAfterKnown?: boolean; outcome?: string;
}
export interface AttemptTrace {
  scope: string; attemptOrdinal: number; retryOrdinal: number; generation: number; budgetMs: number;
  startedAt: number; endedAt?: number; outcome?: string; category?: string; code?: string; status?: number;
  delayMs?: number; retryAfterKnown?: boolean; sessionId?: string; contextMode?: string;
  requests: RequestTrace[]; requestCount: number;
}
export interface ReviewTrace {
  reviewId: string; callId: string; rules: string; reviewer: { provider: string; model: string };
  startedAt: number; endedAt?: number; elapsedMs?: number; terminalReason?: string; finalRoute?: string;
  fallbackOutcome?: string; retriesUsed: number; formatRetriesUsed: number; contextRebuilds: number;
  complete: boolean; attempts: AttemptTrace[]; requestsTruncated: boolean; knownUsage: unknown[]; overflowKnownUsage?: Record<string, number>; usageComplete: boolean;
}
const permanent = new Set(['AUTH', 'INVALID_CREDENTIAL', 'MISSING_CREDENTIAL', 'QUOTA', 'ACCOUNT_QUOTA', 'NO_ADAPTER', 'INVALID_REQUEST', 'MODEL_NOT_FOUND', 'UNSUPPORTED_REASONING_EFFORT']);
const transport = new Set(['TRANSPORT', 'STREAM_CLOSED', 'TIMEOUT']);

/** Classify only public, typed provider facts, supplemented by request-local HTTP. */
export function reviewFailure(error: unknown, http?: HttpFactsSink): ReviewFailure {
  const own = error instanceof ReviewFailure ? error : undefined;
  const failure = own?.failure ?? (error instanceof LlmError ? error.failure : undefined);
  http = own?.http ?? http;
  const status = http?.status ?? failure?.status;
  const code = failure?.code;
  if (own && !failure) return own;
  if (code && permanent.has(code) || status === 401 || status === 403) return new ReviewFailure('permanent', failure, http);
  if (code === 'CONTEXT_WINDOW_EXCEEDED') return new ReviewFailure('context', failure, http);
  if (code === 'EMPTY_RESPONSE') return new ReviewFailure('empty_response', failure, http);
  if (code === 'RATE_LIMIT' || status === 429 || status === 503 || code === 'SERVER' && status === undefined || code && transport.has(code)) return new ReviewFailure('transient', failure, http);
  return own ?? new ReviewFailure('unavailable_unknown', failure, http);
}

/** Race a signal without forgetting the underlying promise or its rejection. */
export async function whileActive<T>(work: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) { void work.catch(() => {}); throw signal.reason; }
  let abort!: () => void;
  const cancelled = new Promise<never>((_, reject) => { abort = () => reject(signal.reason); signal.addEventListener('abort', abort, { once: true }); });
  try { return await Promise.race([work, cancelled]); }
  finally { signal.removeEventListener('abort', abort); }
}

/** One normal stage/Guardian lifetime; a generation can never be reactivated. */
export class ReviewAttempt {
  private active = true;
  readonly controller = new AbortController();
  readonly signal: AbortSignal;
  private http?: HttpFactsSink;
  onQuarantine?: (pending: Promise<unknown>) => void;
  readonly drains = new Set<Promise<unknown>>();
  constructor(readonly owner: ReviewRecovery, readonly trace: AttemptTrace) {
    this.signal = AbortSignal.any([owner.signal, this.controller.signal]);
  }
  assertActive(): void {
    this.signal.throwIfAborted();
    if (!this.active) throw new ReviewFailure('cancelled');
  }
  invalidate(reason?: unknown): void { this.active = false; if (reason) this.controller.abort(reason); }
  failure(error: unknown): ReviewFailure { return reviewFailure(error, this.http); }
  /** Collect a single model request; all iterator operations retain its immutable ALS sink. */
  async *stream(next: () => AsyncIterable<StreamChunk>): AsyncGenerator<StreamChunk> {
    this.assertActive();
    const trace: RequestTrace = { requestOrdinal: ++this.trace.requestCount, ...this.owner.trace.reviewer, startedAt: Date.now(), usageComplete: false };
    if (this.owner.requestCount++ < 100) this.trace.requests.push(trace); else this.owner.trace.requestsTruncated = true;
    const sink: HttpFactsSink = { active: true };
    const assembly = new BlockAssembler();
    const iterator = withReviewHttpFacts(sink, next)[Symbol.asyncIterator]();
    let drained!: () => void;
    const drain = new Promise<void>(resolve => { drained = resolve; });
    this.drains.add(drain);
    let failure: unknown;
    try {
      for (;;) {
        this.assertActive();
        const chunk = await whileActive(Promise.resolve(iterator.next()), this.signal);
        this.assertActive();
        if (chunk.done) break;
        assembly.push(chunk.value);
        if (chunk.value.type === 'usage') trace.usage = chunk.value.usage;
        yield chunk.value;
      }
      if (assembly.finish.kind === 'error' || assembly.finish.kind === 'aborted') throw new LlmError('Review provider failure', assembly.finish.failure.code, assembly.finish.failure);
      trace.usageComplete = assembly.usage !== undefined;
    } catch (error) { failure = error; throw this.failureWithSink(error, sink); }
    finally {
      sink.active = false;
      const returned = Promise.resolve().then(() => iterator.return?.(undefined)).then(() => {
        this.drains.delete(drain); drained();
      });
      try { await this.owner.cleanup(returned); }
      catch (error) { this.onQuarantine?.(drain); throw error; }
      // An invalidated/quarantined generation may drain, but cannot mutate a sealed trace.
      if (this.active && !this.owner.trace.complete) {
        trace.endedAt = Date.now(); trace.outcome = failure ? 'failed' : 'completed';
        const info = reviewFailure(failure, sink);
        trace.code = info.failure?.code; trace.status = sink.status ?? info.failure?.status;
        trace.requestId = sink.requestId ?? info.failure?.requestId; trace.retryAfterKnown = sink.retryAfterUntil !== undefined || info.failure?.providerRetryAfterMs !== undefined;
        // Native adapters can synthesize a zero usage chunk after a pre-response failure.
        // That is not evidence that the failed request was free; retain only known partials.
        const usage = assembly.usage;
        if (usage && (trace.usageComplete || Object.values(usage).some(value => typeof value === 'number' && value > 0))) {
          trace.usage = usage; this.owner.recordUsage(usage);
        } else delete trace.usage;
        if (!trace.usageComplete) this.owner.trace.usageComplete = false;
      }
    }
  }
  private failureWithSink(error: unknown, sink: HttpFactsSink): ReviewFailure {
    this.http = sink;
    return reviewFailure(error, sink);
  }
}

/** Own one pending action's shared recovery, deadlines, cleanup and safe audit summary. */
export class ReviewRecovery {
  readonly trace: ReviewTrace;
  readonly signal: AbortSignal;
  requestCount = 0;
  private readonly lifetime = new AbortController();
  private readonly timer: ReturnType<typeof setTimeout>;
  private closed = false;
  constructor(parent: AbortSignal, callId: string, rules: string, reviewer: { provider: string; model: string }, private readonly track: (pending: Promise<unknown>) => void = () => {}) {
    this.signal = AbortSignal.any([parent, this.lifetime.signal]);
    this.timer = setTimeout(() => this.lifetime.abort(new ReviewFailure('action_timeout')), 360_000);
    this.trace = { reviewId: randomUUID(), callId, rules, reviewer, startedAt: Date.now(), retriesUsed: 0, formatRetriesUsed: 0, contextRebuilds: 0, complete: false, attempts: [], requestsTruncated: false, knownUsage: [], usageComplete: true };
  }
  /** Keep explicit native usage separate from unknown costs; bound per-request detail. */
  recordUsage(usage: object): void {
    if (this.trace.knownUsage.length < 100) this.trace.knownUsage.push(usage);
    else {
      const totals = this.trace.overflowKnownUsage ??= {};
      for (const [key, value] of Object.entries(usage)) if (typeof value === 'number') totals[key] = (totals[key] ?? 0) + value;
    }
  }
  /** Freeze read-only preparation once, without spending any judgment retry allowance. */
  async prepare<T>(work: (signal: AbortSignal) => Promise<T>): Promise<T> {
    const timeout = new AbortController();
    const timer = setTimeout(() => timeout.abort(new ReviewFailure('prepare_timeout')), Math.max(0, 15_000 - (Date.now() - this.trace.startedAt)));
    const signal = AbortSignal.any([this.signal, timeout.signal]);
    try { const result = await whileActive(Promise.resolve().then(() => work(signal)), signal); signal.throwIfAborted(); return result; }
    finally { clearTimeout(timer); }
  }
  /** Revoke owner/config-released work without invoking any fallback. */
  cancel(): void { this.lifetime.abort(new ReviewFailure('cancelled')); }
  takeContextRebuild(): boolean {
    if (this.trace.contextRebuilds) return false;
    this.trace.contextRebuilds++; return true;
  }
  /** Drain a resource for at most five seconds; tracked late cleanup cannot grant permission. */
  async cleanup(work: Promise<unknown>): Promise<void> {
    let timer!: ReturnType<typeof setTimeout>;
    try { await Promise.race([work, new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new ReviewFailure('cleanup_unavailable')), 5_000); })]); }
    catch (error) { this.track(work); throw error instanceof ReviewFailure ? error : new ReviewFailure('cleanup_unavailable'); }
    finally { clearTimeout(timer); }
  }
  async run<T>(scope: string, budgetMs: number, work: (attempt: ReviewAttempt) => Promise<T>): Promise<T> {
    for (;;) {
      this.signal.throwIfAborted();
      if (this.closed) throw new ReviewFailure('cancelled');
      const row: AttemptTrace = { scope, attemptOrdinal: this.trace.attempts.length + 1, generation: this.trace.attempts.length + 1, retryOrdinal: this.trace.retriesUsed, budgetMs, startedAt: Date.now(), requests: [], requestCount: 0 };
      this.trace.attempts.push(row);
      const attempt = new ReviewAttempt(this, row);
      const timer = setTimeout(() => attempt.controller.abort(new ReviewFailure('review_timeout')), budgetMs);
      const pending = Promise.resolve().then(() => work(attempt));
      let failed: ReviewFailure;
      try { const value = await whileActive(pending, attempt.signal); attempt.assertActive(); row.outcome = 'verdict'; return value; }
      catch (error) {
        // Parent cancellation wins a simultaneous verdict or judgment deadline.
        failed = this.signal.aborted ? new ReviewFailure('cancelled') : attempt.signal.aborted ? reviewFailure(attempt.signal.reason) : attempt.failure(error);
        attempt.invalidate(failed);
        try { await this.cleanup(pending.then(() => undefined, () => undefined)); }
        catch { failed = new ReviewFailure('cleanup_unavailable'); attempt.onQuarantine?.(pending); }
        row.outcome = 'failed'; row.category = failed.category; row.code = failed.failure?.code; row.status = failed.http?.status ?? failed.failure?.status;
      } finally {
        clearTimeout(timer); attempt.invalidate(); row.endedAt = Date.now();
        for (const request of row.requests) if (request.endedAt === undefined) {
          request.endedAt = row.endedAt; request.outcome = row.category ?? 'cancelled';
          if (request.usage && typeof request.usage === 'object' && Object.values(request.usage).some(value => typeof value === 'number' && value > 0)) this.recordUsage(request.usage);
          else delete request.usage;
          this.trace.usageComplete = false;
        }
      }
      this.trace.terminalReason = failed.category;
      this.signal.throwIfAborted();
      const format = ['invalid_verdict', 'empty_response', 'empty_text', 'malformed'].includes(failed.category);
      if (!(format || ['transient', 'review_timeout'].includes(failed.category)) || this.trace.retriesUsed >= 2 || format && this.trace.formatRetriesUsed >= 1) throw failed;
      const local = (this.trace.retriesUsed ? 1000 : 500) * (0.9 + Math.random() * 0.2);
      const remaining = failed.http?.retryAfterUntil !== undefined ? Math.max(0, failed.http.retryAfterUntil - performance.now()) : failed.failure?.providerRetryAfterMs;
      row.retryAfterKnown = remaining !== undefined;
      if (remaining !== undefined && remaining > 10_000) { this.trace.terminalReason = 'retry_after_exceeds_budget'; throw new ReviewFailure('retry_after_exceeds_budget', failed.failure, failed.http); }
      row.delayMs = Math.max(local, remaining ?? 0);
      this.trace.retriesUsed++; if (format) this.trace.formatRetriesUsed++;
      let delay!: ReturnType<typeof setTimeout>;
      try { await whileActive(new Promise<void>(resolve => { delay = setTimeout(resolve, row.delayMs); }), this.signal); }
      finally { clearTimeout(delay); }
    }
  }
  /** Seal a privacy-safe summary before the facade persists and returns its original route. */
  finish(terminalReason: string, finalRoute: string, fallbackOutcome?: string): ReviewTrace {
    this.closed = true; clearTimeout(this.timer);
    if (!this.requestCount || this.trace.attempts.some(attempt => attempt.requests.some(request => !request.usageComplete))) this.trace.usageComplete = false;
    Object.assign(this.trace, { endedAt: Date.now(), elapsedMs: Date.now() - this.trace.startedAt, terminalReason, finalRoute, fallbackOutcome, complete: true });
    return structuredClone(this.trace);
  }
}

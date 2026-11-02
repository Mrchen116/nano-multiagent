/** Recovery for direct LLM consumers; native Agent Loop keeps its own recovery owner. */
import { AsyncLocalStorage } from 'node:async_hooks';
import { randomUUID } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import type { Context } from '@deepseek-ai/cordis';
import { BlockAssembler, isAgentLoopRequest, type GenerateOptions, type LlmFailure, type ResolvedRetryPolicy, type StreamChunk } from '@deepseek-ai/dsh-llm';
import { estimateContent } from '@deepseek-ai/dsh-token-meter/estimate';
import { deadline, timeoutOf } from '@deepseek-ai/dsh-timeout';

export interface ReviewBudget { remaining: number; formatRemaining: number }
export interface StandaloneRetryControl<T = unknown> {
  timeoutMs?: number;
  reviewBudget?: ReviewBudget;
  decodeReview?: (text: string) => T | undefined;
  decodedReview?: T;
  purpose?: string;
}
const controls = new AsyncLocalStorage<StandaloneRetryControl>();

/** Apply request-local controls to a direct consumer without changing the LLM API.
 *
 * Args:
 *   control: Per-attempt timeout and, for reviews, shared recovery limits and parser.
 *   run: Existing complete-stream consumer. Native Loop requests ignore these controls.
 * Returns:
 *   The consumer result after a complete attempt, or its final failure.
 */
export function withStandaloneRetry<T>(control: StandaloneRetryControl, run: () => Promise<T>): Promise<T> {
  return controls.run(control, run);
}

function planRetry(failure: LlmFailure, policy: ResolvedRetryPolicy, retries: number, budget?: ReviewBudget): number | undefined {
  if (budget && budget.remaining <= 0) return;
  if (policy.mode === 'normal' && (retries >= policy.maxRetries || !policy.retryableCodes.includes(failure.code))) return;
  const requested = failure.providerRetryAfterMs;
  if (requested !== undefined && Number.isFinite(requested) && requested > 0) {
    if (requested > policy.maxDelayMs && policy.mode === 'normal') return;
    return Math.min(requested, policy.maxDelayMs);
  }
  const base = Math.min(policy.maxDelayMs, policy.initialDelayMs * 2 ** Math.min(retries, 52));
  return Math.min(policy.maxDelayMs, base * (1 + (Math.random() * 2 - 1) * policy.jitterRatio));
}

/** Install one recovery boundary for every direct request through the public LLM service.
 *
 * Args:
 *   ctx: Runtime scope owning the LLM service and middleware lifetime.
 */
export function installStandaloneModelRetry(ctx: Context): void {
  const attempts = new WeakSet<GenerateOptions>();
  const lifetime = new AbortController();
  ctx.effect(() => () => lifetime.abort(new Error('Standalone model recovery disposed')));
  ctx.on('llm/stream', async function* (options, next) {
    if (isAgentLoopRequest(options) || attempts.has(options)) { yield* next(); return; }
    const control = controls.getStore();
    const signal = options.signal ? AbortSignal.any([options.signal, lifetime.signal]) : lifetime.signal;
    const requestId = randomUUID();
    let retries = 0;
    for (let attempt = 1; ; attempt++) {
      signal.throwIfAborted();
      const timer = deadline(signal, control?.timeoutMs ?? 0, 'STANDALONE_MODEL_TIMEOUT');
      const started = Date.now();
      const chunks: StreamChunk[] = [];
      const assembly = new BlockAssembler();
      let policy = ctx.llm.providerRetryPolicy(options.provider);
      let failure: LlmFailure | undefined;
      try {
        const { provider, model, reasoningEffort, temperature, maxTokens, stop } = options;
        const prepared = await ctx.llm.prepareCall({ provider, model, reasoningEffort, temperature, maxTokens, stop }, timer.signal);
        policy = prepared.retryPolicy;
        if (control?.decodeReview) {
          // Preparation pins capabilities to this attempt's adapter generation.
          // An earlier model lookup cannot authorize a request after a route update.
          const limit = prepared.context?.contextWindow;
          if (!limit) throw new Error('Reviewer model has no declared context window');
          const input = options.messages.reduce((sum, message) => sum + estimateContent(message.content) + 4, 0)
            + estimateContent([{ type: 'text', text: options.system ?? '' }, { type: 'text', text: JSON.stringify(options.tools ?? []) }]);
          if (input + (prepared.config.maxTokens ?? 2048) + 512 > limit) throw new Error('Complete review request exceeds current model context window');
        }
        const request: GenerateOptions = { ...options, ...prepared.config, signal: timer.signal };
        attempts.add(request);
        try {
          // The one-shot handle re-enters the waterfall. Only this exact attempt bypasses us.
          // Iteration finishes (including iterator cleanup) before another attempt can begin.
          for await (const chunk of prepared.stream(request)) { chunks.push(chunk); assembly.push(chunk); }
        } finally { attempts.delete(request); }
        if (assembly.finish.kind === 'error') failure = assembly.finish.failure;
      } catch (error) {
        // Adapter failures arrive as terminal chunks. Thrown middleware/consumer errors
        // are not provider failures and must not be retried by guessing their text.
        if (!timeoutOf(timer.signal, 'STANDALONE_MODEL_TIMEOUT')) throw error;
      } finally { timer[Symbol.dispose](); }
      signal.throwIfAborted();
      if (timeoutOf(timer.signal, 'STANDALONE_MODEL_TIMEOUT')) failure = { code: 'TIMEOUT', message: 'Standalone model attempt timed out' };
      let invalid = false;
      if (!failure && assembly.finish.kind !== 'aborted' && control?.decodeReview) {
        const text = assembly.blocks().filter(block => block.type === 'text').map(block => block.text).join('');
        control.decodedReview = control.decodeReview(text);
        invalid = control.decodedReview === undefined;
      }
      ctx.logger.info('standalone-model-attempt %o', {
        requestId, purpose: control?.purpose ?? options.purpose ?? 'direct', sessionId: options.sessionId,
        attempt, provider: options.provider, model: options.model, elapsedMs: Date.now() - started,
        code: failure?.code ?? (invalid ? 'INVALID_VERDICT' : assembly.finish.kind), usage: assembly.usage,
      });
      let waitMs: number | undefined;
      if (failure) waitMs = planRetry(failure, policy, retries, control?.reviewBudget);
      else if (invalid && control?.reviewBudget && control.reviewBudget.remaining > 0 && control.reviewBudget.formatRemaining > 0) {
        control.reviewBudget.formatRemaining--;
        waitMs = 0;
      }
      if (waitMs === undefined) {
        if (invalid) throw new Error('Reviewer returned no valid verdict');
        if (failure) { yield { type: 'finish', reason: { kind: 'error', failure } }; return; }
        if (assembly.finish.kind === 'aborted') { yield { type: 'finish', reason: assembly.finish }; return; }
        yield* chunks;
        return;
      }
      retries++;
      if (control?.reviewBudget) control.reviewBudget.remaining--;
      await delay(waitMs, undefined, { signal });
    }
  }, { prepend: true });
}

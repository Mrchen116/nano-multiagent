import { BlockAssembler, LlmError, ReasoningEffortId } from '@deepseek-ai/dsh-llm';
import { estimateContent } from '@deepseek-ai/dsh-token-meter/estimate';
import type { Context } from '@deepseek-ai/cordis';
import { buildPolicy, parseNanoDecision, parseDshDecision, policyAsset, type ReviewDecision } from './rules.js';
import { inboxSourceInstructions, reviewSourceInstructions, messageReviewInstructions, personalAuthorizationInstructions } from './sources.js';
import type { ApprovalReviewRequest, ApprovalReviewResult } from './types.js';
import { boundedReview, ReviewFailure } from './retry.js';

/** Execute CC's two stages or DSH's single stage within one full review attempt.
 * Args:
 *   ctx: Public runtime services.
 *   request: Frozen action/evidence with the current attempt cancellation boundary.
 * Returns:
 *   Final policy verdict; all available stage usage is retained in the collector.
 */
export async function classify(ctx: Context, request: ApprovalReviewRequest): Promise<ApprovalReviewResult> {
  const { exec, config, sources, inherited, messageContext, reviewer } = request;
  const agent = exec.agent!; const policy = config.approval!;
  const attemptSignal = request.attemptSignal ?? exec.signal;
  const snapshot = request.snapshot ?? {};
  snapshot.classifier ??= (async () => {
    const prompt = await buildPolicy(policy, agent.session.header.cwd!);
    const transcript = await sources.transcript(agent, exec, inherited, messageContext, config.mode !== 'global', request.personalAuthorization);
    const system = `${prompt}\n\n${reviewSourceInstructions}\n\n${inboxSourceInstructions}${messageContext ? `\n\n${messageReviewInstructions}` : ''}${request.personalAuthorization ? `\n\n${personalAuthorizationInstructions}` : ''}`;
    return { system, transcript };
  })();
  const { system, transcript } = await snapshot.classifier;
  attemptSignal.throwIfAborted();
  const model = await ctx.llm.resolveModelInfo(reviewer.provider, reviewer.model, attemptSignal);
  attemptSignal.throwIfAborted();
  let decision: ReviewDecision | undefined; let usage: unknown; let stages = 0;
  for (const stage of policy.rules === 'nano' ? [1, 2] : [1]) {
    const suffix = policy.rules === 'nano' ? await policyAsset(`cc-2.1.267-nano-v1/s${stage}_suffix.txt`) : '';
    attemptSignal.throwIfAborted();
    const assembly = new BlockAssembler();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(new ReviewFailure('timeout')), stage === 1 ? 30_000 : 60_000);
    const signal = AbortSignal.any([attemptSignal, controller.signal]);
    const maxTokens = stage === 1 ? 2112 : 10240;
    const userText = transcript + suffix;
    try {
      // Public estimator is heuristic; reserve the full stage output independently.
      const estimatedInput = estimateContent([{ type: 'text', text: system }, { type: 'text', text: userText }]) + 8;
      if (model.context && estimatedInput + maxTokens > model.context.contextWindow) throw new ReviewFailure('config');
      await boundedReview(async () => {
        for await (const chunk of ctx.llm.stream({ ...reviewer, system, reasoningEffort: ReasoningEffortId('low'),
          messages: [{ role: 'user', content: [{ type: 'text', text: userText }] }], temperature: 0, maxTokens, signal })) {
          signal.throwIfAborted(); assembly.push(chunk);
        }
      }, signal);
      signal.throwIfAborted();
      if (assembly.finish.kind === 'error' || assembly.finish.kind === 'aborted') {
        const failure = assembly.finish.failure;
        if (failure) throw new LlmError(failure.message, failure.code, failure);
        throw new ReviewFailure('unknown');
      }
      const result = assembly.blocks().filter(block => block.type === 'text').map(block => block.text).join('');
      decision = policy.rules === 'nano' ? parseNanoDecision(result) : parseDshDecision(result);
      if (!decision) throw new ReviewFailure('invalid');
    } finally {
      clearTimeout(timeout);
      stages++; usage = assembly.usage;
      request.children?.push({ stage, ...(usage !== undefined ? { usage } : {}) });
    }
    if (policy.rules !== 'nano' || stage === 2 || decision.behavior === 'allow') break;
  }
  // Multi-stage accounting lives in children; the last stage is not a total.
  return { decision: decision!, ...(stages === 1 && usage !== undefined ? { usage } : {}) };
}

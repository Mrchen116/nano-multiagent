import { BlockAssembler, ReasoningEffortId } from '@deepseek-ai/dsh-llm';
import { estimateContent } from '@deepseek-ai/dsh-token-meter/estimate';
import type { Context } from '@deepseek-ai/cordis';
import { buildPolicy, parseNanoDecision, parseDshDecision, policyAsset, type ReviewDecision } from './rules.js';
import { inboxSourceInstructions, reviewSourceInstructions, messageReviewInstructions } from './sources.js';
import type { ApprovalReviewRequest, ApprovalReviewResult } from './types.js';
import { ReviewFailure } from './recovery.js';

/** Preserve CC's stages and legacy's single stage, recovering only the failed stage. */
export async function classify(ctx: Context, request: ApprovalReviewRequest): Promise<ApprovalReviewResult> {
  const { exec, config, sources, inherited, messageContext, reviewer, recovery } = request;
  const agent = exec.agent!; const policy = config.approval!;
  const stages = policy.rules === 'nano' ? [1, 2] : [1];
  const { system, transcript, model, suffixes } = await recovery.prepare(async signal => {
    const [prompt, transcript, model, suffixes] = await Promise.all([
      buildPolicy(policy, agent.session.header.cwd!),
      sources.transcript(agent, exec, inherited, messageContext, config.mode !== 'global'),
      ctx.llm.resolveModelInfo(reviewer.provider, reviewer.model, signal),
      Promise.all(stages.map(stage => policy.rules === 'nano' ? policyAsset(`cc-2.1.267-nano-v1/s${stage}_suffix.txt`) : '')),
    ]);
    return { system: `${prompt}\n\n${reviewSourceInstructions}\n\n${inboxSourceInstructions}${messageContext ? `\n\n${messageReviewInstructions}` : ''}`, transcript, model, suffixes };
  });
  let decision: ReviewDecision | undefined;
  for (const stage of stages) {
    const maxTokens = stage === 1 ? 2112 : 10240;
    const userText = transcript + suffixes[stage - 1];
    // CC never shrinks authorization or the action to fit a retry.
    const estimatedInput = estimateContent([{ type: 'text', text: system }, { type: 'text', text: userText }]) + 8;
    if (model.context && estimatedInput + maxTokens > model.context.contextWindow) throw new ReviewFailure('context');
    decision = await recovery.run(policy.rules === 'nano' ? `cc-s${stage}` : 'legacy', stage === 1 ? 30_000 : 60_000, async attempt => {
      const assembly = new BlockAssembler();
      for await (const chunk of attempt.stream(() => ctx.llm.stream({ ...reviewer, system,
        sessionId: agent.session.id, reasoningEffort: ReasoningEffortId('low'),
        messages: [{ role: 'user', content: [{ type: 'text', text: userText }] }], temperature: 0, maxTokens, signal: attempt.signal }))) assembly.push(chunk);
      const result = assembly.blocks().filter(block => block.type === 'text').map(block => block.text).join('');
      const verdict = policy.rules === 'nano' ? parseNanoDecision(result) : parseDshDecision(result);
      if (!verdict) throw new ReviewFailure(result.trim() ? 'malformed' : 'empty_text');
      return verdict;
    });
    if (policy.rules !== 'nano' || stage === 2 || decision.behavior === 'allow') break;
  }
  // Full cost lives in recovery.knownUsage, not merely the last successful call.
  return { decision: decision! };
}

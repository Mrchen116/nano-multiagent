import { BlockAssembler, ReasoningEffortId } from '@deepseek-ai/dsh-llm';
import { estimateContent } from '@deepseek-ai/dsh-token-meter/estimate';
import type { Context } from '@deepseek-ai/cordis';
import { buildPolicy, parseNanoDecision, parseDshDecision, policyAsset, type ReviewDecision } from './rules.js';
import { inboxSourceInstructions, reviewSourceInstructions, messageReviewInstructions } from './sources.js';
import type { ApprovalReviewRequest, ApprovalReviewResult } from './types.js';

/** Existing pinned CC two-stage and legacy DSH one-stage classification. */
export async function classify(ctx: Context, request: ApprovalReviewRequest): Promise<ApprovalReviewResult> {
  const { exec, config, sources, inherited, messageContext, reviewer } = request;
  const agent = exec.agent!; const policy = config.approval!;
  let decision: ReviewDecision | undefined; let usage: unknown;
  const prompt = await buildPolicy(policy, agent.session.header.cwd!);
  const transcript = await sources.transcript(agent, exec, inherited, messageContext, config.mode !== 'global');
  const model = await ctx.llm.resolveModelInfo(reviewer.provider, reviewer.model, exec.signal);
  const system = `${prompt}\n\n${reviewSourceInstructions}\n\n${inboxSourceInstructions}${messageContext ? `\n\n${messageReviewInstructions}` : ''}`;
  for (const stage of policy.rules === 'nano' ? [1, 2] : [1]) {
    const suffix = policy.rules === 'nano' ? await policyAsset(`cc-2.1.267-nano-v1/s${stage}_suffix.txt`) : '';
    const assembly = new BlockAssembler();
    const signal = AbortSignal.any([exec.signal, AbortSignal.timeout(stage === 1 ? 30_000 : 60_000)]);
    const maxTokens = stage === 1 ? 2112 : 10240;
    const userText = transcript + suffix;
    // Public DSH estimator is a heuristic, not the provider tokenizer. Reserve the full stage output.
    const estimatedInput = estimateContent([{ type: 'text', text: system }, { type: 'text', text: userText }]) + 8;
    if (model.context && estimatedInput + maxTokens > model.context.contextWindow) {
      throw new Error(`Review context exceeds configured window: estimated input ${estimatedInput} + output ${maxTokens} > ${model.context.contextWindow}`);
    }
    for await (const chunk of ctx.llm.stream({ ...reviewer, system, reasoningEffort: ReasoningEffortId('low'),
      messages: [{ role: 'user', content: [{ type: 'text', text: userText }] }], temperature: 0, maxTokens, signal })) assembly.push(chunk);

    usage = assembly.usage;
    if (assembly.finish.kind === 'error' || assembly.finish.kind === 'aborted') throw new Error(JSON.stringify(assembly.finish));
    const result = assembly.blocks().filter(block => block.type === 'text').map(block => block.text).join('');
    decision = policy.rules === 'nano' ? parseNanoDecision(result) : parseDshDecision(result);
    if (!decision) throw new Error('Reviewer returned no valid verdict');
    if (policy.rules !== 'nano' || stage === 2 || decision.behavior === 'allow') break;
  }
  return { decision: decision!, usage };
}

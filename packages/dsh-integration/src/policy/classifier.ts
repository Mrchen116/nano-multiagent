import { BlockAssembler } from '@deepseek-ai/dsh-llm';
import { estimateContent } from '@deepseek-ai/dsh-token-meter/estimate';
import type { Context } from '@deepseek-ai/cordis';
import { buildPolicy, parseNanoDecision, parseDshDecision, policyAsset, type ReviewDecision } from './rules.js';
import { inboxSourceInstructions, reviewSourceInstructions, messageReviewInstructions } from './sources.js';
import type { ApprovalReviewRequest, ApprovalReviewResult } from './types.js';
import { ReviewRecovery, ReviewFailure, invalidVerdict, publicFailure } from './recovery.js';

/** Existing pinned CC two-stage and legacy DSH one-stage classification. */
export async function classify(ctx: Context, request: ApprovalReviewRequest): Promise<ApprovalReviewResult> {
  const { exec, config, sources, inherited, messageContext, reviewer } = request;
  const agent = exec.agent!; const policy = config.approval!;
  const recovery = request.recovery ?? new ReviewRecovery(exec.signal, exec.callId);
  let decision: ReviewDecision | undefined; let usage: unknown;
  try {
    const { system, transcript, model, suffixes } = await recovery.prepare(async signal => {
      const [prompt, transcript, model, suffixes] = await Promise.all([
        buildPolicy(policy, agent.session.header.cwd!),
        sources.transcript(agent, exec, inherited, messageContext, config.mode !== 'global'),
        ctx.llm.resolveModelInfo(reviewer.provider, reviewer.model, signal),
        policy.rules === 'nano' ? Promise.all([1, 2].map(stage => policyAsset(`cc-2.1.267-nano-v1/s${stage}_suffix.txt`))) : Promise.resolve(['']),
      ]);
      return { system: `${prompt}\n\n${reviewSourceInstructions}\n\n${inboxSourceInstructions}${messageContext ? `\n\n${messageReviewInstructions}` : ''}`, transcript, model, suffixes };
    });
    const reasoningEffort = model.reasoning?.efforts.find(value => value.id === 'low')?.id ?? model.reasoning?.defaultEffort ?? model.reasoning?.efforts[0]?.id;
    for (const stage of policy.rules === 'nano' ? [1, 2] : [1]) {
      const maxTokens = stage === 1 ? 2112 : 10240;
      const userText = transcript + suffixes[stage - 1];
      const estimatedInput = estimateContent([{ type: 'text', text: system }, { type: 'text', text: userText }]) + 8;
      if (model.context && estimatedInput + maxTokens > model.context.contextWindow) {
        throw new ReviewFailure('context', `Review context exceeds configured window: estimated input ${estimatedInput} + output ${maxTokens} > ${model.context.contextWindow}`);
      }
      const result = await recovery.run(policy.rules === 'nano' ? `cc-s${stage}` : 'legacy', stage === 1 ? 30_000 : 60_000, async attempt => {
        const assembly = new BlockAssembler();
        for await (const chunk of attempt.stream({ ...reviewer, reasoningEffort }, () => ctx.llm.stream({ ...reviewer, system, reasoningEffort,
          sessionId: agent.session.id, messages: [{ role: 'user', content: [{ type: 'text', text: userText }] }], temperature: 0, maxTokens, signal: attempt.signal }))) assembly.push(chunk);
        if (assembly.finish.kind === 'error' || assembly.finish.kind === 'aborted') throw publicFailure(assembly.finish.failure);
        const text = assembly.blocks().filter(block => block.type === 'text').map(block => block.text).join('');
        const decision = policy.rules === 'nano' ? parseNanoDecision(text) : parseDshDecision(text);
        if (!decision) throw invalidVerdict(text.trim() ? 'malformed' : 'empty_text');
        return { decision, usage: assembly.usage };
      });
      decision = result.decision; usage = result.usage;
      if (policy.rules !== 'nano' || stage === 2 || decision.behavior === 'allow') break;
    }
    return { decision: decision!, usage };
  } finally { if (!request.recovery) recovery.finish(decision?.behavior ?? 'unavailable', 'standalone'); }
}

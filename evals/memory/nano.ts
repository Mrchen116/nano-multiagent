import type { MemoryCandidate } from '@nano/product-contracts';
import type { EvaluationConfiguration } from './plan.js';

/** Load the runtime only at the explicitly authorized run boundary. */
export async function createNanoCandidate(config: EvaluationConfiguration['candidate'], id: string, root: string, allowModelCalls: boolean): Promise<MemoryCandidate> {
  if (!allowModelCalls) throw new Error('Candidate model calls require --allow-model-calls');
  const { builtinSkillsRoot } = await import('@nano/personal-assistant');
  const { NanoMemoryCandidate } = await import('@nano/dsh-integration/evaluation');
  return new NanoMemoryCandidate({ id, root, allowModelCalls, builtinSkillsRoot, provider: 'evaluation', model: config.model,
    reasoningEffort: config.reasoningEffort, knowledge: { dreaming: config.dreaming },
    providerPatch: [{ id: 'llm-pi-ai', config: { providers: { evaluation: {
      api: 'openai-completions', baseURL: config.baseURL, apiKeyEnv: config.apiKeyEnv, models: [{ id: config.model }],
    } } } }],
  });
}

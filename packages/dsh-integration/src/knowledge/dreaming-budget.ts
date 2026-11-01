import type { Context } from '@deepseek-ai/cordis';
import type { AgentConfiguration } from '../index.js';

/** Conservative shared estimate for rendered text, including multibyte evidence. */
export const estimateInputTokens = (text: string): number => Math.ceil(Buffer.byteLength(text, 'utf8') / 3);

/** Reserve continuation space using the selected model's declared context capacity. */
export async function dreamingInputLimit(ctx: Context, config: AgentConfiguration, signal?: AbortSignal): Promise<number> {
  const { context } = await ctx.llm.resolveModelInfo(config.provider, config.model, signal);
  const contextWindow=context?.contextWindow;
  if (contextWindow===undefined || !Number.isFinite(contextWindow) || contextWindow <= 8192) throw new Error('Dreaming requires a declared model context window larger than its output reserve.');
  return Math.min(Math.floor(contextWindow * 0.7), contextWindow - 8192);
}

export interface DreamingInputBudget {
  limit: number;
  measure(input: string): Promise<number>;
}
export type DreamingInput = (budget: DreamingInputBudget) => Promise<string>;

import { AsyncLocalStorage } from 'node:async_hooks';
import type { Context } from '@deepseek-ai/cordis';
import { assembleContextFor, type Agent, type ModelSelection } from '@deepseek-ai/dsh-agent';
import { ReasoningEffortId } from '@deepseek-ai/dsh-llm';
import type { PromptAssembly } from '@deepseek-ai/dsh-system-prompt';

const diagnosticAssembly = new AsyncLocalStorage<boolean>();

export function isDiagnosticPromptAssembly(): boolean {
  return diagnosticAssembly.getStore() === true;
}

function selectionFor(agent: Agent): Readonly<ModelSelection> | undefined {
  const current = agent.model.current();
  if (current) return current;
  const header = agent.session.requestHeader()?.config;
  const provider = header?.provider ?? agent.options.provider;
  const model = header?.model ?? agent.options.model;
  if (!provider || !model) return undefined;
  const effort = header?.reasoningEffort ?? agent.options.reasoningEffort;
  return { provider, model, ...(effort ? { reasoningEffort: ReasoningEffortId(effort) } : {}) };
}

/** Assemble an Agent's system prompt and admitted tool schemas using step toolSet admission. */
export async function assembleAgentPrompt(ctx: Context, agent: Agent, signal = new AbortController().signal): Promise<PromptAssembly> {
  return diagnosticAssembly.run(true, async () => {
    const modelSelection = selectionFor(agent);
    if (!modelSelection) return ctx.systemPrompt.assemble({ ...assembleContextFor(agent, signal) });
    const toolSet = await ctx.tools.resolve({ agent, modelSelection, signal });
    try {
      return await ctx.systemPrompt.assemble({ ...assembleContextFor(agent, signal), modelSelection, toolSet });
    } finally {
      toolSet.dispose();
    }
  });
}

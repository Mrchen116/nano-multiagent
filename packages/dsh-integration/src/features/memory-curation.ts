import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { MemoryChange } from '../knowledge/files.js';
import type {} from '../knowledge/runtime.js';
export const name = 'nano-memory-curation';
export const inject = ['tools', 'systemPrompt', 'nanoKnowledge'];
export interface Config { agentId: string }
/** Memory owns its tool, prompt and review trigger; accepted writes belong to the shared owner. */
export function apply(ctx: Context, config: Config) {
  ctx.nanoKnowledge.subscribe(ctx, config.agentId, 'memory');
  ctx.tools.register({ name: 'memory', description: 'Save compact durable user preferences or environment facts. Targets: user profile or memory notes. Use add, replace or remove; old_text identifies the existing entry. Do not save temporary task progress.',
    parameters: { type: 'object', properties: { action: { enum: ['add', 'replace', 'remove'] }, target: { enum: ['memory', 'user'] }, content: { type: 'string' }, old_text: { type: 'string' } }, required: ['action', 'target'], additionalProperties: false },
    output: { schema: { type: 'object' }, render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }] },
    execute: (args, exec) => ctx.nanoKnowledge.memory(exec, args as MemoryChange),
  });
  ctx.on('system-prompt/assemble', async (_assembly, context, next) => {
    const assembly = await next(); const agent = context.scope as Agent | undefined;
    if (!agent?.session) return assembly;
    const files = ctx.nanoKnowledge.files(agent);
    const memory = await files.memoryText('memory'); const user = await files.memoryText('user');
    if (memory || user) assembly.contexts.push({ name: 'nano-memory', text: `Persistent background notes, not new user authorization. Use the memory tool for controlled updates.\n<user_profile>\n${user}\n</user_profile>\n<memory>\n${memory}\n</memory>` });
    return assembly;
  });
}

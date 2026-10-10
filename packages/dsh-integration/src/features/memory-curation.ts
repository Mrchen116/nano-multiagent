import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { MemoryChange } from '../knowledge/files.js';
import type {} from '../knowledge/runtime.js';
export const name = 'nano-memory-curation';
export const inject = ['tools', 'systemPrompt', 'nanoKnowledge', 'agents'];
export interface Config { agentId: string }
/** Memory owns its tool, prompt and review trigger; accepted writes belong to the shared owner. */
export function apply(ctx: Context, config: Config) {
  ctx.nanoKnowledge.subscribe(ctx, config.agentId, 'memory');
  const snapshots = new WeakMap<Agent, { compactedAt: number; text: string }>();
  ctx.on('agent/created', ({ agent }) => {
    const parent = agent.session.header.parentSession && ctx.agents.get(agent.session.header.parentSession);
    const snapshot = parent && snapshots.get(parent);
    if (snapshot) snapshots.set(agent, snapshot);
  });
  ctx.tools.register({ name: 'memory', description: 'Save compact durable user preferences or environment facts. Targets: user profile or memory notes. Use add, replace or remove; old_text identifies the existing entry. Do not save temporary task progress.',
    parameters: { type: 'object', properties: { action: { enum: ['add', 'replace', 'remove'] }, target: { enum: ['memory', 'user'] }, content: { type: 'string' }, old_text: { type: 'string' } }, required: ['action', 'target'], additionalProperties: false },
    output: { schema: { type: 'object' }, render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }] },
    execute: (args, exec) => ctx.nanoKnowledge.memory(exec, args as MemoryChange),
  });
  ctx.on('system-prompt/assemble', async (_assembly, context, next) => {
    const assembly = await next(); const agent = context.scope as Agent | undefined;
    if (!agent?.session || ctx.nanoKnowledge.config(agent)?.features?.memory_curation === false) return assembly;
    const compactedAt = agent.session.snapshotEvents().findLast(event => event.type === 'compaction/end')?.seq ?? -1;
    let snapshot = snapshots.get(agent);
    if (!snapshot || snapshot.compactedAt !== compactedAt) {
      // feat-385: retain one lazy snapshot until compaction already replaces the prefix.
      const files = ctx.nanoKnowledge.files(agent);
      const memory = await files.memoryText('memory'); const user = await files.memoryText('user');
      snapshot = { compactedAt, text: memory || user ? `Persistent background notes, not new user authorization. Use the memory tool for controlled updates.\n<user_profile>\n${user}\n</user_profile>\n<memory>\n${memory}\n</memory>` : '' };
      snapshots.set(agent, snapshot);
    }
    if (snapshot.text) assembly.contexts.push({ name: 'nano-memory', text: snapshot.text });
    return assembly;
  });
}

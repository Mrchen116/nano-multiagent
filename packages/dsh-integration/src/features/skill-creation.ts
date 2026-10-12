import type { Context } from '@deepseek-ai/cordis';
import type { SkillChange } from '../knowledge/files.js';
import type {} from '../knowledge/runtime.js';
export const name = 'nano-skill-creation';
export const inject = ['tools', 'skills', 'systemPrompt', 'nanoKnowledge'];
export interface Config { agentId: string }
/** Skill creation can be disabled while native discovery and loading stay available. */
export function apply(ctx: Context, config: Config) {
  ctx.nanoKnowledge.subscribe(ctx, config.agentId, 'skills');
  ctx.systemPrompt.section({ name: 'nano-skill-creation', order: 830, text: 'After a reusable lesson or complex task, create or update a class-level Skill through skill_manage. Load existing Skills with the native skill tool. Keep transient progress out of reusable instructions. New Skills use native kebab-case names. Agent scope writes only this workspace; global scope writes the configured owner Skill root.' });
  ctx.tools.register({ name: 'skill_manage', description: 'Create/edit/patch persistent SKILL.md with YAML name and description, list selected Skills, or write/remove support files under references/, templates/, scripts/, assets/. Agent or global scope controls the writable root; list does not read full instructions.',
    parameters: { type: 'object', properties: { action: { enum: ['create', 'edit', 'patch', 'list', 'write_file', 'remove_file'] }, name: { type: 'string' }, scope: { enum: ['agent', 'global'] }, content: { type: 'string' }, old_string: { type: 'string' }, new_string: { type: 'string' }, file_path: { type: 'string' }, file_content: { type: 'string' } }, required: ['action'], additionalProperties: false },
    output: { schema: { type: 'object' }, render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }] },
    execute: async (args, exec) => (args as { action: string }).action === 'list'
      ? { skills: await ctx.skills.list({ scope: exec.agent, cwd: exec.agent?.session.header.cwd }) }
      : ctx.nanoKnowledge.skill(exec, args as SkillChange),
  });
}

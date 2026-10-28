import type { Context } from '@deepseek-ai/cordis';
import type { SkillChange } from '../knowledge/files.js';
import type {} from '../knowledge/runtime.js';
export const name = 'nano-skill-creation';
export const inject = ['tools', 'skills', 'systemPrompt', 'nanoKnowledge'];
export interface Config { agentId: string }
/** Built-in creation guidance is independent from background evolution and tool permissions. */
export function apply(ctx: Context, config: Config) {
  ctx.systemPrompt.section({ name: 'nano-skill-creation', order: 830, text: 'Use the built-in skill-creator when creating or improving a reusable Skill. Maintain a class-level Skill only when verified evidence supports a reusable improvement. There is no update quota. Prefer correcting an existing writable Skill in place. Read its current file before changing it. Keep each complete task rule in one Skill; personal preferences that apply across tasks belong in Memory. Preserve explicit user constraints. If the user defers maintenance or asks only for an acknowledgement this turn, do not create or modify a Skill in that turn. There is no automatic background Skill review. Sending a reply does not finish foreground work. Do not turn an Agent choice or a temporary workaround into a standing user requirement. For a workaround, state its conditions, resource owner, and cleanup. If these are unknown, skip the rule. New Skills use native kebab-case names. Use only enabled maintenance tools within their selected writable scopes.' });

}

/** Register the callable interface independently from automatic Feature behavior. */
export function registerTool(ctx: Context) {
  ctx.tools.register({ name: 'skill_manage', description: `Create or maintain persistent Skills for recurring task types. Each call performs one action. Use list to discover Skills. Use skill to load instructions. Use read to inspect the complete SKILL.md, including its YAML frontmatter, before replacing it. Use read for supporting files when available. Prefer patch for a local correction. Edit replaces the whole SKILL.md. Create and edit require a complete document with matching YAML name and description.

Use write_file or remove_file for supporting files under references/, templates/, scripts/, or assets/. Write only within the selected agent or global scope. This tool cannot delete a whole Skill. Separate calls do not form a transaction. A later failure does not undo an earlier successful call. Check the actual state and report partial results accurately.

Write lessons, not logs: imperative rule + why, no PR numbers/dates/incident narration, one rule per lesson, references/ named by topic (extend before adding).`,
    parameters: { type: 'object', properties: { action: { description: 'One action per call. List discovers Skills; it does not read full instructions.', enum: ['create', 'edit', 'patch', 'list', 'write_file', 'remove_file'] }, name: { description: 'Exact native Skill name. Required for write actions.', type: 'string' }, scope: { description: 'Writable scope: agent for this workspace, global for the configured owner root. Default: agent.', enum: ['agent', 'global'] }, content: { description: 'Complete SKILL.md content for create or edit. Edit replaces the whole file.', type: 'string' }, old_string: { description: 'Non-empty text that must occur exactly once in the current SKILL.md.', type: 'string' }, new_string: { description: 'Replacement text for patch. An empty value removes the matched text.', type: 'string' }, file_path: { description: 'Relative support-file path under references/, templates/, scripts/, or assets/. Not a target for patch.', type: 'string' }, file_content: { description: 'Full supporting-file content for write_file. It replaces any existing content at that path.', type: 'string' } }, required: ['action'], additionalProperties: false },
    output: { schema: { type: 'object' }, render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }] },
    execute: async (args, exec) => (args as { action: string }).action === 'list'
      ? { skills: await ctx.skills.list({ scope: exec.agent, cwd: exec.agent?.session.header.cwd }) }
      : ctx.nanoKnowledge.skill(exec, args as SkillChange),
  });
}

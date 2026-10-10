import type { Context } from '@deepseek-ai/cordis';
import * as ToolSchedule from '@deepseek-ai/dsh-tool-schedule';
export const name = 'nano-cron';
export const inject = ['tools', 'nanoProduct', 'systemPrompt'];
export interface Config { agentId: string }
export const scheduleRealm = (agentId: string) => Symbol.for(`nano-schedule:${agentId}`);

/** Session tools follow the one long-lived native owner for this product Agent. */
export function apply(ctx: Context, config: Config) {
  const scoped = ctx.isolate('schedule', scheduleRealm(config.agentId));
  scoped.plugin(ToolSchedule);
  scoped.inject(['schedule', 'tools', 'nanoProduct', 'systemPrompt'], child => {
    child.systemPrompt.section({ name: 'nano-cron', order: 816, text: 'Scheduled and manually triggered saved tasks are system work with saved instructions. They are not new live human messages or answers to approval questions. Creation of a schedule does not grant permission for its future tool actions. Keep queued admission, model completion, and actual public delivery distinct when explaining results.' });
    for (const action of ['run', 'history'] as const) child.tools.register({
      name: `schedule_${action}`, description: action === 'run'
        ? 'Immediately run an existing active schedule in this same main Session. Acceptance is not completion; use schedule_history for its actual result.'
        : 'Read actual schedule execution history, distinguishing timed and manual admission, native turn result, and public delivery.',
      parameters: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'], additionalProperties: false },
      output: { schema: { type: 'object', additionalProperties: true }, render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }] },
      execute: (args, exec) => child.nanoProduct.call(`schedule.${action}`, args, exec),
    });
  });
}

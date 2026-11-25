import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { MAX_TITLE_LENGTH, MIN_EVERY_INTERVAL_SECONDS, ScheduleInputError } from '@deepseek-ai/dsh-schedule';
import { delegationDepthOf } from '@deepseek-ai/dsh-subagent';
import type { ToolExecution } from '@deepseek-ai/dsh-tools';
import type { ScheduleInput } from '@nano/product-contracts/runtime-rpc';
import { createSessionSchedule, listSessionSchedules, updateSessionSchedule, type ScheduleSelectorInput } from '../cron-owners.js';

export const name = 'nano-cron';
export const inject = ['tools', 'systemPrompt', 'nanoProduct'];
export interface Config { agentId: string }
export const scheduleRealm = (agentId: string) => Symbol.for(`nano-schedule:${agentId}`);

const MANAGEMENT_AUTHORIZATION = "Only create or modify scheduled tasks at the user's explicit request; prior explicit user authorization for the running scheduled task remains valid.";
const TITLE_HELP = `Task name of at most ${MAX_TITLE_LENGTH} characters in the user's language.`;

const dailySchema = {
  type: 'object',
  properties: { time: { type: 'string' }, time_zone: { type: 'string' } },
  required: ['time', 'time_zone'],
  additionalProperties: false,
} as const;

const weeklySchema = {
  type: 'object',
  properties: {
    time: { type: 'string' },
    time_zone: { type: 'string' },
    weekdays: { type: 'array', items: { type: 'integer' } },
  },
  required: ['time', 'time_zone', 'weekdays'],
  additionalProperties: false,
} as const;

const cronSchema = {
  type: 'object',
  properties: { expression: { type: 'string' }, time_zone: { type: 'string' } },
  required: ['expression', 'time_zone'],
  additionalProperties: false,
} as const;

const atSchema = {
  oneOf: [
    { type: 'string' },
    {
      type: 'object',
      properties: { date: { type: 'string' }, time: { type: 'string' }, time_zone: { type: 'string' } },
      required: ['date', 'time', 'time_zone'],
      additionalProperties: false,
    },
  ],
} as const;

const jsonOutput = {
  schema: { type: 'object' as const, additionalProperties: true },
  render: (_args: unknown, result: unknown) => [{ type: 'text' as const, text: JSON.stringify(result) }],
};

async function runForRootSession(exec: ToolExecution, operation: (agent: Agent) => Promise<unknown>): Promise<unknown> {
  const agent = exec.agent;
  if (!agent) return { code: 'internal_error', message: 'The schedule operation failed.' };
  if (delegationDepthOf(agent) > 0 || agent.session.header.origin === 'subagent') {
    return { code: 'subagent_session', message: 'A delegated subagent cannot use scheduled tasks.' };
  }
  try {
    return await operation(agent);
  } catch (error) {
    if (error instanceof ScheduleInputError) return { code: error.code, message: error.message };
    return { code: 'internal_error', message: 'The schedule operation failed.' };
  }
}

/** Session tools follow the one long-lived native owner for this product Agent while preserving Nano's 6-tool surface. */
export function apply(ctx: Context, config: Config) {
  const scoped = ctx.isolate('schedule', scheduleRealm(config.agentId));
  scoped.inject(['schedule', 'tools', 'systemPrompt', 'nanoProduct'], child => {
    child.systemPrompt.section({
      name: 'tool:schedule',
      order: child.systemPrompt.getSectionOrder('TOOL_SCHEDULE'),
      text: ({ scope }) =>
        child.tools.get('schedule_create', scope) !== undefined || child.tools.get('schedule_update', scope) !== undefined
          ? MANAGEMENT_AUTHORIZATION
          : '',
    });

    child.tools.register({
      name: 'schedule_create',
      description: `Create a scheduled task delivered to this main Session when due. Provide title, prompt, and exactly one rule: after_seconds, at, every_seconds (>= ${MIN_EVERY_INTERVAL_SECONDS}), daily, weekly, cron, or rrule.`,
      parameters: {
        type: 'object',
        properties: {
          title: { type: 'string', description: TITLE_HELP },
          prompt: { type: 'string', description: 'Instruction delivered when the schedule fires.' },
          after_seconds: { type: 'integer', description: 'Positive delay in seconds for a one-shot reminder.' },
          at: atSchema,
          every_seconds: { type: 'integer', description: `Fixed interval in seconds (>= ${MIN_EVERY_INTERVAL_SECONDS}).` },
          daily: dailySchema,
          weekly: weeklySchema,
          cron: cronSchema,
          rrule: { type: 'string', description: 'RFC 5545 DTSTART + RRULE lines.' },
        },
        required: ['title', 'prompt'],
        additionalProperties: false,
      },
      output: jsonOutput,
      execute: (args, exec) =>
        runForRootSession(exec, agent =>
          createSessionSchedule(child.schedule, agent.session.id, args as { title: string; prompt: string } & ScheduleSelectorInput, exec.signal)),
    });

    child.tools.register({
      name: 'schedule_list',
      description: 'List active scheduled tasks bound to this main Session.',
      parameters: { type: 'object', properties: {}, additionalProperties: false },
      output: {
        schema: { oneOf: [{ type: 'array', items: { type: 'object', additionalProperties: true } }, { type: 'object', additionalProperties: true }] },
        render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }],
      },
      isConcurrencySafe: () => true,
      execute: (_args, exec) => runForRootSession(exec, agent => listSessionSchedules(child.schedule, agent.session.id)),
    });

    child.tools.register({
      name: 'schedule_update',
      description: 'Atomically update title, prompt, or timing of an existing scheduled task in this main Session using optimistic concurrency on expected.',
      parameters: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          expected: { type: 'object', additionalProperties: true, description: 'Exact record returned by schedule_create or schedule_list.' },
          title: { type: 'string', description: TITLE_HELP },
          prompt: { type: 'string' },
          change: {
            type: 'object',
            additionalProperties: true,
            description: 'Optional replacement rule object ({ kind: "at" | "every" | "daily" | "weekly" | "cron" | "rrule", ... }).',
          },
        },
        required: ['id', 'expected'],
        additionalProperties: false,
      },
      output: jsonOutput,
      execute: (args, exec) =>
        runForRootSession(exec, agent =>
          updateSessionSchedule(child.schedule, agent.session.id, args as ScheduleInput<'update'>['args'], exec.signal)),
    });

    child.tools.register({
      name: 'schedule_delete',
      description: 'Delete a scheduled task in this main Session by id.',
      parameters: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'], additionalProperties: false },
      output: jsonOutput,
      execute: (args, exec) =>
        runForRootSession(exec, () => child.nanoProduct.call('schedule.delete', args, exec)),
    });

    for (const action of ['run', 'history'] as const) {
      child.tools.register({
        name: `schedule_${action}`,
        description: action === 'run'
          ? 'Immediately run an existing active schedule in this same main Session. Acceptance is not completion; use schedule_history for its actual result.'
          : 'Read actual schedule execution history, distinguishing timed and manual admission, native turn result, and public delivery.',
        parameters: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'], additionalProperties: false },
        output: jsonOutput,
        ...(action === 'history' ? { isConcurrencySafe: () => true } : {}),
        execute: (args, exec) => child.nanoProduct.call(`schedule.${action}`, args, exec),
      });
    }
  });
}

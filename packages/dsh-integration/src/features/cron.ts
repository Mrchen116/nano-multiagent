import { Service, type Context } from '@deepseek-ai/cordis';
import type { ScheduleView } from '@deepseek-ai/dsh-schedule';
import { delegationDepthOf } from '@deepseek-ai/dsh-subagent';
import * as ToolSchedule from '@deepseek-ai/dsh-tool-schedule';

type ToolJson = string | number | boolean | null | ToolJson[] | { [key: string]: ToolJson };

export interface LogicalCronClockImpl {
  readonly enabled: boolean;
  now(): number;
  createSchedule(agentId: string, sessionId: string, args: Record<string, unknown>, signal?: AbortSignal): Promise<ScheduleView | { code: string; message: string }>;
  listSchedules(agentId: string, sessionId: string): Promise<ScheduleView[]>;
  alignSchedule(agentId: string, scheduleId: string): Promise<void>;
}

export class LogicalCronClock extends Service implements LogicalCronClockImpl {
  constructor(ctx: Context, private readonly impl: LogicalCronClockImpl) {
    super(ctx, 'nanoCronClock');
  }
  get enabled(): boolean { return this.impl.enabled; }
  now(): number { return this.impl.now(); }
  createSchedule(agentId: string, sessionId: string, args: Record<string, unknown>, signal?: AbortSignal) {
    return this.impl.createSchedule(agentId, sessionId, args, signal);
  }
  listSchedules(agentId: string, sessionId: string) {
    return this.impl.listSchedules(agentId, sessionId);
  }
  alignSchedule(agentId: string, scheduleId: string) {
    return this.impl.alignSchedule(agentId, scheduleId);
  }
}

declare module '@deepseek-ai/cordis' {
  interface Context {
    nanoCronClock?: LogicalCronClock;
  }
}

export const name = 'nano-cron';
export const inject = ['tools', 'nanoProduct'];
export interface Config { agentId: string }
export const scheduleRealm = (agentId: string) => Symbol.for(`nano-schedule:${agentId}`);

/** Session tools follow the one long-lived native owner for this product Agent. */
export function apply(ctx: Context, config: Config) {
  const scoped = ctx.isolate('schedule', scheduleRealm(config.agentId));
  // Preserve native schema/approval/return semantics, routing deletes through durable product intent
  // and anchoring relative/recurring schedules to the logical clock only in isolated E2E clock mode.
  ctx.on('tools/execute', async (exec, next) => {
    if (exec.name === 'schedule_delete' && exec.agent) {
      const value = await ctx.nanoProduct.call('schedule.delete', exec.arguments, exec) as { id: string; deleted: boolean; code?: 'schedule_not_found' };
      return { isError: false, value, content: [{ type: 'text', text: JSON.stringify(value) }] };
    }
    const clock = ctx.get('nanoCronClock');
    if (clock?.enabled && exec.agent && delegationDepthOf(exec.agent) === 0) {
      if (exec.name === 'schedule_create') {
        const raw = await clock.createSchedule(config.agentId, exec.agent.session.id, (exec.arguments ?? {}) as Record<string, unknown>, exec.signal);
        const text = JSON.stringify(raw);
        return { isError: false, value: JSON.parse(text) as ToolJson, content: [{ type: 'text', text }] };
      }
      if (exec.name === 'schedule_list') {
        const raw = await clock.listSchedules(config.agentId, exec.agent.session.id);
        const text = JSON.stringify(raw);
        return { isError: false, value: JSON.parse(text) as ToolJson, content: [{ type: 'text', text }] };
      }
      if (exec.name === 'schedule_update') {
        const result = await next();
        if (!result.isError && result.value && typeof result.value === 'object' && 'id' in (result.value as Record<string, unknown>)) {
          const updated = result.value as { id?: unknown; scheduledAt?: unknown };
          if (typeof updated.id === 'string' && typeof updated.scheduledAt === 'string' && Date.parse(updated.scheduledAt) <= clock.now()) {
            await clock.alignSchedule(config.agentId, updated.id);
          }
        }
        return result;
      }
    }
    return next();
  });
  scoped.plugin(ToolSchedule);
  scoped.inject(['schedule', 'tools', 'nanoProduct'], child => {
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

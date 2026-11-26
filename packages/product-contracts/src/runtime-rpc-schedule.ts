import { z } from 'zod';
import { bool, count, evidence, id, input, rpc, text } from './runtime-rpc-schema.js';

const common = {agentId: id, sessionId: id};
const catalog = {...common, sessionId: id.optional()};
const daily = z.object({time: text, time_zone: text});
const weekly = daily.extend({weekdays: z.array(z.int())});
const cron = z.object({expression: text, time_zone: text});
const at = z.union([text, daily.extend({date: text})]);
const timing = z.discriminatedUnion('kind', [
  z.object({kind: z.literal('after'), afterSeconds: count}),
  z.object({kind: z.literal('at')}),
  z.object({kind: z.literal('every'), everySeconds: count}),
  z.object({kind: z.literal('daily'), time: text, timeZone: text}),
  z.object({kind: z.literal('weekly'), time: text, timeZone: text, weekdays: z.array(z.int())}),
  z.object({kind: z.literal('cron'), expression: text, timeZone: text}),
  z.object({kind: z.literal('rrule'), rrule: text}),
]);
const schedule = z.intersection(z.object({scheduledAt: text}), timing);
const record = z.intersection(z.object({id, title: text, prompt: text}), schedule);
const receipt = z.object({scheduledAt: text, deliveredAt: text, messageId: id, prompt: text.optional()});
const history = z.union([
  z.object({id, records: z.array(receipt), earlierRecordsUnavailable: bool, earlierRecordsPruned: bool.optional(),
    retention: z.object({days: count, records: count}).optional(), nextBefore: id.optional()}),
  z.object({id, code: z.enum(['schedule_not_found', 'delivery_cursor_not_found'])}),
]);
const updateChange = z.discriminatedUnion('kind', [
  z.object({kind: z.literal('at'), at}), z.object({kind: z.literal('every'), every_seconds: z.number()}),
  z.object({kind: z.literal('daily'), daily}), z.object({kind: z.literal('weekly'), weekly}),
  z.object({kind: z.literal('cron'), cron}), z.object({kind: z.literal('rrule'), rrule: text}),
]);
const update = z.union([
  z.object({id, updated: bool, record}),
  z.object({id, updated: z.literal(false), code: z.enum(['schedule_not_found', 'schedule_ended', 'schedule_conflict'])}),
  z.object({code: z.enum(['invalid_prompt', 'invalid_selector', 'invalid_rule', 'invalid_time_zone', 'not_future',
    'time_out_of_range', 'frequency_too_high', 'subagent_session', 'internal_error']), message: text}),
]);

export const scheduleActions = {
  jobs: rpc(input({...catalog, action: z.literal('jobs')}), z.array(z.object({
    id, sessionId: id, name: text, instruction: text, schedule, enabled: bool, delete_after_run: bool,
  }))),
  history: rpc(input({...common, action: z.literal('history'), args: z.object({id, limit: z.int().min(1).max(100).optional()})}), history),
  delete: rpc(input({...common, action: z.literal('delete'), args: z.object({id})}), z.discriminatedUnion('deleted', [
    z.object({id, deleted: z.literal(true)}), z.object({id, deleted: z.literal(false), code: z.literal('schedule_not_found')}),
  ])),
  run: rpc(input({...common, action: z.literal('run'), args: z.object({id, inputId: id.startsWith('manual-schedule:')})}), evidence.extend({inputId: id})),
  catalog: rpc(input({...catalog, action: z.literal('catalog')}), z.array(z.intersection(record, z.object({
    sessionId: id, status: z.enum(['active', 'inactive']), lastDelivery: receipt.optional(),
  })))),
  list: rpc(input({...common, action: z.literal('list')}), z.array(record)),
  create: rpc(input({...common, action: z.literal('create'), args: z.object({
    title: text, prompt: text, after_seconds: z.number().optional(), every_seconds: z.number().optional(),
    at: at.optional(), daily: daily.optional(), weekly: weekly.optional(), cron: cron.optional(), rrule: text.optional(),
  }).refine(args => [args.after_seconds, args.every_seconds, args.at, args.daily, args.weekly, args.cron, args.rrule]
    .filter(selector => selector !== undefined).length === 1, 'Expected one scheduling rule')}), record),
  update: rpc(input({...common, action: z.literal('update'), args: z.object({
    id, expected: record, title: text.optional(), prompt: text.optional(), change: updateChange.optional(),
  })}), update),
};

export type ScheduleAction = keyof typeof scheduleActions;
export type ScheduleInput<A extends ScheduleAction> = z.output<(typeof scheduleActions)[A]['input']>;
export type ScheduleOutput<A extends ScheduleAction> = z.output<(typeof scheduleActions)[A]['result']>;

import { z } from 'zod';
import type { ModelRunProjection, RuntimeEvent, RuntimePublicationEvidence, RuntimeWorkerDetail, RuntimeWorkCatalog, RuntimeWorkPage } from './index.js';
import { workerRuntimes } from './worker-runtimes.js';
import { validateWorkPayload, workObject } from './work-event-codec.js';
import { bool, count, cursor, dataObject, id, ids, input, rpc, text } from './runtime-rpc-schema.js';

const terminal = z.object({kind: id});
const content = z.array(z.object({type: id, text: text.optional()}));
const consumedEventData: Record<string, z.ZodType> = {
  'turn/start': z.object({turn: count}),
  'turn/end': z.object({turn: count, reason: terminal}),
  'user/message': z.object({id, source: z.object({kind: id, background_returns: z.array(z.unknown()).optional()}), content}),
  'assistant/message': z.object({turn: count, message: z.object({id, content})}),
  'tool/call': z.object({turn: count, callId: id, name: id}),
  'tool/result': z.object({turn: count, message: z.object({toolCallId: id, isError: bool.optional(), content})}),
};

export const runtimeEvent = z.object({
  seq: count, time: z.number(), type: id, data: dataObject,
  surfaceOp: z.union([z.literal('append'), z.object({op: z.literal('replace'), startSeq: count, endSeq: count})]).optional(),
}).superRefine((event, ctx) => {
  // Most native data belongs to its plugin. Only inspect message fields the product projects.
  const schema = Object.hasOwn(consumedEventData, event.type) && consumedEventData[event.type];
  if (!schema) return;
  const check = schema.safeParse(event.data);
  if (!check.success) ctx.addIssue({code: 'custom', path: ['data', ...check.error.issues[0]!.path], message: 'Invalid event data'});
}) satisfies z.ZodType<RuntimeEvent>;

export const modelRun = z.object({
  id, sessionId: id, turn: count, state: z.enum(['running', 'switching', 'completed']),
  terminal: terminal.optional(), switched: text.optional(),
  attempts: z.array(z.object({turn: count, route: z.object({provider: id, model: id}),
    error: z.object({message: text, code: text}).optional()})),
}) satisfies z.ZodType<ModelRunProjection>;

const detailTypes = new Set(['turn_started', 'message', 'tool_start', 'tool_end', 'turn_end']);
const detailFact = z.custom<RuntimeWorkerDetail['fact']>(value => {
  if (!workObject(value) || typeof value.type !== 'string' || !detailTypes.has(value.type) || !workObject(value.payload)) return false;
  try { return validateWorkPayload(value.type, value.payload); } catch { return false; }
});
const workerChange = z.object({
  id, time: z.number(), workerId: id, rootId: id, callId: id, label: text, runtime: z.enum(workerRuntimes),
  state: z.enum(['starting', 'running', 'completed', 'interrupted', 'failed']),
  detail: z.object({turnId: id, fact: detailFact}).optional(),
  turnUsage: z.object({id, totalTokens: count.nullable()}).optional(),
});
const workPage: z.ZodType<RuntimeWorkPage> = z.object({
  durable: z.literal(true), inboxDelivered: ids.optional(), workerChanges: z.array(workerChange).optional(),
  events: z.array(runtimeEvent), modelRuns: z.array(modelRun), modelVersion: text, throughSeq: cursor, more: bool,
}).superRefine((page, ctx) => {
  if (page.events.some((event, index) => index > 0 && event.seq !== page.events[index - 1]!.seq + 1) ||
      (page.events.length && page.events.at(-1)!.seq !== page.throughSeq))
    ctx.addIssue({code: 'custom', path: ['throughSeq'], message: 'Cursor must match the last included event'});
});
const workCatalog: z.ZodType<RuntimeWorkCatalog> = z.object({
  children: z.array(z.object({kind: z.enum(['child', 'diagnostic']), id, parentId: id, label: text.optional(),
    reason: text.optional(), workflowRunId: id.optional(), mode: text.optional(), depth: count.optional(),
    activity: text.optional(), hasChildren: bool.optional(), throughSeq: cursor.optional(), modelVersion: text.optional()})),
  next: id.optional(),
});
const publication: z.ZodType<RuntimePublicationEvidence> = z.object({
  durable: z.literal(true), call: z.object({turn: count, seq: count}).optional(),
  reads: z.array(runtimeEvent.refine(event => event.type === 'tool/result')), throughSeq: cursor, head: cursor,
});
const work = {sessionId: id, stoppedRevision: count.optional()};
const page = {...work, afterSeq: cursor.optional(), replayFrom: count.optional(), modelVersion: text.optional()};
const confirmed = z.record(z.string(), z.never());

export const runtimeWork = {
  'session.publication': rpc(input({sessionId: id, afterSeq: cursor, callId: id.optional(), readIds: ids, head: cursor.optional()}), publication),
  'session.inbox-delivered.confirm': rpc(input({...work, inputIds: ids}), confirmed),
  'session.work.workers.confirm': rpc(input({...work, changes: z.array(z.object({workerId: id, id}))}), confirmed),
  'session.work.check': rpc(input(page), z.object({rootSettled: bool})),
  'session.work.root': rpc(input(page), workPage),
  'session.work.child': rpc(input({...page, childId: id}), workPage),
  'session.work.children': rpc(input({...work, afterId: id.optional()}), workCatalog),
  'session.work.targets': rpc(input({...work, childId: id}), workCatalog),
};

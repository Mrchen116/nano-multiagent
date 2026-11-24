import { z } from 'zod';
import type { RuntimeWorkPage } from './index.js';
import type { TaskWaitInspection } from './task-execution.js';
import { bool, count, cursor, dataObject, evidence, id, ids, input, rpc, text } from './runtime-rpc-schema.js';
import { scheduleActions, type ScheduleAction, type ScheduleInput, type ScheduleOutput } from './runtime-rpc-schedule.js';
import { modelRun, runtimeEvent, runtimeWork } from './runtime-rpc-work.js';

export type {ScheduleAction, ScheduleInput, ScheduleOutput} from './runtime-rpc-schedule.js';

const session = {sessionId: id};
const agent = {agentId: id};
const accepted = z.object({acknowledged: z.literal(true)});
const durable = z.object({durable: z.literal(true)});
const ok = z.object({ok: z.literal(true)});
const content = z.array(z.discriminatedUnion('type', [
  z.object({type: z.literal('text'), text}),
  z.object({type: z.literal('image'), mediaType: z.enum(['image/png', 'image/jpeg', 'image/webp', 'image/gif']), data: text, name: text.optional()}),
]));
const attachments = z.array(z.discriminatedUnion('kind', [
  z.object({kind: z.literal('chat'), conversationId: id, messageId: id, url: text}),
  z.object({kind: z.literal('workspace'), path: text}),
]).nullable());
const source = z.object({
  kind: z.enum(['human','system']), actorId: id, channel: id, messageId: id,
  lifecycle_revision: count.optional(), nanoTeamChat: bool.optional(), directHumanText: text.optional(),
  humanTaskControl: dataObject.optional(), contextEnvelope: text.optional(), conversationId: id.optional(),
  sender: dataObject.optional(), pa_agent_id: id.optional(), roleAccountId: id.optional(),
  senderSessionId: id.optional(), background_returns: z.array(dataObject).optional(),
});
const snapshot = z.object({revision: id, allowed: ids, excluded: ids});
const receipt = z.object({operationId: id, path: text, beforeHash: text.nullable(), afterHash: text.nullable(),
  saved: bool, versionRecorded: bool, commit: text.optional(), error: text.optional()});
const fact = z.object({
  id, agentId: id, rootSessionId: id, sessionId: id, turn: count, kind: z.enum(['memory','skills']),
  action: text, path: text, name: text.optional(), scope: text.optional(), skill_root: text.optional(), reviewId: id.optional(),
});
const review = z.object({
  id, agentId: id, rootSessionId: id, childSessionId: id.optional(), at: z.number(), status: id,
  kind: z.enum(['memory', 'skills', 'combined', 'dreaming']), title: text.optional(), endedAt: z.number().optional(),
  summary: text.optional(), stage: z.enum(['extract', 'consolidate']).optional(),
  workMetrics: z.object({tool_count: count, model_request_state: z.enum(['none','requested']),
    model: text.optional(), usage: z.object({total_tokens: count}).optional()}).optional(),
});
const workflow = z.object({
  id, parentSessionId: id, inputIds: ids, meta: z.object({name: text, description: text}),
  startedAt: z.number(), endedAt: z.number(), usage: dataObject, logs: z.array(z.object({text})),
  result: z.object({value: z.unknown(), stopReason: z.enum(['completed','cancelled','error']), error: text.optional()}),
});
const wait: z.ZodType<TaskWaitInspection> = z.object({
  valid: bool, checked_at: text, reason_code: z.enum(['missing','inactive','expired','owner_or_session_mismatch','unavailable']).optional(),
  owner_agent_id: id.optional(), session_id: id.optional(), next_check_at: text.optional(), pending_occurrence_id: id.optional(),
});
const approval = z.object({
  time: z.number(), callId: id, tool: text, source: text, decision: text, reason: text, consecutive: count, total: count,
});

const methods = {
  'session.ensure': rpc(input({...session, ...agent, ownerId: id, cwd: id, revision: id}), z.object({...session, revision: id})),
  'session.lookup': rpc(input({...session, inputId: id}), evidence),
  'session.submit': rpc(input({...session, inputId: id, mode: z.enum(['followup','steer','inject']), content, source,
    attachmentSources: attachments.optional(), onlyIfIdle: bool.optional()}), z.union([
    evidence.extend({durable: z.literal(true)}),
    z.object({accepted: z.literal(false), busy: z.literal(true)}),
    z.object({accepted: z.literal(false), withdrawn: z.literal(true), durable: z.literal(true)}),
  ])),
  'session.cancel': rpc(input({...session, stoppedAt: text.optional(), settleTaskContext: bool.optional()}), z.object({stopped: z.literal(true), wasRunning: bool})),
  'session.command': rpc(input({...session, id, action: z.enum(['compact','effort','config','workflows']), argument: text.optional()}), z.object({text, success: bool.optional()})),
  'session.observe': rpc(input({...session, afterSeq: cursor.optional()}), z.object({
    status: z.enum(['idle','running']), events: z.array(runtimeEvent), durable: z.literal(true), throughSeq: cursor,
    modelRuns: z.array(modelRun), modelVersion: text, approvals: z.array(approval),
  })),
  'session.recovery.probe': rpc(input({...session, afterSeq: cursor, localWork: bool}), z.object({live: bool, unseen: bool})),
  'session.export': rpc(input(session), z.object({path: id})),
  'session.fork': rpc(input({...session, messageId: id, operationId: id}), z.object({...session, revision: id, idMap: z.record(id, id)})),
  ...runtimeWork,
  'schedule.evidence': rpc(input(session), z.array(evidence.extend({
    messageId: id, scheduleId: id, scheduledAt: text.optional(), trigger: z.enum(['timed','manual']),
  }))),
  'schedule.wait.inspect': rpc(input({...session, ...agent, scheduleId: id}), wait),
  'task.context.passive': rpc(input({...session, ...agent, messages: z.array(z.object({
    inputId: id, conversationId: id, humanControl: dataObject.optional(), content,
  })), revoked: ids}), durable),
  'task.execution.block': rpc(input({...session, blocked: bool}), ok),
  'task.execution.changed': rpc(input({...agent, reset: bool.optional()}), ok),
  'task.wait.repair': rpc(input({...session, ...agent, inputId: id.startsWith('task-wait-repair:')}), durable),
  'knowledge.facts': rpc(input({}), z.object({facts: z.array(fact), reviews: z.array(review)})),
  'knowledge.acknowledge': rpc(input({id}), accepted),
  'knowledge.sources.pending': rpc(input(agent), z.object({pending: z.literal(true)})),
  'knowledge.sources.sync': rpc(input({...agent, snapshot}), z.union([z.object({mode: z.literal('legacy')}),
    z.object({generation: count, sourcesPending: bool, sources: snapshot.optional(), receipts: z.array(receipt), backupRoot: text})])),
  'workflow.pending': rpc(input({}), z.array(workflow)),
  'workflow.acknowledge': rpc(input({runId: id}), accepted),
  'approval.answer': rpc(input({requestId: id, decision: z.enum(['allowed-once', 'rejected']), reason: text.optional()}), z.object({answered: z.literal(true)})),
  'configuration.selection': rpc(input({...agent, cwd: id}), z.object({tools: ids, skills: z.array(z.object({name: id}))})),
  'pa.review': rpc(z.discriminatedUnion('kind', [
    input({...agent, kind: z.literal('input'), evidence: dataObject, sessionId: id.optional(), callId: id.optional()}),
    input({...agent, kind: z.literal('action'), evidence: dataObject, ...session, callId: id.optional()}),
  ]), z.object({decision: z.enum(['allow','deny','needs_owner','unavailable']), reason: text, incident: z.object({reason: text}).optional()})),
};

type OrdinaryMethod = keyof typeof methods;
export type RuntimeMethod = OrdinaryMethod | 'schedule.command';
export type RuntimeInput<K extends RuntimeMethod> = K extends OrdinaryMethod ? z.output<(typeof methods)[K]['input']> : ScheduleInput<ScheduleAction>;
export type RuntimeRequestInput<K extends RuntimeMethod, A extends ScheduleAction = ScheduleAction> = RuntimeInput<K> & (K extends 'schedule.command' ? {action: A} : unknown);
export type RuntimeOutput<K extends RuntimeMethod, A extends ScheduleAction = ScheduleAction> = K extends OrdinaryMethod ? z.output<(typeof methods)[K]['result']> : ScheduleOutput<A>;
export const runtimeMethods: readonly RuntimeMethod[] = [...Object.keys(methods) as OrdinaryMethod[], 'schedule.command'];
/** Check whether a transport method belongs to the public product port. */
export function isRuntimeMethod(value: string): value is RuntimeMethod {
  return value === 'schedule.command' || Object.hasOwn(methods, value);
}

export interface RuntimeRequest {
  <K extends RuntimeMethod, A extends ScheduleAction = ScheduleAction>(method: K, input: RuntimeRequestInput<NoInfer<K>, A>): Promise<RuntimeOutput<K, A>>;
}
type Handler<I, O> = (input: I) => O | Promise<O>;
export type ScheduleHandlerMap = {[A in ScheduleAction]: Handler<ScheduleInput<A>, ScheduleOutput<A>>};
export type RuntimeHandlerMap = {[K in OrdinaryMethod]: Handler<RuntimeInput<K>, RuntimeOutput<K>>} & {'schedule.command': ScheduleHandlerMap};

export class RuntimeRpcValidationError extends Error {}
function schemaFor(method: RuntimeMethod, input: unknown) {
  if (method !== 'schedule.command') return methods[method];
  const action = input && typeof input === 'object' && 'action' in input ? input.action : undefined;
  if (typeof action !== 'string' || !Object.hasOwn(scheduleActions, action)) throw new RuntimeRpcValidationError('Invalid schedule.command input at action');
  return scheduleActions[action as ScheduleAction];
}

function checked<T>(schema: z.ZodType, method: RuntimeMethod, side: 'input' | 'result', value: unknown): T {
  const check = schema.safeParse(value);
  if (!check.success) {
    const path = check.error.issues[0]?.path.join('.') || '<root>';
    throw new RuntimeRpcValidationError(`Invalid ${method} ${side} at ${path}`);
  }
  // The schema validates product fields. Returning the wire object retains native extensions and nested identities.
  return value as T;
}

/**
 * Validate untrusted stdio input before dispatching any product operation.
 *
 * Args:
 *   method: Registered product method selected by the transport.
 *   raw: Incoming parameters, including lifecycle metadata where present.
 * Returns:
 *   The original parameters with their validated product type.
 */
export function decodeRuntimeInput<K extends RuntimeMethod>(method: K, raw: unknown): RuntimeInput<K> {
  return checked(schemaFor(method, raw).input, method, 'input', raw);
}

/**
 * Validate a result before it affects routing, persistence or the consuming product.
 *
 * Args:
 *   method: Method of the originating request.
 *   input: Original parameters selecting the schedule action or Work cursor.
 *   raw: Untrusted transport result.
 * Returns:
 *   The original result, including extension fields and native event bodies.
 */
export function decodeRuntimeResult<K extends RuntimeMethod, A extends ScheduleAction = ScheduleAction>(
  method: K, input: RuntimeRequestInput<NoInfer<K>, A>, raw: unknown,
): RuntimeOutput<K, A> {
  const result = checked<RuntimeOutput<K, A>>(schemaFor(method, input).result, method, 'result', raw);
  if (method === 'session.work.root' || method === 'session.work.child') {
    const page = result as RuntimeWorkPage;
    const {afterSeq = -1, stoppedRevision} = input as RuntimeInput<'session.work.root'>;
    // A root may advance only its worker or Inbox confirmations while the native cursor stays fixed.
    const acknowledgements = method === 'session.work.root' &&
      (page.workerChanges?.length || (stoppedRevision === undefined && page.inboxDelivered?.length));
    // Only native inheritance can advance past offsets absent from this page.
    const firstOffset = page.events[0] ? page.events[0].seq - 1 : page.throughSeq;
    if (firstOffset < afterSeq ||
        (page.inheritedThroughSeq !== undefined ? page.inheritedThroughSeq !== firstOffset || firstOffset <= afterSeq :
          firstOffset !== afterSeq) ||
        (page.more && !page.events.length && !acknowledgements))
      throw new RuntimeRpcValidationError(`Invalid ${method} result at throughSeq`);
  }
  return result;
}

/**
 * Adapt a transport at the first product consumer.
 *
 * Args:
 *   raw: Transport callback scoped to the correct host and generation.
 * Returns:
 *   A typed request function that verifies each successful reply once.
 */
export function typedRuntimeRequest(raw: (method: RuntimeMethod, input: RuntimeInput<RuntimeMethod>) => Promise<unknown>): RuntimeRequest {
  return async (method, input) => decodeRuntimeResult(method, input, await raw(method, input));
}

/**
 * Invoke the handler corresponding to an already validated method and action.
 *
 * Args:
 *   handlers: The host's complete, checked registration table.
 *   method: Product method to dispatch.
 *   input: Parameters returned by decodeRuntimeInput.
 * Returns:
 *   The handler's synchronous or asynchronous result.
 */
export function invokeRuntimeHandler<K extends RuntimeMethod>(handlers: RuntimeHandlerMap, method: K, input: RuntimeInput<NoInfer<K>>): RuntimeOutput<K> | Promise<RuntimeOutput<K>> {
  // TypeScript does not retain the correlation of a dynamic index with the argument.
  const handler = method === 'schedule.command'
    ? handlers['schedule.command'][(input as ScheduleInput<ScheduleAction>).action]
    : handlers[method as OrdinaryMethod];
  return (handler as unknown as Handler<RuntimeInput<K>, RuntimeOutput<K>>)(input);
}

/**
 * Dispatch an untrusted request through the product contract.
 *
 * Args:
 *   handlers: The host's complete, checked registration table.
 *   method: Product method selected by the transport.
 *   raw: Untrusted parameters.
 * Returns:
 *   The selected handler's result, after successful input validation.
 */
export function dispatchRuntime<K extends RuntimeMethod>(handlers: RuntimeHandlerMap, method: K, raw: unknown) {
  return invokeRuntimeHandler(handlers, method, decodeRuntimeInput(method, raw));
}

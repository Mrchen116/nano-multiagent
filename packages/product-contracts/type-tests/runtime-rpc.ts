import type { RuntimeHandlerMap, RuntimeRequest, ScheduleHandlerMap } from '../src/runtime-rpc.js';
import { decodeRuntimeResult } from '../src/runtime-rpc.js';

declare const request: RuntimeRequest;
declare const handlers: RuntimeHandlerMap;
declare const schedules: ScheduleHandlerMap;

async function checkCalls() {
  const {sessionId, idMap} = await request('session.fork', {sessionId: 's', messageId: 'm', operationId: 'op'});
  idMap[sessionId]?.toUpperCase();
  const jobs = await request('schedule.command', {agentId: 'a', action: 'jobs'});
  jobs.map(job => job.name);
  const removed = await request('schedule.command', {agentId: 'a', sessionId: 's', action: 'delete', args: {id: 'job'}});
  removed.deleted satisfies boolean;
  const history = decodeRuntimeResult('schedule.command', {agentId: 'a', sessionId: 's', action: 'history', args: {id: 'job'}}, {});
  if ('records' in history) history.records.map(row => row.messageId);

  // @ts-expect-error host-only method is absent from the product port
  await request('trajectory.open', {});
  // @ts-expect-error session.fork requires a durable operation ID
  await request('session.fork', {sessionId: 's', messageId: 'm'});
  // @ts-expect-error inputs from another method cannot select the output by inference
  await request('session.lookup', {sessionId: 's', callId: 'c', readIds: [], afterSeq: -1});
  // @ts-expect-error run requires its stable input identity
  await request('schedule.command', {agentId: 'a', sessionId: 's', action: 'run', args: {id: 'job'}});
  // @ts-expect-error checkout/action-specific result cannot be read as another action
  removed.records;
}

const { 'session.export': omitted, ...missingExport } = handlers;
// @ts-expect-error every method needs its own registered handler
missingExport satisfies RuntimeHandlerMap;
// @ts-expect-error fork cannot implement export's path-bearing result
handlers['session.fork'] satisfies RuntimeHandlerMap['session.export'];
// @ts-expect-error delete cannot respond with jobs
const wrongDelete: ScheduleHandlerMap['delete'] = async () => schedules.jobs({agentId: 'a', action: 'jobs'});
const {create: omittedCreate, ...missingCreate} = schedules;
// @ts-expect-error all host schedule actions are registered
missingCreate satisfies ScheduleHandlerMap;

const forward: RuntimeRequest = (method, input) => request(method, input);

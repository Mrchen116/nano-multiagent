import { describe, expect, it, vi } from 'vitest';
import {
  decodeRuntimeInput, decodeRuntimeResult, dispatchRuntime, isRuntimeMethod, runtimeMethods,
  typedRuntimeRequest, type RuntimeHandlerMap,
} from '../src/runtime-rpc.js';

// Product methods registered in the parent of refactor-783, including the direct stopped-host Work reader.
const baseline = [
  'session.ensure', 'session.lookup', 'session.submit', 'session.cancel', 'session.command', 'session.observe',
  'session.recovery.probe', 'session.export', 'session.fork', 'session.publication', 'session.inbox-delivered.confirm',
  'session.work.check', 'session.work.root', 'session.work.children', 'session.work.child', 'session.work.targets',
  'session.work.workers.confirm', 'schedule.command', 'schedule.evidence', 'schedule.wait.inspect',
  'task.context.passive', 'task.execution.block', 'task.execution.changed', 'task.wait.repair',
  'knowledge.facts', 'knowledge.acknowledge', 'knowledge.sources.pending', 'knowledge.sources.sync',
  'workflow.pending', 'workflow.acknowledge', 'approval.answer', 'configuration.selection', 'pa.review',
];

describe('runtime RPC', () => {
  it('exposes the finite product surface', () => {
    expect([...runtimeMethods].sort()).toEqual(baseline.sort());
    expect(isRuntimeMethod('session.status')).toBe(false);
    expect(isRuntimeMethod('constructor')).toBe(false);
  });

  it('rejects invalid mutation parameters before the registered handler runs', () => {
    const fork = vi.fn(), submit = vi.fn(), remove = vi.fn();
    const handlers = {'session.fork': fork, 'session.submit': submit, 'schedule.command': {delete: remove}} as unknown as RuntimeHandlerMap;
    expect(() => dispatchRuntime(handlers, 'session.fork', {sessionId: 's', messageId: 'm'})).toThrow('operationId');
    expect(() => dispatchRuntime(handlers, 'session.submit', {
      sessionId: 's', inputId: 'i', mode: 'steer', content: [{type: 'text', text: 'private message'}],
      source: {kind: 'system', actorId: 'a', messageId: 'm'},
    })).toThrow('source.channel');
    expect(() => dispatchRuntime(handlers, 'schedule.command', {action: 'delete', agentId: 'a', sessionId: 's', args: {}})).toThrow('args.id');
    expect([fork, submit, remove].every(fn => fn.mock.calls.length === 0)).toBe(true);
    expect(() => decodeRuntimeInput('schedule.command', {agentId: 'a', sessionId: 's', action: 'create',
      args: {title: 'reminder', prompt: 'check', after_seconds: 30, every_seconds: 3600}})).toThrow('args');
    expect(() => decodeRuntimeInput('pa.review', {kind: 'action', agentId: 'a', evidence: {body: 'private message'}})).toThrow('sessionId');
    expect(() => decodeRuntimeInput('session.recovery.probe', {sessionId: 's', afterSeq: -2, localWork: true})).toThrow('afterSeq');
  });

  it('decodes the reply using the requested schedule action, retaining business failures', async () => {
    const raw = vi.fn().mockResolvedValueOnce({id: 'j', deleted: true}).mockResolvedValueOnce([])
      .mockResolvedValueOnce({id: 'missing', code: 'schedule_not_found'});
    const request = typedRuntimeRequest(raw);
    await expect(request('schedule.command', {action: 'jobs', agentId: 'a'})).rejects.toThrow('schedule.command result');
    await expect(request('schedule.command', {action: 'delete', agentId: 'a', sessionId: 's', args: {id: 'j'}})).rejects.toThrow('schedule.command result');
    expect(await request('schedule.command', {action: 'history', agentId: 'a', sessionId: 's', args: {id: 'missing'}})).toEqual({id: 'missing', code: 'schedule_not_found'});
    expect(() => decodeRuntimeResult('session.fork', {sessionId: 's', messageId: 'm', operationId: 'op'},
      {sessionId: 'new', revision: 'r', idMap: {old: 5}})).toThrow('idMap.old');
  });

  it('preserves native event bodies, worker payloads and extensions while checking the complete page', () => {
    const event = {seq: 7, time: 0, type: 'assistant/message', surfaceOp: 'append', data: {
      turn: 0, message: {id: 'response', content: [{type: 'text', text: 'original'}], source: {kind: 'model', extension: [3, 1]}},
    }};
    const change = {id: 'c', workerId: 'w', rootId: 's', callId: 'call', label: '', runtime: 'codex', state: 'completed', time: 0,
      detail: {turnId: 'wt', fact: {type: 'message', payload: {text: 'full raw message', source_refs: [{source: 'agent'}]}}}};
    const page = {durable: true, more: false, throughSeq: 7, modelVersion: '', events: [event], modelRuns: [], workerChanges: [change]};
    const input = {sessionId: 's', stoppedRevision: 42, afterSeq: 6};
    expect(decodeRuntimeResult('session.work.root', input, page)).toBe(page);
    expect(decodeRuntimeResult('session.work.child', {...input, childId: 'c'}, page).events[0]).toBe(event);
    const workerOnly = {...page, more: true, throughSeq: 6, events: []};
    expect(decodeRuntimeResult('session.work.root', input, workerOnly)).toBe(workerOnly);
    expect(() => decodeRuntimeResult('session.work.child', {...input, childId: 'c'}, workerOnly)).toThrow('throughSeq');
    expect(() => decodeRuntimeResult('session.work.root', input, {...workerOnly, workerChanges: []})).toThrow('throughSeq');
    expect(() => decodeRuntimeResult('session.work.root', {...input, afterSeq: 7}, page)).toThrow('throughSeq');
    expect(() => decodeRuntimeResult('session.work.root', {sessionId:'s'}, {...page,events:[],throughSeq:100})).toThrow('throughSeq');
    expect(() => decodeRuntimeResult('session.work.root', input, {...page, events:[], throughSeq:100})).toThrow('throughSeq');
    expect(() => decodeRuntimeResult('session.work.root', input, {...page, events:[{...event,seq:100}], throughSeq:100})).toThrow('throughSeq');
    const inherited = {...page, events:[], throughSeq:100, inheritedThroughSeq:100};
    expect(decodeRuntimeResult('session.work.child', {...input,childId:'child'}, inherited)).toBe(inherited);
    const invalidInbox = {...page, events:[{...event,type:'agent/inbox/spliced',data:{}}]};
    expect(() => decodeRuntimeResult('session.work.root', input, invalidInbox)).toThrow('data.inserted');
    expect(() => decodeRuntimeResult('session.work.root', input, {...page, durable: false})).toThrow('durable');
    expect(() => decodeRuntimeResult('session.work.root', input, {...page, throughSeq: 8})).toThrow('throughSeq');
    expect(() => decodeRuntimeResult('session.work.root', input, {...page, events: [{...event, data: {turn: 0}}]})).toThrow('events.0.data.message');
    expect(() => decodeRuntimeResult('session.work.root', input, {...page, workerChanges: [{...change,
      detail: {turnId: 'wt', fact: {type: 'message', payload: {text: 8}}}}]})).toThrow('workerChanges.0.detail.fact');
  });

  it('requires both empty-object confirmations and validates collection members before owner filtering', () => {
    const ack = {};
    expect(decodeRuntimeResult('session.inbox-delivered.confirm', {sessionId: 's', inputIds: ['m']}, ack)).toBe(ack);
    expect(decodeRuntimeResult('session.work.workers.confirm', {sessionId: 's', changes: []}, ack)).toBe(ack);
    expect(() => decodeRuntimeResult('session.work.workers.confirm', {sessionId: 's', changes: []}, null)).toThrow();
    expect(() => decodeRuntimeResult('session.inbox-delivered.confirm', {sessionId: 's', inputIds: []}, {error: 'not confirmed'})).toThrow();
    expect(() => decodeRuntimeResult('workflow.pending', {}, [{id: 'run', parentSessionId: 42}])).toThrow();
    expect(() => decodeRuntimeResult('knowledge.facts', {}, {facts: [], reviews: [{agentId: 9}]})).toThrow();
  });
});

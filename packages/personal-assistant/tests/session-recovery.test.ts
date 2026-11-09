import {expect, it} from 'vitest';
import type {AgentConfiguration, RelayInput, SessionBinding} from '@nano/product-contracts';
import {SingleThread} from '../src/single-thread.js';
import {NodeStore} from '../src/store.js';

const agent: AgentConfiguration = {agentId: 'a', mode: 'single_thread', provider: 'p', model: 'm', revision: '1', workspace: '/tmp'};
const binding = (sessionId: string, conversationId = sessionId): SessionBinding => ({
  sessionId, conversationId, agentId: 'a', ownerId: 'owner', revision: '1', cwd: '/tmp',
});
const input = (id: string): RelayInput => ({agent_id: 'a', conversation_id: 'delivery', relay_task_id: id, idempotency_key: id,
  metadata: {conversation_type: 'direct'}, message: {id, content: id, sender_type: 'user', sender_user_id: 'owner', attachments: []}});

it('selects a terminal delivery with an unconfirmed receipt while skipping verified cold history', async () => {
  const store = new NodeStore(':memory:', 'owner');
  const calls: string[] = [], receipts: unknown[] = [];
  const product = new SingleThread({store, agents: [agent], nodeId: 'node', ownerId: 'owner',
    recoveryGeneration: () => 'new-runtime', image: async () => '', onError: error => { throw error; },
    runtime: {onNotification: () => () => {}, async request(method) {
      calls.push(method);
      if (method === 'session.recovery.probe') return {live: false, unseen: true};
      return {durable: true, events: []};
    }},
    relay: {async request(type, payload) {
      expect(type).toBe('node.delivery_receipt');
      receipts.push(payload);
      return {type: 'ack', payload: {}};
    }},
  });
  try {
    for (const id of ['verified', 'delivery']) {
      store.bind(binding(id));
      store.confirmColdSession(id, undefined);
      const eventId = store.receive(id, input(id));
      store.inputEvidence(eventId, {accepted: true, turn: 1, terminal: {kind: 'completed'}}, true);
      store.updateDelivery(store.prepareDelivery(id, 1).operationId, 'confirmed', 'existing-bubble', 'saved');
      if (id === 'verified') store.confirmReceipt(eventId, 'completed');
    }
    expect(store.recoveryCandidates(['a']).map(candidate => candidate.binding.sessionId)).toEqual(['delivery']);
    await product.recover();
    expect(calls).toEqual(['session.recovery.probe', 'session.ensure', 'session.observe']);
    expect(receipts).toEqual([{node_id: 'node', relay_task_id: 'delivery', delivery_status: 'completed'}]);
    expect(store.delivery('delivery', 1)).toMatchObject({state: 'confirmed', messageId: 'existing-bubble'});
    expect(store.recoveryCandidates(['a'])).toEqual([]);
  } finally { await product.stop(); store.close(); }
});

it('retains failed probes and cannot clear a new writable generation from an older cut', async () => {
  const store = new NodeStore(':memory:', 'owner');
  const calls: string[] = [];
  let fails = true;
  const product = new SingleThread({store, agents: [agent], nodeId: 'node', ownerId: 'owner',
    recoveryGeneration: () => 'new-runtime', image: async () => '', onError: error => { throw error; },
    runtime: {onNotification: () => () => {}, async request(method) {
      calls.push(method);
      if (fails) throw new Error('Native history unreadable');
      store.markSessionWritable('web', 'new-runtime');
      return {live: false, unseen: false};
    }},
    relay: {async request() { throw new Error('unexpected relay'); }},
  });
  try {
    store.bind(binding('web'));
    store.bind(binding('stopped', 'external:chat'));
    store.markSessionWritable('web', 'old-runtime');
    store.saveControl({id: 'stop', binding: binding('stopped', 'external:chat'), input: input('stop'), action: 'task-stop', argument: ''});
    await expect(product.recover(true)).resolves.toBeUndefined();
    expect(calls).toEqual([]);
    await expect(product.recover()).rejects.toThrow('Native history unreadable');
    expect(store.recoveryCandidates(['a']).find(item => item.binding.sessionId === 'web')?.generation).toBe('old-runtime');
    fails = false;
    await product.recover();
    expect(calls).toEqual(['session.recovery.probe', 'session.recovery.probe']);
    expect(store.recoveryCandidates(['a']).find(item => item.binding.sessionId === 'web')?.generation).toBe('new-runtime');
  } finally { await product.stop(); store.close(); }
});


it.each([
  {waitAt: 'session.ensure', changed: 'channel'},
  {waitAt: 'session.lookup', changed: 'stop'},
])('rechecks $changed after $waitAt before restoring pending input', async ({waitAt,changed}) => {
  const store = new NodeStore(':memory:', 'owner');
  const session = store.bind(binding('delivery','external:delivery'));
  store.receive(session.sessionId,input('unsubmitted'));
  let release!: () => void;
  const waiting = new Promise<void>(resolve => { release = resolve; });
  let connected = true;
  const calls: string[] = [];
  const product = new SingleThread({store, agents: [agent], nodeId: 'node', ownerId: 'owner',
    recoveryGeneration: () => connected ? 'runtime' : undefined, image: async () => '', onError: error => { throw error; },
    runtime: {onNotification: () => () => {}, async request(method) {
      calls.push(method);
      if (method === waitAt) await waiting;
      return method === 'session.recovery.probe' ? {live:false,unseen:false} : {accepted:false};
    }},
    relay: {async request() { throw new Error('unexpected relay'); }},
  });
  try {
    const recovering = product.recover();
    await expect.poll(() => calls.includes(waitAt)).toBe(true);
    if (changed === 'channel') connected = false;
    else store.saveControl({id:'stop',binding:session,input:input('stop'),action:'task-stop',argument:''});
    release();
    await recovering;
    expect(calls).not.toContain('session.submit');
    expect(calls).not.toContain('session.observe');
    expect(store.pendingInputs(session.sessionId)).toHaveLength(1);
  } finally { release(); await product.stop(); store.close(); }
});

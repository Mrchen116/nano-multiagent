import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { expect, it } from 'vitest';
import type { ModelRunProjection, RelayInput, RuntimeEvent } from '@nano/product-contracts';
import { NodeStore } from '../src/store.js';
import { SingleThread } from '../src/single-thread.js';

type Evidence = { accepted: boolean; pending?: boolean; turn?: number; terminal?: unknown };
const binding = { sessionId: 's', agentId: 'a', conversationId: 'c', ownerId: 'owner', cwd: '/tmp', revision: '1' };
const input = (id: string): RelayInput => ({ agent_id: 'a', conversation_id: 'c', relay_task_id: id, idempotency_key: id,
  metadata: { conversation_type: 'direct' }, message: { id, content: id, sender_type: 'user', sender_user_id: 'owner', attachments: [] } });
const completed = (turn: number): Evidence => ({ accepted: true, pending: false, turn, terminal: { kind: 'completed' } });

function harness(store: NodeStore) {
  const state = { evidence: new Map<string, Evidence>(), events: [] as RuntimeEvent[], runs: [] as ModelRunProjection[],
    lookups: [] as string[], frames: [] as Record<string, unknown>[], failReceipt: false };
  const product = new SingleThread({ nodeId: 'n', ownerId: 'owner', store,
    agents: [{ agentId: 'a', revision: '1', mode: 'single_thread', provider: 'p', model: 'm', workspace: '/tmp' }],
    runtime: { onNotification: () => () => {}, async request(method, value) {
      const args = value as { inputId: string; afterSeq: number };
      if (method === 'session.lookup') {
        state.lookups.push(args.inputId);
        const evidence = state.evidence.get(args.inputId);
        if (!evidence) throw new Error(`Unexpected lookup: ${args.inputId}`);
        return evidence;
      }
      if (method === 'session.observe') return { durable: true, events: state.events.filter(event => event.seq > args.afterSeq), modelRuns: state.runs };
      return {};
    } },
    relay: { async request(type, payload) {
      if (type === 'node.delivery_receipt' && state.failReceipt) throw new Error('receipt offline');
      state.frames.push({ type, ...payload });
      return { type: 'ack', payload: { message_id: 'reply' } };
    } }, image: async () => '', onError: error => { throw error; },
  });
  return { state, product };
}

it('bounds steady-state lookup RPCs by unresolved inputs after old terminal rows are verified', async () => {
  const store = new NodeStore(':memory:', 'owner');
  store.bind(binding);
  const { state, product } = harness(store);
  try {
    for (let turn = 1; turn <= 1000; turn++) {
      const id = store.receive('s', input(String(turn)));
      store.inputEvidence(id, completed(turn));
      const delivery = store.prepareDelivery('s', turn);
      store.updateDelivery(delivery.operationId, 'confirmed', `reply-${turn}`, 'done');
      store.confirmReceipt(id, 'completed');
      state.evidence.set(id, completed(turn));
    }
    await product.recover();
    expect(state.lookups).toHaveLength(1000);
    state.lookups.length = 0;
    await product.recover();
    expect(state.lookups).toEqual([]);
    for (const id of ['pending', 'unconsumed', 'missing-pending']) {
      const key = store.receive('s', input(id));
      store.accepted(key);
      state.evidence.set(key, id === 'missing-pending' ? { accepted: true, terminal: { kind: 'completed' } } : { accepted: true, pending: id === 'pending' });
    }
    await product.recover();
    expect(state.lookups).toEqual(['a:pending', 'a:unconsumed', 'a:missing-pending']);
    state.lookups.length = 0;
    state.evidence.set('a:pending', { accepted: true, pending: false, terminal: { kind: 'cancelled-before-consumption' } });
    await product.recover();
    state.lookups.length = 0;
    await product.recover();
    expect(state.lookups).toEqual(['a:unconsumed', 'a:missing-pending']);
    expect(state.frames).toEqual([]);
  } finally { await product.stop(); store.close(); }
});

it('retains final evidence across database upgrade and restart while retrying an unconfirmed receipt', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-input-recovery-'));
  const path = join(directory, 'node.sqlite3');
  // Recreate the deployed inputs schema: its existing terminal is not a finality marker.
  const legacy = new DatabaseSync(path);
  legacy.exec(`CREATE TABLE inputs (input_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id),
    relay_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, accepted INTEGER NOT NULL DEFAULT 0, turn INTEGER, terminal TEXT)`);
  legacy.close();
  let store = new NodeStore(path, 'owner');
  store.bind(binding);
  const id = store.receive('s', input('one'));
  store.inputEvidence(id, completed(1));
  let current = harness(store);
  try {
    current.state.evidence.set(id, completed(1));
    current.state.events = [
      { seq: 1, time: 1, type: 'assistant/message', data: { turn: 1, message: { id: 'answer', content: [{ type: 'text', text: 'done' }] } } },
      { seq: 2, time: 2, type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
    ];
    current.state.failReceipt = true;
    await expect(current.product.recover()).rejects.toThrow('receipt offline');
    expect(current.state.lookups).toEqual([id]);
    expect(current.state.frames.filter(frame => frame.kind === 'message_completed')).toHaveLength(1);
    await current.product.stop(); store.close();
    store = new NodeStore(path, 'owner');
    current = harness(store);
    await current.product.recover();
    await current.product.recover();
    expect(current.state.lookups).toEqual([]);
    expect(current.state.frames).toEqual([expect.objectContaining({ type: 'node.delivery_receipt', delivery_status: 'completed' })]);
    expect(store.receipt(id)).toBe('completed');
    expect(store.prepareDelivery('s', 1)).toMatchObject({ state: 'confirmed', content: 'done' });
  } finally { await current.product.stop(); store.close(); await rm(directory, { recursive: true, force: true }); }
});

it('preserves logical terminal evidence when a later observe replays the failed physical attempt', async () => {
  const store = new NodeStore(':memory:', 'owner');
  store.bind(binding);
  const id = store.receive('s', input('fallback'));
  store.accepted(id);
  const delivery = store.prepareDelivery('s', 1);
  store.updateDelivery(delivery.operationId, 'confirmed', 'reply', 'done');
  store.confirmReceipt(id, 'completed');
  const { state, product } = harness(store);
  try {
    // Lookup can see the completed logical run after observe took its empty snapshot.
    state.evidence.set(id, completed(1));
    await product.recover();
    state.lookups.length = 0;
    state.runs = [{ id: 'logical', sessionId: 's', turn: 1, state: 'completed', terminal: { kind: 'completed' },
      attempts: [{ turn: 1, route: { provider: 'p', model: 'primary' } }, { turn: 2, route: { provider: 'p', model: 'backup' } }] }];
    state.events = [{ seq: 1, time: 1, type: 'turn/end', data: { turn: 1, reason: { kind: 'error' } } },
      { seq: 2, time: 2, type: 'turn/end', data: { turn: 2, reason: { kind: 'completed' } } }];
    await product.recover();
    expect(state.lookups).toEqual([]);
    expect(JSON.parse(store.inputs('s')[0]!.terminal!)).toEqual({ kind: 'completed' });
    expect(store.events('s')).toHaveLength(2);
    expect(state.frames).toEqual([]);
  } finally { await product.stop(); store.close(); }
});

it.each(['running', 'switching'] as const)('does not settle newer lookup evidence against an older %s model run', async runState => {
  const store = new NodeStore(':memory:', 'owner');
  store.bind(binding);
  const id = store.receive('s', input('late'));
  store.accepted(id);
  const delivery = store.prepareDelivery('s', 1);
  store.updateDelivery(delivery.operationId, 'confirmed', 'reply', 'done');
  store.confirmReceipt(id, 'completed');
  const { state, product } = harness(store);
  try {
    state.evidence.set(id, completed(1));
    state.runs = [{ id: 'logical', sessionId: 's', turn: 1, state: runState,
      attempts: [{ turn: 1, route: { provider: 'p', model: 'm' } }] }];
    await product.recover();
    await product.recover();
    expect(state.lookups).toEqual([id, id]);
    state.runs[0]!.state = 'completed';
    state.runs[0]!.terminal = { kind: 'completed' };
    await product.recover();
    state.lookups.length = 0;
    await product.recover();
    expect(state.lookups).toEqual([]);
  } finally { await product.stop(); store.close(); }
});

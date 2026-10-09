import { expect, it } from 'vitest';
import type { RelayInput, RuntimeEvent } from '@nano/product-contracts';
import { NodeStore } from '../src/store.js';
import { SingleThread } from '../src/single-thread.js';

it('parks group background without starting runtime, admits it on mention, and suppresses silent replies', async () => {
  const store = new NodeStore(':memory:', 'owner');
  const submitted: Record<string, unknown>[] = []; const frames: Record<string, unknown>[] = [];
  let ensured = 0; let events: RuntimeEvent[] = [];
  let notify: (method: string, value: unknown) => void = () => {};
  const product = new SingleThread({ nodeId: 'node', ownerId: 'owner', store,
    agents: [{ agentId: 'a', revision: '1', mode: 'single_thread', provider: 'test', model: 'test', workspace: '/tmp' }],
    runtime: { onNotification(listener) { notify = listener; return () => {}; }, async request(method, value) {
      const args = value as Record<string, unknown>;
      if (method === 'session.ensure') ensured++;
      if (method === 'session.submit') submitted.push(args);
      if (method === 'session.lookup') return { accepted: submitted.some(input => input.inputId === args.inputId), ...(submitted.some(input => input.mode === 'followup') ? { turn: 1 } : {}) };
      return { durable: true, events };
    } }, relay: { async request(_type, payload) { frames.push(payload); return { type: 'ack', payload: { message_id: 'bubble' } }; } },
    image: async () => '', onError: error => { throw error; },
  });
  const input = (id: string, mentioned = false): RelayInput => ({ agent_id: 'a', conversation_id: 'group', relay_task_id: id, idempotency_key: id,
    metadata: { conversation_type: 'group', mentioned_agent_ids: mentioned ? ['a'] : [] },
    message: { id, content: id, sender_user_id: 'human', sender_type: 'user', attachments: [] } });
  try {
    await product.receive(input('background'));
    expect(ensured).toBe(0); expect(submitted).toHaveLength(0);
    await product.recover(); expect(ensured).toBe(0);
    await product.receive(input('mention', true));
    expect(submitted.map(input => [input.inputId, input.mode])).toEqual([['a:background', 'inject'], ['a:mention', 'followup']]);
    await product.receive(input('mention', true)); expect(submitted).toHaveLength(2);
    const sessionId = store.bindingFor('a', 'group')!.sessionId;
    notify('session.stream', { sessionId, frame: { type: 'start', attemptId: 'attempt', turn: 1 } });
    notify('session.stream', { sessionId, frame: { type: 'chunk', attemptId: 'attempt', chunk: { type: 'text-delta', text: 'NO_' } } });
    events = [{ seq: 1, time: 1, type: 'assistant/message', data: { turn: 1, message: { id: 'answer', content: [{ type: 'text', text: 'NO_REPLY' }] } } },
      { seq: 2, time: 2, type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } }];
    await product.recover();
    expect(frames.some(frame => frame.kind === 'message_delta')).toBe(false);
    expect(frames.some(frame => frame.kind === 'message_completed' && frame.final_content === 'NO_REPLY')).toBe(false);
    expect(frames.filter(frame => frame.kind === 'message_discarded')).toHaveLength(1);
  } finally { await product.stop(); store.close(); }
});

it('withholds an internal group draft when an accepted correction is waiting and publishes the revised turn', async () => {
  const store = new NodeStore(':memory:', 'owner'); const frames: Record<string, unknown>[] = []; const submitted: Record<string, unknown>[] = [];
  let events: RuntimeEvent[] = []; let correctionConsumed = false;
  const product = new SingleThread({ nodeId: 'node', ownerId: 'owner', store,
    agents: [{ agentId: 'a', revision: '1', mode: 'single_thread', provider: 'test', model: 'test', workspace: '/tmp', groupReplyPolicy: 'always' }],
    runtime: { onNotification() { return () => {}; }, async request(method, value) {
      const args = value as Record<string, unknown>;
      if (method === 'session.submit') submitted.push(args);
      if (method === 'session.lookup') return { accepted: submitted.some(input => input.inputId === args.inputId), ...(args.inputId === 'a:first' ? { turn: 1 } : correctionConsumed ? { turn: 2 } : {}) };
      return { durable: true, events };
    } }, relay: { async request(_type, payload) { frames.push(payload); return { type: 'ack', payload: { message_id: String(payload.idempotency_key) } }; } }, image: async () => '', onError: () => {},
  });
  const input = (id: string): RelayInput => ({ agent_id: 'a', conversation_id: 'group', relay_task_id: id, idempotency_key: id, metadata: { conversation_type: 'group' }, message: { id, content: id, sender_type: 'user', sender_user_id: 'human', attachments: [] } });
  try {
    await product.receive(input('first'));
    events = [{ seq: 1, time: 1, type: 'assistant/message', data: { turn: 1, message: { id: 'draft', content: [{ type: 'text', text: 'Thursday' }] } } }, { seq: 2, time: 2, type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } }];
    await product.receive(input('correction'));
    expect(frames.some(frame => frame.kind === 'message_completed' && frame.final_content === 'Thursday')).toBe(false);
    expect(frames.some(frame => frame.kind === 'reply_process' && (frame.item as Record<string, unknown>).text === 'Thursday')).toBe(true);
    correctionConsumed = true;
    events.push({ seq: 3, time: 3, type: 'assistant/message', data: { turn: 2, message: { id: 'revised', content: [{ type: 'text', text: 'Friday' }] } } }, { seq: 4, time: 4, type: 'turn/end', data: { turn: 2, reason: { kind: 'completed' } } });
    await product.recover();
    expect(frames.some(frame => frame.kind === 'message_completed' && frame.final_content === 'Friday')).toBe(true);
  } finally { await product.stop(); store.close(); }
});

it('starts a fresh context for /new without submitting the command as a model prompt or resetting twice', async () => {
  const store = new NodeStore(':memory:', 'owner'); const submitted: string[] = []; const frames: Record<string, unknown>[] = [];
  const product = new SingleThread({ nodeId: 'node', ownerId: 'owner', store,
    agents: [{ agentId: 'a', revision: '2', mode: 'single_thread', provider: 'p', model: 'm', workspace: '/tmp' }],
    runtime: { onNotification: () => () => {}, async request(method, value) {
      if (method === 'session.submit') submitted.push((value as { inputId: string }).inputId);
      if (method === 'session.lookup') return { accepted: false };
      return { durable: true, events: [], wasRunning: false };
    } }, relay: { async request(_type, payload) { frames.push(payload); return { type: 'ack', payload: { message_id: 'reply' } }; } }, image: async () => '', onError: () => {},
  });
  const input = (id: string, content: string): RelayInput => ({ agent_id: 'a', conversation_id: 'c', relay_task_id: id, idempotency_key: id, metadata: { conversation_type: 'direct' }, message: { id, content, sender_type: 'user', sender_user_id: 'owner', attachments: [] } });
  try {
    await product.receive(input('before', 'remember old context')); const before = store.bindingFor('a', 'c')!;
    await product.receive(input('new', '/new')); const after = store.bindingFor('a', 'c')!;
    expect(after.sessionId).not.toBe(before.sessionId);
    expect(store.bindings().find(row => row.sessionId === before.sessionId)?.conversationId).toBe('c');
    await product.receive(input('new', '/new'));
    expect(store.bindingFor('a', 'c')?.sessionId).toBe(after.sessionId);
    expect(store.canonical('a')?.sessionId).toBe(after.sessionId);
    expect(submitted).toEqual(['a:before']);
    expect(frames.some(frame => frame.final_content === '已开始新会话。')).toBe(true);
  } finally { await product.stop(); store.close(); }
});

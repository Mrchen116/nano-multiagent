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

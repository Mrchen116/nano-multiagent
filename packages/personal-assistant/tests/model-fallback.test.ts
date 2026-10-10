import { expect, it } from 'vitest';
import type { ModelRunProjection, RelayInput, RuntimeEvent } from '@nano/product-contracts';
import { SingleThread } from '../src/single-thread.js';
import { NodeStore } from '../src/store.js';

it.each(['chat', 'owner:owner'])('keeps a failed attempt pending and delivers fallback notices/body to %s', async conversation => {
  const store = new NodeStore(':memory:', 'owner');
  const frames: Record<string, unknown>[] = [];
  let accepted = false;
  let events: RuntimeEvent[] = [];
  const runs: ModelRunProjection[] = [];
  const product = new SingleThread({
    nodeId: 'n',
    ownerId: 'owner',
    store,
    agents: [
      { agentId: 'a', revision: '1', mode: 'single_thread', provider: 'p', model: 'primary', workspace: '/tmp' },
    ],
    runtime: {
      onNotification() {
        return () => {};
      },
      async request(method) {
        if (method === 'session.submit') accepted = true;
        if (method === 'session.lookup')
          return { accepted, turn: 1, terminal: runs[0]?.state === 'completed' ? runs[0].terminal : undefined };
        return { durable: true, events, modelRuns: runs };
      },
    },
    relay: {
      async request(_type, payload) {
        if (payload.kind === 'turn_start' && conversation.startsWith('owner:') && !frames.some(frame => frame.kind === 'turn_start')) { expect(payload).toHaveProperty('to_user_id', 'owner'); expect(payload).not.toHaveProperty('conversation_id'); }
        if (payload.kind === 'turn_start') expect(payload.conversation_id ?? `owner:${payload.to_user_id}`).toBe(frames.some(frame => frame.kind === 'turn_start') ? 'chat' : conversation);
        frames.push(payload);
        return { type: 'ack', payload: { message_id: payload.idempotency_key, conversation_id: 'chat' } };
      },
    },
    image: async () => '',
    onError: (error) => {
      throw error;
    },
  });
  const input: RelayInput = {
    agent_id: 'a',
    conversation_id: conversation,
    relay_task_id: 'relay',
    idempotency_key: 'input',
    metadata: { conversation_type: 'direct' },
    message: { id: 'input', content: 'Do the task', sender_type: 'user', sender_user_id: 'owner', attachments: [] },
  };
  try {
    if (conversation.startsWith('owner:')) {
      const binding = await product.heartbeatBinding({agentId:'a',revision:'1',mode:'single_thread',provider:'p',model:'primary',workspace:'/tmp'});
      input.metadata.origin = 'heartbeat'; input.metadata.runtime_input_id = 'a:input'; store.receive(binding.sessionId, input); accepted = true;
    } else await product.receive(input);
    const sessionId = store.bindingFor('a', conversation)!.sessionId;
    runs.push({
      id: 'logical',
      sessionId,
      turn: 1,
      state: 'switching',
      attempts: [
        { turn: 1, route: { provider: 'p', model: 'primary' }, error: { code: 'AUTH', message: 'unavailable' } },
      ],
    });
    events = [
      {
        seq: 0,
        type: 'assistant/message',
        time: 1,
        data: {
          turn: 1,
          message: { id: 'failed', content: [] },
          usage: { inputTokens: 10, outputTokens: 0, cacheReadTokens: 5, totalTokens: 15 },
        },
      },
      { seq: 1, type: 'turn/end', time: 2, data: { turn: 1, reason: { kind: 'error' } } },
    ];
    expect(await product.modelCheck({ sessionId, turn: 1 })).toEqual({ published: false });
    expect(frames.filter((frame) => frame.delivery_status === 'failed').map((frame) => frame.kind)).toEqual([
      'message_completed',
    ]);
    expect(frames.filter((frame) => frame.relay_task_id === 'relay').map((frame) => frame.delivery_status)).toEqual(conversation === 'chat' ? ['sent'] : []);
    runs[0]!.attempts.push({ turn: 2, route: { provider: 'p', model: 'backup' } });
    runs[0]!.state = 'completed';
    runs[0]!.terminal = { kind: 'completed' };
    runs[0]!.switched = 'backup';
    events.push(
      {
        seq: 2,
        type: 'assistant/message',
        time: 3,
        data: {
          turn: 2,
          message: { id: 'answer', content: [{ type: 'text', text: 'Completed original task' }] },
          usage: { inputTokens: 20, outputTokens: 3, cacheReadTokens: 7, totalTokens: 30 },
        },
      },
      { seq: 3, type: 'turn/end', time: 4, data: { turn: 2, reason: { kind: 'completed' } } },
    );
    await product.recover();
    await product.recover();
    const completed = frames.filter((frame) => frame.kind === 'message_completed');
    expect(completed.map((frame) => frame.final_content)).toEqual([
      'primary 暂时无法完成回复：unavailable',
      '已改用 backup，因为主模型不可用。',
      'Completed original task',
    ]);
    expect(completed.at(-1)?.token_usage).toMatchObject({
      context_used: 27,
      output: 3,
      total: 45,
      cache_read_tokens: 12,
      cache_total_input_tokens: 42,
    });
    expect(frames.filter((frame) => frame.relay_task_id === 'relay').map((frame) => frame.delivery_status)).toEqual(conversation === 'chat' ? ['sent', 'completed'] : []);
  } finally {
    await product.stop();
    store.close();
  }
});

it('waits for queued stream deltas before settling the complete native answer', async () => {
  const store = new NodeStore(':memory:', 'owner');
  const frames: Record<string, unknown>[] = [];
  let accepted = false;
  let events: RuntimeEvent[] = [];
  let notify: (method: string, value: unknown) => void = () => {};
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let deltaEntered = false;
  const product = new SingleThread({
    nodeId: 'n',
    ownerId: 'owner',
    store,
    agents: [{ agentId: 'a', revision: '1', mode: 'single_thread', provider: 'p', model: 'm', workspace: '/tmp' }],
    runtime: {
      onNotification(listener) {
        notify = listener;
        return () => {};
      },
      async request(method) {
        if (method === 'session.submit') accepted = true;
        if (method === 'session.lookup') return { accepted, turn: 1 };
        return { durable: true, events };
      },
    },
    relay: {
      async request(_type, payload) {
        if (payload.kind === 'message_delta') {
          deltaEntered = true;
          await gate;
        }
        frames.push(payload);
        return { type: 'ack', payload: { message_id: 'bubble' } };
      },
    },
    image: async () => '',
    onError: (error) => {
      throw error;
    },
  });
  try {
    await product.receive({
      agent_id: 'a',
      conversation_id: 'chat',
      relay_task_id: 'relay',
      idempotency_key: 'input',
      metadata: { conversation_type: 'direct' },
      message: { id: 'input', content: 'Reply fully', sender_type: 'user', sender_user_id: 'owner', attachments: [] },
    });
    const sessionId = store.bindingFor('a', 'chat')!.sessionId;
    notify('session.stream', { sessionId, frame: { type: 'start', attemptId: 'attempt', turn: 1 } });
    notify('session.stream', {
      sessionId,
      frame: { type: 'chunk', attemptId: 'attempt', index: 0, chunk: { type: 'text-delta', text: 'PART' } },
    });
    await expect.poll(() => deltaEntered).toBe(true);
    events = [
      {
        seq: 1,
        time: 1,
        type: 'assistant/message',
        data: { turn: 1, message: { id: 'answer', content: [{ type: 'text', text: 'PART_COMPLETE' }] } },
      },
      { seq: 2, time: 2, type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
    ];
    notify('session.stream', {
      sessionId,
      frame: { type: 'chunk', attemptId: 'attempt', index: 1, chunk: { type: 'text-delta', text: '_COMPLETE' } },
    });
    notify('session.stream', { sessionId, frame: { type: 'end', attemptId: 'attempt' } });
    await product.recover();
    expect(frames.some((frame) => frame.kind === 'message_completed')).toBe(false);
    release();
    await expect.poll(() => frames.filter((frame) => frame.kind === 'message_completed').length).toBe(1);
    expect(
      frames
        .filter((frame) => ['message_delta', 'message_completed'].includes(String(frame.kind)))
        .map((frame) => frame.delta_text ?? frame.final_content),
    ).toEqual(['PART', '_COMPLETE', 'PART_COMPLETE']);
  } finally {
    release();
    await product.stop();
    store.close();
  }
});

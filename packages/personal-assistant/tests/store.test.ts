import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { NodeStore } from '../src/store.js';
import { tokenUsage } from '../src/presentation.js';

it('recovers input attribution and confirmed delivery without creating a second send', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-node-store-'));
  const path = join(directory, 'node.sqlite3');
  const binding = { sessionId: 's1', conversationId: 'c1', agentId: 'a1', ownerId: 'o1', cwd: directory, revision: '1' };
  const input = { relay_task_id: 'r1', agent_id: 'a1', conversation_id: 'c1', idempotency_key: 'upstream1', metadata: {}, message: {
    id: 'm1', content: 'hello', sender_user_id: 'o1', sender_type: 'user', attachments: [],
  } };
  let store = new NodeStore(path, 'o1');
  try {
    store.bind(binding);
    const inputId = store.receive('s1', input);
    store.inputEvidence(inputId, { accepted: true, turn: 1, terminal: { kind: 'completed' } });
    const send = store.prepareDelivery('s1', 1);
    store.updateDelivery(send.operationId, 'confirmed', 'im-result', 'hello back');
    store.close();
    store = new NodeStore(path, 'o1');
    expect(store.receive('s1', input)).toBe(inputId);
    expect(store.inputs('s1')).toHaveLength(1);
    expect(store.inputForTurn('s1', 1)?.id).toBe(inputId);
    expect(store.prepareDelivery('s1', 1)).toMatchObject({ operationId: send.operationId, state: 'confirmed', messageId: 'im-result' });
    expect(() => new NodeStore(path, 'another-owner')).toThrow('different owner');
  } finally { store.close(); await rm(directory, { recursive: true, force: true }); }
});

it('adds cache buckets to uncached input once and keeps unknown cache fields absent', () => {
  const event = (seq: number, type: string, data: Record<string, unknown>) => ({ seq, type, time: seq, data });
  expect(tokenUsage([
    event(0, 'request/context', { contextWindow: 1000 }),
    event(1, 'assistant/message', { turn: 1, usage: { inputTokens: 10, cacheReadTokens: 20, cacheWriteTokens: 5, outputTokens: 3, totalTokens: 38 } }),
    event(2, 'request/context', { contextWindow: 2000 }),
  ], 1)).toEqual({ context_used: 35, output: 3, total: 38, cache_read_tokens: 20, cache_total_input_tokens: 35, context_window: 1000 });
  expect(tokenUsage([event(0, 'assistant/message', { turn: 2, usage: { inputTokens: 10, outputTokens: 3 } })], 2)).toEqual({ context_used: 10, output: 3 });
});

it('projects native schedule admission with its original message identity across replay', () => {
  const store = new NodeStore(':memory:', 'o');
  store.bind({ sessionId: 's', conversationId: 'chat', agentId: 'a', ownerId: 'o', cwd: '/tmp', revision: '1' });
  const message = { id: 'native-schedule-id', content: [{ type: 'text', text: 'reminder' }], source: { kind: 'schedule' } };
  const events = [{ seq: 1, time: 1, type: 'agent/inbox/spliced', data: { inserted: [message] } }];
  try {
    store.recordEvents('s', events); store.recordEvents('s', events);
    expect(store.inputs('s')).toHaveLength(1);
    expect(store.inputs('s')[0]).toMatchObject({ id: message.id, accepted: true,
      input: { conversation_id: 'chat', metadata: { runtime_input_id: message.id, origin: 'schedule' } } });
  } finally { store.close(); }
});

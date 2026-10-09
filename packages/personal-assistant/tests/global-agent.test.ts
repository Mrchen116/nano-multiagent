import { expect, it } from 'vitest';
import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';
import { GlobalAgent, type ProductCall } from '../src/global-agent.js';
import type { RelayInput } from '@nano/product-contracts';

it('holds a group draft when a correction arrives before dispatch and keeps tool identity idempotent', async () => {
  const store = new NodeStore(':memory:', 'owner'); const inbox = new InboxStore(':memory:');
  const binding = store.bind({ agentId: 'alice', sessionId: 'main', conversationId: 'global:alice', ownerId: 'owner', cwd: '/tmp/alice', revision: '1' });
  let sent = 0;
  const input: RelayInput = { agent_id: 'alice', conversation_id: 'c_group', relay_task_id: 'relay', idempotency_key: 'correction', metadata: { conversation_type: 'group' }, message: { id: 'correction', content: 'Change the date', sender_type: 'user', sender_user_id: 'human', attachments: [] } };
  const product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [{ agentId: 'alice', workspace: '/tmp/alice', revision: '1', provider: 'test', model: 'test', mode: 'global' }], store, inbox,
    runtime: { onNotification: () => () => {}, request: async () => ({ events: [], durable: true, status: 'idle' }) },
    relay: { request: async (type, payload) => {
      if (type === 'agent.work.append') return { type: 'agent.work.ack', payload: { through_seq: (payload.events as { seq: number }[]).at(-1)!.seq } };
      if (type === 'conversation.query') { inbox.receive(input, true); return { type: 'conversation.query.result', payload: { ok: true, result: { type: 'group', channel: 'web', name: 'Group' } } }; }
      if (type === 'agent.message') sent++;
      return { type: 'ack', payload: { message_id: 'sent-message', conversation_id: 'c_group' } };
    } }, image: async () => '', onError: error => { throw error; },
  });
  const call: ProductCall = { method: 'send_message', args: { target: 'c_group', text: 'old draft' }, operationId: 'main:call', callId: 'call', sessionId: binding.sessionId, rootSessionId: binding.sessionId, agentId: 'alice', ownerId: 'owner' };
  try {
    expect(await product.call(call)).toMatchObject({ status: 'held_for_revalidation' });
    expect(sent).toBe(0);
    const page = inbox.read('alice', 'main', 'read', { target: 'c_group' });
    inbox.commitRead('main', 'read', [{ type: 'text', text: JSON.stringify(page) }], false);
    expect(await product.call(call)).toMatchObject({ status: 'held_for_revalidation' });
    expect(sent).toBe(0);
    expect(await product.call({ ...call, operationId: 'main:reconsidered', callId: 'reconsidered', args: { target: 'c_group', text: 'new draft' } })).toMatchObject({ status: 'sent' });
    expect(sent).toBe(1);
    await expect(product.call({ ...call, agentId: 'bob' })).rejects.toThrow('identity');
    await expect(product.call({ ...call, method: 'inbox', sessionId: 'child', args: { action: 'check' } })).rejects.toThrow('main Agent');
  } finally { await product.stop(); inbox.close(); store.close(); }
});

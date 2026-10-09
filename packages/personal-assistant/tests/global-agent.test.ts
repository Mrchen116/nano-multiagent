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
    runtime: { onNotification: () => () => {}, request: async method => method === 'session.descendants' ? [] : ({ events: [], durable: true, status: 'idle' }) },
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

it('projects durable native child lineage and drafts into Work without a public send', async () => {
  const store = new NodeStore(':memory:', 'owner'); const inbox = new InboxStore(':memory:'); let sends = 0;
  const childEvents = [
    { seq: 1, time: 1, type: 'turn/start', data: { turn: 1 } },
    { seq: 2, time: 2, type: 'user/message', data: { source: { kind: 'subagent' } } },
    { seq: 3, time: 3, type: 'assistant/message', data: { turn: 1, message: { id: 'draft', content: [{ type: 'text', text: 'private child draft' }] } } },
    { seq: 4, time: 4, type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
  ];
  const product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [{ agentId: 'alice', workspace: '/tmp/alice', revision: '1', provider: 'test', model: 'test', mode: 'global' }], store, inbox,
    runtime: { onNotification: () => () => {}, async request(method, value) {
      if (method === 'session.descendants') return [{ kind: 'child', id: 'child', parentId: (value as { sessionId: string }).sessionId, label: 'Research', events: childEvents, throughSeq: 4 }];
      return { events: [], durable: true, status: 'idle' };
    } }, relay: { ready: false, async request() { sends++; return { type: 'ack', payload: {} }; } }, image: async () => '', onError: () => {},
  });
  try {
    await product.recover(); await product.recover();
    const events = inbox.journal(0);
    expect(events.filter(event => event.session_id === 'child' && event.type === 'session_registered')).toEqual([expect.objectContaining({ payload: expect.objectContaining({ scope: 'subagent', child_agent_id: 'child', title: 'Research' }) })]);
    expect(events.filter(event => event.session_id === 'child' && event.type === 'message')).toHaveLength(1);
    expect(events.some(event => event.type === 'message_sent')).toBe(false); expect(sends).toBe(0);
  } finally { await product.stop(); inbox.close(); store.close(); }
});

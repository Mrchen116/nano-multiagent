import { expect, it } from 'vitest';
import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';
import { GlobalAgent } from '../src/global-agent.js';
import { projectWorkEvent } from '../src/work-projection.js';
import type { RuntimeEvent } from '@nano/product-contracts';

it.each([
  { source: { kind: 'user', actorId: 'owner', channel: 'web', messageId: 'native' }, messageId: 'native', trigger: 'human' },
  { source: { kind: 'nano-human', actorId: 'owner', channel: 'web', messageId: 'legacy' }, messageId: 'legacy', trigger: 'human' },
  { source: { kind: 'user' }, messageId: null, trigger: 'inbox' },
  { source: { kind: 'user', messageId: 'unattested' }, messageId: null, trigger: 'inbox' },
  { source: { kind: 'nano-system', actorId: 'owner', channel: 'heartbeat', messageId: 'wake' }, messageId: null, trigger: 'heartbeat' },
  { source: { kind: 'schedule' }, messageId: null, trigger: 'cron' },
  { source: { kind: 'agent-message', senderSessionId: 'peer' }, messageId: null, trigger: 'background_task' },
])('preserves $source.kind provenance in task linkage and work views', async ({ source, messageId, trigger }) => {
  const store = new NodeStore(':memory:', 'owner'); const inbox = new InboxStore(':memory:');
  const binding = store.bind({ agentId: 'a', sessionId: 'main', conversationId: 'c_chat', ownerId: 'owner', cwd: '/tmp', revision: '1' });
  const events: RuntimeEvent[] = [
    { type: 'turn/start', seq: 0, time: 1, data: { turn: 1 } },
    { type: 'user/message', seq: 1, time: 2, data: { id: 'input', content: [{ type: 'text', text: 'A request' }], source } },
  ];
  const sent: Record<string, unknown>[] = [];
  const product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [{ agentId: 'a', workspace: '/tmp', revision: '1', provider: 'p', model: 'm', mode: 'single_thread' }], store, inbox,
    runtime: { onNotification: () => () => {}, request: async () => ({ events, durable: true, status: 'idle' }) },
    relay: { request: async (type, payload) => { if (type === 'task_graph.command') sent.push(payload); return { type: 'ack', payload: { ok: true, result: {} } }; } },
    image: async () => '', onError: error => { throw error; } });
  try {
    await product.call({ method: 'task_graph', args: { action: 'create', title: 'Task', request_key: 'create' }, operationId: 'main:create', callId: 'create', sessionId: binding.sessionId, rootSessionId: binding.sessionId, agentId: 'a', ownerId: 'owner' });
    expect(sent).toHaveLength(1);
    expect(sent[0]?.source_message_id).toBe(messageId);
    expect(projectWorkEvent('main', events[0]!, events)?.payload.trigger).toMatchObject({ kind: trigger, source });
    expect(projectWorkEvent('child', events[0]!, events, true)?.payload.trigger).toMatchObject({ kind: 'background_task' });
  } finally { await product.stop(); inbox.close(); store.close(); }
});

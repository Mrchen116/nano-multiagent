import { expect, it } from 'vitest';
import { ExternalChannels } from '../src/external.js';
import { NodeStore } from '../src/store.js';
import type { RelayInput } from '@nano/product-contracts';

it('keeps external execution and confirmed sends available offline and does not resend on replay', async () => {
  const store = new NodeStore(':memory:', 'owner'); let sends = 0;
  const accepted: RelayInput[] = []; let online = false; const mirrored: Record<string, unknown>[] = []; const requests: unknown[] = [];
  const external = new ExternalChannels(':memory:', { nodeId: 'node', ownerId: 'owner', store,
    relay: { get ready() { return online; }, async request(_type, payload) { mirrored.push(payload); return { type: 'ack', payload: { message_id: 'im-bubble' } }; } },
    im: async (path, options) => { if (!online) throw new Error('offline'); requests.push(JSON.parse(String(options?.body))); return { id: path.endsWith('find-or-create') ? 'shadow-chat' : 'shadow-input' }; }, receive: async input => { accepted.push(input); }, permission: async () => {}, onError: () => {},
  });
  external.add('a', { config: { appId: 'app', botOpenId: 'bot', ownerOpenId: 'human' }, async send() { sends++; return 'platform-result'; }, async thinking() { return undefined; }, async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; }, async updateCard() {} });
  const message = { messageId: 'source', chatId: 'chat', senderId: 'human', isGroup: false, mentioned: false, time: '1000', parts: [{ type: 'text' as const, text: 'hello' }] };
  try {
    await external.receive('a', message); await external.receive('a', message);
    expect(accepted).toHaveLength(1);
    const input = accepted[0]!;
    expect(input.message.sender_user_id).toBe('human');
    const start = await external.request('node.streaming_delta', { node_id: 'node', kind: 'turn_start', agent_id: 'a', conversation_id: input.conversation_id, idempotency_key: 'turn', external_reply: input.metadata.external_reply });
    const complete = { kind: 'message_completed', message_id: start.payload.message_id, final_content: 'answer', delivery_status: 'completed' };
    await external.request('node.streaming_delta', complete); await external.request('node.streaming_delta', complete);
    expect(sends).toBe(1);
    const imStart = await external.request('node.streaming_delta', { kind: 'turn_start', agent_id: 'a', conversation_id: input.conversation_id, idempotency_key: 'im-triggered' });
    await external.request('node.streaming_delta', { ...complete, message_id: imStart.payload.message_id });
    expect(sends).toBe(1);
    store.bind({ agentId: 'a', sessionId: 'session', conversationId: input.conversation_id, ownerId: 'owner', cwd: '/tmp', revision: '1' });
    online = true; await external.recover(); await external.recover();
    expect(sends).toBe(1);
    expect(store.bindingFor('a', 'shadow-chat')?.sessionId).toBe('session');
    expect(mirrored.filter(frame => frame.kind === 'turn_start')).toHaveLength(2);
    expect(mirrored.filter(frame => frame.kind === 'message_completed')).toHaveLength(2);
    expect(requests).toContainEqual(expect.objectContaining({ sender_source_id: 'human', suppress_relay: true }));
  } finally { await external.stop(); store.close(); }
});

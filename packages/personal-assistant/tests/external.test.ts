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
    const notice = { conversation_id: input.conversation_id, idempotency_key: 'knowledge-review', text: 'skills updated', system_notice: { source_agent_id: 'a', kind: 'self_evolution_review', updated_targets: ['skills'] } };
    await external.request('node.system_message', notice); await external.request('node.system_message', notice);
    expect(sends).toBe(2);
    store.bind({ agentId: 'a', sessionId: 'session', conversationId: input.conversation_id, ownerId: 'owner', cwd: '/tmp', revision: '1' });
    online = true; await external.recover(); await external.recover();
    expect(sends).toBe(2);
    expect(mirrored.filter(frame => frame.system_notice)).toHaveLength(1);
    expect(store.bindingFor('a', 'shadow-chat')?.sessionId).toBe('session');
    expect(mirrored.filter(frame => frame.kind === 'turn_start')).toHaveLength(2);
    expect(mirrored.filter(frame => frame.kind === 'message_completed')).toHaveLength(2);
    await external.request('node.system_message', { ...notice, conversation_id: 'shadow-chat', idempotency_key: 'internal-review' });
    expect(sends).toBe(2);
    expect(requests).toContainEqual(expect.objectContaining({ sender_source_id: 'human', suppress_relay: true }));
  } finally { await external.stop(); store.close(); }
});

it('keeps group approval values private and accepts only the bound owner on the actual card', async () => {
  const store = new NodeStore(':memory:', 'owner'); const inputs: RelayInput[] = []; let decisions = 0; let card: unknown;
  const external = new ExternalChannels(':memory:', { nodeId: 'node', ownerId: 'owner', store,
    relay: { ready: false, async request() { throw new Error('offline'); } }, im: async () => { throw new Error('offline'); },
    receive: async input => { inputs.push(input); }, permission: async () => { decisions++; }, onError: () => {},
  });
  external.add('a', { config: { appId: 'app', botOpenId: 'bot', ownerOpenId: 'owner-openid' }, async send(_chat, _text, _key, payload) { card = payload; return 'card'; }, async thinking() { return undefined; }, async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; }, async updateCard() {} });
  try {
    await external.receive('a', { messageId: 'group-input', chatId: 'group', senderId: 'member', isGroup: true, mentioned: true, time: '1000', parts: [{ type: 'text', text: 'request' }] });
    const input = inputs[0]!;
    const start = await external.request('node.streaming_delta', { kind: 'turn_start', agent_id: 'a', conversation_id: input.conversation_id, idempotency_key: 'turn', external_reply: input.metadata.external_reply });
    await external.request('node.streaming_delta', { kind: 'permission_request', message_id: start.payload.message_id, permission_request: { request_id: 'request', tool_name: 'bash', reason: 'private-owner-data', tool_input: { command: 'private-owner-data' } } });
    expect(JSON.stringify(card)).not.toContain('private-owner-data');
    const action = { context: { open_message_id: 'card' }, action: { value: { request_id: 'request', decision: 'allow_once' } } };
    await external.card('a', { ...action, operator: { open_id: 'member' } }); expect(decisions).toBe(0);
    await external.card('a', { ...action, operator: { open_id: 'owner-openid' } }); expect(decisions).toBe(1);
    await external.card('a', { ...action, operator: { open_id: 'owner-openid' } }); expect(decisions).toBe(1);
  } finally { await external.stop(); store.close(); }
});

it('never reports completed before the platform response and preserves unknown outcomes across restart', async () => {
  const { mkdtemp, rm } = await import('node:fs/promises'); const { tmpdir } = await import('node:os'); const { join } = await import('node:path');
  const directory = await mkdtemp(join(tmpdir(), 'nano-external-')); const path = join(directory, 'external.sqlite3');
  const store = new NodeStore(':memory:', 'owner'); const accepted: RelayInput[] = []; const frames: Record<string, unknown>[] = [];
  let sends = 0; let rejectSend: (error: Error) => void = () => {};
  const options = { nodeId: 'node', ownerId: 'owner', store,
    relay: { ready: true, async request(_type: string, payload: Record<string, unknown>) { frames.push(payload); return { type: 'ack', payload: { message_id: 'mirror' } }; } },
    im: async (path: string) => ({ id: path.endsWith('find-or-create') ? 'shadow' : 'input' }), receive: async (input: RelayInput) => { accepted.push(input); }, permission: async () => {}, onError: () => {},
  };
  const connection = { config: { appId: 'app', botOpenId: 'bot' }, send() { sends++; return new Promise<string>((_resolve, reject) => { rejectSend = reject; }); }, async thinking() { return undefined; }, async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; }, async updateCard() {} };
  let external = new ExternalChannels(path, options); external.add('a', connection);
  try {
    await external.receive('a', { messageId: 'source', chatId: 'chat', senderId: 'human', isGroup: false, mentioned: false, time: '1000', parts: [{ type: 'text', text: 'hello' }] });
    const input = accepted[0]!;
    const start = await external.request('node.streaming_delta', { kind: 'turn_start', agent_id: 'a', conversation_id: input.conversation_id, idempotency_key: 'turn', external_reply: input.metadata.external_reply });
    const complete = { kind: 'message_completed', message_id: start.payload.message_id, final_content: 'answer', delivery_status: 'completed' };
    const pending = external.request('node.streaming_delta', complete); const rejected = expect(pending).rejects.toMatchObject({ delivery: 'unknown' });
    await external.recover(); expect(frames.some(frame => frame.kind === 'message_completed')).toBe(false);
    rejectSend(new Error('platform connection lost after send')); await rejected;
    await external.recover();
    expect(frames.filter(frame => frame.kind === 'message_completed')).toEqual([expect.objectContaining({ delivery_status: 'failed', external_delivery_status: 'unknown' })]);
    await external.stop(); external = new ExternalChannels(path, options); external.add('a', connection);
    await expect(external.request('node.streaming_delta', complete)).rejects.toMatchObject({ delivery: 'unknown' });
    expect(sends).toBe(1);
  } finally { await external.stop(); store.close(); await rm(directory, { recursive: true, force: true }); }
});

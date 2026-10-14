import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import type { RelayInput, RuntimeEvent } from '@nano/product-contracts';
import { GlobalAgent, type ProductCall } from '../src/global-agent.js';
import { InboxStore } from '../src/inbox.js';
import { NodeStore } from '../src/store.js';

const external = 'external:personal-agent:feishu:cli_a449d9dfb789cd8:dm:ou_2c73e759316310c16a2ddf99fdec10ff';
const runtime = { onNotification: () => () => {}, request: async (method: string) => method === 'session.descendants' ? [] : { events: [], durable: true, status: 'idle' } };
const base: ProductCall = { method: '', args: {}, agentId: 'alice', ownerId: 'owner', sessionId: 'main', rootSessionId: 'main', callId: '', operationId: '' };
const call = (product: GlobalAgent, method: string, args: Record<string, unknown>, id = method) => product.call({ ...base, method, args, callId: id, operationId: `main:${id}` }) as Promise<any>;
const message = (id: string): RelayInput => ({ agent_id: 'alice', conversation_id: external, relay_task_id: id, idempotency_key: id,
  metadata: { conversation_type: 'direct' }, message: { id, content: id, sender_type: 'user', sender_user_id: 'owner', attachments: [] },
});

it('keeps compact Feishu targets and frozen Inbox pages valid after restart, with canonical approval, images and delivery', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'nano-tool-references-'));
  let store: NodeStore, inbox: InboxStore, product: GlobalAgent;
  let sent = 0;
  let events: RuntimeEvent[] = [];
  const open = () => {
    store = new NodeStore(join(dir, 'node.sqlite3'), 'owner'); inbox = new InboxStore(join(dir, 'inbox.sqlite3'));
    for (const [agentId, sessionId] of [['alice', 'main'], ['bob', 'other']]) store.bind({ agentId, sessionId, ownerId: 'owner', conversationId: `global:${agentId}`, cwd: dir, revision: '1' });
    store.aliasConversation('alice', 'c_shadow', external);
    product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', store, inbox, runtime: { ...runtime,
      request: async method => method === 'session.descendants' ? [] : { events, durable: true, status: 'idle' },
    },
      agents: [{ agentId: 'alice', workspace: dir, revision: '1', provider: 'test', model: 'test', mode: 'global' }],
      relay: { async request(type, payload) {
        if (type === 'agent.work.append') return { type: 'ack', payload: { through_seq: (payload.events as any[]).at(-1).seq } };
        if (type === 'conversation.query') {
          const info = { target: external, id: external, type: 'direct', channel: 'feishu', owner_recipient: true, name: 'Owner' };
          if (payload.action === 'describe') return { type: 'result', payload: { ok: true, result: { conversations: [info] } } };
          expect(payload.target).toBe(external);
          return { type: 'result', payload: { ok: true, result: info } };
        }
        if (type === 'task_graph.command') {
          expect(payload.args).toMatchObject({ conversation_id: 'c_shadow' });
          return { type: 'result', payload: { ok: true, result: { graph_id: 'tg_12345678' } } };
        }
        expect(type).toBe('agent.message'); expect(payload.to).toBe(`conversation:${external}`); sent++;
        return { type: 'ack', payload: { message_id: 'sent-1', conversation_id: external } };
      } }, image: async () => 'image-bytes', onError: error => { throw error; },
    });
  };
  const close = async () => { await product.stop(); inbox.close(); store.close(); };
  open();
  try {
    const photo = message('first'); photo.message.attachments.push({ url: 'private-photo', content_type: 'image/png' });
    inbox.receive(photo, true); inbox.receive(message('second'), true);
    const target = (await call(product, 'inbox', { action: 'check' })).sources[0].target;
    expect(target).toMatch(/^c_f_[a-f0-9]{8}$/);
    const first = await call(product, 'inbox', { action: 'read', target, limit: 1 }, 'first');
    expect(first).toMatchObject({ target, messages: [{ id: 'first' }] });
    expect(first.messages[0]).not.toHaveProperty('target');
    expect(first.next_cursor).toMatch(/^p_[a-f0-9]{8}$/);
    expect(inbox.commitRead('main', 'first', [{ type: 'text', text: 'truncated' }], false)).toBe(false);
    expect(inbox.commitRead('main', 'first', [{ type: 'text', text: JSON.stringify(first) }], false, 1)).toBe(true);
    await close(); open();
    expect((await call(product, 'inbox', { action: 'check' })).sources[0].target).toBe(target);
    expect(await call(product, 'inbox', { action: 'read', target, limit: 1 }, 'first')).toEqual(first);
    const page = await call(product, 'inbox', { action: 'read', target, cursor: first.next_cursor, limit: 1 }, 'photo');
    const image = await call(product, 'inbox.image', { url: 'private-photo' }, 'photo');
    expect(image.source).toEqual({ kind: 'chat', conversationId: external, messageId: 'first', url: 'private-photo' });
    const content = [{ type: 'text', text: JSON.stringify(page) }, { type: 'image', attachment: { attachmentId: 'image' } }];
    await call(product, 'inbox.prepare', { content }, 'photo');
    expect(inbox.commitRead('main', 'photo', content, false, 1)).toBe(true);
    events = [{ seq: 1, time: 1, type: 'tool/result', data: { turn: 1, message: { toolCallId: 'photo', content, isError: false } } }];
    inbox.receive(message('later'), true);
    const last = await call(product, 'inbox', { action: 'read', target, cursor: page.next_cursor }, 'last');
    expect(last.messages.map((item: any) => item.id)).toEqual(['second']);
    expect(inbox.commitRead('main', 'last', [{ type: 'text', text: JSON.stringify(last) }], false, 1)).toBe(true);
    expect(await call(product, 'send_message', { target, text: 'draft' }, 'draft')).toMatchObject({ status: 'held_for_revalidation', target, inbox_targets: [target] });
    expect(sent).toBe(0);
    expect(inbox.journal(0).find(event => event.type === 'inbox_read_committed')).toMatchObject({
      payload: { source_refs: [{ conversation_id: external, message_id: 'first' }] },
    });
    const correction = await call(product, 'inbox', { action: 'read', target }, 'correction');
    expect(inbox.commitRead('main', 'correction', [{ type: 'text', text: JSON.stringify(correction) }], false, 1)).toBe(true);
    expect(await call(product, 'send_message.context', { target })).toMatchObject({ target: external, channel: 'feishu', recipient: { kind: 'owner' } });
    expect(await call(product, 'conversations', { action: 'info', target })).toMatchObject({ target, name: 'Owner' });
    expect(await call(product, 'task_graph', { action: 'create', target, title: 'Plan', mode: 'dag', request_key: 'plan' })).toMatchObject({ ok: true });
    const sentResult = await call(product, 'send_message', { target, text: 'done' }, 'send');
    expect(sentResult).toEqual({ status: 'sent', target, message_id: 'sent-1' });
    expect(await call(product, 'send_message', { target: external, text: 'done' }, 'send')).toEqual(sentResult);
    expect(sent).toBe(1);
    for (const args of [{ action: 'info', target }, { action: 'list', cursor: first.next_cursor }]) {
      await expect(product.call({ ...base, agentId: 'bob', sessionId: 'other', rootSessionId: 'other', method: 'conversations', args })).rejects.toThrow('scope');
    }
  } finally { await close(); rmSync(dir, { recursive: true }); }
});

it.each(['conversations', 'task_graph'])('round-trips %s pagination without exposing its opaque state or changing native schedule IDs', async method => {
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  store.bind({ agentId: 'alice', sessionId: 'main', ownerId: 'owner', conversationId: 'global:alice', cwd: '/tmp', revision: '1' });
  const legacy = Buffer.from(JSON.stringify({ snapshot: '00000000-0000-4000-8000-000000000000', offset: 20 })).toString('base64url');
  const observed: Record<string, unknown>[] = [];
  const product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [], store, inbox, runtime,
    relay: { async request(type, payload) {
      const args = type === 'task_graph.command' ? payload.args as Record<string, unknown> : payload;
      observed.push(args);
      return { type: 'result', payload: { ok: true, result: { items: [{ id: 'kept', content: { target: external, next_cursor: legacy } }], next_cursor: legacy } } };
    } }, image: async () => '', onError: error => { throw error; },
  });
  try {
    const unwrap = (result: any) => method === 'task_graph' ? result.result : result;
    const first = unwrap(await call(product, method, { action: 'list', query: 'hello' }));
    expect(first.next_cursor).toMatch(/^p_[a-f0-9]{8}$/);
    expect(first.items[0].content).toEqual({ target: external, next_cursor: legacy });
    expect(unwrap(await call(product, method, { action: 'list', query: 'hello', cursor: first.next_cursor })).next_cursor).toBe(first.next_cursor);
    expect(observed.at(-1)).toMatchObject({ cursor: legacy, query: 'hello' });
    await call(product, method, { action: 'list', query: 'hello', cursor: legacy });
    expect(observed.at(-1)).toMatchObject({ cursor: legacy });
    await expect(call(product, method === 'conversations' ? 'task_graph' : 'conversations', { action: 'list', cursor: first.next_cursor })).rejects.toThrow('scope');
    await expect(call(product, method, { action: 'list', cursor: 'p_unknown' })).rejects.toThrow('reference');
    const native = { id: 'schedule-00000000-0000-4000-8000-000000000000' };
    expect(store.toolReferences.arguments('alice', 'schedule.run', native)).toEqual(native);
    expect(store.toolReferences.result('alice', 'schedule.history', native)).toEqual(native);
  } finally { await product.stop(); inbox.close(); store.close(); }
});

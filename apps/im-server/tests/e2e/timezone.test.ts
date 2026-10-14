import { expect, it } from 'vitest';
import { once } from 'node:events';
import { start, bind, connect } from './helpers.js';
import { InboxStore } from '../../../../packages/personal-assistant/src/inbox.js';
import { formatLocalTime } from '@nano/product-contracts';

it('persists foreground timezone, pushes it to Gateways, and freezes each relayed message timezone', async () => {
  const f = await start();
  const g = await bind(f);
  const set = (timezone: string) => f.http('PATCH', '/im/v1/me/timezone', { timezone }, f.tokens.alice);
  expect((await set('Asia/Shanghai')).status).toBe(200);
  expect((await g.frames.next(frame => frame.type === 'user.timezone')).payload).toEqual({ timezone: 'Asia/Shanghai' });
  expect((await f.http('GET', '/im/v1/auth/me', undefined, f.tokens.alice)).body.timezone).toBe('Asia/Shanghai');
  const chat = await f.http('POST', '/im/v1/conversations', { title: 'Time', type: 'direct',
    participants: [{ type: 'agent', id: 'global' }] }, f.tokens.alice);
  expect(chat.status).toBe(201);
  const path = `/im/v1/conversations/${chat.body.id}/messages`;
  const first = await f.http('POST', path, { sender_user_id: 'alice', content: '早，今天有什么安排？', timezone: 'Asia/Shanghai' },
    f.tokens.alice, { 'Idempotency-Key': 'first-timezone' });
  expect(first.status).toBe(201);
  const relay = await g.frames.next(frame => frame.type === 'relay.message');
  expect(relay.payload.message.timezone).toBe('Asia/Shanghai');
  const inbox = new InboxStore(':memory:');
  try {
    inbox.receive(relay.payload, true);
    expect(inbox.read('global', 'main', 'read', { target: chat.body.id })).toMatchObject({
      messages: [{ time: formatLocalTime(first.body.created_at, 'Asia/Shanghai'), content: [{ text: first.body.content }] }],
    });
  } finally { inbox.close(); }
  const next = await f.http('POST', path, { sender_user_id: 'alice', content: '继续', timezone: 'Asia/Tokyo' }, f.tokens.alice);
  expect(next.status).toBe(201);
  expect((await g.frames.next(frame => frame.type === 'user.timezone')).payload.timezone).toBe('Asia/Tokyo');
  const retry = await f.http('POST', path, { sender_user_id: 'alice', content: first.body.content, timezone: 'Asia/Tokyo' },
    f.tokens.alice, { 'Idempotency-Key': 'first-timezone' });
  expect(retry.body.timezone).toBe('Asia/Shanghai');
  const history = await f.http('GET', path, undefined, f.tokens.alice);
  expect(history.body.items.find((item: any) => item.message?.id === first.body.id)?.message).toMatchObject({
    timezone: 'Asia/Shanghai', content: '早，今天有什么安排？', created_at: first.body.created_at,
  });
  expect((await set('invalid/timezone')).status).toBe(422);
  const closed = once(g.socket, 'close'); g.socket.terminate(); await closed;
  const reconnect = await connect(f, g.node, g.runtime);
  const ack = await reconnect.frames.send('node.register', { node_id: g.node, agents: ['assistant', 'global'] });
  expect(ack.payload.owner_timezone).toBe('Asia/Tokyo');
}, 30000);

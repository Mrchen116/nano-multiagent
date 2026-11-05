import Fastify from 'fastify';
import { afterEach, expect, it, vi } from 'vitest';
import { fixture, connectFixtureGateway } from './control-fixture.js';
import { Gateway } from '../src/gateway.js';
import { Messaging, registerMessagingRoutes } from '../src/messaging.js';
import { all, one } from '../src/context.js';

const apps: ReturnType<typeof Fastify>[] = [];
afterEach(async () => {
  for (const app of apps.splice(0)) await app.close();
});

/** Drive the real Gateway streaming path so discards share the production transaction. */
function setup() {
  const f = fixture();
  const ctx = f.ctx;
  ctx.messaging = new Messaging(ctx);
  const connection = connectFixtureGateway(f);
  ctx.gateway = new Gateway(ctx);
  const broadcast = vi.fn();
  ctx.gateway.broadcast = broadcast;
  ctx.gateway.register(connection, { node_id: 'n', agents: ['a'], capabilities: { agent_lifecycle_v1: 1 } });
  const app = Fastify();
  apps.push(app);
  registerMessagingRoutes(app, ctx);
  const read = (user: string) =>
    app.inject({ method: 'GET', url: '/im/v1/conversations/chat', headers: { 'x-user': user } });
  const markRead = (user: string, messageId: string) =>
    app.inject({
      method: 'POST',
      url: '/im/v1/conversations/chat/read',
      headers: { 'x-user': user },
      payload: { last_read_message_id: messageId },
    });
  const history = (user: string) =>
    app.inject({ method: 'GET', url: '/im/v1/conversations/chat/messages', headers: { 'x-user': user } });
  const start = (conversationId = 'chat') =>
    ctx.gateway.handle(connection, 'node.streaming_delta', {
      node_id: 'n',
      agent_id: 'a',
      conversation_id: conversationId,
      kind: 'turn_start',
      lifecycle_revision: 1,
    });
  const discard = (messageId: string, conversationId = 'chat') =>
    ctx.gateway.handle(connection, 'node.streaming_delta', {
      node_id: 'n',
      kind: 'message_discarded',
      message_id: messageId,
      conversation_id: conversationId,
      lifecycle_revision: 1,
      reason: 'no_reply',
    });
  const unread = (user: string) =>
    one(f.db, 'SELECT unread_count FROM conversation_participants WHERE conversation_id=? AND user_id=?', 'chat', user)
      ?.unread_count;
  return { ...f, ctx, connection, app, broadcast, read, markRead, history, start, discard, unread };
}

it('restores unread, preview and timestamp to the remaining message when a placeholder is discarded', async () => {
  const { db, ctx, broadcast, read, history, start, discard, unread } = setup();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
  // Another conversation must never be part of the rollback.
  db.prepare("INSERT INTO conversations(id,title,created_at) VALUES('other','Other',?)").run(new Date().toISOString());
  for (const user of ['u1', 'a1']) {
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('other',?)").run(user);
  }
  const other = ctx.messaging.insertMessage('other', 'a1', 'agent', 'other conversation reply');
  const earlier = ctx.messaging.insertMessage('chat', 'u1', 'user', 'earlier real reply');
  expect((await read('u1')).json()).toMatchObject({ unread_count: 0, last_message_preview: 'earlier real reply' });
  const placeholder = (await start()).payload.message_id;
  expect(await unread('u1')).toBe(1);
  expect(await unread('u2')).toBe(2);

  await discard(placeholder);

  expect((await read('u1')).json()).toMatchObject({
    unread_count: 0,
    last_message_preview: 'earlier real reply',
    last_message_at: earlier.created_at,
  });
  // u1 was read up to the end; u2 still owns one real unread; the Agent that wrote the placeholder gained none.
  expect(await unread('u1')).toBe(0);
  expect(await unread('u2')).toBe(1);
  expect(await unread('a1')).toBe(1);
  expect((await read('u1')).json().run_state).toBe('idle');
  // The row is gone and history does not resurrect it.
  expect(all(db, 'SELECT id FROM messages WHERE conversation_id=?', 'chat').map((row) => row.id)).toEqual([earlier.id]);
  const page = (await history('u1')).json();
  expect(page.items.map((item: any) => item.message?.id)).toEqual([earlier.id]);
  // The discard stays broadcast so online clients can still remove the bubble.
  expect(broadcast.mock.calls.map(([, frame]) => frame)).toContainEqual(
    expect.objectContaining({ event_type: 'message.discarded', data: expect.objectContaining({ message_id: placeholder, reason: 'no_reply' }) }),
  );
  // The unrelated conversation keeps its own projection.
  expect(one(db, 'SELECT last_message_preview,last_message_at FROM conversations WHERE id=?', 'other')).toMatchObject({
    last_message_preview: 'other conversation reply',
    last_message_at: other.created_at,
  });
  expect(one(db, 'SELECT unread_count FROM conversation_participants WHERE conversation_id=? AND user_id=?', 'other', 'u1')?.unread_count).toBe(1);
});

it('keeps the unread a reader already cleared and the unread of messages that arrived later', async () => {
  const { db, ctx, read, markRead, start, discard, unread } = setup();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
  ctx.messaging.insertMessage('chat', 'u1', 'user', 'earlier real reply');
  const placeholder = (await start()).payload.message_id;
  // u2 reads while the placeholder still exists, so the placeholder is no longer part of u2's unread.
  expect((await markRead('u2', placeholder)).json()).toMatchObject({ unread_count: 0, last_message_at: ctx.messaging.message(placeholder).created_at });
  ctx.messaging.insertMessage('chat', 'u1', 'user', 'later real reply');
  expect(await unread('u2')).toBe(1);

  await discard(placeholder);

  // Deleting an already-read placeholder must not consume the later real unread.
  expect(await unread('u2')).toBe(1);
  expect((await read('u2')).json()).toMatchObject({ last_message_preview: 'later real reply', unread_count: 1 });
});

it('returns to an empty projection when the placeholder was the only message in the conversation', async () => {
  const { db, start, discard, unread } = setup();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
  const placeholder = (await start()).payload.message_id;
  expect(await unread('u1')).toBe(1);

  await discard(placeholder);

  expect(one(db, 'SELECT last_message_preview,last_message_at FROM conversations WHERE id=?', 'chat')).toMatchObject({
    last_message_preview: null,
    last_message_at: null,
  });
  expect(await unread('u1')).toBe(0);
  expect(await unread('u2')).toBe(0);
  expect(all(db, 'SELECT id FROM messages WHERE conversation_id=?', 'chat')).toHaveLength(0);
});

it('does not roll back the projection twice when the same discard is replayed', async () => {
  const { db, ctx, broadcast, start, discard, unread } = setup();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
  const earlier = ctx.messaging.insertMessage('chat', 'u1', 'user', 'earlier real reply');
  const placeholder = (await start()).payload.message_id;
  await discard(placeholder);
  const projection = one(db, 'SELECT last_message_preview,last_message_at FROM conversations WHERE id=?', 'chat');
  const counts = all(db, 'SELECT user_id,unread_count FROM conversation_participants WHERE conversation_id=? ORDER BY user_id', 'chat');
  const broadcasts = broadcast.mock.calls.length;

  await expect(discard(placeholder)).rejects.toMatchObject({ statusCode: 404 });

  expect(one(db, 'SELECT last_message_preview,last_message_at FROM conversations WHERE id=?', 'chat')).toEqual(projection);
  expect(all(db, 'SELECT user_id,unread_count FROM conversation_participants WHERE conversation_id=? ORDER BY user_id', 'chat')).toEqual(counts);
  expect(await unread('u2')).toBe(1);
  expect(all(db, 'SELECT id FROM messages WHERE conversation_id=?', 'chat').map((row) => row.id)).toEqual([earlier.id]);
  expect(broadcast.mock.calls.length).toBe(broadcasts);
});

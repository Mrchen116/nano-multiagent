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
  // Observe the discard broadcast itself: the seam that decides whether a rolled-back write
  // could still be announced to online clients.
  const announced: { open: boolean; row: boolean; tombstone: boolean }[] = [];
  const broadcast = vi.fn((_readers: string[], frame: any) => {
    if (frame.event_type !== 'message.discarded') return;
    announced.push({
      open: ctx.db.isTransaction,
      row: Boolean(one(f.db, 'SELECT 1 FROM messages WHERE id=?', frame.data.message_id)),
      tombstone: Boolean(one(f.db, 'SELECT 1 FROM conversation_events WHERE event_id=?', frame.event_id)),
    });
  });
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
  return { ...f, ctx, connection, app, broadcast, announced, read, markRead, history, start, discard, unread };
}

it('restores unread, preview and timestamp to the remaining message when a placeholder is discarded', async () => {
  const { db, ctx, broadcast, announced, read, history, start, discard, unread } = setup();
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
  // It is announced only after the commit, with the row already gone and the tombstone stored.
  expect(announced).toEqual([{ open: false, row: false, tombstone: true }]);
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

it('returns to the projection the previous insert wrote when message timestamps are not monotonic', async () => {
  const { ctx, read, start, discard } = setup();
  // Ingress and event replay can store a message with an older created_at after a newer one,
  // so "the message before the placeholder" is the last inserted row, not the newest timestamp.
  ctx.messaging.insertMessage('chat', 'u1', 'user', 'arrived first', [], null, 'completed', { created_at: '2026-01-01T00:00:00.000Z' });
  ctx.messaging.insertMessage('chat', 'u1', 'user', 'backdated ingress', [], null, 'completed', { created_at: '2025-12-01T00:00:00.000Z' });
  const placeholder = (await start()).payload.message_id;

  await discard(placeholder);

  expect((await read('u1')).json()).toMatchObject({
    last_message_preview: 'backdated ingress',
    last_message_at: '2025-12-01T00:00:00.000Z',
    unread_count: 0,
  });
});

it('treats a read mark left on a discarded message as no watermark instead of subtracting a real unread', async () => {
  const { db, ctx, markRead, start, discard, unread } = setup();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
  const first = (await start()).payload.message_id;
  expect((await markRead('u2', first)).json()).toMatchObject({ unread_count: 0 });
  await discard(first);
  // u2's read mark still names the discarded message, so it can no longer be resolved.
  expect(
    one(db, 'SELECT last_read_message_id FROM conversation_participants WHERE conversation_id=? AND user_id=?', 'chat', 'u2')
      ?.last_read_message_id,
  ).toBe(first);
  ctx.messaging.insertMessage('chat', 'u1', 'user', 'real reply after the discarded placeholder');
  const second = (await start()).payload.message_id;
  expect(await unread('u2')).toBe(2);

  await discard(second);

  // Only the second placeholder's own +1 is rolled back; the real reply stays unread.
  expect(await unread('u2')).toBe(1);
});

it('restores the attachment or mention preview that the discarded placeholder had replaced', async () => {
  const { db, ctx, read, start, discard } = setup();
  db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('u3','carol','Carol','o3',?)").run(new Date().toISOString());
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u3')").run();
  ctx.messaging.insertMessage('chat', 'u1', 'user', '', [{ file_name: 'report.pdf' }]);
  const placeholder = (await start()).payload.message_id;
  await discard(placeholder);
  expect((await read('u1')).json().last_message_preview).toBe('report.pdf');
  // A mention preview is resolved from the remaining message, never from the dropped body.
  ctx.messaging.insertMessage('chat', 'u1', 'user', '<mention type="user" target_id="u3"/> please review');
  const second = (await start()).payload.message_id;
  await discard(second);
  expect((await read('u1')).json().last_message_preview).toBe('@Carol please review');
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

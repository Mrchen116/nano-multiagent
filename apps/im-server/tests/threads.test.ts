import Fastify from 'fastify';
import { expect, it } from 'vitest';
import { fixture } from './control-fixture.js';
import { Messaging, registerMessagingRoutes } from '../src/messaging.js';
import { searchMessages } from '../src/message-search.js';

it('keeps a topic off the main timeline and only unread-counts its followers', async () => {
  const {ctx, db} = fixture();
  ctx.gateway.broadcast = () => {};
  ctx.messaging = new Messaging(ctx);
  const app = Fastify();
  registerMessagingRoutes(app, ctx);
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
  const root = ctx.messaging.insertMessage('chat', 'u1', 'user', '下周三要补哪三页');
  const send = (user: string, content: string, key: string) => app.inject({
    method: 'POST', url: '/im/v1/conversations/chat/messages', headers: {'idempotency-key': key, 'x-user': user},
    payload: {sender: {type: 'user', id: user}, content, thread_root_message_id: root.id},
  });
  try {
    const sent = await send('u2', '先看第二页', 'topic-1');
    expect(sent.statusCode, sent.body).toBe(201);
    expect(sent.json().thread_root_message_id).toBe(root.id);
    const timeline = await app.inject('/im/v1/conversations/chat/messages');
    expect(timeline.json().items.map((item: {message?: {id: string}}) => item.message?.id)).not.toContain(sent.json().id);
    const followers = db.prepare('SELECT user_id, following FROM thread_follows WHERE root_message_id=? ORDER BY user_id').all(root.id) as {user_id: string}[];
    expect(followers.map(row => row.user_id).sort()).toEqual(['u1', 'u2']);
    const unread = db.prepare('SELECT user_id, unread_count FROM conversation_participants WHERE conversation_id=?').all('chat') as {user_id: string; unread_count: number}[];
    expect(unread.find(row => row.user_id === 'u1')?.unread_count).toBeGreaterThan(0);
    expect(db.prepare('SELECT 1 FROM relay_tasks WHERE message_id=?').get(sent.json().id)).toBeUndefined();
    expect((await app.inject({method:'POST',url:'/im/v1/conversations/chat/messages',headers:{'idempotency-key':'missing','x-user':'u2'},payload:{sender:{type:'user',id:'u2'},content:'no',thread_root_message_id:'missing'}})).statusCode).toBe(404);
  } finally { await app.close(); }
});

it('does not relay a group topic to an Agent who is not following it', async () => {
  const {ctx, db} = fixture();
  ctx.gateway.broadcast = () => {};
  ctx.messaging = new Messaging(ctx);
  const app = Fastify();
  registerMessagingRoutes(app, ctx);
  db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES('b1','agent:b','Bee','o1',datetime('now'),'active')").run();
  db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,tool_allowlist_json,workspace_root,work_mode,collaboration_scope,created_at,updated_at) VALUES('b','o1','n','Bee','[]','/bee','single_thread','team',datetime('now'),datetime('now'))").run();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','b1')").run();
  const root = ctx.messaging.insertMessage('chat', 'u1', 'user', '另一件事');
  const send = (content: string, key: string) => app.inject({
    method: 'POST', url: '/im/v1/conversations/chat/messages', headers: {'idempotency-key': key, 'x-user': 'u1'},
    payload: {sender: {type: 'user', id: 'u1'}, content, thread_root_message_id: root.id},
  });
  try {
    const reply = await send('旁人讨论', 'aside');
    expect(reply.statusCode, reply.body).toBe(201);
    expect(db.prepare('SELECT payload_json FROM relay_tasks WHERE message_id=?').all(reply.json().id)).toEqual([]);
    db.prepare("INSERT INTO thread_follows(conversation_id,root_message_id,user_id,following) VALUES('chat',?,'b1',1)").run(root.id);
    const heard = await send('第二页不用了', 'heard');
    expect(heard.statusCode, heard.body).toBe(201);
    const payload = JSON.parse((db.prepare("SELECT payload_json FROM relay_tasks WHERE message_id=? AND json_extract(payload_json,'$.agent_id')='b'").get(heard.json().id) as {payload_json: string}).payload_json);
    expect(payload.metadata.thread_root_excerpt).toContain('另一件事');
    expect(payload.metadata.thread_earlier.map((item: {excerpt: string}) => item.excerpt)).toContain('旁人讨论');
    expect(payload.metadata.addressed_to_agent).toBe(true);
    const timeline = searchMessages(db, {targets: ['chat'], terms: [], action: 'read'});
    expect(timeline.map(row => row.id)).not.toContain(heard.json().id);
    const found = searchMessages(db, {targets: ['chat'], terms: ['第二页'], action: 'search'});
    expect(found.map(row => row.id)).toContain(heard.json().id);
    const topic = searchMessages(db, {targets: ['chat'], terms: [], action: 'read', threadRoot: root.id});
    expect(topic.map(row => row.id).sort()).toEqual([reply.json().id, heard.json().id].sort());
  } finally { await app.close(); }
});

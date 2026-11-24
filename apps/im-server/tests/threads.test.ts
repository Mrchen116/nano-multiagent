import Fastify from 'fastify';
import { expect, it } from 'vitest';
import { personalFixture } from './personal-fixture.js';
import { Gateway } from '../src/gateway.js';
import { fixture } from './control-fixture.js';
import { Messaging, registerMessagingRoutes } from '../src/messaging.js';
import { searchMessages } from '../src/message-search.js';
import { listUnread } from '../src/threads.js';

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
    const quoted = await send('u2', '引用根消息', 'topic-quote');
    expect(quoted.statusCode, quoted.body).toBe(201);
    const outside = ctx.messaging.insertMessage('chat', 'u1', 'user', '另一条主时间线');
    const rejected = await app.inject({
      method: 'POST', url: '/im/v1/conversations/chat/messages', headers: {'idempotency-key': 'outside', 'x-user': 'u2'},
      payload: {sender: {type: 'user', id: 'u2'}, content: '不该离开话题', thread_root_message_id: root.id, reply_to_message_id: outside.id},
    });
    expect(rejected.statusCode, rejected.body).toBe(422);
    const inside = await app.inject({
      method: 'POST', url: '/im/v1/conversations/chat/messages', headers: {'idempotency-key': 'inside', 'x-user': 'u2'},
      payload: {sender: {type: 'user', id: 'u2'}, content: '留在话题里', thread_root_message_id: root.id, reply_to_message_id: root.id},
    });
    expect(inside.statusCode, inside.body).toBe(201);
    expect(inside.json().reply_to.message_id).toBe(root.id);
    expect(inside.json().thread_root_message_id).toBe(root.id);
    const final = await send('u1', '先验证这个方向', 'topic-final');
    expect(final.statusCode).toBe(201);
    const refreshed = await app.inject('/im/v1/conversations/chat/messages');
    const rootView = refreshed.json().items.map((item: {message?: {id: string; thread?: {reply_count: number; participants?: {id: string}[]}}}) => item.message).find((message: {id: string} | undefined) => message?.id === root.id);
    expect(rootView.thread.reply_count).toBe(4);
    expect(rootView.thread.recent_replies).toEqual([
      expect.objectContaining({id: inside.json().id, sender_user_id: 'u2', preview: '留在话题里'}),
      expect.objectContaining({id: final.json().id, sender_user_id: 'u1', preview: '先验证这个方向'}),
    ]);
    expect(rootView.thread.participants.map((person: {id: string}) => person.id)).toContain('u2');
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

it('clears only the opened group topic and keeps a direct topic on the watermark', async () => {
  const {ctx, db} = fixture();
  ctx.gateway.broadcast = () => {};
  ctx.messaging = new Messaging(ctx);
  const app = Fastify();
  registerMessagingRoutes(app, ctx);
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
  const root = ctx.messaging.insertMessage('chat', 'u1', 'user', '根');
  const send = (content: string, key: string, extra: Record<string, string> = {}) => app.inject({
    method: 'POST', url: '/im/v1/conversations/chat/messages', headers: {'idempotency-key': key, 'x-user': 'u2'},
    payload: {sender: {type: 'user', id: 'u2'}, content, thread_root_message_id: root.id, ...extra},
  });
  try {
    const reply = await send('话题里', 'group-reply');
    expect(reply.statusCode, reply.body).toBe(201);
    const before = db.prepare("SELECT unread_count FROM thread_follows WHERE user_id='u1' AND root_message_id=?").get(root.id) as {unread_count: number};
    expect(before.unread_count).toBeGreaterThan(0);
    expect((await app.inject({url: `/im/v1/conversations/chat/threads/${root.id}`, headers: {'x-user': 'u1'}})).statusCode).toBe(200);
    const count = () => (db.prepare("SELECT unread_count FROM conversation_participants WHERE user_id='u1' AND conversation_id='chat'").get() as {unread_count:number}).unread_count;
    expect(count()).toBe(1); // Fetching a search result is not a read acknowledgement.
    const later = await send('同时到达', 'later');
    const mark = (id:string) => app.inject({method:'POST',url:'/im/v1/conversations/chat/read',payload:{last_read_message_id:id}});
    await mark(reply.json().id);
    expect(count()).toBe(1);
    await mark(later.json().id);
    expect(count()).toBe(0);
    await app.inject({method:'POST',url:`/im/v1/conversations/chat/threads/${root.id}/follow`,payload:{following:false}});
    await send('取消关注期间', 'muted');
    expect(count()).toBe(0);
    const mention = await send('<mention type="user" target_id="u1"/>', 'mentioned');
    expect(count()).toBe(1);
    await mark(mention.json().id);
    expect(count()).toBe(0);
    db.prepare("UPDATE conversations SET type='direct' WHERE id='chat'").run();
    db.prepare("DELETE FROM thread_follows WHERE conversation_id='chat'").run();
    const direct = ctx.messaging.insertMessage('chat', 'u2', 'user', '私聊话题', [], null, 'completed', {thread_root_id: root.id});
    const watermark = (db.prepare('SELECT rowid FROM messages WHERE id=?').get(root.id) as {rowid: number}).rowid;
    expect(listUnread(db, 'chat', 'u1', watermark)).toBeGreaterThan(0);
    expect(direct.thread_root_message_id).toBe(root.id);
    expect(ctx.messaging.conversation('chat','u1').last_message_preview).toBe('根');
  } finally { await app.close(); }
});


it('keeps unaddressed streamed group replies out of PA observations and Agent relays', () => {
  const {ctx,db,service,args,principal} = personalFixture();
  db.prepare("UPDATE conversations SET type='group' WHERE id='peer'").run();
  db.prepare("UPDATE agent_profiles SET collaboration_scope='team' WHERE agent_id='a'").run();
  db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('author','agent:writer','Writer','o1',datetime('now'))").run();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','author')").run();
  const root=ctx.messaging.insertMessage('peer','u2','user','Planning');
  const stream=(text:string)=>{
    const m=ctx.messaging.insertMessage('peer','author','agent','',[],null,'running',{thread_root_id:root.id});
    ctx.messaging.records.complete(m,{kind:'message_completed',message_id:m.id,lifecycle_revision:1,final_content:text});
    ctx.messaging.event('peer',m.id,'message.completed',ctx.messaging.message(m.id));
    return m.id;
  };
  const ignored=stream('ordinary text including a1');
  expect(db.prepare('SELECT 1 FROM pa_source_events WHERE message_id=?').get(ignored)).toBeUndefined();
  const addressed=stream('<mention type="user" target_id="a1"/> please help');
  const observed=service.observations(principal,args).items.find((item:{message_id:string})=>item.message_id===addressed);
  expect(observed).toMatchObject({delivery:'observer',addressed_to_agent:true,thread_root_message_id:root.id});
  expect(service.admitSource(principal,{...args,conversation_id:'peer',source_message_id:addressed})).toMatchObject({delivery:'observer',addressed_to_agent:true,thread_root_excerpt:'Planning'});

  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')").run();
  const gateway=new Gateway(ctx);
  const next=stream('one more question');
  gateway.groupReply(next,{deferDelivery:true});
  const relay=db.prepare('SELECT payload_json FROM relay_tasks WHERE message_id=?').get(next);
  expect(JSON.parse(String(relay?.payload_json))).toMatchObject({metadata:{addressed_to_agent:true,thread_root_message_id:root.id}});
});

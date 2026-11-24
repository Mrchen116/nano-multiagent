import Fastify from 'fastify';
import { registerMessagingRoutes } from '../src/messaging.js';
import { expect, it, vi } from 'vitest';
import { Work } from '../src/work.js';
import { personalFixture } from './personal-fixture.js';

function fixture(personal: boolean) {
  const f = personalFixture();
  if (!personal) {
    f.db.prepare('DELETE FROM pa_policies').run();
    f.db.prepare('DELETE FROM personal_agent_bindings').run();
  }
  f.db.prepare("UPDATE agent_profiles SET work_mode='global' WHERE agent_id='a'").run();
  const work = new Work(f.ctx);
  work.register('a', 'main', 'n', { scope: 'global_main', title: 'Agent' });
  work.register('a', 'child', 'n', { scope: 'subagent', parent_session_id: 'main', title: 'Child' });
  const message = f.ctx.messaging.insertMessage('chat', 'u1', 'user', 'needle');
  const listing = vi.spyOn(f.ctx.messaging, 'conversations');
  const sources = vi.spyOn(f.service, 'sourceConversations');
  const query = (args: Record<string, unknown>) => work.query(f.principal, { agent_id: 'a', session_id: 'main', ...args });
  return { ...f, work, query, message, listing, sources };
}

it.each([false, true])('reads only requested chats without discovery (personal=%s)', personal => {
  const { query, message, listing, sources } = fixture(personal);
  expect(query({ action: 'info', target: 'chat' })).toMatchObject({ target: 'chat', name: 'u1' });
  expect(query({ action: 'describe', targets: ['chat'] }).conversations.map((c: any) => c.target)).toEqual(['chat']);
  expect(query({ action: 'describe', targets: [] }).conversations).toEqual([]);
  expect(query({ action: 'read', target: 'chat' }).messages.map((m: any) => m.message_id)).toEqual([message.id]);
  expect(query({ action: 'search', target: 'chat', query: 'needle' }).messages.map((m: any) => m.message_id)).toEqual([message.id]);
  expect(listing).not.toHaveBeenCalled();
  expect(sources).not.toHaveBeenCalled();
});

it.each(['single_thread', 'global'])('projects current execution nodes only for authorized group members (%s)', mode => {
  const { db, query, message } = fixture(false);
  db.prepare("UPDATE agent_profiles SET work_mode=? WHERE agent_id='a'").run(mode);
  db.prepare("UPDATE conversations SET type='group',visibility='public' WHERE id='chat'").run();
  db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('remote','o2','Node','offline'),('unnamed','o2','unnamed','online')").run();
  for (const [id, owner, node] of [['near', 'o1', 'n'], ['far', 'o2', 'remote'], ['unlabelled', 'o2', 'unnamed'], ['private-peer', 'o2', 'remote']]) {
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES(?,?,?,?,datetime('now'))")
      .run(id, `agent:${id}`, id, owner);
    db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,created_at,updated_at) VALUES(?,?,?,?,datetime('now'),datetime('now'))")
      .run(id, owner, node, id);
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat',?)").run(id);
  }
  db.prepare(`INSERT INTO personal_agent_bindings VALUES
    ('owner-pa','o1','u1','near','n',1,'owner-direct','Near','create','active',NULL,datetime('now')),
    ('peer-pa','o2','u2','private-peer','remote',1,'peer-direct','Peer','create','active',NULL,datetime('now'))`).run();
  const info = { action: 'info', target: 'chat' };
  expect(query(info).members.every((member: any) => !member.execution_node)).toBe(true);
  const members = query({ ...info, include_execution_nodes: true }).members;
  expect(members).toEqual(expect.arrayContaining([
    expect.objectContaining({ user_id: 'near', execution_node: { id: 'n', name: 'Node' } }),
    expect.objectContaining({ user_id: 'far', execution_node: { id: 'remote', name: 'Node' } }),
    expect.objectContaining({ user_id: 'unlabelled', execution_node: { id: 'unnamed' } }),
  ]));
  expect(query({ ...info, target: `chat:${message.id}`, include_execution_nodes: true }).members).toEqual(members);
  expect(members.find((member: any) => member.user_id === 'private-peer')).not.toHaveProperty('execution_node');
  db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat' AND user_id='a1'").run();
  expect(query({ ...info, include_execution_nodes: true }).members.every((member: any) => !member.execution_node)).toBe(true);
});

it('uses the PA participant perspective even when access comes from its observing owner', () => {
  const { db, ctx, query, listing, sources } = fixture(true);
  db.prepare("DELETE FROM conversation_participants WHERE conversation_id='peer' AND user_id='u1'").run();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')").run();
  ctx.messaging.insertMessage('peer', 'u2', 'user', 'needle');
  const expected = ctx.messaging.conversation('peer', 'u1');
  expect(expected.is_observer).toBe(true);
  expect(expected.title).not.toBe('Peer');
  expect(query({ action: 'read', target: 'peer' }).messages[0].source.name).toBe('u2');
  expect(listing).not.toHaveBeenCalled();
  expect(sources).not.toHaveBeenCalled();
});

it.each([false, true])('retains discovery and targeted authority checks (personal=%s)', personal => {
  const { db, query, listing, sources, service, principal, args } = fixture(personal);
  const list = query({ action: 'list' });
  expect(list.conversations.some((c: any) => c.target === 'chat')).toBe(true);
  expect(query({ action: 'search', query: 'needle' }).messages).toHaveLength(1);
  if (personal) expect(query({ action: 'resolve_target', target: 'chat' }).target).toBe('chat');
  expect(listing).toHaveBeenCalled();
  if (personal) expect(sources).toHaveBeenCalled();
  listing.mockClear(); sources.mockClear();

  for (const scope of ['bad-scope', '', 12]) expect(() => query({ action: 'info', target: 'chat', scope })).toThrow('invalid scope');
  expect(() => query({ action: 'info', target: 'chat', session_id: 'child' })).toThrow('scope_not_allowed');
  expect(() => query({ action: 'info', target: 'chat', session_id: 'missing' })).toThrow('scope_not_allowed');
  if (personal) {
    expect(() => query({ action: 'info', target: 'chat', binding_id: 'other' })).toThrow('personal_binding_not_authorized');
    const command = service.ctx.messaging.insertMessage('chat', 'u1', 'user', 'Do not read peer');
    service.sources(principal, { ...args, action: 'exclude', conversation_id: 'peer', source_message_id: command.id, expected_revision: 1 });
    expect(() => query({ action: 'info', target: 'peer' })).toThrow('target_not_accessible');
    listing.mockClear(); sources.mockClear();
  }
  db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat'").run();
  expect(() => query({ action: 'info', target: 'chat' })).toThrow('target_not_accessible');
  db.prepare("UPDATE users SET membership_status='disabled',personal_space_enabled=0 WHERE id='u1'").run();
  expect(() => query({ action: 'info', target: 'chat' })).toThrow();
  expect(listing).not.toHaveBeenCalled();
  expect(sources).not.toHaveBeenCalled();
});


it.each([false, true])('uses the actual reader name consistently across Agent conversation tools (personal=%s)', personal => {
  const {db, ctx, query, message} = fixture(personal);
  db.exec("UPDATE users SET display_name='Alice' WHERE id='u1'; UPDATE users SET display_name='Assistant' WHERE id='a1'; UPDATE conversations SET title='Assistant' WHERE id='chat'");
  const assertName = (name: string) => {
    expect(query({action:'info',target:'chat'})).toMatchObject({target:'chat',name});
    expect(query({action:'describe',targets:['chat']}).conversations).toMatchObject([{target:'chat',name}]);
    expect(query({action:'list'}).conversations.find((chat: any) => chat.target === 'chat')).toMatchObject({name});
    for (const action of ['read','search']) {
      const result=query({action,target:'chat',...(action==='search'?{query:'needle'}:{})});
      expect(result).toMatchObject({target:'chat',name});
      expect(result.messages).toMatchObject([{message_id:message.id,sender:{name: 'Alice'},source:{target:'chat',name}}]);
    }
    expect(query({action:'search',query:'needle'}).messages).toMatchObject([{source:{target:'chat',name}}]);
  };
  expect(ctx.messaging.conversation('chat','u1').title).toBe('Assistant');
  assertName('Alice');
  db.exec("UPDATE users SET display_name='Alicia' WHERE id='u1'");
  expect(query({action:'info',target:'chat'}).name).toBe('Alicia');
  db.exec("UPDATE users SET display_name='Alice' WHERE id='u1'; UPDATE conversations SET title='Launch plan',title_is_custom=1 WHERE id='chat'");
  expect(ctx.messaging.conversation('chat','u1').title).toBe('Launch plan');
  assertName('Launch plan');
  expect(query({action:'info',target:'chat'}).members.map((member: any)=>member.name)).toEqual(['Alice','Assistant']);
  expect(db.prepare("SELECT id,title FROM conversations WHERE id='chat'").get()).toEqual({id:'chat',title:'Launch plan'});
});

it('names owner-observed private chats by both participants for the PA, while keeping group and external titles', () => {
  const {db,ctx,query,service,principal,args} = fixture(true);
  db.exec("UPDATE users SET display_name='Alice' WHERE id='u1'; UPDATE users SET display_name='Bob' WHERE id='u2'; UPDATE users SET display_name='Assistant' WHERE id='a1'");
  const peer=ctx.messaging.insertMessage('peer','u1','user','needle from owner');
  expect(ctx.messaging.conversation('peer','u1').title).toBe('Bob');
  expect(ctx.messaging.conversation('peer','u2').title).toBe('Alice');
  expect(query({action:'info',target:'peer'}).name).toBe('Alice ↔ Bob');
  expect(query({action:'read',target:'peer'}).messages[0].source).toMatchObject({name:'Alice ↔ Bob',delivery:'observer'});
  expect(service.sources(principal,{...args,action:'list'}).items.find((chat:any)=>chat.id==='peer').title).toBe('Alice ↔ Bob');
  expect(service.sourceConversations(service.binding('o1')!).find((chat:any)=>chat.id==='peer').title).toBe('Bob');
  expect(service.authorization(principal,args).conversations.find((chat:any)=>chat.id==='peer').name).toBe('Alice ↔ Bob');
  db.exec("UPDATE conversations SET title='Team room',type='group' WHERE id='peer'");
  expect(query({action:'info',target:'peer'}).name).toBe('Team room');
  db.exec("UPDATE conversations SET title='Feishu contact',type='direct',external_source='feishu',external_chat_id='external-peer' WHERE id='peer'");
  expect(query({action:'info',target:'peer'}).name).toBe('Feishu contact');
  expect(query({action:'read',target:'peer'}).messages[0].message_id).toBe(peer.id);
});


it('projects the same peer name in Web list, detail, sync and search, preserving an explicit rename', async () => {
  const {ctx,db} = fixture(true);
  db.exec("UPDATE users SET display_name='Alice' WHERE id='u1'; UPDATE users SET display_name='Bob' WHERE id='u2'");
  ctx.messaging.insertMessage('peer','u1','user','needle');
  const app=Fastify(); registerMessagingRoutes(app,ctx);
  const get=async(url:string,viewer='u1')=>{
    const response=await app.inject({url,headers:{'x-user':viewer}});
    expect(response.statusCode).toBe(200); return response.json();
  };
  try {
    expect((await get('/im/v1/conversations/peer')).title).toBe('Bob');
    expect((await get('/im/v1/conversations/peer','u2')).title).toBe('Alice');
    for(const path of ['/im/v1/conversations','/im/v1/sync']) expect((await get(path)).items.find((chat:any)=>chat.id==='peer').title).toBe('Bob');
    expect((await get('/im/v1/messages/search?q=needle')).messages.find((message:any)=>message.conversation_id==='peer').conversation_name).toBe('Bob');
    const renamed=await app.inject({method:'PATCH',url:'/im/v1/conversations/peer',headers:{'x-user':'u1'},payload:{title:'Weekend plans'}});
    expect(renamed.statusCode).toBe(200);
    expect((await get('/im/v1/conversations/peer','u2')).title).toBe('Weekend plans');
  } finally {await app.close();}
});

it('shows the other Agent to each participant and both names to their observing owner', () => {
  const {ctx,db} = fixture(false);
  db.exec("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,workspace_root,created_at,updated_at) VALUES('b','o1','n','Builder','/builder','now','now')");
  const builder=ctx.messaging.agentUser('b');
  db.exec("UPDATE users SET display_name='Planner' WHERE id='a1'");
  const id=ctx.messaging.resolveTarget('a','agent:b',true)!;
  expect(ctx.messaging.conversation(id,'a1').title).toBe('Builder');
  expect(ctx.messaging.conversation(id,builder.id).title).toBe('Planner');
  db.exec("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES('o1','agent-owner','Owner','o1','now','active')");
  expect(ctx.messaging.conversation(id,'o1').title).toBe('Planner ↔ Builder');
});

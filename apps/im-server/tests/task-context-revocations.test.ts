import Fastify from 'fastify';
import { backup } from 'node:sqlite';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import { fixture, connectFixtureGateway } from './control-fixture.js';
import { Gateway, type Connection } from '../src/gateway.js';
import { personalFixture } from './personal-fixture.js';
import { Messaging, registerMessagingRoutes } from '../src/messaging.js';
import { AgentLifecycles } from '../src/agent-lifecycle.js';
import { all, one, transaction, type ImContext } from '../src/context.js';
import { openDatabase } from '../src/db.js';
import { captureTaskContextAccess, revokeLostTaskContextAccess } from '../src/task-context-access.js';

const apps:ReturnType<typeof Fastify>[]=[];
afterEach(async()=>{for(const app of apps.splice(0))await app.close();});
function messaging(f=fixture()) {
  f.ctx.gateway.broadcast=vi.fn();f.ctx.messaging=new Messaging(f.ctx);
  f.db.prepare("UPDATE conversations SET creator_id='u1' WHERE id='chat'").run();
  const app=Fastify();apps.push(app);registerMessagingRoutes(app,f.ctx);
  return {...f,app,service:f.ctx.messaging};
}
function original(ctx:ImContext,conversation='chat',agent='a',text='PRIVATE Task title and body') {
  return transaction(ctx.db,()=>ctx.messaging.persistTaskNotice(conversation,'u1',text,
    {kind:'task_graph',change_kinds:['title'],attention_actor_ids:[agent],task_refs:[{graph_id:'private-graph',node_id:'private-node'}]}));
}
const revoked=(ctx:ImContext)=>all(ctx.db,"SELECT * FROM task_context_index WHERE projection_kind='revoked' ORDER BY seq");
function minimal(item:any) {
  expect(item).toMatchObject({allowed:true,projection_kind:'revoked',input:{participants:[],metadata:{task_context:true}}});
  expect(item.input.message.system_notice).toMatchObject({kind:'task_graph',change_kinds:['access_revoked']});
  expect(JSON.stringify(item)).not.toMatch(/PRIVATE|private-graph|private-node/);
}

it('records one new withdrawal for actual member loss, revalidates before the fixed cut, and never deletes consumed history',async()=>{
  const f=messaging(),old=original(f.ctx),cut=f.service.syncTaskContext('a',0,undefined,32);
  expect(cut.items[0]).toMatchObject({allowed:true,input:{message:{id:old.id}}});
  const remove=()=>f.app.inject({method:'DELETE',url:'/im/v1/conversations/chat/participants/a1'});
  expect((await remove()).statusCode).toBe(204);
  const rows=revoked(f.ctx);expect(rows).toHaveLength(1);
  expect((await remove()).statusCode).toBe(204);expect(revoked(f.ctx)).toHaveLength(1);
  expect(f.service.syncTaskContext('a',cut.through,cut.through,32,undefined,[old.id]).revoked_message_ids).toEqual([old.id]);
  minimal(f.service.syncTaskContext('a',cut.through,undefined,32).items[0]);
  expect(f.service.message(old.id).content).toContain('PRIVATE');
  const notice=rows[0],stored=one(f.db,'SELECT * FROM task_context_revocations WHERE message_id=?',notice.message_id)!;
  expect(f.service.message(notice.message_id).created_at).toBe(stored.created_at);
  const relay=one(f.db,'SELECT * FROM relay_tasks WHERE message_id=?',notice.message_id)!;
  expect(f.service.relayEligible(relay)).toBe(true);
  const forged={...relay,payload_json:JSON.stringify({...JSON.parse(relay.payload_json),lifecycle_revision:0})};
  expect(f.service.relayEligible(forged)).toBe(false);
  f.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','a1')").run();
  expect(f.service.syncTaskContext('a',0,undefined,32).items[0].allowed).toBe(false);
  const fresh=original(f.ctx,'chat','a','Newly authorized Task');
  expect(f.service.syncTaskContext('a',0,undefined,32).items.find((item:any)=>item.message_id===fresh.id).allowed).toBe(true);
});

it('rolls the authority mutation back if its minimal original cannot be persisted',async()=>{
  const f=messaging();original(f.ctx);
  f.db.exec("CREATE TRIGGER reject_withdrawal BEFORE INSERT ON task_context_revocations BEGIN SELECT RAISE(ABORT,'withdrawal unavailable'); END");
  expect((await f.app.inject({method:'DELETE',url:'/im/v1/conversations/chat/participants/a1'})).statusCode).toBe(500);
  expect(one(f.db,"SELECT 1 FROM conversation_participants WHERE conversation_id='chat' AND user_id='a1'")).toBeTruthy();
  expect(revoked(f.ctx)).toEqual([]);
});

it('revalidates every pending original against mutations newer than a paged fixed cut',async()=>{
  const f=messaging(),ids=Array.from({length:70},()=>original(f.ctx).id);
  const first=f.service.syncTaskContext('a',0,undefined,32);
  await f.app.inject({method:'DELETE',url:'/im/v1/conversations/chat/participants/a1'});
  const second=f.service.syncTaskContext('a',first.next,first.through,32);
  expect(second.through).toBe(first.through);expect(second.items.every((item:any)=>!item.allowed&&!item.input)).toBe(true);
  for(let i=0;i<ids.length;i+=32)expect(f.service.syncTaskContext('a',first.through,first.through,32,undefined,ids.slice(i,i+32)).revoked_message_ids).toEqual(ids.slice(i,i+32));
});

it('dissolves a group with a new minimal original without erasing its previous history',()=>{
  const f=messaging(),old=original(f.ctx);
  f.ctx.gateway.tasks={closeForConversationDissolution:vi.fn(()=>[]),notifyChange:vi.fn()} as any;
  f.service.dissolveConversation('u1','chat');
  expect(revoked(f.ctx)).toHaveLength(1);
  const page=f.service.syncTaskContext('a',0,undefined,32,undefined,[old.id]);
  expect(page.revoked_message_ids).toEqual([old.id]);minimal(page.items[1]);
  expect(f.service.message(old.id).content).toContain('PRIVATE');
  expect(all(f.db,"SELECT * FROM relay_tasks WHERE status IN ('queued','sent','accepted')")).toEqual([]);
});

it('retains the same minimal original and index across Direct hard-delete cascade and database reopen',async()=>{
  const f=messaging();f.db.prepare("UPDATE conversations SET type='direct' WHERE id='chat'").run();
  const old=original(f.ctx),cut=f.service.syncTaskContext('a',0,undefined,32);
  expect((await f.app.inject({method:'DELETE',url:'/im/v1/conversations/chat'})).statusCode).toBe(204);
  expect(one(f.db,"SELECT 1 FROM conversations WHERE id='chat'")).toBeUndefined();
  expect(one(f.db,'SELECT 1 FROM messages WHERE id=?',old.id)).toBeUndefined();
  const fact=one(f.db,'SELECT * FROM task_context_revocations')!;
  const dir=mkdtempSync(join(tmpdir(),'task-revocation-')),path=join(dir,'im.db');
  let db:ReturnType<typeof openDatabase>|undefined;
  try {
    await backup(f.db,path);db=openDatabase(path);
    const service=new Messaging({...f.ctx,db});
    const page=service.syncTaskContext('a',cut.through,undefined,32,undefined,[old.id]);
    expect(page.revoked_message_ids).toEqual([old.id]);minimal(page.items[0]);
    expect(page.items[0].input.message).toMatchObject({id:fact.message_id,created_at:fact.created_at,conversation_id:'chat'});
    expect(service.syncTaskContext('a',0,undefined,32).items[0]).toMatchObject({allowed:false,message_id:old.id});
  } finally {db?.close();rmSync(dir,{recursive:true,force:true});}
});

it.each(['owner','agent'])('preserves PA source access when its %s route remains, and revokes only after the union is lost',async remaining=>{
  const f=personalFixture();f.ctx.gateway.broadcast=vi.fn();
  f.db.prepare("UPDATE conversations SET type='group',creator_id='u2' WHERE id='peer'").run();
  f.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')").run();
  const app=Fastify();apps.push(app);registerMessagingRoutes(app,f.ctx);
  const old=original(f.ctx,'peer');expect(f.ctx.messaging.syncTaskContext('a',0,undefined,32).items[0].allowed).toBe(true);
  const remove=(id:string)=>app.inject({method:'DELETE',url:'/im/v1/conversations/peer/participants/'+id,headers:{'x-user':'u2'}});
  expect((await remove(remaining==='owner'?'a1':'u1')).statusCode).toBe(204);
  expect(revoked(f.ctx)).toEqual([]);
  expect(f.ctx.messaging.syncTaskContext('a',0,undefined,32).items[0].allowed).toBe(true);
  expect((await remove(remaining==='owner'?'u1':'a1')).statusCode).toBe(204);
  expect(revoked(f.ctx)).toHaveLength(1);
  expect(f.ctx.messaging.syncTaskContext('a',0,undefined,32,undefined,[old.id]).revoked_message_ids).toEqual([old.id]);
});

it('uses current public read access rather than treating past membership as either a grant or an automatic loss',async()=>{
  const f=personalFixture();f.ctx.gateway.broadcast=vi.fn();
  f.db.prepare("UPDATE conversations SET type='group',creator_id='u2',visibility='public' WHERE id='peer'").run();
  const old=original(f.ctx,'peer');
  const app=Fastify();apps.push(app);registerMessagingRoutes(app,f.ctx);
  await app.inject({method:'DELETE',url:'/im/v1/conversations/peer/participants/u1',headers:{'x-user':'u2'}});
  expect(revoked(f.ctx)).toEqual([]);expect(f.service.sourceAllowed(f.service.binding('o1')!,'peer')).toBe(true);
  expect((await app.inject({method:'PATCH',url:'/im/v1/conversations/peer',headers:{'x-user':'u2'},payload:{visibility:'private'}})).statusCode).toBe(200);
  expect(revoked(f.ctx)).toHaveLength(1);
  expect(f.ctx.messaging.syncTaskContext('a',0,undefined,32,undefined,[old.id]).revoked_message_ids).toEqual([old.id]);
});

it('adds PA source exclusions transactionally without revoking unrelated sources or reviving withdrawn originals',()=>{
  const f=personalFixture(),old=original(f.ctx,'peer');
  const own=original(f.ctx,'chat');
  const binding=f.service.binding('o1')!;
  f.service.updatePolicy('o1',{expected_revision:1,excluded_conversation_ids:['peer']});
  expect(revoked(f.ctx).map(row=>row.conversation_id)).toEqual(['peer']);
  const page=f.ctx.messaging.syncTaskContext('a',0,undefined,32);
  expect(page.items.find((item:any)=>item.message_id===old.id).allowed).toBe(false);
  expect(page.items.find((item:any)=>item.message_id===own.id).allowed).toBe(true);
  f.service.updatePolicy('o1',{expected_revision:2,excluded_conversation_ids:['peer']});expect(revoked(f.ctx)).toHaveLength(1);
  expect(f.service.sourceAllowed(binding,'peer')).toBe(false);
  f.service.updatePolicy('o1',{expected_revision:3,excluded_conversation_ids:[]});
  expect(f.ctx.messaging.syncTaskContext('a',0,undefined,32).items.find((item:any)=>item.message_id===old.id).allowed).toBe(false);
});

it('stops handling on disable without changing chat read ACLs, revives only new work, and keeps lifecycle delivery fences',()=>{
  const f=messaging(),old=original(f.ctx),service=new AgentLifecycles(f.ctx);
  f.ctx.gateway.tasks={freezeAgent:vi.fn()} as any;
  const off={enabled:false,request_id:'off',expected_revision:1};
  service.change('a','u1',off);service.change('a','u1',off);
  expect(revoked(f.ctx)).toHaveLength(1);
  expect(f.service.conversation('chat','a1').id).toBe('chat');expect(f.service.message(old.id).content).toContain('PRIVATE');
  const minimalRelay=one(f.db,'SELECT * FROM relay_tasks WHERE message_id=?',revoked(f.ctx)[0].message_id)!;
  expect(f.service.relayEligible(minimalRelay)).toBe(false);
  const disabled=original(f.ctx,'chat','a','Task fact during disabled generation');
  expect(one(f.db,'SELECT 1 FROM task_context_index WHERE message_id=?',disabled.id)).toBeUndefined();
  f.db.prepare("UPDATE agent_lifecycle SET observed='disabled',applied_revision=revision WHERE agent_id='a'").run();
  service.change('a','u1',{enabled:true,request_id:'on',expected_revision:2});
  expect(f.service.syncTaskContext('a',0,undefined,32).items[0].allowed).toBe(false);
  expect(f.service.relayEligible(minimalRelay)).toBe(false);
  const fresh=original(f.ctx,'chat','a','New generation');
  expect(f.service.syncTaskContext('a',0,undefined,32).items.find((item:any)=>item.message_id===fresh.id).allowed).toBe(true);
});

it("suspends company source access but retains a PA owner's personal source eligibility and history",()=>{
  const f=personalFixture();
  f.db.prepare("UPDATE users SET personal_space_enabled=1,password_hash='hash' WHERE id='u1'").run();
  f.db.prepare("UPDATE agent_profiles SET space_id='personal:o1' WHERE agent_id='a'").run();
  f.db.prepare("UPDATE conversations SET space_id='personal:o1',owner_id='o1' WHERE id='chat'").run();
  const company=original(f.ctx,'peer'),personal=original(f.ctx,'chat');
  f.ctx.identity.transition('u2','u1','suspend');
  expect(revoked(f.ctx).map(row=>row.conversation_id)).toEqual(['peer']);
  const page=f.ctx.messaging.syncTaskContext('a',0,undefined,32);
  expect(page.items.find((item:any)=>item.message_id===company.id).allowed).toBe(false);
  expect(page.items.find((item:any)=>item.message_id===personal.id).allowed).toBe(true);
  f.ctx.identity.transition('u2','u1','suspend');expect(revoked(f.ctx)).toHaveLength(1);
  expect(f.ctx.messaging.message(company.id).content).toContain('PRIVATE');
});

it('compares the final real Gateway roster: same-roster reconnect retains access, retirement revokes once, and same-source peers remain eligible',()=>{
  const f=fixture();f.ctx.messaging=new Messaging(f.ctx);
  const connection=connectFixtureGateway(f);
  const socket=()=>({readyState:1,bufferedAmount:0,send:vi.fn(),close:vi.fn()}) as any;
  connection.socket=socket();f.ctx.gateway=new Gateway(f.ctx);
  const register=(c:Connection,agents:string[])=>f.ctx.gateway.register(c,{node_id:'n',agents,capabilities:{agent_lifecycle_v1:true}});
  expect(register(connection,['a','kept'])).toMatchObject({message_type:'node.register',node_id:'n'});
  f.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat',?)").run(f.ctx.messaging.agentUser('kept').id);
  f.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('other-node','o1','Other','online')").run();
  f.db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,created_at,updated_at) VALUES('other','o1','other-node','Other',datetime('now'),datetime('now'))").run();
  f.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat',?)").run(f.ctx.messaging.agentUser('other').id);
  const old=original(f.ctx),kept=original(f.ctx,'chat','kept'),other=original(f.ctx,'chat','other');
  const reconnected={...connection,socket:socket()};
  register(reconnected,['a','kept']);
  expect(connection.socket.close).toHaveBeenCalledOnce();
  expect(revoked(f.ctx)).toEqual([]);
  expect(f.ctx.messaging.syncTaskContext('a',0,undefined,32).items[0].allowed).toBe(true);
  register(reconnected,['kept']);
  expect(revoked(f.ctx)).toHaveLength(1);
  expect(revoked(f.ctx)[0]).toMatchObject({agent_id:'a',conversation_id:'chat'});
  expect(one(f.db,"SELECT is_stale FROM agent_profiles WHERE agent_id='a'")!.is_stale).toBe(1);
  expect(f.ctx.messaging.syncTaskContext('a',0,undefined,32,undefined,[old.id]).revoked_message_ids).toEqual([old.id]);
  for(const [agent,message] of [['kept',kept],['other',other]] as const)expect(f.ctx.messaging.syncTaskContext(agent,0,undefined,32).items.find((item:any)=>item.message_id===message.id).allowed).toBe(true);
  register(reconnected,['kept']);expect(revoked(f.ctx)).toHaveLength(1);
  expect(f.ctx.messaging.message(old.id).content).toContain('PRIVATE');
});

it('does not re-revoke historical full references after restored access without new Task originals',()=>{
  const f=messaging();original(f.ctx);
  for(let i=0;i<2;i++)transaction(f.db,()=>{
    const before=captureTaskContextAccess(f.db,{agentIds:['a']});
    f.db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat' AND user_id='a1'").run();
    revokeLostTaskContextAccess(f.db,before,'u1');
    f.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','a1')").run();
  });
  expect(revoked(f.ctx)).toHaveLength(1);
});

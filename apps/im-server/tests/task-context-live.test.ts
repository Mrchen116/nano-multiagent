import Fastify from 'fastify';
import { backup } from 'node:sqlite';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import { fixture, connectFixtureGateway } from './control-fixture.js';
import { personalFixture } from './personal-fixture.js';
import { Gateway } from '../src/gateway.js';
import { Messaging } from '../src/messaging.js';
import { registerControlRoutes } from '../src/control-routes.js';
import { createServer } from '../src/server.js';
import { all, one, transaction, type ImContext } from '../src/context.js';

const cleanup:(()=>void|Promise<void>)[]=[];
afterEach(async()=>{for(const close of cleanup.splice(0))await close();});
function original(ctx:ImContext,conversation='chat') {
  return transaction(ctx.db,()=>ctx.messaging.persistTaskNotice(conversation,'u1','PRIVATE Task title and body',
    {kind:'task_graph',change_kinds:['title'],attention_actor_ids:['a'],task_refs:[{graph_id:'private-graph',node_id:'private-node'}]}));
}
function live(ctx:ImContext,user='u1',node=true) {
  const browser:any[]=[],frames:any[]=[],order:string[]=[];
  if(node){
    ctx.gateway=new Gateway(ctx);
    const connection=connectFixtureGateway({ctx,db:ctx.db});
    connection.agent_lifecycle_v1=true;
    connection.socket={readyState:1,bufferedAmount:0,send:(raw:string)=>{
      expect(ctx.db.isTransaction).toBe(false);
      const frame=JSON.parse(raw);frames.push(frame);order.push(frame.type);
    },close:vi.fn()} as any;
  }
  ctx.db.prepare('INSERT INTO auth_sessions(session_id,user_id,epoch,refresh_hash,expires_at) VALUES(?,?,0,?,?)')
    .run('live-session',user,'unused',Math.floor(Date.now()/1000)+300);
  ctx.gateway.browsers.add({userId:user,sessionId:'live-session',ready:true,cursor:0,socket:{readyState:1,bufferedAmount:0,send:(raw:string)=>{
    expect(ctx.db.isTransaction).toBe(false);
    const frame=JSON.parse(raw);browser.push(frame);
    if(frame.data?.system_notice?.change_kinds?.includes('access_revoked'))order.push('withdrawal');
  },close:vi.fn()}} as any);
  return {browser,frames,order,drain:vi.spyOn(ctx.messaging,'deliverRelays')};
}
const withdrawals=(events:any[])=>events.filter(event=>event.data?.system_notice?.change_kinds?.includes('access_revoked'));
function minimal(ctx:ImContext,events:any[],oldId:string) {
  expect(withdrawals(events)).toHaveLength(1);
  const event=withdrawals(events)[0];
  expect(event).toMatchObject({op:'event',conversation_id:one(ctx.db,'SELECT conversation_id FROM messages WHERE id=?',oldId)!.conversation_id,
    data:{sender_type:'system',system_notice:{kind:'task_graph',change_kinds:['access_revoked']}}});
  expect(event.data.system_notice.task_refs).toBeUndefined();
  expect(event.message_id).not.toBe(oldId);
  expect(one(ctx.db,'SELECT message_id FROM task_context_revocations WHERE message_id=?',event.message_id)).toBeDefined();
  expect(event.data.content).toBe(one(ctx.db,'SELECT content FROM messages WHERE id=?',event.message_id)!.content);
  expect(JSON.stringify(events)).not.toMatch(/PRIVATE|private-graph|private-node/);
  expect(one(ctx.db,'SELECT content FROM messages WHERE id=?',oldId)!.content).toContain('PRIVATE');
}
function abortWithdrawal(ctx:ImContext) {
  ctx.db.exec("CREATE TRIGGER abort_withdrawal AFTER INSERT ON task_context_index WHEN NEW.projection_kind='revoked' BEGIN SELECT RAISE(ABORT,'test rollback'); END");
}
function noEffects(ctx:ImContext,before:number[],observed:ReturnType<typeof live>) {
  expect(observed.browser).toEqual([]);expect(observed.frames).toEqual([]);expect(observed.drain).not.toHaveBeenCalled();
  expect(['messages','relay_tasks','conversation_events','pa_source_events'].map(table=>one(ctx.db,'SELECT count(*) AS n FROM '+table)!.n)).toEqual(before);
  expect(all(ctx.db,'SELECT * FROM task_context_revocations')).toEqual([]);
}
const counts=(ctx:ImContext)=>['messages','relay_tasks','conversation_events','pa_source_events'].map(table=>one(ctx.db,'SELECT count(*) AS n FROM '+table)!.n);

it('publishes only new minimal policy withdrawals after commit, without relaying old/full bodies or replaying earlier facts',()=>{
  const f=personalFixture(),old=original(f.ctx,'peer'),observed=live(f.ctx);
  const result=f.service.updatePolicy('o1',{expected_revision:1,excluded_conversation_ids:['peer']});
  expect(result).toEqual({revision:2,excluded_conversation_ids:['peer']});
  minimal(f.ctx,observed.browser,old.id);
  expect(observed.frames.map(frame=>frame.type)).toEqual(['pa.observations.available']);
  expect(observed.order.indexOf('withdrawal')).toBeLessThan(observed.order.indexOf('pa.observations.available'));
  expect(observed.drain).not.toHaveBeenCalled();
  observed.browser.length=0;observed.frames.length=0;
  f.service.updatePolicy('o1',{expected_revision:2,excluded_conversation_ids:['peer']});
  expect(withdrawals(observed.browser)).toEqual([]);
  expect(observed.frames.map(frame=>frame.type)).toEqual(['pa.observations.available']);
});

it('does not publish, relay, or wake for rolled-back source policy loss',()=>{
  const f=personalFixture();original(f.ctx,'peer');const observed=live(f.ctx),before=counts(f.ctx);abortWithdrawal(f.ctx);
  expect(()=>f.service.updatePolicy('o1',{expected_revision:1,excluded_conversation_ids:['peer']})).toThrow('test rollback');
  expect(f.service.policy('binding')).toEqual({revision:1,excluded_conversation_ids:[]});
  noEffects(f.ctx,before,observed);
});

it('commits disable and sends lifecycle control before minimal live publication, without relay/wake or HTTP body leakage',async()=>{
  const f=fixture();f.ctx.messaging=new Messaging(f.ctx);const old=original(f.ctx),observed=live(f.ctx);
  const app=Fastify();cleanup.push(()=>app.close());registerControlRoutes(app,f.ctx);
  const request=()=>app.inject({method:'PUT',url:'/im/v1/agents/a/lifecycle',payload:{enabled:false,expected_revision:1,request_id:'disable'}});
  const result=await request();expect(result.statusCode).toBe(202);
  expect(result.json()).toMatchObject({desired:'disabled',revision:2});
  expect(result.body).not.toMatch(/access_revoked|PRIVATE|private-graph|private-node/);
  minimal(f.ctx,observed.browser,old.id);
  expect(observed.frames.map(frame=>frame.type)).toEqual(['agent.lifecycle.apply','task.execution.changed']);
  expect(observed.order.indexOf('agent.lifecycle.apply')).toBeLessThan(observed.order.indexOf('withdrawal'));
  expect(observed.drain).not.toHaveBeenCalled();
  observed.browser.length=0;await request();expect(withdrawals(observed.browser)).toEqual([]);
});

it('does not send lifecycle controls, live events, relay frames, or wakes after disable rollback',async()=>{
  const f=fixture();f.ctx.messaging=new Messaging(f.ctx);original(f.ctx);const observed=live(f.ctx),before=counts(f.ctx);abortWithdrawal(f.ctx);
  const app=Fastify();cleanup.push(()=>app.close());registerControlRoutes(app,f.ctx);
  const result=await app.inject({method:'PUT',url:'/im/v1/agents/a/lifecycle',payload:{enabled:false,expected_revision:1,request_id:'disable'}});
  expect(result.statusCode).toBe(500);
  expect(one(f.db,"SELECT desired FROM agent_lifecycle WHERE agent_id='a'")?.desired??'enabled').toBe('enabled');
  noEffects(f.ctx,before,observed);
});

async function identityServer() {
  const f=fixture();f.ctx.messaging=new Messaging(f.ctx);
  f.db.prepare("UPDATE users SET password_hash='hash' WHERE id='u1'").run();
  f.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
  const old=original(f.ctx),directory=mkdtempSync(join(tmpdir(),'task-live-')),path=join(directory,'im.db');
  await backup(f.db,path);
  const app=await createServer({dbPath:path,uploadDir:join(directory,'uploads'),publicUrl:'http://im.test',jwtSecret:'live-callback-secret'});
  cleanup.push(async()=>{await app.close();rmSync(directory,{recursive:true,force:true});});
  app.im.messaging.delivery.stop();
  app.im.identity.authenticateRequest=()=>app.im.identity.user('u2')!;
  const observed=live(app.im,'u2');
  return {app,old,observed,ctx:app.im,request:()=>app.inject({method:'POST',url:'/im/v1/company/members/u1/suspend'})};
}

it('injects the identity callback in the production root and emits only the new minimal event after company suspension',async()=>{
  const {ctx,old,observed,request}=await identityServer();
  const result=await request();expect(result.statusCode).toBe(200);
  expect(result.json()).toMatchObject({id:'u1',membership_status:'suspended'});
  expect(result.body).not.toMatch(/access_revoked|PRIVATE|private-graph|private-node/);
  minimal(ctx,observed.browser,old.id);expect(observed.drain).not.toHaveBeenCalled();expect(observed.frames).toEqual([]);
  observed.browser.length=0;await request();expect(withdrawals(observed.browser)).toEqual([]);
});

it('never invokes the production identity callback on rollback or leaks relay/wake side effects',async()=>{
  const {ctx,observed,request}=await identityServer(),before=counts(ctx);abortWithdrawal(ctx);
  const result=await request();expect(result.statusCode).toBe(500);
  expect(ctx.identity.user('u1')!.membership_status).toBe('active');
  noEffects(ctx,before,observed);
});

import Fastify from 'fastify';
import { afterEach, expect, it, vi } from 'vitest';
import { fixture, connectFixtureGateway } from './control-fixture.js';
import { registerControlRoutes } from '../src/control.js';
import { Gateway } from '../src/gateway.js';
import { Messaging, registerMessagingRoutes } from '../src/messaging.js';
import { registerConversationActions } from '../src/conversation-actions.js';

const apps: ReturnType<typeof Fastify>[]=[];
afterEach(async()=>{for(const app of apps.splice(0))await app.close();});
function setup() {
  const f=fixture();f.ctx.messaging=new Messaging(f.ctx);
  const connection=connectFixtureGateway(f);const frames:any[]=[];
  connection.socket={readyState:1,bufferedAmount:0,send:(frame:string)=>frames.push(JSON.parse(frame)),close:vi.fn()} as any;
  f.ctx.gateway=new Gateway(f.ctx);
  const registered=f.ctx.gateway.register(connection,{node_id:'n',agents:['a'],capabilities:{agent_lifecycle_v1:true}});
  const app=Fastify();apps.push(app);registerControlRoutes(app,f.ctx);registerMessagingRoutes(app,f.ctx);registerConversationActions(app,f.ctx);
  const http=(method:'GET'|'PUT'|'POST',payload?:object,user='u1')=>app.inject({method,url:'/im/v1/agents/a/lifecycle'+(method==='POST'?'/retry':''),payload,headers:{'x-user':user}});
  const report=(revision:number,observed:string,instance='process-a')=>f.ctx.gateway.handle(connection,'agent.lifecycle.report',{node_id:'n',agent_id:'a',revision,observed,process_instance_id:instance});
  return {...f,app,http,report,registered,frames,connection};
}
it('persists human intent with CAS and request identity, separately confirms stop and rejects unauthorized mutation',async()=>{
  const f=setup();
  expect(f.registered).toMatchObject({agent_lifecycle_v1:1,agent_lifecycles:[{agent_id:'a',desired:'enabled',revision:1}]});
  expect((await f.http('GET')).json()).toMatchObject({desired:'enabled',revision:1});
  expect((await f.http('GET',undefined,'u2')).statusCode).toBe(200);
  expect((await f.http('PUT',{enabled:false,request_id:'deny',expected_revision:1},'u2')).statusCode).toBe(403);
  await f.report(1,'enabling');await f.report(1,'enabled');
  const off={enabled:false,request_id:'off',expected_revision:1};
  const stopped=await f.http('PUT',off);expect(stopped.statusCode).toBe(202);
  expect(stopped.json()).toMatchObject({desired:'disabled',revision:2,observed:'stopping',disabled_through_revision:2});
  expect(f.frames.find(frame=>frame.type==='agent.lifecycle.apply')).toMatchObject({type:'agent.lifecycle.apply',payload:{desired:'disabled',revision:2}});
  expect((await f.http('PUT',off)).json().revision).toBe(2);
  expect((await f.http('PUT',{enabled:true,request_id:'on-too-soon',expected_revision:2})).statusCode).toBe(409);
  expect((await f.http('PUT',{enabled:true,request_id:'off',expected_revision:2})).statusCode).toBe(409);
  await expect(f.report(1,'enabled')).rejects.toThrow();
  await expect(f.report(2,'disabled','stale-process')).rejects.toThrow();
  await f.report(2,'stop_unconfirmed');
  expect((await f.http('POST',{request_id:'retry'})).json()).toMatchObject({revision:2,desired:'disabled'});
  await f.report(2,'disabled');
  expect((await f.http('PUT',off)).statusCode).toBe(200);
  expect((await f.http('PUT',{enabled:true,request_id:'on',expected_revision:2})).json()).toMatchObject({revision:3,desired:'enabled',disabled_through_revision:2});
});
it('closes relay, output and Task admission immediately, retains reads and requires a human to restore old work',async()=>{
  const f=setup(),tasks=f.ctx.gateway.tasks;
  const human={kind:'user' as const,id:'u1'},agent={kind:'agent' as const,id:'a',node_id:'n'};
  const graph=tasks.execute(human,'create',{title:'Old work',conversation_id:'chat',request_key:'create',mode:'dag',assignee:{type:'agent',id:'a'},status:'doing'});
  const added=tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:1,request_key:'add',change_note:'Queued work',operations:[{op:'add_task',container_id:'n1',client_ref:'later',title:'Later',status:'todo',assignee:{type:'agent',id:'a'}}]});
  const start=await f.ctx.gateway.handle(f.connection,'node.streaming_delta',{node_id:'n',agent_id:'a',conversation_id:'chat',kind:'turn_start',lifecycle_revision:1});
  await f.ctx.gateway.handle(f.connection,'node.streaming_delta',{node_id:'n',kind:'permission_request',message_id:start.payload.message_id,run_id:'run',lifecycle_revision:1,permission_request:{request_id:'approve',options:[{id:'allow_once'}]}});
  const send=(content:string)=>f.app.inject({method:'POST',url:'/im/v1/conversations/chat/messages',headers:{'x-user':'u1'},payload:{sender_user_id:'u1',content}});
  expect((await send('Before stop')).statusCode).toBe(201);
  expect(f.frames.find(frame=>frame.type==='relay.message')?.payload.lifecycle_revision).toBe(1);
  await f.report(1,'enabling');await f.report(1,'enabled');
  await f.http('PUT',{enabled:false,request_id:'off',expected_revision:1});
  const count=f.frames.filter(frame=>frame.type==='relay.message').length;
  const held=await send('During stop');expect(held.statusCode).toBe(201);
  expect(f.frames.filter(frame=>frame.type==='relay.message')).toHaveLength(count);
  expect(f.ctx.messaging.message(held.json().id).content).toBe('During stop');
  expect(f.ctx.messaging.message(start.payload.message_id)).toMatchObject({delivery_status:'failed',permission_requests:[{status:'invalidated'}]});
  expect(tasks.execute(human,'get',{graph_id:graph.graph_id,view:'all'}).nodes[0].status).toBe('paused');
  expect(tasks.executionSnapshot(agent,'chat').items).toEqual([]);
  await expect(f.ctx.gateway.handle(f.connection,'node.streaming_delta',{node_id:'n',kind:'message_completed',message_id:start.payload.message_id,final_content:'Late output',lifecycle_revision:1})).rejects.toThrow();
  await f.report(2,'disabled');await f.http('PUT',{enabled:true,request_id:'on',expected_revision:2});
  expect((await f.app.inject({method:'POST',url:'/im/v1/conversations/chat/permissions/approve',headers:{'x-user':'u1'},payload:{message_id:start.payload.message_id,decision:'allow_once'}})).statusCode).toBe(409);
  await expect(f.ctx.gateway.handle(f.connection,'agent.message',{node_id:'n',from_session_id:'agent:a|tool_call:late',to:'conversation:chat',text:'Old result',lifecycle_revision:1})).rejects.toThrow();
  const resume=(who:typeof human|typeof agent,id:string,revision:number,key:string)=>tasks.execute(who,'apply',{graph_id:graph.graph_id,base_revision:revision,request_key:key,change_note:'Resume',operations:[{op:'update_task',node_id:id,patch:{status:'doing'}}]});
  expect(()=>resume(agent,added.client_refs.later,3,'agent-resume')).toThrow();
  resume(human,'n1',3,'human-resume');
  expect(tasks.executionSnapshot(agent,'chat').items.map((n:any)=>n.node_id)).toEqual(['n1']);
  expect(tasks.execute(human,'get',{graph_id:graph.graph_id,view:'all'}).nodes.find((n:any)=>n.id===added.client_refs.later).status).toBe('todo');
});
it('does not wait for an in-flight Task validation and rejects the write when it finally returns',async()=>{
  const f=setup(),tasks=f.ctx.gateway.tasks;
  const graph=tasks.execute({kind:'user',id:'u1'},'create',{title:'Pending write',mode:'dag',conversation_id:'chat',request_key:'create',status:'doing',assignee:{type:'agent',id:'a'}});
  let release!:(value:any)=>void,entered!:()=>void;
  const checking=new Promise<void>(resolve=>{entered=resolve;});
  f.ctx.gateway.request=async()=>{entered();return new Promise(resolve=>{release=resolve;});};
  const writing=f.ctx.gateway.handle(f.connection,'task_graph.command',{node_id:'n',agent_id:'a',request_id:'write',lifecycle_revision:1,action:'apply',args:{graph_id:graph.graph_id,base_revision:1,request_key:'wait',change_note:'Wait',operations:[{op:'update_task',node_id:'n1',patch:{status:'waiting',wait:{reason:'External result pending',schedule_id:'schedule'}}}]}});
  await checking;
  expect((await f.http('PUT',{enabled:false,request_id:'off',expected_revision:1})).statusCode).toBe(202);
  expect(f.frames.some(frame=>frame.type==='agent.lifecycle.apply')).toBe(true);
  release({valid:true,owner_agent_id:'a',session_id:'s',next_check_at:new Date(Date.now()+60000).toISOString(),checked_at:new Date().toISOString()});
  expect((await writing).payload.ok).toBe(false);
  expect(tasks.execute({kind:'user',id:'u1'},'get',{graph_id:graph.graph_id,view:'all'}).nodes[0].status).toBe('paused');
});
it('retains durable stop intent on database reopen and old-node registration',async()=>{
  const {backup}=await import('node:sqlite'),{mkdtempSync,rmSync}=await import('node:fs'),{tmpdir}=await import('node:os'),{join}=await import('node:path');
  const {openDatabase}=await import('../src/db.js');
  const f=setup();await f.http('PUT',{enabled:false,request_id:'offline-off',expected_revision:1});
  const directory=mkdtempSync(join(tmpdir(),'lifecycle-reopen-')),path=join(directory,'im.db');
  await backup(f.db,path);
  const db=openDatabase(path);
  try {
    expect(db.prepare('SELECT * FROM agent_lifecycle WHERE agent_id=?').get('a')).toMatchObject({desired:'disabled',revision:2,request_id:'offline-off'});
    const ctx={...f.ctx,db};ctx.messaging=new Messaging(ctx);ctx.gateway=new Gateway(ctx);
    const ack=ctx.gateway.register(f.connection,{node_id:'n',agents:['a']});
    expect(ack.agent_lifecycles[0]).toMatchObject({desired:'disabled',revision:2,observed:'stop_unconfirmed',error_code:'node_upgrade_required'});
  }finally{db.close();rmSync(directory,{recursive:true,force:true});}
});
it('sends lifecycle authority in the real socket registration ACK before recovery and rejects replaced connections',async()=>{
  const {default:websocket}=await import('@fastify/websocket'),{default:WebSocket}=await import('ws'),{once}=await import('node:events');
  const {registerSockets}=await import('../src/gateway.js'),{digest}=await import('../src/identity.js'),{Frames}=await import('./e2e/helpers.js');
  const f=setup();await f.report(1,'enabling');await f.report(1,'enabled');
  await f.http('PUT',{enabled:false,request_id:'off',expected_revision:1});
  // Use a separate unstarted app so real upgrade hooks are installed before routes.
  const app=Fastify();apps.push(app);await app.register(websocket);registerSockets(app,f.ctx);
  f.db.prepare('UPDATE node_binding_state SET runtime_token_hash=? WHERE node_id=?').run(digest('lifecycle-runtime'),'n');
  const url=await app.listen({port:0,host:'127.0.0.1'});
  const socket=new WebSocket(url.replace('http:','ws:')+'/im/ws/gateway',{headers:{authorization:'Bearer lifecycle-runtime'}}),frames=new Frames(socket);
  try {
    await once(socket,'open');socket.send(JSON.stringify({type:'node.register',payload:{node_id:'n',agents:['a'],capabilities:{agent_lifecycle_v1:true}}}));
    const ack=await frames.next(()=>true);expect(ack.type).toBe('ack');
    expect(ack.payload.agent_lifecycles).toMatchObject([{desired:'disabled',revision:2,process_instance_id:'process-a'}]);
    await expect(f.report(2,'disabled')).rejects.toThrow('node_not_registered');
    socket.send(JSON.stringify({type:'agent.lifecycle.report',payload:{node_id:'n',agent_id:'a',revision:2,observed:'disabled',process_instance_id:'process-a',request_id:'stop-confirmed'}}));
    expect((await frames.next(frame=>frame.payload?.request_id==='stop-confirmed')).type).toBe('ack');
    expect((await f.http('GET')).json()).toMatchObject({observed:'disabled',applied_revision:2});
  }finally{const server=f.ctx.gateway.nodes.get('n')?.socket;const closed=server?once(server,'close'):Promise.resolve();socket.close();await closed;await app.close();}
});
it('continues historical Work synchronization and ACK while an old approval loses execution authority',async()=>{
  const {registerWorkRoutes}=await import('../src/work.js');
  const f=setup();registerWorkRoutes(f.app,f.ctx);
  f.db.prepare("UPDATE agent_profiles SET work_mode='global' WHERE agent_id='a'").run();
  const events=[
    {type:'session_registered',payload:{scope:'global_main'}},
    {type:'turn_started',payload:{lifecycle_revision:1}},
    {type:'permission_request',payload:{lifecycle_revision:1,request_id:'work-permission',options:[{id:'allow_once'}]}},
  ].map((event,i)=>({...event,seq:i+1,event_id:'work-'+i,root_agent_id:'a',session_id:'main',...(i?{turn_id:'turn'}:{})}));
  await f.report(1,'enabling');await f.report(1,'enabled');
  await f.http('PUT',{enabled:false,request_id:'off',expected_revision:1});
  const ack=await f.ctx.gateway.handle(f.connection,'agent.work.append',{node_id:'n',journal_id:'work',from_seq:1,events});
  expect(ack).toMatchObject({type:'agent.work.ack',payload:{through_seq:3}});
  await f.report(2,'disabled');await f.http('PUT',{enabled:true,request_id:'on',expected_revision:2});
  const response=await f.app.inject({method:'POST',url:'/im/v1/agents/a/work/permissions/work-permission',headers:{'x-user':'u1'},payload:{decision:'allow_once'}});
  expect(response.statusCode,response.body).toBe(409);
  expect(f.db.prepare('SELECT through_seq FROM agent_work_journals WHERE journal_id=?').get('work')).toMatchObject({through_seq:3});
});

it('keeps only old Task schedules frozen and releases the specific human-resumed Task',async()=>{
  const f=setup(),tasks=f.ctx.gateway.tasks,human={kind:'user' as const,id:'u1'};
  const graph=tasks.execute(human,'create',{title:'Waiting work',conversation_id:'chat',request_key:'waiting-create',mode:'dag',assignee:{type:'agent',id:'a'},status:'doing'});
  // Persist the already validated native Schedule reference as it exists before disable.
  const row=f.db.prepare('SELECT document_json FROM task_graphs WHERE graph_id=?').get(graph.graph_id) as {document_json:string};
  const document=JSON.parse(row.document_json);document.nodes[0].status='waiting';document.nodes[0].wait={schedule_id:'task-schedule',session_id:'s',owner_agent_id:'a',reason:'Waiting',next_check_at:new Date(Date.now()+60000).toISOString()};
  f.db.prepare('UPDATE task_graphs SET document_json=? WHERE graph_id=?').run(JSON.stringify(document),graph.graph_id);
  await f.report(1,'enabling');await f.report(1,'enabled');
  await f.http('PUT',{enabled:false,request_id:'freeze',expected_revision:1});
  const frozen=()=>f.ctx.gateway.handle(f.connection,'task.execution.frozen_schedules',{node_id:'n',agent_id:'a'});
  expect((await frozen()).payload.schedule_ids).toEqual(['task-schedule']);
  await f.report(2,'disabled');await f.http('PUT',{enabled:true,request_id:'restore',expected_revision:2});
  expect((await frozen()).payload.schedule_ids).toEqual(['task-schedule']);
  tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:2,request_key:'resume-one',change_note:'Resume',operations:[{op:'update_task',node_id:'n1',patch:{status:'doing'}}]});
  expect((await frozen()).payload.schedule_ids).toEqual([]);
});

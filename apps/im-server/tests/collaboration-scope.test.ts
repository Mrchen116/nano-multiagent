import {expect,it} from 'vitest';
import Fastify from 'fastify';
import {registerControlRoutes} from '../src/control-routes.js';
import {connectFixtureGateway} from './control-fixture.js';
import {personalFixture} from './personal-fixture.js';
import {Gateway} from '../src/gateway.js';
import {chatAllowed} from '../src/collaboration.js';

it('commits owner-only with retired backlog, preserves public history and other recipients, and starts fresh on reopening',async()=>{
  const f=personalFixture(), {db,ctx,service,principal,args}=f;
  const connection=connectFixtureGateway(f);
  const app=Fastify();registerControlRoutes(app,ctx);
  ctx.gateway.request=async (_node,_command,payload)=>({status:'applied',operation_id:payload.operation_id,candidate_fingerprint:payload.candidate_fingerprint,agent:payload.agent});
  db.exec("UPDATE conversations SET type='group' WHERE id='peer'; INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')");
  const send=(chat:string,sender:string,text:string)=>ctx.messaging.sendMessage({params:{conversation_id:chat},query:{},headers:{'x-user':sender},body:{sender_user_id:sender,content:text}} as any);
  const configure=(version:number,scope?:string,confirmWiden=false)=>app.inject({method:'PATCH',url:'/im/v1/agents/a/config',payload:{
    profile_version:version,display_name:'Agent',...(scope?{collaboration_scope:scope}:{}),...(confirmWiden?{confirm_scope_widen:true}:{})}});
  const admit=(message:{id:string;conversation_id:string})=>service.admitSource(principal,{...args,source_message_id:message.id,conversation_id:message.conversation_id});
  const relays=(id:string)=>db.prepare('SELECT status FROM relay_tasks WHERE message_id=?').all(id);
  const recipients=(id:string)=>db.prepare('SELECT recipient_id FROM message_receipts WHERE message_id=? ORDER BY recipient_id').all(id).map(r=>r.recipient_id);
  try {
    const before=await send('peer','u2','<mention type="user" target_id="u1"/> What do you think?');
    expect(admit(before)).toMatchObject({addressed_to_owner:true,addressed_to_agent:false,owner_direct:false,delivery:'participant'});
    expect(relays(before.id)).toEqual([{status:'queued'}]);expect(recipients(before.id)).toEqual(['a1','u1']);
    const obs=service.observations(principal,args).items.find(e=>e.message_id===before.id)!;
    expect(obs.addressed_to_owner).toBe(true);
    const restricted=await configure(1,'owner_only');
    expect(restricted.statusCode,restricted.body).toBe(200);
    expect(relays(before.id)).toEqual([{status:'cancelled'}]);expect(recipients(before.id)).toEqual(['u1']);
    expect(db.prepare("SELECT user_id FROM conversation_participants WHERE conversation_id='peer' ORDER BY user_id").all().map((r:any)=>r.user_id)).toEqual(['u1','u2']);
    const gateway=new Gateway(ctx);
    gateway.nodes.set(connection.node_id,connection);
    const relay=db.prepare('SELECT relay_task_id FROM relay_tasks WHERE message_id=?').get(before.id)!;
    const receipt=(stage:string)=>gateway.handle(connection,'node.delivery_receipt',{node_id:'n',relay_task_id:relay.relay_task_id,delivery_status:stage});
    await receipt('accepted');
    expect(recipients(before.id)).toEqual(['u1']);
    await receipt('sent');await receipt('read');
    expect(db.prepare("SELECT status FROM message_receipts WHERE recipient_id='a1' AND message_id=?").get(before.id)?.status).toBe(2);
    service.acknowledge(principal,{...args,event_ids:[obs.event_id],stage:'received'});
    const blocked=await send('peer','u1','<mention type="user" target_id="a1"/> Still here?');
    expect(blocked.delivery_status).toBe('completed');expect(relays(blocked.id)).toEqual([]);expect(recipients(blocked.id)).toEqual(['u2']);
    // Private PA exited the external group, yet retains silent observer access to its owner's group chat.
    expect(admit(blocked)).toMatchObject({allowed:true,delivery:'observer',owner_direct:false,owner_internal:false,addressed_to_agent:false});
    expect((await configure(2)).json().collaboration_scope).toBe('owner_only');
    expect(admit(await send('chat','u1','Owner direct'))).toMatchObject({allowed:true,owner_direct:true});
    db.prepare("INSERT INTO conversations(id,title,type,created_at) VALUES('colleague-dm','Colleague DM','direct',?)").run(new Date().toISOString());
    for (const id of ['u2','a1']) db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('colleague-dm',?)").run(id);
    const preFreeze=ctx.messaging.insertMessage('colleague-dm','u2','user','Pre-freeze DM',[],null,'completed');
    expect(admit(preFreeze)).toMatchObject({allowed:false});
    await expect(send('colleague-dm','u2','Third party direct')).rejects.toMatchObject({statusCode:403,detail:{code:'agent_private'}});
    expect((await configure(3,'team')).statusCode).toBe(409);
    expect((await configure(3,'team',true)).json().collaboration_scope).toBe('team');
    expect(service.observations(principal,args).items.find(e=>e.message_id===before.id)).toMatchObject({delivery:'observer',addressed_to_owner:true,addressed_to_agent:false});
    expect(admit(before)).toMatchObject({allowed:true,delivery:'observer',addressed_to_owner:true,addressed_to_agent:false});
    service.acknowledge(principal,{...args,event_ids:[obs.event_id],stage:'processed'});
    expect(service.observations(principal,args).items.map(e=>e.message_id)).not.toContain(before.id);
    expect(relays((await send('colleague-dm','u2','Reopened direct')).id)).toEqual([{status:'queued'}]);
    db.exec("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')");
    expect(relays((await send('peer','u2','New message')).id)).toEqual([{status:'queued'}]);
    expect(ctx.messaging.message(blocked.id).content).toBe(blocked.content);
  }finally{await app.close();}
});

it('uses original Feishu sender and authenticated targets in the private channel binding',()=>{
  const {db,ctx,service,principal,args}=personalFixture();
  db.exec(`UPDATE conversations SET owner_id='o1',config_agent_id='a',external_source='feishu',external_chat_id='feishu:app:dm:first' WHERE id='peer';
    INSERT INTO agent_channels VALUES('channel','o1','a','n','feishu',1,'{"app_id":"app"}','fp',1,'{"owner_open_id":"first"}','{}','key',1,1,'now','now');
    UPDATE agent_profiles SET collaboration_scope='owner_only'`);
  const facts={source_time:'2026-11-18T10:00:00.000Z',mentioned_bot:false,mentioned_owner:true,replied_to_bot:false,replied_to_owner:false,context_only:false,scope_skipped:false};
  const store=(sender:string)=>ctx.messaging.insertMessage('peer','u1','user','hello',[],null,'completed',{sender_source_id:sender,provider_facts:facts});
  const owner=store('first');
  expect(chatAllowed(db,'a',owner.id)).toBe(true);
  expect(chatAllowed(db,'a',store('peer').id)).toBe(false);
  db.exec("UPDATE conversations SET type='group',external_chat_id='feishu:app:group:g' WHERE id='peer'; UPDATE agent_profiles SET collaboration_scope='team'");
  const group=store('peer');
  const event=service.observations(principal,args).items.find(e=>e.message_id===group.id);
  expect(event).toMatchObject({addressed_to_agent:false,addressed_to_owner:true,owner_direct:false,provider_source_time:facts.source_time});
});

it('resolves an observed Feishu DM from its own app binding although every shadow includes the local owner',()=>{
  const {db,ctx,service,principal,args}=personalFixture();
  db.exec(`INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('other-bot','agent:other','Other','o1','now');
    INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,created_at,updated_at) VALUES('other','o1','n','Other','now','now');
    UPDATE conversations SET owner_id='o1',config_agent_id='other',external_source='feishu',external_chat_id='feishu:app:dm:peer' WHERE id='peer';
    INSERT INTO agent_channels VALUES('channel','o1','other','n','feishu',1,'{"app_id":"app"}','fp',1,'{"owner_open_id":"owner-open"}','{}','key',1,1,'now','now')`);
  const admit=(m:{id:string})=>service.admitSource(principal,{...args,source_message_id:m.id,conversation_id:'peer'});
  expect(admit(ctx.messaging.insertMessage('peer','other-bot','agent','To another person')))
    .toMatchObject({delivery:'observer',addressed_to_owner:false,addressed_to_agent:false});
  db.exec("UPDATE conversations SET external_chat_id='feishu:app:dm:owner-open' WHERE id='peer'");
  expect(admit(ctx.messaging.insertMessage('peer','other-bot','agent','To the owner')))
    .toMatchObject({delivery:'observer',addressed_to_owner:true,addressed_to_agent:false,owner_direct:false});
  expect(admit(ctx.messaging.insertMessage('peer','u1','user','Hello, other bot',[],null,'completed',{sender_source_id:'owner-open'})))
    .toMatchObject({is_owner:true,delivery:'observer',addressed_to_owner:false,addressed_to_agent:false,owner_direct:false});
});

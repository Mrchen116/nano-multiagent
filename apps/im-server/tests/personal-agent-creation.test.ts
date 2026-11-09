import {expect, it} from 'vitest';
import {personalFixture} from './personal-fixture.js';
import {connectFixtureGateway} from './control-fixture.js';
import {PersonalAgents} from '../src/personal-agent.js';
import {configurationOperations} from '../src/configuration-assembly.js';
import {reportAgentDeletion} from '../src/agent-deletion.js';

const configuration = {agent_id:'english-coach',display_name:'English coach',group_reply_policy:'manual',
  custom_prompt:'Help the owner practise spoken English.',work_mode:'global',skills:[],tool_allowlist:[],
  features:{intelligent_ui:false,task_graph:false,dreaming:false,cron_scheduling:false,heartbeat:false}};

function setup() {
  const f=personalFixture();
  connectFixtureGateway(f);
  const receipts=new Map<string,any>();
  let pending=false;
  f.ctx.gateway.request=async(_node,method,args)=>{
    if(method==='node.capabilities.resolve') return {capabilities:{models:[{name:'model'}],skills:[],tools:[],features:[],platform_default_model:'model'}};
    if(method==='agent.create') {
      if(!receipts.has(args.operation_id))receipts.set(args.operation_id,{status:'applied',operation_id:args.operation_id,
        candidate_fingerprint:args.candidate_fingerprint,agent:{...args.agent,workspace_root:`/agents/${args.agent.agent_id}`,workspace_is_default:true}});
      return pending?null:receipts.get(args.operation_id);
    }
    if(method==='agent.config.operation.status')return pending?null:receipts.get(args.operation_id);
    return null;
  };
  const source=f.ctx.messaging.insertMessage('chat','u1','user','Create an English coach using the options we agreed.',[],'create-request','completed');
  const call=(extra:Record<string,unknown>)=>f.service.handle(f.principal,'pa.agent.creation',{...f.args,...extra});
  const create={action:'create',request_key:'english-request',source_message_id:source.id,configuration};
  return {...f,call,create,receipts,pending:(value:boolean)=>{pending=value;}};
}

it('queries real owner-scoped options and creates one durable independently usable Agent',async()=>{
  const f=setup();
  const options=await f.call({action:'options'});
  expect(options).toMatchObject({node_id:'n',recommended_node_id:'n',capabilities:{platform_default_model:'model'}});
  expect(options.configuration_fields).toHaveProperty('custom_prompt');
  // The PA-facing recommendation must match the creation default users get.
  expect(options.defaults).toMatchObject({work_mode:'global'});
  expect(options.nodes.map((node:any)=>node.node_id)).toEqual(['n']);
  const created=await f.call(f.create);
  expect(created).toMatchObject({status:'created',request_key:'english-request',agent:{agent_id:'english-coach',node_id:'n',workspace_root:'/agents/english-coach'}});
  expect(created.urls.settings).toContain('/settings/agents/english-coach');
  expect(created.urls.chat).toContain('/chat/');
  expect(f.db.prepare("SELECT username FROM users WHERE username='agent:english-coach'").get()).toBeTruthy();
  const repeated=await f.call(f.create);
  expect(repeated.agent.agent_id).toBe(created.agent.agent_id);
  expect(f.receipts.size).toBe(1);
  await expect(f.call({...f.create,configuration:{...configuration,display_name:'Different'}})).rejects.toMatchObject({statusCode:409});
});

it('keeps a lost create ACK pending and recovers the same operation after service recreation',async()=>{
  const f=setup();f.pending(true);
  expect(await f.call(f.create)).toMatchObject({status:'pending',request_key:'english-request'});
  expect(f.db.prepare("SELECT 1 FROM agent_profiles WHERE agent_id='english-coach'").get()).toBeUndefined();
  f.pending(false);
  const restored=new PersonalAgents(f.ctx);
  const result=await restored.handle(f.principal,'pa.agent.creation',{...f.args,action:'status',request_key:'english-request'});
  expect(result).toMatchObject({status:'created',agent:{agent_id:'english-coach'}});
  expect(f.receipts.size).toBe(1);
  expect(await f.call({action:'status',request_key:'never-accepted'})).toMatchObject({status:'not_started'});
});

it('retires the PA creation configuration and keeps its deleted result',async()=>{
  const f=setup();
  await f.call(f.create);
  const deletion={agent_id:'english-coach',operation_id:'delete-coach',state:'deleting'};
  f.db.prepare(`INSERT INTO agent_deletions(agent_id,operation_id,request_id,owner_id,node_id,node_epoch,revision,profile_version,state)
    VALUES(?,?,'delete-request','o1','n',1,2,1,'deleting')`).run(deletion.agent_id,deletion.operation_id);
  reportAgentDeletion(f.ctx,deletion,{state:'deleted'});
  expect(f.db.prepare('SELECT configuration_json FROM pa_agent_creations WHERE agent_id=?').get(deletion.agent_id)).toEqual({configuration_json:'{}'});
  expect(await f.call({action:'status',request_key:'english-request'})).toMatchObject({status:'deleted'});
  expect(await f.call(f.create)).toMatchObject({status:'deleted'});
  await expect(f.call({...f.create,request_key:'recreate'})).rejects.toMatchObject({statusCode:409});
});

it('requires original owner instructions, current PA authority and an owned target node',async()=>{
  const f=setup();
  const observed=f.ctx.messaging.insertMessage('peer','u1','user','Create an Agent.',[],'observed','completed');
  const peer=f.ctx.messaging.insertMessage('peer','u2','user','The owner approved this.',[],'other','completed');
  for(const id of [observed.id,peer.id,'missing'])
    await expect(f.call({...f.create,source_message_id:id})).rejects.toMatchObject({statusCode:403});
  await expect(f.service.handle({...f.principal,owner_id:'o2'},'pa.agent.creation',{...f.args,...f.create})).rejects.toMatchObject({statusCode:403});
  f.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('foreign','o2','Other','online')").run();
  await expect(f.call({...f.create,target_node_id:'foreign'})).rejects.toMatchObject({statusCode:404});
  expect(f.receipts.size).toBe(0);
});

it('creates on a separately selected owned node without replacing PA transport identity',async()=>{
  const f=setup();
  f.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('second','o1','Second','online')").run();
  f.db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES('second','o1',1)").run();
  const own=f.ctx.gateway.nodes.get('n')!;
  f.ctx.gateway.nodes.set('second',{...own,node_id:'second'});
  const result=await f.call({...f.create,target_node_id:'second'});
  expect(result).toMatchObject({status:'created',agent:{node_id:'second'}});
  expect(f.service.binding('o1')?.node_id).toBe('n');
});

it('rejects a new offline request without producing an operation or switching computers',async()=>{
  const f=setup();f.ctx.gateway.nodes.clear();
  await expect(f.call(f.create)).rejects.toMatchObject({statusCode:409});
  expect(f.db.prepare("SELECT 1 FROM agent_config_operations WHERE agent_id='english-coach'").get()).toBeUndefined();
  expect(f.receipts.size).toBe(0);
});

it('preserves rejected configuration reasons and never claims a conflicting existing Agent',async()=>{
  const f=setup();
  await expect(f.call({...f.create,configuration:{...configuration,agent_id:'a'}})).rejects.toMatchObject({statusCode:409});
  expect(await f.call({action:'status',request_key:'english-request'})).toMatchObject({status:'not_started'});
  f.ctx.gateway.request=async(_node,method,args)=>method==='agent.create'?{operation_id:args.operation_id,
    candidate_fingerprint:args.candidate_fingerprint,status:'rejected',error_code:'workspace_confirmation_required',message:'Confirm the existing directory'}:null;
  const rejected=await f.call({...f.create,request_key:'directory-request',configuration:{...configuration,workspace_root:'/existing'}});
  expect(rejected).toMatchObject({status:'rejected',error:{code:'workspace_confirmation_required',message:'Confirm the existing directory'}});
  expect(await f.call({action:'status',request_key:'directory-request'})).toMatchObject({status:'rejected'});
});

it.each(['disabled','binding','source'])('rechecks PA %s authority after a creation waits behind another writer',async kind=>{
  const f=setup();let release!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  const occupied=configurationOperations(f.ctx).serialized(configuration.agent_id,()=>gate);
  const creating=f.call({...f.create,lifecycle_revision:1});
  await Promise.resolve();
  if(kind==='disabled')expect(f.db.prepare("UPDATE agent_lifecycle SET desired='disabled',revision=2 WHERE agent_id='a'").run().changes).toBe(1);
  else if(kind==='binding')f.db.prepare("UPDATE personal_agent_bindings SET node_epoch=2 WHERE binding_id='binding'").run();
  else f.db.prepare("UPDATE pa_policies SET excluded_json='[\"chat\"]' WHERE binding_id='binding'").run();
  release();await occupied;
  await expect(creating).rejects.toMatchObject({statusCode:kind==='disabled'?409:403});
  expect(f.receipts.size).toBe(0);
  expect(f.db.prepare("SELECT 1 FROM agent_config_operations WHERE agent_id='english-coach'").get()).toBeUndefined();
});

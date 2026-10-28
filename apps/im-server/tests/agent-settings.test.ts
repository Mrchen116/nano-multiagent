import Fastify from 'fastify';
import {expect, it, vi} from 'vitest';
import {registerControlRoutes} from '../src/control-routes.js';
import {fixture, connectFixtureGateway} from './control-fixture.js';
import {one} from '../src/context.js';

function setup() {
  const f=fixture();
  const connection=connectFixtureGateway(f);
  const app=Fastify();
  app.setErrorHandler((error:any,_req,reply)=>reply.code(error.statusCode??500).send({detail:error.detail??error.message}));
  registerControlRoutes(app,f.ctx);
  return {...f,app,connection};
}
const capabilities={models:[{name:'model',display_name:'Model',reasoning:{kind:'selectable',levels:['low','high'],default:'high'}},{name:'unused-secret-model'}],
  inherited_approval_rules:'codex',platform_default_model:'model',features:[{key:'heartbeat',default_on:true}],tools:[{name:'task_graph',description:'Tasks'},{name:'not-selected'}],
  skills:[{name:'enabled',source_group:'global'},{name:'excluded',source_group:'workspace'}]};

it('keeps older Gateway capabilities without optional Features editable',async()=>{
  const {app,ctx}=setup();
  const {features: _features,...legacy}=capabilities;
  ctx.gateway.request=async()=>({capabilities:legacy});
  try {
    expect((await app.inject('/im/v1/agents/a/capabilities')).json()).toMatchObject({features:[]});
    expect((await app.inject('/im/v1/agents/a/settings')).json()).toMatchObject({ready:true,node:{state:'online'},live_capabilities:{features:[]},display:{source:'current',error:null}});
  } finally {await app.close();}
});

it('persists only selected display metadata and reads committed settings while offline or pending',async()=>{
  const {app,ctx,db}=setup();
  db.prepare("UPDATE agent_profiles SET skills_selection_mode='explicit_denylist',skills_json='[\"excluded\"]'").run();
  ctx.gateway.request=vi.fn(async()=>({capabilities}));
  try {
    const live=await app.inject('/im/v1/agents/a/settings');
    expect(live.statusCode,live.body).toBe(200);
    expect(live.headers['cache-control']).toContain('no-store');
    expect(live.json()).toMatchObject({ready:true,node:{state:'online'},display:{source:'current',data:{derived_current:true,reasoning:{value:'high',source:'inherited'},skills:[{name:'enabled',enabled:true},{name:'excluded',enabled:false}]}}});
    expect(live.json().live_capabilities.inherited_approval_rules).toBe('codex');
    expect(live.json().display.data.inherited_approval_rules).toBe('codex');
    const saved=one(db,'SELECT data_json FROM agent_settings_snapshots')!.data_json;
    expect(saved).not.toContain('unused-secret-model'); expect(saved).not.toContain('not-selected'); expect(saved).not.toContain('levels');
    ctx.gateway.nodes.clear();
    const offline=await app.inject('/im/v1/agents/a/settings');
    expect(offline.json()).toMatchObject({ready:false,live_capabilities:null,node:{state:'offline'},display:{source:'last_known'}});
    expect(offline.json().display.data.inherited_approval_rules).toBe('codex');
    expect(ctx.gateway.request).toHaveBeenCalledTimes(1);
    db.prepare("UPDATE agent_profiles SET profile_version=2,default_model='new-model',reasoning_effort='low',features_json='{\"heartbeat\":false}',skills_json='[\"enabled\"]'").run();
    const changed=(await app.inject('/im/v1/agents/a/settings')).json();
    expect(changed.display.data).toMatchObject({derived_current:false,models:[{name:'new-model'}],reasoning:{value:'low',source:'explicit'},features:expect.arrayContaining([{key:'heartbeat',enabled:false,source:'explicit',label_i18n:'',help_i18n:''}])});
    expect(changed.display.data.inherited_approval_rules).toBeNull();
    expect(changed.display.data.features.filter((feature:any)=>feature.key!=='heartbeat').every((feature:any)=>feature.enabled===null)).toBe(true);
    expect(changed.display.data.skills.find((s:any)=>s.name==='enabled').enabled).toBe(false);
    db.prepare("INSERT INTO agent_config_operations(operation_id,root_operation_id,agent_id,owner_id,node_id,operation_kind,status,candidate_json,candidate_fingerprint,created_at,updated_at) VALUES('pending','pending','a','o1','n','update','pending','{\"secret\":true}','hash',datetime('now'),datetime('now'))").run();
    const pending=(await app.inject('/im/v1/agents/a/settings')).json();
    expect(pending.pending_operation).toEqual({operation_id:'pending',status:'pending'}); expect(pending.config.profile_version).toBe(2); expect(JSON.stringify(pending)).not.toContain('secret');
    db.prepare('UPDATE node_binding_state SET node_epoch=2').run();
    expect((await app.inject('/im/v1/agents/a/settings')).json().display).toMatchObject({source:'unavailable',data:null});
  } finally {await app.close();}
});

it.each(['disconnect','reconnect','version','epoch','workspace','node','owner','space','session'])('rejects late settings data after %s changes',async change=>{
  const {app,ctx,db,connection}=setup();
  ctx.gateway.request=async()=>{
    if(change==='disconnect')connection.socket.readyState=3 as never;
    if(change==='reconnect')ctx.gateway.nodes.set('n',{...connection});
    if(change==='version')db.prepare('UPDATE agent_profiles SET profile_version=profile_version+1').run();
    if(change==='workspace')db.prepare("UPDATE agent_profiles SET workspace_root='/new'").run();
    if(change==='node')db.prepare("UPDATE agent_profiles SET node_id='new'").run();
    if(change==='epoch')db.prepare('UPDATE node_binding_state SET node_epoch=2').run();
    if(change==='owner')db.prepare("UPDATE agent_profiles SET owner_id='o2'").run();
    if(change==='space')db.prepare("UPDATE agent_profiles SET space_id='personal:o2'").run();
    if(change==='session')ctx.identity.authenticateRequest=()=>{throw Object.assign(new Error('unauthorized'),{statusCode:401});};
    return {capabilities};
  };
  try {
    const response=await app.inject('/im/v1/agents/a/settings');
    if(['owner','space','session'].includes(change))expect(response.statusCode).toBe(change==='session'?401:404);
    else expect(response.json()).toMatchObject({ready:false,live_capabilities:null,display:{source:'unavailable'}});
    expect(one(db,'SELECT * FROM agent_settings_snapshots')).toBeUndefined();
  } finally {await app.close();}
});

it('keeps unavailable sections distinct from successful empty results and strips runtime diagnostics',async()=>{
  const {app,ctx,db}=setup();
  ctx.gateway.request=async(_node,action)=> action==='node.plugins.request'
    ?{plugins:{workspace:'/forged',entries:[{name:'test',enabled:true,state:'failed',diagnostics:['SECRET'],rows:[{id:'tool',name:'Tool',secret:'SECRET'}]}],error:'SECRET',pending:{action:'set_bundle',target:'test',phase:'waiting',secret:'SECRET'}}}
    :{jobs:[]};
  try {
    const plugins=(await app.inject('/im/v1/agents/a/settings/sections/plugins')).json();
    expect(plugins.data.workspace).toBe('/agent'); expect(JSON.stringify(plugins)).not.toContain('SECRET');
    expect((await app.inject('/im/v1/agents/a/settings/sections/cron')).json()).toMatchObject({source:'current',data:[]});
    expect((await app.inject('/im/v1/agents/a/cron/jobs')).json()).toEqual([]);
    ctx.gateway.request=async()=>{throw Object.assign(new Error('timeout'),{statusCode:504});};
    expect((await app.inject('/im/v1/agents/a/settings/sections/cron')).json()).toMatchObject({source:'last_known',data:[],error:{code:'timeout'}});
    expect((await app.inject('/im/v1/agents/a/cron/jobs')).statusCode).toBe(504);
    ctx.gateway.nodes.clear();
    expect((await app.inject('/im/v1/agents/a/settings/sections/usage')).json()).toMatchObject({source:'unavailable',data:null,error:{code:'offline'}});
    expect((await app.inject('/im/v1/agents/a/cron/jobs')).statusCode).toBe(503);
    expect((await app.inject({url:'/im/v1/agents/a/settings',headers:{'x-user':'u2'}})).statusCode).toBe(404);
    expect(one(db,"SELECT * FROM agent_settings_snapshots WHERE section='usage'")).toBeUndefined();
  } finally {await app.close();}
});

it('rejects offline setting writes before creating operations or dispatching node commands',async()=>{
  const {app,ctx,db,connection}=setup(); connection.socket.readyState=3 as never;
  ctx.gateway.request=vi.fn(async()=>null as never);
  try {
    for(const request of [
      {method:'PATCH' as const,url:'/im/v1/agents/a/config',payload:{display_name:'Changed',group_reply_policy:'manual',profile_version:1}},
      {method:'POST' as const,url:'/im/v1/agents/a/plugins',payload:{action:'remove_bundle',target:'test'}},
      {method:'DELETE' as const,url:'/im/v1/agents/a/cron/jobs/job'},
      {method:'POST' as const,url:'/im/v1/agents/a/channels',payload:{provider:'feishu',config:{app_id:'app'},credentials:{mode:'replace',app_secret:'secret'}}},
    ]) {
      const result=await app.inject(request); expect(result.statusCode,result.body).toBe(409); expect(result.json().detail.code).toBe('agent_node_offline');
    }
    expect(one(db,'SELECT * FROM agent_config_operations')).toBeUndefined();
    expect(one(db,'SELECT * FROM channel_manifest_heads')).toBeUndefined();
    expect(one(db,'SELECT display_name FROM agent_profiles')?.display_name).toBe('Agent'); expect(ctx.gateway.request).not.toHaveBeenCalled();
  } finally {await app.close();}
});

it('keeps channel revisions and removal receipts unchanged for every offline mutation',async()=>{
  const {ChannelService}=await import('../src/channels.js');
  const {generateKeyPairSync}=await import('node:crypto');
  const {app,ctx,db}=setup();
  const publicKey=generateKeyPairSync('x25519').publicKey.export({format:'jwk'}).x!;
  db.prepare("INSERT INTO node_credential_keys(node_id,owner_id,key_id,algorithm,public_key,updated_at) VALUES('n','o1','key','X25519',?,datetime('now'))").run(Buffer.from(publicKey,'base64url').toString('base64'));
  const channels=new ChannelService(db),created=channels.create('o1','a',{provider:'feishu',config:{app_id:'app'},credentials:{mode:'replace',app_secret:'secret'}});
  const id=created.resource.channel_id;
  ctx.gateway.nodes.clear(); ctx.gateway.send=vi.fn(()=>false);
  const before=one(db,'SELECT * FROM agent_channels'); const head=one(db,'SELECT * FROM channel_manifest_heads');
  try {
    for(const request of [
      {method:'PATCH' as const,url:`/im/v1/agents/a/channels/${id}`,payload:{channel_revision:1,enabled:false,config:{app_id:'changed'},credentials:{mode:'replace',app_secret:'new-secret'}}},
      {method:'DELETE' as const,url:`/im/v1/agents/a/channels/${id}?channel_revision=1`},
      {method:'POST' as const,url:`/im/v1/agents/a/channels/${id}/actions/reconnect`},
    ]) expect((await app.inject(request)).json()).toMatchObject({detail:{code:'agent_node_offline'}});
    expect(one(db,'SELECT * FROM agent_channels')).toEqual(before);expect(one(db,'SELECT * FROM channel_manifest_heads')).toEqual(head);
    expect(one(db,'SELECT * FROM agent_channel_removals')).toBeUndefined();
    expect((await app.inject({method:'PATCH',url:`/im/v1/agents/a/channels/${id}`,headers:{'x-user':'u2'},payload:{}})).statusCode).toBe(404);
    expect((await app.inject({method:'POST',url:'/im/v1/agents/a/channels/missing/actions/reconnect'})).statusCode).toBe(404);
    channels.delete('o1','a',id,1);
    const removal=one(db,'SELECT * FROM agent_channel_removals');
    expect((await app.inject({method:'POST',url:`/im/v1/agents/a/channel-removals/${id}/actions/retry`})).json()).toMatchObject({detail:{code:'agent_node_offline'}});
    expect(one(db,'SELECT * FROM agent_channel_removals')).toEqual(removal);expect(ctx.gateway.send).not.toHaveBeenCalled();
  } finally {await app.close();}
});

it('recovers an already accepted config operation and keeps committed settings visible while confirmation is pending',async()=>{
  const {app,ctx,db}=setup();
  let confirmed=false;
  let applied: Record<string,unknown> | null = null;
  const calls:string[]=[];
  ctx.gateway.request=async(_node,action,payload)=>{
    calls.push(action);
    if(action==='agent.capabilities.resolve')return {capabilities};
    if (action==='agent.config.apply') applied={status:'applied',operation_id:payload.operation_id,candidate_fingerprint:payload.candidate_fingerprint,agent:payload.agent};
    return confirmed ? applied! : null as never;
  };
  try {
    const patched=await app.inject({method:'PATCH',url:'/im/v1/agents/a/config',payload:{display_name:'Accepted',group_reply_policy:'manual',profile_version:1}});
    expect(patched.statusCode).toBe(503);
    const pending=(await app.inject('/im/v1/agents/a/settings')).json();
    expect(pending).toMatchObject({ready:false,config:{display_name:'Agent',profile_version:1},pending_operation:{status:'pending'}});
    ctx.gateway.nodes.clear();
    const count=calls.length;
    expect((await app.inject('/im/v1/agents/a/settings')).json()).toMatchObject({ready:false,config:{display_name:'Agent'},pending_operation:{status:'pending'}});
    expect(calls).toHaveLength(count);
    connectFixtureGateway({ctx,db});confirmed=true;
    const recovered=(await app.inject('/im/v1/agents/a/settings')).json();
    expect(recovered).toMatchObject({ready:true,config:{display_name:'Accepted',profile_version:2},pending_operation:null});
    expect(one(db,'SELECT COUNT(*) AS n FROM agent_config_operations')?.n).toBe(1);
  } finally {await app.close();}
});

it('rejects offline PA policy and name changes while preserving existing source access',async()=>{
  const {personalFixture}=await import('./personal-fixture.js');
  const {registerPersonalAgentRoutes}=await import('../src/personal-agent.js');
  const {ctx,db}=personalFixture(),app=Fastify();
  registerPersonalAgentRoutes(app,ctx);
  const before=one(db,'SELECT * FROM pa_policies');
  try {
    expect((await app.inject({method:'PATCH',url:'/im/v1/personal-agent/policy',payload:{expected_revision:1,excluded_conversation_ids:['peer']}})).statusCode).toBe(409);
    expect((await app.inject({method:'PATCH',url:'/im/v1/personal-agent',payload:{display_name:'Changed'}})).statusCode).toBe(409);
    expect(one(db,'SELECT * FROM pa_policies')).toEqual(before);expect(one(db,'SELECT * FROM agent_config_operations')).toBeUndefined();
    connectFixtureGateway({ctx,db});
    expect((await app.inject({method:'PATCH',url:'/im/v1/personal-agent/policy',payload:{expected_revision:1,excluded_conversation_ids:['peer']}})).statusCode).toBe(200);
    expect(one(db,'SELECT revision FROM pa_policies')?.revision).toBe(2);
  } finally {await app.close();}
});

it('fences section reads and retains only safe usage references across failed refreshes',async()=>{
  const {app,ctx,db}=setup();
  ctx.gateway.request=async()=>({usage:{statistics_since:'2026-10-28T00:00:00Z',period_start:'2026-09-29',period_end:'2026-10-28',skills:[{statistics_since:'2026-10-28T00:00:00Z',name:'skill',source:'user',state:'active',use_count:2,body:'SECRET',session_refs:[{session_id:'s',tool_call_id:'c',timestamp:'then',location:'skill',arguments:'SECRET'}]}],heatmap_data:[2],health:{created_auto_total:1,active_auto_total:1,used_auto_total:1,secret:'SECRET'}}});
  try {
    const current=(await app.inject('/im/v1/agents/a/settings/sections/usage')).json();
    expect(current).toMatchObject({source:'current',data:{skills:[{name:'skill',use_count:2,session_refs:[{session_id:'s'}]}]}});
    expect(JSON.stringify(current)).not.toContain('SECRET');
    ctx.gateway.request=async()=>{ db.prepare('UPDATE node_binding_state SET node_epoch=2').run();return {usage:{skills:[]}}; };
    const stale=(await app.inject('/im/v1/agents/a/settings/sections/usage')).json();
    expect(stale).toMatchObject({source:'unavailable',data:null,error:{code:'read_failed'}});
    expect(JSON.parse(one(db,"SELECT data_json FROM agent_settings_snapshots WHERE section='usage'")!.data_json).skills).toHaveLength(1);
    db.prepare('UPDATE node_binding_state SET node_epoch=1').run();
    ctx.gateway.request=async()=>{ctx.identity.authenticateRequest=()=>{throw Object.assign(new Error('unauthorized'),{statusCode:401});};return {jobs:[]};};
    expect((await app.inject('/im/v1/agents/a/settings/sections/cron')).statusCode).toBe(401);
    expect(one(db,"SELECT * FROM agent_settings_snapshots WHERE section='cron'")).toBeUndefined();
  } finally {await app.close();}
});


it('rejects legacy live and cached usage while retaining fresh offline statistics', async () => {
  const {app,ctx,db,connection}=setup();
  const fresh={statistics_since:'2026-10-28T00:00:00Z',period_start:'2026-09-29',period_end:'2026-10-28',
    skills:[{skill_id:'skill',name:'skill',use_count:75,statistics_since:'2026-10-28T00:00:00Z',statistics:{other:{use_count:999}}}],heatmap_data:[75]};
  ctx.gateway.request=async()=>({usage:fresh});
  try {
    const live=(await app.inject('/im/v1/agents/a/settings/sections/usage')).json();
    const direct=(await app.inject('/im/v1/agents/a/skills/usage')).json();
    expect(direct).toEqual(live.data);
    expect(JSON.stringify(direct)).not.toContain('other');
    ctx.gateway.nodes.clear();
    expect((await app.inject('/im/v1/agents/a/settings/sections/usage')).json()).toMatchObject({source:'last_known',captured_at:live.captured_at,data:live.data});
    db.prepare("UPDATE agent_settings_snapshots SET data_json=? WHERE section='usage'").run(JSON.stringify({skills:[{use_count:999}],heatmap_data:[60]}));
    expect((await app.inject('/im/v1/agents/a/settings/sections/usage')).json()).toMatchObject({source:'unavailable',data:null,error:{code:'offline'}});
    ctx.gateway.nodes.set('n',connection);
    ctx.gateway.request=async()=>({usage:{skills:[{use_count:999}],heatmap_data:[60]}});
    expect((await app.inject('/im/v1/agents/a/settings/sections/usage')).json()).toMatchObject({source:'unavailable',data:null,error:{code:'read_failed'}});
    expect((await app.inject('/im/v1/agents/a/skills/usage')).statusCode).toBe(502);
    ctx.gateway.request=async()=>{throw new Error('failed');};
    expect((await app.inject('/im/v1/agents/a/settings/sections/usage')).json()).toMatchObject({source:'unavailable',data:null,error:{code:'read_failed'}});
  } finally {await app.close();}
});

it('preserves fixed context and personal tools in settings capabilities', async () => {
  const {app,ctx}=setup();
  ctx.gateway.request=async()=>({capabilities:{...capabilities,fixed_tools:['new_context','personal_sources']}});
  try {
    const legacy=(await app.inject('/im/v1/agents/a/capabilities')).json();
    const settings=(await app.inject('/im/v1/agents/a/settings')).json();
    expect(settings.live_capabilities.fixed_tools).toEqual(legacy.fixed_tools);
    expect(settings.live_capabilities.fixed_tools).toEqual(['new_context','personal_sources']);
  } finally {await app.close();}
});

it('resolves approval for the owned node and exact target workspace', async () => {
  const {app,ctx}=setup();
  ctx.gateway.request=vi.fn(async()=>({inherited_approval_rules:'nano',private_config:'never expose'}));
  try {
    const result=await app.inject('/im/v1/nodes/n/approval?workspace_root=%2Fcustom%20space');
    expect(result.statusCode,result.body).toBe(200);
    expect(result.json()).toEqual({inherited_approval_rules:'nano'});
    expect(ctx.gateway.request).toHaveBeenCalledWith('n','node.approval.resolve',{workspace_root:'/custom space'});
    expect((await app.inject('/im/v1/nodes/n/approval')).statusCode).toBe(422);
    expect((await app.inject('/im/v1/nodes/unknown/approval?workspace_root=%2Fcustom')).statusCode).toBe(404);
    expect(ctx.gateway.request).toHaveBeenCalledTimes(1);
  } finally {await app.close();}
});

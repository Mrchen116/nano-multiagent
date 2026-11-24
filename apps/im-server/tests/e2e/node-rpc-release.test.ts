import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { ChannelKey } from '@nano/channels';
import { expect, it, vi } from 'vitest';
import { createServer } from '../../src/server.js';
import { digest } from '../../src/identity.js';
import type { ImContext } from '../../src/context.js';

// Frozen wire examples from v2.1.0 (ac275ecc78f96679d21273b27cee7f5b54f5268e):
// apps/im-server/src/node-rpc-contracts.ts, apps/node/src/{main,capability-requests}.ts.
// Never derive these pairs or bodies from the current command catalogue.
function releaseSamples(workspace: string): [string, string, object, object][] {
  const agent = {agent_id:'global'};
  const mutation = {agent, candidate_fingerprint:'obsolete', expected_previous_fingerprint:null};
  const preview = {features:{task_graph:false,intelligent_ui:false,memory_curation:false,skill_creation:false,dreaming:false,cron_scheduling:false,heartbeat:false}, tool_ids:[], skill_ids:[], skills_selection_mode:'explicit_denylist', scenario:'direct'};
  return [
    ['agent.create', 'agent.created', {...mutation, operation_id:'create'}, {status:'rejected',operation_id:'create'}],
    ['agent.config.apply', 'agent.config.apply.result', {...mutation, expected_previous_fingerprint:'previous', operation_id:'apply'}, {status:'rejected',operation_id:'apply'}],
    ['agent.config.operation.status', 'agent.config.operation.status.result', {operation_id:'unknown'}, {status:'pending',operation_id:'unknown'}],
    ['agent.config.get', 'agent.config', agent, {agent}],
    ['agent.capabilities.resolve', 'agent.capabilities', agent, {capabilities:{tools:expect.any(Array)}}],
    ['node.capabilities.resolve', 'node.capabilities', {workspace_root:workspace}, {capabilities:{skills:expect.any(Array)}}],
    ['node.approval.resolve', 'node.approval.resolve.result', {workspace_root:workspace}, {inherited_approval_rules:expect.anything()}],
    ['agent.prompt.preview.request', 'agent.prompt.preview', {...preview,...agent}, {preview:{prompt:expect.any(String)}}],
    ['node.prompt.preview.request', 'node.prompt.preview', {...preview,workspace_root:workspace}, {preview:{section_count:expect.any(Number)}}],
    ['node.plugins.request', 'node.plugins', {...agent,action:'list_bundles'}, {plugins:expect.any(Object)}],
    ['node.skills.usage.request', 'node.skills.usage', agent, {usage:{...agent,skills:expect.any(Array)}}],
    ['agent.capability-usage.request', 'agent.capability-usage', agent, {usage:{active_schedules:0}}],
    ['node.heartbeat.md.request', 'node.heartbeat.md', {workspace_root:workspace}, {content:'historic heartbeat'}],
    ['node.agent.role.request', 'node.agent.role', agent, {role:{content:expect.any(String)}}],
    ['node.cron.jobs.request', 'node.cron.jobs', {workspace_root:workspace}, {jobs:[]}],
    ['node.cron.delete.request', 'node.cron.delete', {...agent,job_id:'absent',operation_id:'delete',actor_user_id:'owner'}, {deleted:false}],
    ['node.setup.request', 'node.setup', {action:'status'}, {revision:expect.any(String),services:expect.any(Array)}],
    ['node.distill.prompt.request', 'node.distill.prompt', {sources:[{conversation_id:'source',source_agent_id:'global'}],execution_agent_id:'absent',target_scope:'agent'}, {error_code:'execution_unavailable'}],
    ['session.fork.request', 'session.fork.result', {...agent,source_conversation_id:'source',new_conversation_id:'target',fork_point:{message_id:'message'}}, {ok:false,error:expect.any(String)}],
    ['agent.deletion.preview', 'agent.deletion.preview.result', {agent_id:'absent'}, {}],
    ['task.execution.state', 'task.execution.state.result', agent, {state:expect.any(String)}],
    ['task.wait.validate', 'task.wait.validate.result', {...agent,conversation_id:'source',graph_id:'graph',node_id:'task',schedule_id:'absent'}, {valid:false}],
  ];
}

// For mixed-release acceptance, extract and build the pinned tag independently.
// Set NANO_RPC_V210_IM_ROOT or NANO_RPC_V210_NODE_ROOT to its absolute directory.
// The default runs current production code at both real endpoints.
it('exchanges the released RPC frames and submits a reconstructed historical Global permission through HTTP', async () => {
  const oldImRoot = process.env.NANO_RPC_V210_IM_ROOT;
  const oldNodeRoot = process.env.NANO_RPC_V210_NODE_ROOT;
  const home = await mkdtemp(join(tmpdir(), 'nano-rpc-release-'));
  const startCenter: typeof createServer = oldImRoot
    ? (await import(/* @vite-ignore */ pathToFileURL(join(oldImRoot,'apps/im-server/lib/server.js')).href)).createServer
    : createServer;
  const app = await startCenter({dbPath:join(home,'im.db'),publicUrl:'http://127.0.0.1'});
  const ctx = app.getDecorator<ImContext>('im');
  let node: ReturnType<typeof spawn> | undefined, exited: Promise<unknown> | undefined, log = '';
  try {
    const base = await app.listen({port:0,host:'127.0.0.1'});
    const owner = await ctx.identity.register('owner','test-password','Owner');
    ctx.identity.initializeCompany(owner.user.id);
    const nodeId = 'release-node', runtimeToken = 'release-runtime';
    ctx.db.prepare('INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES(?,?,?,?)').run(nodeId,owner.user.id,nodeId,'offline');
    const key = (await ChannelKey.load(join(home,'channel-credentials-v1.pem'))).registration;
    ctx.identity.enrollDevice(nodeId,key.credential_public_key,key.credential_key_id);
    ctx.db.prepare('UPDATE node_binding_state SET node_epoch=2,runtime_token_hash=? WHERE node_id=?').run(digest(runtimeToken),nodeId);
    const workspace = join(home,'global'), config = join(home,'gateway.yaml');
    await mkdir(join(workspace,'.nanoassistant'),{recursive:true});
    await writeFile(join(workspace,'.nanoassistant','HEARTBEAT.md'),'historic heartbeat');
    await writeFile(config,JSON.stringify({
      node:{node_id:nodeId,user_id:owner.user.id,workspace_base:join(home,'workspaces')},
      im_service:{url:base,token:runtimeToken},
      agents:[{agent_id:'global',workspace_root:workspace,work_mode:'global',tool_allowlist:[],
        features:{task_graph:false,intelligent_ui:false,memory_curation:false,skill_creation:false,dreaming:false}}],
      llm:{default_model:'fixture',providers:[{name:'test',base_url:'http://127.0.0.1:9',api_key:'fixture',models:[{name:'fixture'}]}]},
    }));
    const outbound = vi.spyOn(ctx.gateway,'send'), inbound = vi.spyOn(ctx.gateway,'handle');
    node = spawn(process.execPath,[resolve(oldNodeRoot ?? '.', 'apps/node/lib/main.js'),'--config',config],{
      stdio:['ignore','ignore','pipe'],env:{...process.env,HOME:home,NANO_OWNER_CONFIG_ROOT:home},
    });
    node.stderr!.on('data', bytes => { log += String(bytes); });
    exited = once(node,'exit');
    await expect.poll(() => ctx.db.prepare("SELECT observed FROM agent_lifecycle WHERE agent_id='global'").get()?.observed,
      {timeout:40_000}).toBe('enabled');
    expect(inbound.mock.calls.find(([,type])=>type==='node.register')?.[2]).toMatchObject({
      agents:['global'],release:{kind:'source'},capabilities:{agent_lifecycle_v1:true,model_setup:true},
    });

    // Exercise the untyped wire shape, including workspace-only lookups used before agent_id.
    const request = ctx.gateway.request as (id:string,type:string,payload:object,signal?:AbortSignal) => Promise<unknown>;
    for (const [type,reply,input,expected] of releaseSamples(workspace)) {
      const id = 'release/' + type;
      const started = Date.now();
      const result = await request(nodeId,type,{...input,request_id:id});
      const wire = outbound.mock.calls.find(([,frame])=>frame.payload.request_id===id)?.[1];
      expect(wire, type).toMatchObject({type,payload:{...input,request_id:id}});
      if (type.endsWith('capabilities.resolve') || type.endsWith('prompt.preview.request'))
        expect(wire!.payload.deadline_at, type).toBeGreaterThan(started);
      const actual = inbound.mock.calls.filter(([,name,p])=>name===reply && p.request_id===id);
      expect(actual, reply).toHaveLength(1);
      expect(actual[0]![2], reply).toMatchObject({node_id:nodeId,...expected});
      expect(result, type).toMatchObject(expected);
    }

    const controller = new AbortController();
    const cancelled = request(nodeId,'node.capabilities.resolve',{request_id:'release-cancel'},controller.signal);
    controller.abort();
    await expect(cancelled).rejects.toMatchObject({statusCode:503});
    expect(outbound.mock.calls).toContainEqual([nodeId,{type:'node.request.cancel',payload:{target_request_id:'release-cancel'}}]);

    // Global does not create active approval cards today. Upload historical wire facts, with
    // two decisions to distinguish the former binding's local rejection from a Node reply.
    const events = [
      {type:'session_registered',payload:{scope:'global_main'}},
      {type:'turn_started',payload:{lifecycle_revision:1}},
      ...['former','current'].map(request_id => ({type:'permission_request',
        payload:{lifecycle_revision:1,request_id,options:[{id:'allow_once'}]}})),
    ].map((event,index)=>({...event,event_id:'history-'+index,seq:index+1,root_agent_id:'global',
      session_id:'history',...(index ? {turn_id:'turn'} : {})}));
    const upload = await fetch(base+'/im/v1/gateway/work-sync/journals/historical/events',{
      method:'POST',headers:{authorization:'Bearer '+runtimeToken,'content-type':'application/json'},
      body:JSON.stringify({from_seq:1,events}),
    });
    expect(await upload.json()).toMatchObject({through_seq:4});
    ctx.db.prepare("UPDATE agent_work_items SET payload=json_set(payload,'$.node_epoch',1) WHERE item_id='permission:former'").run();
    const http = (path:string, body?:object) => fetch(base+'/im/v1/agents/global/work'+path,{
      method:body?'POST':'GET',headers:{authorization:'Bearer '+owner.access_token,'content-type':'application/json'},
      ...(body ? {body:JSON.stringify(body)} : {}),
    });
    const readItems = async () => {
      const page = await http('/sessions/history/turns');
      expect(page.status).toBe(200);
      return (await page.json()).turns[0].items;
    };
    expect(await readItems()).toEqual(expect.arrayContaining(['former','current'].map(id=>expect.objectContaining({
      item_id:'permission:'+id,payload:expect.objectContaining({status:'pending',request_id:id}),
    }))));
    const former = await http('/permissions/former',{decision:'allow_once'});
    expect(former.status).toBe(409);
    expect(await former.json()).toMatchObject({detail:'request_ended'});
    expect(outbound.mock.calls.some(([,frame])=>frame.type==='agent.work.permission')).toBe(false);
    const submitted = await http('/permissions/current',{decision:'allow_once'});
    expect(outbound.mock.calls.filter(([,frame])=>frame.type==='agent.work.permission')).toEqual([[nodeId,{
      type:'agent.work.permission',payload:{request_id:'current',root_agent_id:'global',lifecycle_revision:1,session_id:'history',decision:'allow_once',reason:''},
    }]]);
    const replies = inbound.mock.calls.filter(([,type])=>type==='agent.work.permission.result').map(([, ,p])=>p);
    if (oldNodeRoot) {
      expect(submitted.status).toBe(504); // v2.1.0 had no Node handler for this released IM command.
      expect(replies).toEqual([]);
    } else {
      expect(submitted.status).toBe(409);
      expect(await submitted.json()).toMatchObject({detail:'request_ended'});
      expect(replies).toEqual([{request_id:'current',node_id:nodeId,ok:false,error:'request_ended'}]);
    }
    expect(await readItems()).toHaveLength(2);
  } catch(error) {
    throw new Error(String(error)+'\nNode stderr:\n'+log,{cause:error});
  } finally {
    if (node?.exitCode === null && node.signalCode === null) node.kill('SIGTERM');
    if (exited) await exited;
    await app.close();
    await rm(home,{recursive:true,force:true});
  }
},120_000);

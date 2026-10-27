import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { RuntimeClient, prepareProfile } from '../lib/client.js';
import type { TaskExecutionSnapshot } from '@nano/product-contracts';

it.each(['live', 'cold'])('binds a real child and enforces withdrawn Tasks across %s execution', async mode => {
  const home = await mkdtemp(join(tmpdir(), 'task-native-binding-'));
  let client: RuntimeClient | undefined, logs = '', childId = '';
  let snapshot: TaskExecutionSnapshot = { kind: 'quiescent', tasks: [], repair_task_ids: [] };
  try {
    await writeFile(join(home, 'fixture.mjs'), `import {appendFile,readFile} from 'node:fs/promises';
export const name='native-task-fixture';export const inject=['agents','subagents','llm'];
export function apply(ctx){let n=0;ctx.on('llm/stream',async function*(o){
 const agent=ctx.agents.get(o.sessionId);
 await appendFile(process.env.DSH_HOME+'/calls.jsonl',JSON.stringify({id:agent.id,messages:o.messages})+'\\n');
 if(agent.session.header.origin==='subagent'){
  await new Promise(resolve=>{if(o.signal.aborted)resolve();else o.signal.addEventListener('abort',resolve,{once:true});});
  return;
 }
 const restore=await readFile(process.env.DSH_HOME+'/restore-child','utf8').catch(()=>null);
 if(restore){
  await ctx.subagents.sendMessage(agent,restore,[{type:'text',text:'Late correction after withdrawal'}],{signal:o.signal});
  await appendFile(process.env.DSH_HOME+'/restore-delivered','accepted');
  yield{type:'block-end',index:0,block:{type:'text',text:'late input attempted'}};yield{type:'finish',reason:{kind:'stop'}};return;
 }
 let block;
 if(n===0)block={type:'tool-call',id:'spawn',name:'subagent',arguments:JSON.stringify({description:'Long task',prompt:'Wait for task inputs',run_in_background:true})};
 else if(n===1){const child=(await ctx.subagents.listChildren(agent.id))[0];block={type:'tool-call',id:'bind',name:'task_graph',arguments:JSON.stringify({action:'apply',graph_id:'g',base_revision:1,operations:[{op:'bind_execution',node_id:'n',child_id:child.id,request_revision:1}]})};}
 else block={type:'text',text:'coordination recorded'};
 n++;yield{type:'block-end',index:0,block};yield{type:'finish',reason:{kind:block.type==='tool-call'?'tool-calls':'stop'}};
});}`);
    await prepareProfile(home, [{ insert: [{ id: 'native-task-fixture', name: join(home, 'fixture.mjs') }] }]);
    const start=async()=>{
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    client.rpc.handle('product.task_execution.snapshot', () => snapshot);
    client.rpc.handle('product.call', value => {
      const call = value as {method: string; args: any};
      expect(call.method).toBe('task_graph');
      const op = call.args.operations[0]; childId = op.child_id;
      expect(op.root_session_id).toBe('root');
      snapshot = {kind:'continue',repair_task_ids:[],tasks:[{graph_id:'g',node_id:'n',title:'Long task',status:'doing',revision:2,updated_at:'2026-10-26T00:00:00Z',conversation:{id:'chat'},relative_url:'/tasks/g',execution:{child_id:childId,root_session_id:'root',owner_agent_id:'a',request_revision:1,bound_revision:2}}]};
      return {ok:true,result:{revision:2}};
    });
    await client!.rpc.request('initialize', {protocol:1,agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:['subagent','task_graph'],features:{task_graph:true},approval:{dangerouslySkipPermissions:true}}],bindings:[]});
    await client!.rpc.request('session.ensure', {sessionId:'root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'});
    };await start();
    await client!.rpc.request('session.submit', {sessionId:'root',inputId:'seed',mode:'followup',content:[{type:'text',text:'Start long task'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'seed'}});
    const calls = async () => (await readFile(join(home,'calls.jsonl'),'utf8').catch(()=>'' )).trim().split('\n').filter(Boolean).map(line=>JSON.parse(line));
    await expect.poll(() => childId, {timeout:15000}).not.toBe('');
    await expect.poll(async () => (await client!.rpc.request('session.observe',{sessionId:'root'}) as any).status).toBe('idle');
    expect((await client!.rpc.request('session.descendants',{sessionId:'root'}) as any[]).find(row=>row.id===childId)?.activity).toBe('running');
    const count = (await calls()).filter(row=>row.id==='root').length;
    await client!.rpc.request('task.execution.changed',{agentId:'a'});
    await new Promise(resolve=>setTimeout(resolve,100));
    expect((await calls()).filter(row=>row.id==='root')).toHaveLength(count);
    if(mode==='cold'){
      const childCalls=(await calls()).filter(row=>row.id===childId).length;expect(childCalls).toBeGreaterThan(0);
      await client!.shutdown();client=undefined;
      snapshot={kind:'quiescent',tasks:[],repair_task_ids:[]};
      await writeFile(join(home,'restore-child'),childId);await start();
      await client!.rpc.request('session.submit',{sessionId:'root',inputId:'late',mode:'followup',content:[{type:'text',text:'Deliver a late correction'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'late'}});
      await expect.poll(()=>readFile(join(home,'restore-delivered'),'utf8').catch(()=>''),{timeout:10000}).toBe('accepted');
      await expect.poll(async()=>(await client!.rpc.request('session.descendants',{sessionId:'root'}) as any[]).find(row=>row.id===childId)?.activity).not.toBe('running');
      expect((await calls()).filter(row=>row.id===childId)).toHaveLength(childCalls);
      expect(snapshot.tasks).toEqual([]);return;
    }
    snapshot.tasks[0]!.execution!.needs_coordination=true;
    snapshot.tasks[0]!.revision=3;
    snapshot.tasks[0]!.title='Corrected requirement';
    await client!.rpc.request('task.execution.changed',{agentId:'a'});
    await expect.poll(async () => (await calls()).filter(row=>row.id==='root').length).toBeGreaterThan(count);
    snapshot={kind:'quiescent',tasks:[],repair_task_ids:[]};
    await client!.rpc.request('task.execution.changed',{agentId:'a'});
    await expect.poll(async () => (await client!.rpc.request('session.descendants',{sessionId:'root'}) as any[]).find(row=>row.id===childId)?.activity).not.toBe('running');
  } catch(error) { throw new Error(`${error}\n${logs}`,{cause:error}); }
  finally { await client?.shutdown().catch(()=>{}); await rm(home,{recursive:true,force:true}); }
},30000);

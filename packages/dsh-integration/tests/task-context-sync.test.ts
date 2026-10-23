import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';
import type {TaskExecutionSnapshot} from '@nano/product-contracts';

// Native request history is the consumer seam: a relay hint alone does not prove model visibility.
async function fixture() {
  const home=await mkdtemp(join(tmpdir(),'nano-task-context-'));
  await writeFile(join(home,'probe.mjs'),`import {appendFile} from 'node:fs/promises';
export const name='task-context-probe';export const inject=['llm'];
export function apply(ctx){ctx.on('llm/stream',async function*(o){await appendFile(process.env.DSH_HOME+'/calls',JSON.stringify(o.messages)+'\\n');yield{type:'block-end',index:0,block:{type:'text',text:'Current responsibility checked.'}};yield{type:'finish',reason:{kind:'stop'}};});}`);
  await prepareProfile(home,[{insert:[{id:'task-context-probe',name:join(home,'probe.mjs')}]}]);
  const agent={agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:['task_graph']};
  const binding={sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home};
  const empty:TaskExecutionSnapshot={kind:'quiescent',tasks:[],repair_task_ids:[]};
  const calls=async()=>{const text=await readFile(join(home,'calls'),'utf8').catch(()=>'');return text.trim()?text.trim().split('\n').map(line=>JSON.parse(line)):[];};
  const submit=(client:RuntimeClient,id:string)=>client.rpc.request('session.submit',{sessionId:'s',inputId:id,mode:'followup',content:[{type:'text',text:id}],source:{kind:'human',actorId:'o',channel:'test',messageId:id}});
  const idle=(client:RuntimeClient)=>expect.poll(async()=>((await client.rpc.request('session.observe',{sessionId:'s'})) as {status:string}).status).toBe('idle');
  return {home,agent,binding,empty,calls,submit,idle};
}

it('adds current empty responsibility when resuming history after Tasks were withdrawn offline',async()=>{
  const f=await fixture();let client:RuntimeClient|undefined;
  try {
    client=new RuntimeClient({home:f.home,cwd:f.home});
    client.rpc.handle('product.task_execution.snapshot',async()=>({kind:(await f.calls()).length?'quiescent':'continue',tasks:[{graph_id:'g',node_id:'n1',title:'OLD_RESPONSIBILITY',status:(await f.calls()).length?'waiting':'doing',revision:1,updated_at:'2026-10-23T15:00:00Z',conversation:{id:'c'},relative_url:'/tasks/g'}],repair_task_ids:[]}));
    await client.rpc.request('initialize',{protocol:1,agents:[f.agent],bindings:[]});
    await client.rpc.request('session.ensure',f.binding);
    await expect.poll(async()=>(await f.calls()).length).toBe(1);await f.idle(client);
    expect(JSON.stringify((await f.calls())[0])).toContain('OLD_RESPONSIBILITY');
    await client.shutdown();client=new RuntimeClient({home:f.home,cwd:f.home});
    client.rpc.handle('product.task_execution.snapshot',()=>f.empty);
    await client.rpc.request('initialize',{protocol:1,agents:[f.agent],bindings:[f.binding]});
    await client.rpc.request('session.ensure',f.binding);
    await f.submit(client,'After offline change');await expect.poll(async()=>(await f.calls()).length).toBe(2);await f.idle(client);
    const messages=(await f.calls())[1];
    expect(JSON.stringify(messages)).toContain('OLD_RESPONSIBILITY');
    const reminder=messages.filter((m:any)=>['task-change','task-execution'].includes(m.source?.channel)).at(-1);
    expect(reminder).toBeTruthy();
    expect(reminder.content.map((b:any)=>b.text??'').join('')).toContain('"tasks":[]');
    expect(JSON.stringify(reminder)).not.toContain('OLD_RESPONSIBILITY');
  } finally {await client?.shutdown();await rm(f.home,{recursive:true,force:true});}
},20_000);

it('wakes a real UI resume even when a passive stop notice is pending',async()=>{
  const f=await fixture();let client:RuntimeClient|undefined;
  try {
    client=new RuntimeClient({home:f.home,cwd:f.home});let resumed=false;
    client.rpc.handle('product.task_execution.snapshot',async()=>!resumed||(await f.calls()).length?f.empty:{kind:'continue',tasks:[{graph_id:'g',node_id:'n1',title:'UI_RESUMED',status:'doing',revision:3,updated_at:'2026-10-23T15:01:00Z',resume_request:{actor_id:'o',at:'2026-10-23T15:01:00Z',revision:3},conversation:{id:'c'},relative_url:'/tasks/g'}],repair_task_ids:[]});
    await client.rpc.request('initialize',{protocol:1,agents:[f.agent],bindings:[]});
    await client.rpc.request('session.ensure',f.binding);
    await client.rpc.request('session.cancel',{sessionId:'s'});
    await client.rpc.request('session.submit',{sessionId:'s',inputId:'stop-notice',mode:'inject',content:[{type:'text',text:'HOST_STOP_NOTICE'}],source:{kind:'system',actorId:'o',channel:'task-human-control',messageId:'stop'}});
    expect(await f.calls()).toHaveLength(0);
    resumed=true;await client.rpc.request('task.execution.changed',{agentId:'a'});
    await expect.poll(async()=>(await f.calls()).length).toBe(1);await f.idle(client);
    const messages=(await f.calls())[0];
    expect(JSON.stringify(messages)).toContain('HOST_STOP_NOTICE');
    expect(JSON.stringify(messages)).toContain('UI_RESUMED');
    expect(messages.filter((m:any)=>m.source?.channel==='task-human-control')).toHaveLength(2);
  } finally {await client?.shutdown();await rm(f.home,{recursive:true,force:true});}
},20_000);


it('retains an unconsumed stop fact through normal runtime teardown without waking on restore',async()=>{
  const f=await fixture();let client:RuntimeClient|undefined;
  try {
    client=new RuntimeClient({home:f.home,cwd:f.home});
    client.rpc.handle('product.task_execution.snapshot',()=>f.empty);
    await client.rpc.request('initialize',{protocol:1,agents:[f.agent],bindings:[]});
    await client.rpc.request('session.ensure',f.binding);
    await client.rpc.request('session.cancel',{sessionId:'s'});
    await client.rpc.request('session.submit',{sessionId:'s',inputId:'task-stop-notice:a:stop',mode:'inject',content:[{type:'text',text:'HOST_STOP_NOTICE: old input is not new resume intent.'}],source:{kind:'system',actorId:'o',channel:'task-human-control',messageId:'stop'}});
    expect(await f.calls()).toHaveLength(0);
    await client.shutdown();client=new RuntimeClient({home:f.home,cwd:f.home});
    client.rpc.handle('product.task_execution.snapshot',()=>f.empty);
    await client.rpc.request('initialize',{protocol:1,agents:[f.agent],bindings:[f.binding]});
    await client.rpc.request('session.ensure',f.binding);
    expect(await f.calls()).toHaveLength(0);
    await f.submit(client,'New independent question');await expect.poll(async()=>(await f.calls()).length).toBe(1);await f.idle(client);
    expect(JSON.stringify((await f.calls())[0])).toContain('HOST_STOP_NOTICE');
    await f.submit(client,'Another independent question');await expect.poll(async()=>(await f.calls()).length).toBe(2);await f.idle(client);
    expect((await f.calls())[1].filter((m:any)=>m.source?.channel==='task-human-control')).toHaveLength(1);
  } finally {await client?.shutdown();await rm(f.home,{recursive:true,force:true});}
},20_000);

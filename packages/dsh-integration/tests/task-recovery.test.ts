import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';

it.each(['source','flush'])('holds automatic model execution during a %s failure and rechecks after recovery',async fault=>{
  const home=await mkdtemp(join(tmpdir(),'nano-task-recovery-'));let client:RuntimeClient|undefined;let logs='';
  try {
    await writeFile(join(home,'probe.mjs'),`import {readFile,writeFile} from 'node:fs/promises';
export const name='task-recovery-probe';export const inject=['llm','sessions'];
export function apply(ctx){
 const flush=ctx.sessions.flush.bind(ctx.sessions);
 ctx.sessions.flush=async session=>{
  if(await readFile(process.env.DSH_HOME+'/fail-flush','utf8').catch(()=>''))throw new Error('Injected storage failure');
  return flush(session);
 };
 ctx.on('llm/stream',async function*(){
  await writeFile(process.env.DSH_HOME+'/completed','verified');
  yield{type:'block-end',index:0,block:{type:'text',text:'Verified work completed'}};yield{type:'finish',reason:{kind:'stop'}};
 });
}`);
    await prepareProfile(home,[{insert:[{id:'task-recovery-probe',name:join(home,'probe.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
    let active=false,online=false,reads=0;
    client.rpc.handle('product.task_execution.snapshot',async()=>{
      reads++;
      if(!active)return {kind:'quiescent',tasks:[],repair_task_ids:[]};
      if(fault==='source'&&!online)throw new Error('Injected task source failure');
      const completed=await readFile(join(home,'completed'),'utf8').catch(()=>'');
      return completed?{kind:'quiescent',tasks:[],repair_task_ids:[]}:{kind:'continue',tasks:[{graph_id:'g',node_id:'n',title:'Still doing',status:'doing',revision:1,updated_at:'2026-10-23T15:00:00Z',conversation:{id:'c'},relative_url:'/tasks/g'}],repair_task_ids:[]};
    });
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:['task_graph']}],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home});
    // Let the initial quiescent discovery finish before injecting an idle flush fault.
    await expect.poll(()=>reads).toBeGreaterThan(0);
    await expect.poll(async()=>(await client!.rpc.request('session.observe',{sessionId:'s'}) as {status:string}).status).toBe('idle');
    active=true;
    if(fault==='flush')await writeFile(join(home,'fail-flush'),'yes');
    const before=reads;
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await new Promise(resolve=>setTimeout(resolve,150));
    if(fault==='source')expect(reads).toBeGreaterThan(before);
    expect(await readFile(join(home,'completed'),'utf8').catch(()=>null)).toBeNull();
    online=true;await rm(join(home,'fail-flush'),{force:true});
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await expect.poll(()=>readFile(join(home,'completed'),'utf8').catch(()=>null)).toBe('verified');
    await expect.poll(async()=>(await client!.rpc.request('session.observe',{sessionId:'s'}) as {status:string}).status).toBe('idle');
  } catch(error) {
    const observed=await client?.rpc.request('session.observe',{sessionId:'s'}).catch(e=>String(e));
    throw new Error(String(error)+'\n'+logs+'\n'+JSON.stringify(observed),{cause:error});
  } finally {await rm(join(home,'fail-flush'),{force:true});await client?.shutdown();await rm(home,{recursive:true,force:true});}
},20_000);

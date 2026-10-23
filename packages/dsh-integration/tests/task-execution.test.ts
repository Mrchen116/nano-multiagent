import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';
import type {TaskExecutionSnapshot} from '@nano/product-contracts';

it('admits fresh native Task continuations, yields to competing inputs, and holds after cancellation',async()=>{
  const home=await mkdtemp(join(tmpdir(),'nano-task-execution-'));let client:RuntimeClient|undefined;let logs='';
  try {
    await writeFile(join(home,'probe.mjs'),`import {appendFile} from 'node:fs/promises';
export const name='task-execution-probe';export const inject=['llm','agents'];
export function apply(ctx){ctx.on('llm/stream',async function*(o){
 const agent=ctx.agents.currentInitiator();
 await appendFile(process.env.DSH_HOME+'/calls.jsonl',JSON.stringify({session:agent.id,messages:o.messages})+'\\n');
 if(o.messages.some(m=>m.role==='user'&&m.content.some(b=>b.type==='text'&&b.text==='hold'))){await new Promise(resolve=>{if(o.signal.aborted)resolve();else o.signal.addEventListener('abort',resolve,{once:true})});return;}
 yield{type:'block-end',index:0,block:{type:'text',text:'NO_REPLY'}};yield{type:'finish',reason:{kind:'stop'}};
});}`);
    await prepareProfile(home,[{insert:[{id:'task-execution-probe',name:join(home,'probe.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
    let task:TaskExecutionSnapshot={kind:'quiescent',tasks:[],repair_task_ids:[]};
    let reads=0,blockRead:undefined|(()=>Promise<void>);
    const calls=async()=>{const text=await readFile(join(home,'calls.jsonl'),'utf8').catch(()=>'');return text.trim()?text.trim().split('\n').map(line=>JSON.parse(line)):[];};
    const active=(title:string):TaskExecutionSnapshot=>({kind:'continue',tasks:[{graph_id:'g',node_id:'n1',title,status:'doing',revision:2,updated_at:'2026-10-23T15:00:00Z',resume_request:{actor_id:'o',at:'2026-10-22T06:00:00Z',revision:2},conversation:{id:'c'},relative_url:'/tasks/g'}],repair_task_ids:[]});
    // Change between idle discovery and admission must replace the queued body.
    let discovered=0;
    client.rpc.handle('product.task_execution.snapshot',async()=>{
      reads++;
      if(blockRead){const block=blockRead;blockRead=undefined;await block();}
      if(task.kind==='continue'&&discovered++===0)return active('OLD_DISCOVERY');
      return task;
    });
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:['task_graph']}],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home});
    task=active('LATEST_TASK');
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await expect.poll(async()=>(await calls()).length).toBeGreaterThanOrEqual(1);
    task={kind:'quiescent',tasks:[],repair_task_ids:[]};
    await expect.poll(async()=>(await client!.rpc.request('session.observe',{sessionId:'s'}) as {status:string}).status).toBe('idle');
    const first=(await calls())[0];expect(first.messages.filter((message:{source?:{channel?:string}})=>message.source?.channel==='task-human-control')).toHaveLength(1);expect(JSON.stringify(first.messages)).toContain('LATEST_TASK');expect(JSON.stringify(first.messages)).not.toContain('OLD_DISCOVERY');
    const count=(await calls()).length;
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    expect((await calls()).length).toBe(count);

    // A real human arriving during the asynchronous idle read keeps native priority.
    let release!:()=>void;let entered!:()=>void;const waiting=new Promise<void>(r=>{entered=r;});
    blockRead=async()=>{entered();await new Promise<void>(r=>{release=r;});};task=active('RACE_TASK');
    await client.rpc.request('task.execution.changed',{agentId:'a'});await waiting;
    await client.rpc.request('session.submit',{sessionId:'s',inputId:'human-hold',mode:'followup',content:[{type:'text',text:'hold'}],source:{kind:'human',actorId:'o',channel:'test',messageId:'human-hold'}});
    release();
    await expect.poll(async()=>(await calls()).length).toBeGreaterThan(count);
    expect(JSON.stringify((await calls()).at(-1).messages)).toContain('human-hold');
    await client.rpc.request('session.cancel',{sessionId:'s'});
    const cancelledCount=(await calls()).length;const before=reads;
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await new Promise(resolve=>setTimeout(resolve,100));expect(reads).toBeGreaterThan(before);expect((await calls()).length).toBe(cancelledCount);
    task={kind:'quiescent',tasks:[],repair_task_ids:[]};
  }catch(error){throw new Error(String(error)+'\n'+logs,{cause:error});}
  finally{await client?.shutdown();await rm(home,{recursive:true,force:true});}
},30_000);

it.each(['automatic', 'human'])('holds automatic retries after %s permission failure and delivers the final result after responsibility ends', async denial => {
  const home = await mkdtemp(join(tmpdir(), 'nano-task-policy-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  try {
    await writeFile(join(home, 'probe.mjs'), `import {appendFile,writeFile} from 'node:fs/promises';
export const name='task-policy-probe';export const inject=['tools','llm','agents'];
export function apply(ctx){
 let denied=false;
 ctx.tools.register({name:'fixture_effect',description:'Test effect',parameters:{type:'object',properties:{readOnly:{type:'boolean'}}},output:{schema:{type:'string'},render:(_args,value)=>[{type:'text',text:value}]},
  execute:async(args)=>{if(!args.readOnly)await writeFile(process.env.DSH_HOME+'/completed','yes');return 'completed';}});
 ctx.on('tools/pre-execute',(exec,next)=>{
  if(exec.name!=='fixture_effect')return next();
  if(!denied){denied=true;return ${denial==='human'?"{kind:'ask',reason:'Requires permission'}":"{kind:'deny',reason:'Requires permission',info:{name:'NanoApprovalDenied',code:'classifier_block'}}"};}
  return {kind:'allow'};
 },{prepend:true});
 ctx.on('llm/stream',async function*(o){
  const last=o.messages.at(-1);
  const isResult=last?.role==='tool'||last?.role==='user'&&o.messages.at(-2)?.role==='tool';
  await appendFile(process.env.DSH_HOME+'/calls.jsonl',JSON.stringify({isResult,messages:o.messages})+'\\n');
  const trigger=o.messages.findLast(m=>m.role==='user'&&['task-execution','heartbeat'].includes(m.source?.channel));
  const readOnly=trigger?.source?.channel==='heartbeat';
  const block=isResult?{type:'text',text:'RESULT_OR_BLOCKER_VISIBLE'}:{type:'tool-call',id:'effect-'+Date.now(),name:'fixture_effect',arguments:JSON.stringify({readOnly})};
  yield{type:'block-end',index:0,block};yield{type:'finish',reason:{kind:isResult?'stop':'tool-calls'}};
 });
}`);
    await prepareProfile(home, [{insert: [{id: 'task-policy-probe', name: join(home, 'probe.mjs')}]}]);
    client = new RuntimeClient({home, cwd: home, onLog: text => {logs += text;}});
    client.rpc.onNotification((method,payload)=>{if(method==='approval.request')void client!.rpc.request('approval.answer',{requestId:(payload as {requestId:string}).requestId,decision:'rejected'});});
    let revision = 1, updated = '2026-10-23T15:00:00Z';
    client.rpc.handle('product.task_execution.snapshot', async () => {
      const completed = await readFile(join(home, 'completed'), 'utf8').catch(() => '');
      return completed ? {kind:'quiescent',tasks:[],repair_task_ids:[]} : {
        kind:'continue',tasks:[{graph_id:'g',node_id:'n1',title:'Task',status:'doing',revision,updated_at:updated,conversation:{id:'c'},relative_url:'/tasks/g'}],repair_task_ids:[],
      };
    });
    const calls = async () => (await readFile(join(home, 'calls.jsonl'), 'utf8').catch(() => '')).trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
    await client.rpc.request('initialize', {protocol:1,agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash'}],bindings:[]});
    await client.rpc.request('session.ensure', {sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home});
    await expect.poll(async () => (await calls()).length).toBeGreaterThanOrEqual(2);
    await expect.poll(async () => (await client!.rpc.request('session.observe',{sessionId:'s'}) as {status:string}).status).toBe('idle');
    await client.rpc.request('task.execution.changed',{agentId:'a',reset:false});
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await new Promise(resolve => setTimeout(resolve, 150));
    expect((await calls()).length).toBe(2);
    expect(await readFile(join(home,'completed'),'utf8').catch(()=>null)).toBeNull();

    // Neither a heartbeat with a successful different action on the same tool,
    // nor an unrelated node's graph revision may reopen the denied responsibility.
    await client.rpc.request('session.submit',{sessionId:'s',inputId:'unrelated',mode:'followup',content:[{type:'text',text:'Unrelated read'}],source:{kind:'system',actorId:'a',channel:'heartbeat',messageId:'unrelated'}});
    await expect.poll(async () => (await calls()).length).toBeGreaterThanOrEqual(4);
    await expect.poll(async () => (await client!.rpc.request('session.observe',{sessionId:'s'}) as {status:string}).status).toBe('idle');
    revision = 2;
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await new Promise(resolve => setTimeout(resolve, 150));
    expect((await calls()).length).toBe(4);
    expect(await readFile(join(home,'completed'),'utf8').catch(()=>null)).toBeNull();
    // A change to this node's own contents permits reassessment under approval.
    updated = '2026-10-23T15:01:00Z';
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await expect.poll(() => readFile(join(home,'completed'),'utf8').catch(()=>null)).toBe('yes');
    await expect.poll(async () => (await calls()).length).toBe(6);
    const observed = await client.rpc.request('session.observe',{sessionId:'s'}) as {events:{type:string;data:Record<string,unknown>}[]};
    expect(observed.events.filter(e=>e.type==='assistant/message').map(e=>JSON.stringify(e.data)).filter(s=>s.includes('RESULT_OR_BLOCKER_VISIBLE'))).toHaveLength(3);
  } catch(error) {throw new Error(String(error)+'\n'+logs,{cause:error});}
  finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},30_000);


it.each(['throw', 'finish', 'finish-with-inbox','new-input'])('rechecks unchanged responsibility after a %s model failure is repaired', async failure => {
  const home = await mkdtemp(join(tmpdir(), 'nano-task-model-recovery-'));
  let client: RuntimeClient | undefined;
  try {
    await writeFile(join(home, 'probe.mjs'), `import {appendFile,readFile,writeFile} from 'node:fs/promises';
export const name='task-model-recovery';export const inject=['llm','agents'];
export function apply(ctx){ctx.on('llm/stream',async function*(){
 await appendFile(process.env.DSH_HOME+'/calls','request\\n');
 if(!await readFile(process.env.DSH_HOME+'/healthy','utf8').catch(()=>'')){
 if(${JSON.stringify(failure)}==='finish-with-inbox')ctx.agents.currentInitiator().followup({id:'assignment-notice',role:'user',content:[{type:'text',text:'An assignment notification arrived while the model was failing.'}],source:{kind:'user'}});
 if(${JSON.stringify(failure)}==='throw')throw new Error('Fixture model unavailable');
 yield{type:'finish',reason:{kind:'error',failure:{message:'Fixture credential unavailable',code:'AUTH'}}};return;
 }
 await writeFile(process.env.DSH_HOME+'/completed','yes');
 yield{type:'block-end',index:0,block:{type:'text',text:'Recovered result'}};yield{type:'finish',reason:{kind:'stop'}};
});}`);
    await prepareProfile(home, [{insert:[{id:'task-model-recovery',name:join(home,'probe.mjs')}]}]);
    client = new RuntimeClient({home,cwd:home});
    client.rpc.handle('product.task_execution.snapshot', async () => await readFile(join(home,'completed'),'utf8').catch(()=>null)
      ? {kind:'quiescent',tasks:[],repair_task_ids:[]}
      : {kind:'continue',tasks:[{graph_id:'g',node_id:'n1',title:'Task',status:'doing',revision:1,updated_at:'2026-10-23T15:00:00Z',conversation:{id:'c'},relative_url:'/tasks/g'}],repair_task_ids:[]});
    const config = {agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash'};
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home});
    await expect.poll(async () => {
      const observed = await client!.rpc.request('session.observe',{sessionId:'s'}) as {status:string;events:{type:string}[]};
      return observed.status==='idle' && observed.events.some(e=>e.type==='turn/end');
    }).toBe(true);
    const calls = async () => (await readFile(join(home,'calls'),'utf8')).trim().split('\n').length;
    expect(await calls()).toBe(1);
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await new Promise(resolve=>setTimeout(resolve,100));
    expect(await calls()).toBe(1);
    await writeFile(join(home,'healthy'),'yes');
    if(failure==='new-input')await client.rpc.request('session.submit',{sessionId:'s',inputId:'repaired-input',mode:'followup',content:[{type:'text',text:'Recheck the task after recovery'}],source:{kind:'human',actorId:'o',channel:'test',messageId:'repaired-input'}});
    else await client.rpc.request('configuration.apply',{...config,revision:'2',model:'deepseek-v4-flash'});
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await expect.poll(()=>readFile(join(home,'completed'),'utf8').catch(()=>null)).toBe('yes');
    await expect.poll(async ()=>(await client!.rpc.request('session.observe',{sessionId:'s'}) as {status:string}).status).toBe('idle');
    // The queued ordinary turn also observes its Task's removal at the next step.
    expect(await calls()).toBe(failure==='finish-with-inbox'?3:2);
    if(failure==='finish-with-inbox') {
      const observed=await client.rpc.request('session.observe',{sessionId:'s'}) as {events:{type:string;data:{id?:string}}[]};
      expect(observed.events.filter(event=>event.type==='user/message'&&event.data.id==='assignment-notice')).toHaveLength(1);
    }
  } finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},30_000);

it.each(['node','dependency','subtree'] as const)('keeps an unchanged denied Task held while independent work completes: %s',async(scope)=>{
  const home=await mkdtemp(join(tmpdir(),'nano-task-scope-'));let client:RuntimeClient|undefined;
  try {
    await writeFile(join(home,'probe.mjs'),`import {appendFile} from 'node:fs/promises';
export const name='task-scope-probe';export const inject=['tools','llm'];
export function apply(ctx){let step=0,denied=false;
 ctx.on('tools/pre-execute',(exec,next)=>{
  if(exec.name!=='task_graph')return next();
  if(!denied){denied=true;return {kind:'deny',reason:'Permission required for A',info:{name:'NanoApprovalDenied'}};}
  return {kind:'allow'};
 },{prepend:true});
 ctx.on('llm/stream',async function*(o){
  step++;await appendFile(process.env.DSH_HOME+'/calls',JSON.stringify(o.messages)+'\\n');
  const node=step===3?'B':'A';
  const args=step===1&&${JSON.stringify(scope)}==='dependency'?{action:'apply',graph_id:'g',base_revision:1,request_key:'edge',change_note:'Order A after remote',operations:[{op:'add_dependency',from:'remote',to:'A'}]}:step===1&&${JSON.stringify(scope)}==='subtree'?{action:'delete',graph_id:'g',node_id:'parent',base_revision:1,request_key:'delete'}:{action:'apply',graph_id:node==='B'&&${JSON.stringify(scope)}==='subtree'?'other':'g',base_revision:1,request_key:'finish-'+node,change_note:'Verified result',operations:[{op:'update_task',node_id:node,patch:{status:'done',result:'Verified '+node}}]};
  const block=step%2?{type:'tool-call',id:'effect-'+step,name:'task_graph',arguments:JSON.stringify(args)}:{type:'text',text:'The result or blocker has been handled.'};
  yield{type:'block-end',index:0,block};yield{type:'finish',reason:{kind:step%2?'tool-calls':'stop'}};
 });
}`);
    await prepareProfile(home,[{insert:[{id:'task-scope-probe',name:join(home,'probe.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home});
    let revision=1,updated='2026-10-23T15:00:00Z';const completed:string[]=[];
    client.rpc.handle('product.task_execution.snapshot',()=>({kind:completed.length===2?'quiescent':'continue',tasks:['A','B'].filter(id=>!completed.includes(id)).map(id=>({graph_id:id==='B'&&scope==='subtree'?'other':'g',node_id:id,title:id,status:'doing',revision,updated_at:updated,conversation:{id:'c'},relative_url:'/tasks/g'})),repair_task_ids:[]}));
    client.rpc.handle('product.call',value=>{
      const call=value as {method:string;args:{operations:{node_id:string}[]}};
      expect(call.method).toBe('task_graph');completed.push(call.args.operations[0]!.node_id);revision++;
      return {ok:true,result:{graph_id:'g',revision}};
    });
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',mode:'global',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:['task_graph']}],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home});
    await expect.poll(()=>completed).toEqual(['B']);
    await expect.poll(async()=>(await client!.rpc.request('session.observe',{sessionId:'s'}) as {status:string}).status).toBe('idle');
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await new Promise(resolve=>setTimeout(resolve,100));
    const calls=()=>readFile(join(home,'calls'),'utf8').then(text=>text.trim().split('\n').map(line=>JSON.parse(line)));
    expect(await calls()).toHaveLength(4);
    updated='2026-10-23T15:01:00Z';
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await expect.poll(()=>completed).toEqual(['B','A']);
    await expect.poll(async()=>(await calls()).length).toBe(6);
  } finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},20_000);

it('withdraws A at the next native step while completing the remaining B responsibility', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-task-steer-'));
  let client: RuntimeClient | undefined;
  try {
    await writeFile(join(home, 'probe.mjs'), `import {appendFile,readFile,writeFile} from 'node:fs/promises';
export const name='task-steer-probe';export const inject=['tools','llm'];
export function apply(ctx){let call=0;
 ctx.tools.register({name:'fixture_task_step',description:'Perform one Task step',parameters:{type:'object',properties:{task:{type:'string'}},required:['task']},output:{schema:{type:'string'},render:(_args,value)=>[{type:'text',text:value}]},execute:async({task})=>{
  if(task==='A'){await writeFile(process.env.DSH_HOME+'/entered','yes');while(!await readFile(process.env.DSH_HOME+'/release','utf8').catch(()=>''))await new Promise(r=>setTimeout(r,20));}
  await appendFile(process.env.DSH_HOME+'/effects',task+'\\n');
  if(task==='B')await writeFile(process.env.DSH_HOME+'/completed','yes');return task+' completed';
 }});
 ctx.on('tools/pre-execute',(exec,next)=>exec.name==='fixture_task_step'?{kind:'allow'}:next(),{prepend:true});
 ctx.on('llm/stream',async function*(o){call++;await appendFile(process.env.DSH_HOME+'/calls',JSON.stringify(o.messages)+'\\n');
  const block=call<3?{type:'tool-call',id:'step-'+call,name:'fixture_task_step',arguments:JSON.stringify({task:call===1?'A':'B'})}:{type:'text',text:'B result delivered'};
  yield{type:'block-end',index:0,block};yield{type:'finish',reason:{kind:call<3?'tool-calls':'stop'}};
 });
}`);
    await prepareProfile(home,[{insert:[{id:'task-steer-probe',name:join(home,'probe.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home});
    let withdrawn=false;
    client.rpc.handle('product.task_execution.snapshot',async()=>{
      if(await readFile(join(home,'completed'),'utf8').catch(()=>null))return {kind:'quiescent',tasks:[],repair_task_ids:[]};
      return {kind:'continue',tasks:(withdrawn?['B']:['A','B']).map(task=>({graph_id:'g',node_id:task==='A'?'n1':'n2',title:task,status:'doing',revision:withdrawn?2:1,conversation:{id:'c'},relative_url:'/tasks/g'})),repair_task_ids:[]};
    });
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash'}],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home});
    await expect.poll(()=>readFile(join(home,'entered'),'utf8').catch(()=>null)).toBe('yes');
    expect(await client.rpc.request('task.execution.state',{agentId:'a'})).toEqual({state:'running'});
    withdrawn=true;
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await writeFile(join(home,'release'),'yes');
    await expect.poll(()=>readFile(join(home,'completed'),'utf8').catch(()=>null)).toBe('yes');
    await expect.poll(async()=>((await client!.rpc.request('session.observe',{sessionId:'s'})) as {status:string}).status).toBe('idle');
    expect(await client.rpc.request('task.execution.state',{agentId:'a'})).toEqual({state:'idle'});
    expect((await readFile(join(home,'effects'),'utf8')).trim().split('\n')).toEqual(['A','B']);
    const calls=(await readFile(join(home,'calls'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    expect(calls).toHaveLength(3);
    const delta=calls[1].flatMap((m:{content:{type:string;text?:string}[]})=>m.content).filter((b:{text?:string})=>b.text?.startsWith('Task responsibility changed.')).at(-1).text;
    expect(delta).toContain('"removed":["g/n1"]');expect(delta).toContain('"doing":["g/n2"]');
  } finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},30_000);

it('keeps a confirmed stop quiet and consumes its durable notice with the next external wake', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-task-stop-restart-'));
  let client:RuntimeClient|undefined;
  try {
    await writeFile(join(home,'probe.mjs'),`import {appendFile} from 'node:fs/promises';
export const name='task-stop-probe';export const inject=['llm'];
export function apply(ctx){ctx.on('llm/stream',async function*(o){await appendFile(process.env.DSH_HOME+'/calls',JSON.stringify(o.messages)+'\\n');yield{type:'block-end',index:0,block:{type:'text',text:'Human reply'}};yield{type:'finish',reason:{kind:'stop'}};});}`);
    await prepareProfile(home,[{insert:[{id:'task-stop-probe',name:join(home,'probe.mjs')}]}]);
    const agent={agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{cron_scheduling:true}};
    const binding={sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home};
    const empty={kind:'quiescent',tasks:[],repair_task_ids:[]};
    client=new RuntimeClient({home,cwd:home});
    client.rpc.handle('product.task_execution.snapshot',()=>empty);
    await client.rpc.request('initialize',{protocol:1,agents:[agent],bindings:[]});
    await client.rpc.request('session.ensure',binding);
    await client.rpc.request('session.observe',{sessionId:'s'});
    await client.rpc.request('schedule.command',{agentId:'a',sessionId:'s',action:'create',args:{title:'STOP_OLD_SCHEDULE',prompt:'STOP_OLD_SCHEDULE: read current Task before considering any action.',after_seconds:2}});
    await client.shutdown();
    client=new RuntimeClient({home,cwd:home});
    let pending=true;
    client.rpc.handle('product.task_execution.snapshot',()=>pending?{kind:'continue',tasks:[{graph_id:'g',node_id:'n1',title:'Unconfirmed stop',status:'doing',revision:1,updated_at:'2026-10-23T15:00:00Z',conversation:{id:'c'},relative_url:'/tasks/g'}],repair_task_ids:[]}:empty);
    await client.rpc.request('initialize',{protocol:1,agents:[agent],bindings:[binding],taskStops:['s']});
    // A due Schedule also resolves the cold session while product recovery ensures it.
    await Promise.all([client.rpc.request('session.observe',{sessionId:'s'}),client.rpc.request('session.ensure',binding)]);
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await client.rpc.request('session.submit',{sessionId:'s',inputId:'kept-human',mode:'followup',content:[{type:'text',text:'Keep this ordinary input'}],source:{kind:'human',actorId:'o',channel:'test',messageId:'kept-human'}});
    await expect.poll(async()=> {
      const observed=await client!.rpc.request('session.observe',{sessionId:'s'}) as {events:{type:string;data:{inserted?:{source?:{kind:string}}[]}}[]};
      return observed.events.some(event=>event.type==='agent/inbox/spliced'&&event.data.inserted?.some(message=>message.source?.kind==='schedule'));
    },{timeout:5000}).toBe(true);
    expect(await readFile(join(home,'calls'),'utf8').catch(()=>null)).toBeNull();
    await client.rpc.request('session.submit',{sessionId:'s',inputId:'stop-notice',mode:'inject',content:[{type:'text',text:'HOST_STOP_NOTICE: prior queued replies cannot resume paused Tasks.'}],source:{kind:'system',actorId:'o',channel:'task-human-control',messageId:'stop'}});
    await client.rpc.request('session.submit',{sessionId:'s',inputId:'concurrent-wake',mode:'followup',content:[{type:'text',text:'Another queued input'}],source:{kind:'human',actorId:'o',channel:'test',messageId:'concurrent-wake'}});
    await expect.poll(async()=>{
      const observed=await client!.rpc.request('session.observe',{sessionId:'s'}) as {events:{type:string;data:{inserted?:{id:string}[]}}[]};
      return observed.events.filter(event=>event.type==='agent/inbox/spliced'&&event.data.inserted?.some(message=>message.id==='stop-notice')).length;
    }).toBeGreaterThanOrEqual(2);
    pending=false;
    await client.rpc.request('task.execution.block',{sessionId:'s',blocked:false});
    await new Promise(resolve=>setTimeout(resolve,150));
    expect(await readFile(join(home,'calls'),'utf8').catch(()=>null)).toBeNull();
    expect((await client.rpc.request('session.observe',{sessionId:'s'}) as {status:string}).status).toBe('idle');
    await client.rpc.request('session.submit',{sessionId:'s',inputId:'after-stop',mode:'followup',content:[{type:'text',text:'A new question after stop'}],source:{kind:'human',actorId:'o',channel:'test',messageId:'after-stop'}});
    await expect.poll(()=>readFile(join(home,'calls'),'utf8').catch(()=>'')).toContain('A new question after stop');
    await expect.poll(async()=>((await client!.rpc.request('session.observe',{sessionId:'s'})) as {status:string}).status).toBe('idle');
    const calls=await readFile(join(home,'calls'),'utf8');
    expect(calls).toContain('STOP_OLD_SCHEDULE');
    // Native inbox classes may admit the held human and Schedule in separate turns.
    expect(calls.trim().split('\n')[0]).toContain('HOST_STOP_NOTICE');
    expect(calls).toContain('Another queued input');
    expect(calls).not.toContain('Unconfirmed stop');
  } finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},30_000);

it('rechecks a consumed native Schedule and becomes quiet after a valid replacement', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-task-schedule-'));
  let client:RuntimeClient|undefined;
  try {
    await writeFile(join(home,'probe.mjs'),`import {appendFile,readFile} from 'node:fs/promises';
export const name='task-schedule-probe';export const inject=['llm'];
export function apply(ctx){ctx.on('llm/stream',async function*(o){await appendFile(process.env.DSH_HOME+'/calls',JSON.stringify(o.messages)+'\\n');while(!await readFile(process.env.DSH_HOME+'/release','utf8').catch(()=>''))await new Promise(r=>setTimeout(r,20));yield{type:'block-end',index:0,block:{type:'text',text:'NO_REPLY'}};yield{type:'finish',reason:{kind:'stop'}};});}`);
    await prepareProfile(home,[{insert:[{id:'task-schedule-probe',name:join(home,'probe.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home});
    let scheduleId:string|undefined;
    client.rpc.handle('product.task_execution.snapshot',async()=>{
      if(!scheduleId)return {kind:'quiescent',tasks:[],repair_task_ids:[]};
      const proof=await client!.rpc.request('schedule.wait.inspect',{agentId:'a',sessionId:'s',scheduleId}) as {valid:boolean};
      return {kind:proof.valid?'quiescent':'continue',tasks:[{graph_id:'g',node_id:'n1',title:'Wait for answer',status:'waiting',revision:1,updated_at:'2026-10-23T15:00:00Z',conversation:{id:'c'},relative_url:'/tasks/g'}],repair_task_ids:proof.valid?[]:['g/n1']};
    });
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{cron_scheduling:true}}],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home});
    scheduleId=(await client.rpc.request('schedule.command',{agentId:'a',sessionId:'s',action:'create',args:{title:'Task check',prompt:'Read Task g/n1 before deciding.',after_seconds:1}}) as {id:string}).id;
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await expect.poll(()=>readFile(join(home,'calls'),'utf8').catch(()=>''),{timeout:5000}).toContain('g/n1');
    const oldScheduleId=scheduleId;
    expect(await client.rpc.request('schedule.wait.inspect',{agentId:'a',sessionId:'s',scheduleId})).toMatchObject({valid:false});
    scheduleId=(await client.rpc.request('schedule.command',{agentId:'a',sessionId:'s',action:'create',args:{title:'Next Task check',prompt:'Read Task g/n1 before deciding.',after_seconds:3600}}) as {id:string}).id;
    expect(scheduleId).not.toBe(oldScheduleId);
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await writeFile(join(home,'release'),'yes');
    await expect.poll(async()=>((await client!.rpc.request('session.observe',{sessionId:'s'})) as {status:string}).status).toBe('idle');
    await client.rpc.request('task.execution.changed',{agentId:'a',reset:false});
    await new Promise(resolve=>setTimeout(resolve,100));
    const calls=(await readFile(join(home,'calls'),'utf8')).trim().split('\n');
    // The in-flight native turn receives the replacement delta before its final reply.
    expect(calls).toHaveLength(2);expect(calls[0]).toContain('repair_task_ids');
    expect(JSON.parse(calls[1]).at(-1).content[0].text).toContain('"repair_task_ids":[]');
    expect(await client.rpc.request('schedule.wait.inspect',{agentId:'a',sessionId:'s',scheduleId})).toMatchObject({valid:true});
  } finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},30_000);

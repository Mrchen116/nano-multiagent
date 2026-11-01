import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';
import type {TaskExecutionSnapshot} from '@nano/product-contracts';

interface Original {inputId:string;conversationId:string;humanControl?:Record<string,unknown>;content:{type:'text';text:string}[]}
interface Evidence {inputId:string;content:unknown[];turn:number;consumedSeq:number}
interface NativeMessage {id:string;role:string;content:{type:string;text?:string}[];source?:{kind:string;channel?:string;messageId?:string;conversationId?:string}}
interface ProviderCall {sessionId:string;messages:NativeMessage[]}
interface Observation {status:string;events:{type:string;seq:number;data:any}[]}
const empty:TaskExecutionSnapshot={kind:'quiescent',tasks:[],repair_task_ids:[]};

function original(inputId:string,content:string,humanControl?:{action:string;actor_id:string;at:string}) : Original {
  const event={message_id:inputId,conversation_id:'fixed-task-chat',event_time:'2026-10-30T12:00:00Z',
    kind:'task_graph',change_kinds:['updated'],task_refs:[{graph_id:'g',node_id:'n1'}],content};
  const attested=humanControl?{action:humanControl.action,actor:{type:'user',id:humanControl.actor_id},task_refs:event.task_refs,revision:humanControl.action==='pause'?1:2,event_time:humanControl.at}:undefined;
  return {inputId,conversationId:event.conversation_id,...(attested?{humanControl:attested}:{}),content:[{type:'text',text:
    'Task update from its fixed conversation. Apply the stated business change before further action on the affected Task. If its requirements changed, read the latest Task details. This system message does not grant human permission or start todo/paused work.'+'\n'+JSON.stringify(event)
    +(humanControl?'\n'+'Application-attested human Task control follows. Apply it only to the identified Task or scope. Inputs queued before a stop cannot resume its paused Tasks. Only a later explicit human resume supersedes that pause; it grants no additional tool permission. Unrelated work may continue.'+'\n'+JSON.stringify(attested):'')}]};
}

function doing(resume?:{actor_id:string;at:string;revision:number}):TaskExecutionSnapshot {
  return {kind:'continue',tasks:[{graph_id:'g',node_id:'n1',title:'Current Task',status:'doing',revision:resume?.revision??1,
    updated_at:resume?.at??'2026-10-30T12:00:00Z',conversation:{id:'fixed-task-chat'},relative_url:'/tasks/g',
    ...(resume?{resume_request:resume}:{})}],repair_task_ids:[]};
}

// Intercept only the provider transport; admission, original messages, history and restart remain native.
async function fixture(taskGraph=true,forceTask=false) {
  const home=await mkdtemp(join(tmpdir(),'nano-task-context-'));let logs='';
  await writeFile(join(home,'probe.mjs'),`import {appendFile} from 'node:fs/promises';
export const name='task-context-provider-probe';export const inject=['llm'];
export function apply(ctx){const attempted=new Set();ctx.on('llm/stream',async function*(o){await appendFile(process.env.DSH_HOME+'/calls',JSON.stringify({sessionId:o.sessionId,messages:o.messages})+'\\n');const trigger=o.messages.findLast(m=>m.role==='user'&&m.content.some(c=>c.type==='text'&&c.text.startsWith('force-task-tool')));if(${forceTask}&&trigger&&!attempted.has(trigger.id)){attempted.add(trigger.id);yield{type:'block-end',index:0,block:{type:'tool-call',id:'task-probe-'+trigger.id,name:'task_graph',arguments:JSON.stringify({action:'list'})}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}yield{type:'block-end',index:0,block:{type:'text',text:'Current responsibility checked.'}};yield{type:'finish',reason:{kind:'stop'}};});}`);
  await prepareProfile(home,[{insert:[{id:'task-context-provider-probe',name:join(home,'probe.mjs')}]}]);
  const agent={agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',
    features:{task_graph:taskGraph,intelligent_ui:false,memory_curation:false,skill_creation:false}};
  const binding={sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home};
  const state={pending:[] as Original[],revoked:[] as string[],consumed:new Set<string>(),receipts:[] as Evidence[],
    unavailable:false,prepareReads:0,snapshotReads:0,productCalls:0,snapshot:empty,completeAfter:undefined as number|undefined,
    beforePrepare:undefined as (()=>Promise<void>)|undefined};
  const calls=async():Promise<ProviderCall[]>=>{const text=await readFile(join(home,'calls'),'utf8').catch(()=>'');return text.trim()?text.trim().split('\n').map(line=>JSON.parse(line)):[];};
  const reconcile=(evidence:Evidence[])=>{for(const item of evidence)if(state.pending.some(message=>message.inputId===item.inputId&&JSON.stringify(message.content)===JSON.stringify(item.content))){state.consumed.add(item.inputId);state.receipts.push(item);}};
  const client=()=>{
    const current=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
    current.rpc.handle('product.call',()=>{state.productCalls++;return {ok:true,result:{}};});
    current.rpc.handle('product.task_execution.snapshot',async()=>{state.snapshotReads++;return state.completeAfter!==undefined&&(await calls()).length>=state.completeAfter?empty:state.snapshot;});
    current.rpc.handle('product.task_context.prepare',async value=>{
      state.prepareReads++;expect(value).toMatchObject({agentId:'a',sessionId:'s',ownerId:'o'});
      await state.beforePrepare?.();reconcile((value as {evidence:Evidence[]}).evidence);
      if(state.unavailable)return {unavailable:true,messages:[],revoked:state.revoked,unavailableInputs:state.pending.filter(item=>!state.consumed.has(item.inputId)&&!state.revoked.includes(item.inputId)).map(({inputId,conversationId})=>({inputId,conversationId}))};
      return {messages:state.pending.filter(message=>!state.consumed.has(message.inputId)&&!state.revoked.includes(message.inputId)),revoked:state.revoked};
    });
    current.rpc.handle('product.task_context.commit',value=>{reconcile((value as {evidence:Evidence[]}).evidence);return null;});
    return current;
  };
  const start=async(current:RuntimeClient,taskStopFences:(string|{sessionId:string;stoppedAt?:string})[]=[])=>{
    await current.rpc.request('initialize',{protocol:1,agents:[agent],bindings:[binding],taskStopFences});
    await current.rpc.request('session.ensure',binding);
  };
  const observe=async(current:RuntimeClient)=>await current.rpc.request('session.observe',{sessionId:'s'}) as Observation;
  const idle=async(current:RuntimeClient)=>{await expect.poll(async()=>(await observe(current)).status).toBe('idle');};
  const submit=(current:RuntimeClient,id:string,mode:'inject'|'followup'='followup')=>current.rpc.request('session.submit',
    {sessionId:'s',inputId:id,mode,content:[{type:'text',text:id}],source:{kind:'human',actorId:'o',channel:'test',messageId:id}});
  const passive=(current:RuntimeClient,messages:Original[])=>current.rpc.request('task.context.passive',{agentId:'a',sessionId:'s',messages,revoked:[]});
  const changed=async(current:RuntimeClient)=>{const reads=state.snapshotReads;await current.rpc.request('task.execution.changed',{agentId:'a'});await expect.poll(()=>state.snapshotReads).toBeGreaterThan(reads);};
  return {home,state,client,start,calls,observe,idle,submit,passive,changed,logs:()=>logs};
}

function noSyntheticContext(calls:ProviderCall[]) {
  expect(calls.flatMap(call=>call.messages).filter(message=>message.source?.channel==='task-change'
    ||message.source?.channel==='task-human-control'||message.id.startsWith('task-change:')||message.id.startsWith('task-stop-notice:'))).toEqual([]);
}

it.each([{outage:'source',taskGraph:true},{outage:'snapshot',taskGraph:true},{outage:'source',taskGraph:false},{outage:'snapshot',taskGraph:false}] as const)('hard-denies actual native Task tools during $outage outage (task_graph=$taskGraph), reopening only after revalidation',async({outage,taskGraph})=>{
  const f=await fixture(taskGraph,true),client=f.client();
  if(outage==='source')f.state.unavailable=true;
  else f.state.snapshot={kind:'unavailable',reason:'task_authority_unavailable',tasks:[],repair_task_ids:[]};
  try{
    await f.start(client);await f.submit(client,'force-task-tool');
    await expect.poll(async()=>(await f.calls()).length).toBe(2);await f.idle(client);
    expect((await f.calls())[0]!.messages.some(message=>message.source?.channel==='task-context-limitation')).toBe(false);
    const denied=(await f.observe(client)).events.find(event=>event.type==='tool/result'&&event.data.message.toolCallId==='task-probe-force-task-tool');
    expect(denied?.data.message.isError).toBe(true);expect(JSON.stringify(denied)).toContain('unavailable');expect(f.state.productCalls).toBe(0);
    f.state.unavailable=false;f.state.snapshot=empty;
    await f.submit(client,'force-task-tool-after-revalidation');
    await expect.poll(()=>f.state.productCalls).toBe(1);await f.idle(client);
    const accepted=(await f.observe(client)).events.find(event=>event.type==='tool/result'&&event.data.message.toolCallId==='task-probe-force-task-tool-after-revalidation');
    expect(accepted?.data.message.isError).toBe(false);
  }catch(error){throw new Error(String(error)+'\n'+f.logs(),{cause:error});}
  finally{await client.shutdown();await rm(f.home,{recursive:true,force:true});}
},25_000);

it('fails closed until Task originals synchronize, then preserves their business identity and consumed history across restart',async()=>{
  const f=await fixture();let client=f.client(),release!:()=>void;
  const message=original('task-business-original','请使用更正后的原文处理任务，不要创建另一份摘要。');
  f.state.pending=[message];
  const blocked=new Promise<void>(resolve=>{release=resolve;});
  f.state.beforePrepare=async()=>{await blocked;throw new Error('Task original synchronization unavailable');};
  try {
    await f.start(client);await f.submit(client,'human-before-context-sync');
    await expect.poll(()=>f.state.prepareReads).toBe(1);
    expect((await f.calls()).length).toBe(0);
    release();await f.idle(client);
    expect((await f.calls()).length).toBe(0);expect(f.state.consumed.has(message.inputId)).toBe(false);

    f.state.beforePrepare=undefined;await f.submit(client,'retry-after-context-sync');
    await expect.poll(async()=>(await f.calls()).length).toBe(1);await f.idle(client);
    const first=(await f.calls())[0]!;
    expect(first.sessionId).toBe('s');
    expect(first.messages.filter(value=>value.id===message.inputId)).toEqual([expect.objectContaining({
      content:message.content,source:expect.objectContaining({kind:'nano-system',channel:'task-context',messageId:message.inputId,conversationId:message.conversationId}),
    })]);
    await expect.poll(()=>f.state.consumed.has(message.inputId)).toBe(true);
    await client.shutdown();client=f.client();await f.start(client);
    await f.submit(client,'human-after-restart');
    await expect.poll(async()=>(await f.calls()).length).toBe(2);await f.idle(client);
    expect((await f.calls())[1]!.messages.filter(value=>value.id===message.inputId)).toEqual([expect.objectContaining({content:message.content})]);
    const events=(await f.observe(client)).events.filter(event=>event.type==='user/message'&&event.data.id===message.inputId);
    expect(events).toHaveLength(1);
    expect(f.state.receipts).toContainEqual(expect.objectContaining({inputId:message.inputId,content:message.content,consumedSeq:events[0]!.seq}));
    noSyntheticContext(await f.calls());
  } catch(error) {throw new Error(String(error)+'\n'+f.logs(),{cause:error});}
  finally {release();await client.shutdown();await rm(f.home,{recursive:true,force:true});}
},25_000);

it.each([false,true])('allows independent offline input without admitting uncertain Task originals (task_graph=%s)',async taskGraph=>{
  const f=await fixture(taskGraph),message=original('offline-pending','UNCERTAIN_TASK_REQUIREMENTS');let client=f.client();
  f.state.pending=[message];f.state.unavailable=true;
  try {
    await f.start(client);await f.passive(client,[message]);await f.submit(client,'ordinary-offline-question');
    await expect.poll(async()=>(await f.calls()).length).toBe(1);await f.idle(client);
    const first=(await f.calls())[0]!;
    expect(first.messages.some(value=>value.id==='ordinary-offline-question')).toBe(true);
    expect(JSON.stringify(first)).not.toContain('UNCERTAIN_TASK_REQUIREMENTS');
    const limitations=first.messages.filter(value=>value.source?.channel==='task-context-limitation');
    expect(limitations).toHaveLength(1);
    expect(JSON.stringify(limitations)).toContain('offline-pending');
    expect(JSON.stringify(limitations)).toContain('fixed-task-chat');
    await f.submit(client,'second-offline-question');
    await expect.poll(async()=>(await f.calls()).length).toBe(2);await f.idle(client);
    expect((await f.observe(client)).events.filter(event=>event.type==='user/message'&&event.data.source?.channel==='task-context-limitation')).toHaveLength(1);
    expect(f.state.consumed.has(message.inputId)).toBe(false);
    await client.shutdown();client=f.client();await f.start(client);await f.submit(client,'offline-after-restart');
    await expect.poll(async()=>(await f.calls()).length).toBe(3);await f.idle(client);
    expect((await f.observe(client)).events.filter(event=>event.type==='user/message'&&event.data.source?.channel==='task-context-limitation')).toHaveLength(1);
    f.state.unavailable=false;await f.submit(client,'after-authority-restored');
    await expect.poll(async()=>(await f.calls()).length).toBe(4);await f.idle(client);
    expect((await f.calls())[3]!.messages.filter(value=>value.id===message.inputId)).toHaveLength(1);
    expect(f.state.consumed.has(message.inputId)).toBe(true);
  } finally {await client.shutdown();await rm(f.home,{recursive:true,force:true});}
},25_000);

it('identifies current Task work when authority fails during a native tool round',async()=>{
  const f=await fixture(true,true),client=f.client();
  f.state.beforePrepare=async()=>{if(f.state.prepareReads===1)f.state.snapshot=doing();else f.state.unavailable=true;};
  try{
    await f.start(client);await f.submit(client,'force-task-tool-current-work');
    await expect.poll(async()=>(await f.calls()).length).toBe(2);await f.idle(client);
    const limitation=(await f.calls())[1]!.messages.find(message=>message.source?.channel==='task-context-limitation');
    expect(limitation).toBeDefined();
    const scope=JSON.parse(limitation!.content[0]!.text!.split('\n').at(-1)!);
    expect(scope.task_refs).toEqual([{graph_id:'g',node_id:'n1'}]);
    expect(scope.input_refs).toEqual([]);expect(f.state.productCalls).toBe(1);
  }finally{await client.shutdown();await rm(f.home,{recursive:true,force:true});}
},25_000);

it('holds Task-only candidates without a provider call or idle retry loop, then rechecks on authority recovery',async()=>{
 const f=await fixture(),client=f.client(),message=original('held-original','HELD_TASK_REQUIREMENTS');
 f.state.pending=[message];f.state.unavailable=true;f.state.snapshot=doing();f.state.completeAfter=1;
 try {
  await f.start(client);await expect.poll(()=>f.state.prepareReads).toBeGreaterThan(0);await f.idle(client);
  expect(await f.calls()).toEqual([]);expect(f.state.consumed.has(message.inputId)).toBe(false);
  const before=f.state.prepareReads;await f.changed(client);
  await expect.poll(()=>f.state.prepareReads).toBe(before+1);await f.idle(client);
  expect(await f.calls()).toEqual([]);
  f.state.unavailable=false;await f.changed(client);
  await expect.poll(async()=>(await f.calls()).length).toBe(1);await f.idle(client);
  expect((await f.calls())[0]!.messages.filter(value=>value.id===message.inputId)).toHaveLength(1);
  expect(f.state.consumed.has(message.inputId)).toBe(true);
 }finally{await client.shutdown();await rm(f.home,{recursive:true,force:true});}
},25_000);

it('revokes an unconsumed offline original before the next provider call without erasing consumed Task history',async()=>{
  const f=await fixture();let client=f.client();
  const consumed=original('consumed-original','已消费原文，必须保留在历史中。'),stale=original('offline-pending-original','REVOKED_UNCONSUMED_TASK_SECRET');
  f.state.pending=[consumed];
  try {
    await f.start(client);await f.submit(client,'initial-task-reading');
    await expect.poll(async()=>(await f.calls()).length).toBe(1);await f.idle(client);
    await expect.poll(()=>f.state.consumed.has(consumed.inputId)).toBe(true);
    f.state.pending.push(stale);await f.passive(client,[stale]);
    expect((await f.observe(client)).status).toBe('idle');expect(await f.calls()).toHaveLength(1);
    await client.shutdown();f.state.revoked=[stale.inputId];client=f.client();await f.start(client);
    await f.submit(client,'unrelated-question-after-revocation');
    await expect.poll(async()=>(await f.calls()).length).toBe(2);await f.idle(client);
    const messages=(await f.calls())[1]!.messages;
    expect(messages.filter(message=>message.id===consumed.inputId)).toHaveLength(1);
    expect(messages.some(message=>message.id===stale.inputId)).toBe(false);
    expect(JSON.stringify(messages)).not.toContain('REVOKED_UNCONSUMED_TASK_SECRET');
    expect(JSON.stringify(messages)).toContain('unrelated-question-after-revocation');
    const history=(await f.observe(client)).events.filter(event=>event.type==='user/message');
    expect(history.filter(event=>event.data.id===consumed.inputId)).toHaveLength(1);
    expect(history.filter(event=>event.data.id===stale.inputId)).toEqual([]);
    noSyntheticContext(await f.calls());
  } catch(error) {throw new Error(String(error)+'\n'+f.logs(),{cause:error});}
  finally {await client.shutdown();await rm(f.home,{recursive:true,force:true});}
},25_000);

it('keeps a real human Task pause original passive after a completed stop, yet makes that same original available to an independent question',async()=>{
  const f=await fixture(),client=f.client();
  const pause=original('human-pause-original','用户暂停了指定任务。',{action:'pause',actor_id:'o',at:'2026-10-30T12:00:00Z'});
  f.state.pending=[pause];
  try {
    await f.start(client,['s']);
    await f.passive(client,[pause]);
    await client.rpc.request('task.execution.block',{sessionId:'s',blocked:false});
    await f.changed(client);await f.idle(client);
    expect((await f.calls()).length).toBe(0);
    expect((await f.observe(client)).events.filter(event=>event.type==='user/message'&&event.data.id===pause.inputId)).toEqual([]);
    await f.submit(client,'future-independent-question');
    await expect.poll(async()=>(await f.calls()).length).toBe(1);await f.idle(client);
    const messages=(await f.calls())[0]!.messages;
    expect(messages.filter(message=>message.id===pause.inputId)).toEqual([expect.objectContaining({
      role:'user',content:pause.content,source:expect.objectContaining({channel:'task-context',messageId:pause.inputId,humanTaskControl:pause.humanControl}),
    })]);
    expect(JSON.stringify(messages)).toContain('Application-attested human Task control');
    noSyntheticContext(await f.calls());
  } catch(error) {throw new Error(String(error)+'\n'+f.logs(),{cause:error});}
  finally {await client.shutdown();await rm(f.home,{recursive:true,force:true});}
},25_000);

it('restores completed-stop fencing over old queued human and pause originals, and admits doing only after a later UI resume request',async()=>{
  const f=await fixture();let client=f.client();
  const pause=original('original-task-stop','停止当前任务。',{action:'pause',actor_id:'o',at:'2026-10-30T12:00:00Z'});
  f.state.pending=[pause];
  try {
    await f.start(client);
    await Promise.all(Array.from({length:3},()=>f.submit(client,'old-queued-human-before-stop','inject')));
    const admissions=()=>(f.observe(client)).then(value=>value.events.flatMap(event=>event.type==='agent/inbox/spliced'?event.data.inserted:[]).filter(message=>message.id==='old-queued-human-before-stop'));
    expect(await admissions()).toHaveLength(1);
    const originalAdmission=(await admissions())[0].source.admittedAt;
    await f.passive(client,[pause]);
    expect((await f.calls()).length).toBe(0);
    await client.shutdown();client=f.client();f.state.snapshot=doing();f.state.completeAfter=1;
    await f.start(client,['s']);
    await f.submit(client,'old-queued-human-before-stop','inject');
    expect(await admissions()).toHaveLength(1);
    expect((await admissions())[0].source.admittedAt).toBe(originalAdmission);
    await f.changed(client);await f.idle(client);
    expect((await f.calls()).length).toBe(0);
    expect(f.state.consumed.has(pause.inputId)).toBe(false);

    const at=new Date().toISOString();
    const resume=original('ui-human-resume-original','用户在设置页明确恢复了指定任务。',{action:'resume',actor_id:'o',at});
    f.state.pending.push(resume);f.state.snapshot=doing({actor_id:'o',at,revision:2});f.state.completeAfter=1;
    await f.changed(client);
    await expect.poll(async()=>(await f.calls()).length,{timeout:5000}).toBe(1);await f.idle(client);
    const messages=(await f.calls())[0]!.messages;
    expect(messages.filter(message=>message.id===resume.inputId)).toEqual([expect.objectContaining({role:'user',content:resume.content,source:expect.objectContaining({channel:'task-context',humanTaskControl:resume.humanControl})})]);
    expect(messages.filter(message=>message.id===pause.inputId)).toHaveLength(1);
    expect(messages.some(message=>message.source?.channel==='task-execution')).toBe(true);
    noSyntheticContext(await f.calls());
  } catch(error) {throw new Error(String(error)+'\n'+f.logs(),{cause:error});}
  finally {await client.shutdown();await rm(f.home,{recursive:true,force:true});}
},25_000);

it('retains a legitimate UI resume across another restart using the original persisted stop timestamp',async()=>{
  const f=await fixture();let client=f.client();
  const stoppedAt=new Date(Date.now()-2000).toISOString(),at=new Date(Date.now()-1000).toISOString();
  const stop={sessionId:'s',stoppedAt};
  const resume=original('persisted-ui-resume-original','此前的有效人工恢复必须跨重启保留。',{action:'resume',actor_id:'o',at});
  f.state.pending=[resume];f.state.snapshot=doing({actor_id:'o',at,revision:2});f.state.completeAfter=1;
  try {
    await f.start(client,[stop]);await f.changed(client);
    await expect.poll(async()=>(await f.calls()).length).toBe(1);await f.idle(client);
    await expect.poll(()=>f.state.consumed.has(resume.inputId)).toBe(true);
    await client.shutdown();client=f.client();f.state.completeAfter=2;
    // Replaying the same completed stop must not manufacture a newer cancellation watermark.
    await f.start(client,[stop]);await f.changed(client);
    await expect.poll(async()=>(await f.calls()).length).toBe(2);await f.idle(client);
    const history=(await f.observe(client)).events.filter(event=>event.type==='user/message'&&event.data.id===resume.inputId);
    expect(history).toHaveLength(1);
    for(const call of await f.calls())expect(call.messages.filter(message=>message.id===resume.inputId)).toEqual([expect.objectContaining({
      role:'user',content:resume.content,source:expect.objectContaining({channel:'task-context',humanTaskControl:resume.humanControl}),
    })]);
    noSyntheticContext(await f.calls());
  } catch(error) {throw new Error(String(error)+'\n'+f.logs(),{cause:error});}
  finally {await client.shutdown();await rm(f.home,{recursive:true,force:true});}
},25_000);

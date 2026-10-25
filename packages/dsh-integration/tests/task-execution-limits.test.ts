import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';

it('resets a short-run streak after sustained work and reopens an exhausted Agent only on an independent wake',async()=>{
  const home=await mkdtemp(join(tmpdir(),'nano-task-limit-'));let client:RuntimeClient|undefined;
  try {
    await writeFile(join(home,'probe.mjs'),`
export const name='task-limit-probe';export const inject=['llm','agents','tools'];
export function apply(ctx){
 const runs=new Map(),counts=new Map();
 ctx.on('agent/pre-step',({agent,turn,messages},next)=>{
  if(runs.get(agent.id)?.turn!==turn){
   const auto=messages.some(m=>m.source?.channel==='task-execution');
   const count=(counts.get(agent.id)||0)+(auto?1:0);counts.set(agent.id,count);
   runs.set(agent.id,{turn,steps:0,auto,target:auto?(count===128?3:1+((count-1)%2)):messages.some(m=>m.source?.channel==='revalidation')?3:1});
  }
  return next();
 });
 ctx.tools.register({name:'fixture_step',description:'One work step',parameters:{type:'object',properties:{}},output:{schema:{type:'string'},render:()=>[{type:'text',text:'ok'}]},execute:async()=>'ok'});
 ctx.on('tools/pre-execute',(exec,next)=>exec.name==='fixture_step'?{kind:'allow'}:next(),{prepend:true});
 ctx.on('llm/stream',async function*(){
  const agent=ctx.agents.currentInitiator(),run=runs.get(agent.id);const more=++run.steps<run.target;
  if(!more&&agent.id==='s'&&run.auto&&counts.get(agent.id)===200)
   agent.followup({id:'early-short',role:'user',source:{kind:'user'},content:[{type:'text',text:'An independent short question before exhaustion'}]});
  yield{type:'block-end',index:0,block:more?{type:'tool-call',id:'step-'+run.turn+'-'+run.steps,name:'fixture_step',arguments:'{}'}:{type:'text',text:'NO_REPLY'}};
  yield{type:'finish',reason:{kind:more?'tool-calls':'stop'}};
 });
}`);
    await prepareProfile(home,[{insert:[{id:'task-limit-probe',name:join(home,'probe.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home});
    const totals=new Map<string,{automatic:number;turns:number;steps:number}>();
    const count=(id:string)=>{let value=totals.get(id);if(!value){value={automatic:0,turns:0,steps:0};totals.set(id,value);}return value;};
    client.rpc.onNotification((method,payload)=>{
      if(method!=='session.event')return;
      const {sessionId,event}=payload as {sessionId:string;event:{type:string;data:{source?:{channel?:string}}}};
      const value=count(sessionId);
      if(event.type==='user/message'&&event.data.source?.channel==='task-execution')value.automatic++;
      if(event.type==='turn/end')value.turns++;
      if(event.type==='step/start')value.steps++;
    });
    client.rpc.handle('product.task_execution.snapshot',identity=>{
      const {sessionId}=identity as {sessionId:string};return {
      // Keep a regressed implementation bounded too, without lowering the real cap.
      kind:count(sessionId).automatic>=(sessionId==='other-agent'?1:641)?'quiescent':'continue',
      tasks:[{graph_id:'g',node_id:'n',title:'Unfinished work',status:'doing',revision:1,updated_at:'2026-10-25T08:00:00Z',conversation:{id:'c'},relative_url:'/tasks/g'}],repair_task_ids:[],
    };});
    await client.rpc.request('initialize',{protocol:1,agents:['a','b'].map(agentId=>({agentId,revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{cron_scheduling:true}})),bindings:[]});
    const ensure=(sessionId:string,agentId:string)=>client!.rpc.request('session.ensure',{sessionId,agentId,ownerId:'o',revision:'1',cwd:home});
    const idle=async(sessionId:string)=>(await client!.rpc.request('session.observe',{sessionId}) as {status:string}).status==='idle';
    await ensure('s','a');
    await expect.poll(async()=>count('s').automatic>=384&&await idle('s'),{timeout:45_000}).toBe(true);
    // The 128th automatic turn has three steps and resets the first 127 short
    // runs. The one-step external turn at 200 does not reset an active streak.
    expect(count('s').automatic).toBe(384);
    expect(count('s').steps).toBe(578);

    // Refreshes and admitted internal context must not reopen a stopped Agent.
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    for(const channel of ['task-human-control','revalidation']) {
      const before=count('s').steps;
      await client.rpc.request('session.submit',{sessionId:'s',inputId:channel,mode:'followup',content:[{type:'text',text:channel}],source:{kind:'system',actorId:'a',channel,messageId:channel}});
      await expect.poll(async()=>count('s').steps>before&&await idle('s')).toBe(true);
      expect(count('s').automatic).toBe(384);
    }
    await ensure('same-agent','a');
    await ensure('other-agent','b');
    await expect.poll(()=>count('other-agent').automatic).toBeGreaterThan(0);
    expect(count('same-agent').automatic).toBe(0);

    // An admitted one-step external reply reopens an exhausted allowance.
    await client.rpc.request('session.submit',{sessionId:'s',inputId:'late-short',mode:'followup',content:[{type:'text',text:'short'}],source:{kind:'human',actorId:'o',channel:'test',messageId:'late-short'}});
    await expect.poll(async()=>count('s').automatic>=640&&await idle('s'),{timeout:45_000}).toBe(true);
    expect(count('s').automatic).toBe(640);
    expect(count('s').steps).toBe(967);

    // A real native Schedule also reopens the exhausted Agent, without a human turn.
    await client.rpc.request('schedule.command',{agentId:'a',sessionId:'s',action:'create',args:{title:'Independent check',prompt:'Read the current Task.',after_seconds:1}});
    await expect.poll(async()=>count('s').automatic>=641&&await idle('s'),{timeout:5000}).toBe(true);
    expect(count('s').automatic).toBe(641);
  } finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},90_000);
